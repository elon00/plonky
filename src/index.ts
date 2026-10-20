/** Real finite Conway logic and read-only EVM RPC. No simulated security/payment claims. */
export interface QMoosaClientConfig {
  quickNodeRpcUrl: string;
  expectedChainId?: bigint;
  timeoutMs?: number;
}
const MAX_BOARD=(1n<<64n)-1n;
const QUANTITY=/^0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)$/;

export function stepConway(board:bigint):bigint {
  if(board<0n || board>MAX_BOARD) throw new RangeError("Board must be a 64-bit unsigned integer");
  let next=0n;
  for(let y=0;y<8;y++) for(let x=0;x<8;x++){
    let neighbors=0;
    for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++){
      const nx=x+dx,ny=y+dy;
      if((dx!==0||dy!==0)&&nx>=0&&nx<8&&ny>=0&&ny<8)
        neighbors+=Number((board>>BigInt(ny*8+nx))&1n);
    }
    const bit=1n<<BigInt(y*8+x);
    if(neighbors===3||(neighbors===2&&(board&bit)!==0n))next|=bit;
  }
  return next;
}

export class QMoosaClient {
  readonly #url:string;
  readonly #expected:bigint|undefined;
  readonly #timeout:number;
  constructor(config:QMoosaClientConfig){
    const url=new URL(config.quickNodeRpcUrl);
    if(url.username||url.password||url.hash)throw new Error("Invalid RPC endpoint");
    if(url.protocol!=="https:"&&!(url.protocol==="http:"&&["localhost","127.0.0.1","[::1]"].includes(url.hostname)))
      throw new Error("HTTPS is required except on loopback");
    if(config.expectedChainId!==undefined&&config.expectedChainId<=0n)throw new Error("Expected chain id must be positive");
    this.#url=url.toString();
    this.#expected=config.expectedChainId;
    this.#timeout=config.timeoutMs??5000;
    if(!Number.isInteger(this.#timeout)||this.#timeout<1||this.#timeout>30000)
      throw new Error("Timeout must be between 1 and 30000ms");
  }
  simulateConwayStep(board:bigint):bigint {return stepConway(board);}
  async #quantity(method:string,id:number):Promise<bigint>{
    try{
      const response=await fetch(this.#url,{method:"POST",redirect:"error",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({jsonrpc:"2.0",id,method,params:[]}),
        signal:AbortSignal.timeout(this.#timeout)});
      if(!response.ok||!response.body)throw new Error("RPC HTTP failure");
      const reader=response.body.getReader();
      const chunks:Uint8Array[]=[];let size=0;
      try {
        while(true){
          const {done,value}=await reader.read();if(done)break;
          size+=value.length;
          if(size>65536){await reader.cancel();throw new Error("Response too large");}
          chunks.push(value);
        }
      } finally {reader.releaseLock();}
      const raw=new Uint8Array(size);let offset=0;
      for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.length;}
      const result:unknown=JSON.parse(new TextDecoder().decode(raw));
      if(typeof result!=="object"||result===null)throw new Error("Invalid RPC object");
      const reply=result as Record<string,unknown>;
      if(reply["jsonrpc"]!=="2.0"||reply["id"]!==id||"error" in reply||
        typeof reply["result"]!=="string"||!QUANTITY.test(reply["result"]))
        throw new Error("Invalid RPC response");
      return BigInt(reply["result"]);
    }catch{throw new Error("RPC request failed, timed out, or returned invalid data");}
  }
  async chainStatus():Promise<{chainId:string;blockNumber:string}>{
    const chain=await this.#quantity("eth_chainId",1);
    const block=await this.#quantity("eth_blockNumber",2);
    if(chain<=0n||(this.#expected!==undefined&&chain!==this.#expected))
      throw new Error("RPC chain id does not match configuration");
    return {chainId:chain.toString(),blockNumber:block.toString()};
  }
}
