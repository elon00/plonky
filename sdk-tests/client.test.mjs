import assert from "node:assert/strict";
import {createServer} from "node:http";
import {test} from "node:test";
import {spawnSync} from "node:child_process";
import path from "node:path";
import {QMoosaClient,stepConway,safeQuantityNumber} from "../dist/index.js";

function board(cells){return cells.reduce((b,[x,y])=>b|(1n<<BigInt(8*y+x)),0n);}
test("Conway block, oscillator and finite edges",()=>{
 const h=board([[2,3],[3,3],[4,3]]),v=board([[3,2],[3,3],[3,4]]);
 assert.equal(stepConway(h),v);assert.equal(stepConway(v),h);
 const b=board([[2,2],[3,2],[2,3],[3,3]]);assert.equal(stepConway(b),b);
 assert.equal(stepConway(0n),0n);assert.equal(stepConway(1n),0n);
 assert.throws(()=>stepConway(-1n));assert.throws(()=>stepConway(1n<<64n));
});
test("TypeScript and Rust agree on varied 64-bit boards",()=>{
 const binary=path.resolve(process.env.CARGO_TARGET_DIR??"target","debug",process.platform==="win32"?"qmoosa-app.exe":"qmoosa-app");
 let b=0xdecafbad12345678n;
 for(let i=0;i<12;i++){
   b=(b*6364136223846793005n+1n)&((1n<<64n)-1n);
   const run=spawnSync(binary,["life",b.toString(16),"1"],{encoding:"utf8"});
   assert.equal(run.status,0,run.error?.message??run.stderr);
   assert.equal(stepConway(b),BigInt("0x"+JSON.parse(run.stdout).board));
 }
});
async function mock(mode,callback){
 const server=createServer(async(req,res)=>{
   let body="";for await(const part of req)body+=part;
   const request=JSON.parse(body);
   if(mode==="redirect"){res.writeHead(302,{Location:"https://example.invalid/private-token"});res.end();return;}
   const reply={jsonrpc:"2.0",id:request.id,result:request.method==="eth_chainId"?"0x1":"0x20000000000001"};
   if(mode==="error")reply.error={message:"private-token"};
   if(mode==="id")reply.id=true;
   if(mode==="hex")reply.result="0x01";
   res.end(mode==="large"?"x".repeat(65537):JSON.stringify(reply));
 });
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
 try{await callback("http://127.0.0.1:"+server.address().port);}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
test("actual read-only RPC keeps large quantities precise",async()=>{
 await mock("valid",async url=>{
  const client=new QMoosaClient({quickNodeRpcUrl:url,expectedChainId:1n});
  assert.deepEqual(await client.chainStatus(),{chainId:"1",blockNumber:"9007199254740993"});
 });
});
test("invalid responses, redirects and wrong chains fail",async()=>{
 for(const mode of ["error","id","hex","large","redirect"])
  await mock(mode,async url=>{
    const client=new QMoosaClient({quickNodeRpcUrl:url});
    await assert.rejects(client.chainStatus(),error=>!error.message.includes("private-token"));
  });
 await mock("valid",async url=>{
   const client=new QMoosaClient({quickNodeRpcUrl:url,expectedChainId:2n});
   await assert.rejects(client.chainStatus(),/chain id/);
 });
});
test("configuration rejects unsafe schemes and invalid settings",()=>{
 for(const url of ["file:///etc/passwd","http://example.com","https://user:password@example.com"])
  assert.throws(()=>new QMoosaClient({quickNodeRpcUrl:url}));
 assert.throws(()=>new QMoosaClient({quickNodeRpcUrl:"https://example.com",timeoutMs:0}));
 assert.throws(()=>new QMoosaClient({quickNodeRpcUrl:"https://example.com",expectedChainId:0n}));
});

test("HTTP/UI quantities use safe integers and reject loss of precision",()=>{
 assert.equal(safeQuantityNumber("11155111"),11155111);
 assert.equal(safeQuantityNumber("11962704"),11962704);
 assert.equal(safeQuantityNumber("9007199254740991"),Number.MAX_SAFE_INTEGER);
 for(const value of ["9007199254740992","-1","01","0x1"])
  assert.throws(()=>safeQuantityNumber(value),RangeError);
});
