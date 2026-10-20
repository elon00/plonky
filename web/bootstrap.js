import init,{life,pqc} from "./pkg/qmoosa_wasm.js";
import {QMoosaClient} from "./sdk/index.js";
const endpoint="https://ethereum-sepolia-rpc.publicnode.com";
try {
 await init();
 const client=new QMoosaClient({quickNodeRpcUrl:endpoint,expectedChainId:11155111n});
 const meta=await (await fetch("./project.json",{cache:"no-store"})).json();
 globalThis.qmoosaApi=async(path,method="GET")=>{
  const url=new URL(path,"https://local.invalid");
  if(url.pathname==="/api/config")return {auth_required:false,name:meta.name,core_version:"0.3.0"};
  if(url.pathname==="/api/health")return {status:"ok",project:meta,core_built:true,rpc:"Public Sepolia endpoint; not yet probed",agents:"not implemented",contracts:"local/testnet reference; no funded deployment"};
  if(url.pathname==="/api/life"){
   const board=url.searchParams.get("board")??"000000001c000000";
   const raw=url.searchParams.get("steps")??"1";
   if(!/^(?:0x)?[0-9a-fA-F]{1,16}$/.test(board)||!/^[0-9]{1,5}$/.test(raw)||Number(raw)>10000)throw new Error("Invalid board or step limit");
   return JSON.parse(life(board,Number(raw)));
  }
  if(url.pathname==="/api/pqc")return JSON.parse(pqc());
  if(url.pathname==="/api/rpc"&&method==="POST"){
   const status=await client.chainStatus();
   return {status:"connected",chain_id:status.chainId,block_number:status.blockNumber,message:"Live Sepolia read-only RPC succeeded.",scope:"PublicNode shared public endpoint; no transactions sent"};
  }
  throw new Error("Unknown operation");
 };
 const note=document.querySelector("#rpc").parentElement.querySelector(".footnote");
 note.textContent="Uses a public Sepolia RPC endpoint. Shared-provider limits may apply. No wallet or API key required.";
 const context=document.querySelector(".context");
 for(const node of context.childNodes)if(node.nodeType===Node.TEXT_NODE&&node.textContent.includes("LOCAL LAB"))node.textContent=" PUBLIC DEMO ";
 await import("./app.js");
} catch(error) {
 document.querySelector("#life-status").textContent="Browser core failed to load. Reload on HTTPS or localhost.";
 console.error("Workbench startup failed");
}
