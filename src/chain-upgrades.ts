/** Read-only upgrade capabilities. RPC observations are not independent consensus proofs. */
export type Rpc = (method:string, params?:unknown[])=>Promise<unknown>;
export class RpcFailure extends Error {
  constructor(public readonly code?:number){super("RPC request failed or returned invalid data");}
}
const METHODS=new Set(["eth_chainId","eth_getBlockByNumber","eth_estimateGas","eth_call",
  "getGenesisHash","getAgGenesisCert","getVersion","getEpochInfo"]);
const QUANTITY=/^0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})$/;
const ADDRESS=/^0x[0-9a-fA-F]{40}$/;
const PROBE_ADDRESS="0x000000000000000000000000000000000000dead";
export const SOLANA_GENESIS={
  devnet:"EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG",
  testnet:"4uhcVJyU9pJkvQyS88uRDiswHXSCkY3zQawwpjk2NsNY",
  "mainnet-beta":"5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d",
} as const;

function object(value:unknown):Record<string,unknown>{
  if(!value||typeof value!=="object"||Array.isArray(value))throw new RpcFailure();
  return value as Record<string,unknown>;
}
function quantity(value:unknown):bigint{
  if(typeof value!=="string"||!QUANTITY.test(value))throw new RpcFailure();
  return BigInt(value);
}
/** Rejects mutating methods, redirects, oversized replies and provider error text. */
export function readOnlyRpc(endpoint:string,timeoutMs=5000,fetchImpl:typeof fetch=fetch):Rpc{
  let url:URL;
  try{url=new URL(endpoint);}catch{throw new Error("Invalid RPC configuration");}
  if(url.username||url.password||url.hash||
    (url.protocol!=="https:"&&!(url.protocol==="http:"&&["127.0.0.1","localhost","[::1]"].includes(url.hostname)))||
    !Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30000)throw new Error("Invalid RPC configuration");
  let id=0;
  return async(method,params=[])=>{
    if(!METHODS.has(method))throw new Error("Only read-only capability methods are allowed");
    const requestId=++id;
    try{
      const response=await fetchImpl(url,{method:"POST",redirect:"error",credentials:"omit",cache:"no-store",
        headers:{"Content-Type":"application/json"},body:JSON.stringify({jsonrpc:"2.0",id:requestId,method,params}),
        signal:AbortSignal.timeout(timeoutMs)});
      if(!response.ok||!response.body)throw new RpcFailure();
      const reader=response.body.getReader(),chunks:Uint8Array[]=[];
      let size=0;
      try{
        while(true){
          const {done,value}=await reader.read();if(done)break;
          size+=value.length;
          if(size>65536){await reader.cancel();throw new RpcFailure();}
          chunks.push(value);
        }
      }finally{reader.releaseLock();}
      const raw=new Uint8Array(size);let offset=0;
      for(const part of chunks){raw.set(part,offset);offset+=part.length;}
      const reply=object(JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(raw)));
      if(reply["jsonrpc"]!=="2.0"||reply["id"]!==requestId)throw new RpcFailure();
      if("error" in reply){
        if("result" in reply)throw new RpcFailure();
        const code=object(reply["error"])["code"];
        throw new RpcFailure(typeof code==="number"&&Number.isSafeInteger(code)?code:undefined);
      }
      if(!Object.hasOwn(reply,"result"))throw new RpcFailure();
      return reply["result"];
    }catch(error){throw error instanceof RpcFailure?error:new RpcFailure();}
  };
}

export interface EvmTransaction {to:string;from:string;value?:string;data?:string;}
/** Estimate this transaction under the node's current rules; enforce an operator supplied ceiling. */
export async function estimateEvmGas(rpc:Rpc,transaction:EvmTransaction,expectedChainId:bigint,maxGas:bigint):Promise<string>{
  if(expectedChainId<=0n||maxGas<=0n||!ADDRESS.test(transaction.to)||
    !ADDRESS.test(transaction.from)||
    (transaction.value!==undefined&&!QUANTITY.test(transaction.value))||
    (transaction.data!==undefined&&!/^0x(?:[a-fA-F0-9]{2})*$/.test(transaction.data))||
    Object.keys(transaction).some(key=>!["to","from","value","data"].includes(key)))throw new Error("Invalid gas estimation configuration");
  if(quantity(await rpc("eth_chainId"))!==expectedChainId)throw new Error("RPC chain id does not match configuration");
  const gas=quantity(await rpc("eth_estimateGas",[transaction,"latest"]));
  if(gas<=0n||gas>maxGas)throw new Error("Gas estimate exceeds the configured ceiling or is invalid");
  return gas.toString();
}

export async function probeEvmUpgrade(rpc:Rpc,expectedChainId:bigint){
  if(expectedChainId<=0n)throw new Error("Expected chain id is required");
  const chain=quantity(await rpc("eth_chainId"));
  if(chain!==expectedChainId)throw new Error("RPC chain id does not match configuration");
  const block=object(await rpc("eth_getBlockByNumber",["latest",false]));
  const blockNumber=quantity(block["number"]);
  const estimate=quantity(await rpc("eth_estimateGas",[{to:PROBE_ADDRESS,value:"0x0"},block["number"]]));
  if(estimate<=0n)throw new RpcFailure();
  const ethereum=chain===1n||chain===11155111n;
  let slotnum:"observed"|"unavailable"|"not_applicable"=ethereum?"unavailable":"not_applicable";
  let slot:string|null=null;
  if(ethereum){
    try{
      // Temporary code override for this eth_call only. Nothing is deployed or broadcast.
      const value=await rpc("eth_call",[{to:PROBE_ADDRESS},block["number"],
        {[PROBE_ADDRESS]:{code:"0x4b60005260206000f3"}}]);
      if(typeof value==="string"&&/^0x[0-9a-fA-F]{64}$/.test(value)&&BigInt(value)>0n&&BigInt(value)<(1n<<64n)){
        slotnum="observed";slot=BigInt(value).toString();
      }
    }catch{/* Unsupported overrides/opcodes/providers remain explicitly unverified. */}
  }
  return {status:"connected",chainId:chain.toString(),blockNumber:blockNumber.toString(),
    dynamicGasEstimation:{status:"observed",probeGas:estimate.toString(),scope:"zero-value transfer probe; estimate each real transaction separately"},
    upgrade:{name:ethereum?"Glamsterdam":null,slotnum,slot,
      verification:slotnum==="observed"?"single_capability_observed":"not_verified",
      scope:"EIP-7843 capability only; not full fork conformance or contract audit"},
    scope:"single configured RPC provider; no transactions sent"};
}

function bytes(value:unknown,length?:number):boolean{
  return Array.isArray(value)&&value.length>0&&value.length<=8192&&
    (length===undefined||value.length===length)&&value.every(x=>Number.isInteger(x)&&x>=0&&x<=255);
}
export async function probeSolanaUpgrade(rpc:Rpc,expectedGenesisHash:string){
  if(!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(expectedGenesisHash))throw new Error("Expected genesis hash is required");
  const genesis=await rpc("getGenesisHash");
  if(genesis!==expectedGenesisHash)throw new Error("RPC genesis hash does not match configuration");
  let consensus:"alpenglow"|"tower"|"unknown"="unknown";
  let capability:"reported_active"|"not_active"|"method_unavailable"|"rpc_error"|"invalid_certificate"="rpc_error";
  let genesisSlot:number|null=null;
  try{
    const value=await rpc("getAgGenesisCert");
    if(value===null){consensus="tower";capability="not_active";}
    else{
      capability="invalid_certificate";
      const cert=object(value),block=object(cert["block"]),signature=object(cert["signature"]);
      const slot=block["slot"];
      if(typeof slot==="number"&&Number.isSafeInteger(slot)&&slot>=0&&bytes(block["blockId"],32)&&
        bytes(signature["signature"],192)&&bytes(signature["bitmap"])&&(signature["bitmap"] as number[]).length<=512&&
        (signature["bitmap"] as number[]).some(x=>x!==0)){
        consensus="alpenglow";capability="reported_active";genesisSlot=slot;
      }
    }
  }catch(error){
    if(error instanceof RpcFailure&&error.code===-32601)capability="method_unavailable";
  }
  return {status:"connected",genesisHash:expectedGenesisHash,
    upgrade:{name:"Alpenglow",consensus,capability,genesisSlot,
      commitment:consensus==="alpenglow"?"finalized" as const:"confirmed" as const,
      scope:"provider-reported genesis certificate; BLS signature not independently verified"},
    scope:"single configured RPC provider; no signing or transactions"};
}

/** CLI policy: unavailable features differ from failed or malformed required observations. */
export function upgradeProbeExitCode(report:{upgrade:{verification?:string;capability?:string}}):0|1|2{
  const {verification,capability}=report.upgrade;
  if(capability==="rpc_error"||capability==="invalid_certificate")return 2;
  if(capability==="reported_active"||verification==="single_capability_observed")return 0;
  return 1;
}
