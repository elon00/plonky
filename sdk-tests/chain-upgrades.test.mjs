import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readOnlyRpc,probeEvmUpgrade,estimateEvmGas,probeSolanaUpgrade,SOLANA_GENESIS,upgradeProbeExitCode} from '../dist/chain-upgrades.js';

const certificate=()=>({block:{slot:504148999,blockId:Array(32).fill(1)},
 signature:{signature:Array(192).fill(2),bitmap:[1]}});
async function server(responder,callback){
 const calls=[];
 const host=createServer(async(req,res)=>{
  let body='';for await(const chunk of req)body+=chunk;
  const request=JSON.parse(body);calls.push(request);
  const result=await responder(request,res);
  if(!res.writableEnded)res.end(JSON.stringify({jsonrpc:'2.0',id:request.id,...result}));
 });
 await new Promise(resolve=>host.listen(0,'127.0.0.1',resolve));
 try{await callback(readOnlyRpc(`http://127.0.0.1:${host.address().port}`),calls);}
 finally{host.closeAllConnections();await new Promise(resolve=>host.close(resolve));}
}
const evm=request=>({result:({eth_chainId:'0xaa36a7',eth_getBlockByNumber:{number:'0x100'},
 eth_estimateGas:'0xc350',eth_call:'0x'+11300000n.toString(16).padStart(64,'0')})[request.method]});

test('Ethereum uses live gas estimation and reports the scope of observed SLOTNUM support',async()=>{
 await server(evm,async(rpc,calls)=>{
  const report=await probeEvmUpgrade(rpc,11155111n);
  assert.equal(report.dynamicGasEstimation.probeGas,'50000');
  assert.equal(report.upgrade.slotnum,'observed');
  assert.equal(report.upgrade.verification,'single_capability_observed');
  assert.equal(calls.at(-1).params[2]['0x000000000000000000000000000000000000dead'].code,'0x4b60005260206000f3');
  assert.ok(calls.every(call=>!call.method.includes('send')));
 });
});
test('unsupported overrides never claim fork support',async()=>{
 await server(req=>req.method==='eth_call'?{error:{code:-32601,message:'private-provider-token'}}:evm(req),async rpc=>{
  const report=await probeEvmUpgrade(rpc,11155111n);
  assert.equal(report.upgrade.verification,'not_verified');
  assert.ok(!JSON.stringify(report).includes('private-provider-token'));
 });
});
test('an L2 is not labelled Glamsterdam',async()=>{
 await server(req=>req.method==='eth_chainId'?{result:'0xa4b1'}:evm(req),async(rpc,calls)=>{
  const report=await probeEvmUpgrade(rpc,42161n);
  assert.equal(report.upgrade.name,null);assert.equal(report.upgrade.slotnum,'not_applicable');
  assert.ok(calls.every(call=>call.method!=='eth_call'));
 });
});
test('wrong EVM identity stops before gas estimation or simulation',async()=>{
 await server(evm,async(rpc,calls)=>{
  await assert.rejects(probeEvmUpgrade(rpc,1n),/chain id/);assert.equal(calls.length,1);
 });
});
test('actual transaction estimates use current RPC pricing and an explicit gas ceiling',async()=>{
 const tx={to:'0x'+'12'.repeat(20),from:'0x'+'34'.repeat(20),value:'0x0',data:'0x1234'};
 await server(evm,async(rpc,calls)=>{
  const {from,...withoutSender}=tx;
  await assert.rejects(estimateEvmGas(rpc,withoutSender,11155111n,60000n),/configuration/);
  assert.equal(calls.length,0);
  assert.equal(await estimateEvmGas(rpc,tx,11155111n,60000n),'50000');
  assert.deepEqual(calls.at(-1).params,[tx,'latest']);
  await assert.rejects(estimateEvmGas(rpc,tx,11155111n,40000n),/ceiling/);
  await assert.rejects(estimateEvmGas(rpc,{...tx,gas:'0x5208'},11155111n,60000n),/configuration/);
 });
});
test('Solana switches commitment only after receiving a structured genesis certificate',async()=>{
 await server(req=>({result:req.method==='getGenesisHash'?SOLANA_GENESIS.devnet:certificate()}),async rpc=>{
  const report=await probeSolanaUpgrade(rpc,SOLANA_GENESIS.devnet);
  assert.equal(report.upgrade.capability,'reported_active');assert.equal(report.upgrade.commitment,'finalized');
  assert.equal(report.upgrade.genesisSlot,504148999);assert.match(report.upgrade.scope,/not independently verified/);
 });
});
test('Tower, old RPC, malformed certificate and provider errors remain distinct',async()=>{
 for(const [reply,capability] of [
  [{result:null},'not_active'],[{error:{code:-32601,message:'provider-secret'}},'method_unavailable'],
  [{result:{}},'invalid_certificate'],[{result:{...certificate(),signature:{signature:Array(192).fill(2),bitmap:Array(513).fill(1)}}},'invalid_certificate'],[{result:{...certificate(),signature:{signature:[],bitmap:[]}}},'invalid_certificate'],
  [{error:{code:-32000,message:'provider-secret'}},'rpc_error'],
 ])await server(req=>req.method==='getGenesisHash'?{result:SOLANA_GENESIS.devnet}:reply,async rpc=>{
  const report=await probeSolanaUpgrade(rpc,SOLANA_GENESIS.devnet);
  assert.equal(report.upgrade.capability,capability);assert.equal(report.upgrade.commitment,'confirmed');
  assert.equal(upgradeProbeExitCode(report),['rpc_error','invalid_certificate'].includes(capability)?2:1);
  assert.notEqual(report.upgrade.consensus,'alpenglow');assert.ok(!JSON.stringify(report).includes('provider-secret'));
 });
});
test('a mismatched Solana cluster stops before querying activation',async()=>{
 await server(()=>({result:SOLANA_GENESIS['mainnet-beta']}),async(rpc,calls)=>{
  await assert.rejects(probeSolanaUpgrade(rpc,SOLANA_GENESIS.devnet),/genesis hash/);assert.equal(calls.length,1);
 });
});
test('capability transport rejects malformed replies, redirects and oversized responses without disclosing credentials',async()=>{
 for(const mode of ['id','large','redirect','missing','error-and-result']){
  await server((req,res)=>{
   if(mode==='id')return{id:true,result:'0x1'};
   if(mode==='missing')return{};
   if(mode==='error-and-result')return{result:'0x1',error:{code:-1,message:'provider-secret'}};
   if(mode==='large'){res.end('x'.repeat(65537));return;}
   res.writeHead(302,{Location:'https://example.invalid/provider-secret'});res.end();
  },async rpc=>{await assert.rejects(rpc('eth_chainId'),error=>!error.message.includes('provider-secret'));});
 }
});
test('mutating methods and unsafe endpoints are rejected before fetch',async()=>{
 let fetched=false;
 const rpc=readOnlyRpc('https://example.invalid',5000,async()=>{fetched=true;throw new Error('not allowed');});
 for(const method of ['sendTransaction','eth_sendRawTransaction','requestAirdrop'])await assert.rejects(rpc(method),/read-only/);
 assert.equal(fetched,false);
 for(const endpoint of ['file:///etc/passwd','http://example.com','https://user:password@example.com','https://example.com/#token'])
  assert.throws(()=>readOnlyRpc(endpoint),/configuration/);
});
