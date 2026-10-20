"use strict";
const $=id=>document.getElementById(id);
const evidence={};
let accessToken="",authRequired=false;
function accessState(unlocked){for(const id of ["step","play","pqc","rpc"])$(id).disabled=!unlocked;$("token").hidden=unlocked;$("unlock").hidden=unlocked;$("lock").hidden=!unlocked;}

let board=0n, generation=0, playing=false, busy=false, revision=0;
const patterns={blinker:[[2,3],[3,3],[4,3]],block:[[2,2],[3,2],[2,3],[3,3]],glider:[[2,1],[3,2],[1,3],[2,3],[3,3]],empty:[]};
function record(key,value){evidence[key]={executed_at:new Date().toISOString(),result:value};$("evidence").textContent=JSON.stringify(evidence,null,2);}
function status(id,message,error=false){$(id).textContent=message;$(id).classList.toggle("error",error);}
async function request(path,method="GET"){
 if(globalThis.qmoosaApi)return globalThis.qmoosaApi(path,method);
 const response=await fetch(path,{method,cache:"no-store",headers:accessToken?{"Authorization":"Bearer "+accessToken}:{},signal:AbortSignal.timeout(25000)});
 if(response.status===401){authRequired=true;$("auth").hidden=false;accessState(false);}
 const result=await response.json(); if(!response.ok)throw new Error(result.error||result.message||"Request failed");return result;
}
function stop(){playing=false;$("play").textContent="Play";}
function render(){
 let count=0;
 for(let i=0;i<64;i++){const live=(board&(1n<<BigInt(i)))!==0n;const cell=$("grid").children[i];cell.classList.toggle("live",live);cell.setAttribute("aria-pressed",String(live));if(live)count++;}
 $("generation").textContent=generation;$("alive").textContent=count;
}
function reset(name){stop();revision++;generation=0;board=patterns[name].reduce((b,[x,y])=>b|(1n<<BigInt(y*8+x)),0n);render();status("life-status","Ready to simulate");}
for(let i=0;i<64;i++){
 const cell=document.createElement("button");cell.className="cell";cell.type="button";cell.setAttribute("aria-label","Cell "+(i%8+1)+", "+(Math.floor(i/8)+1));
 cell.addEventListener("click",()=>{stop();revision++;board^=1n<<BigInt(i);render();});$("grid").append(cell);
}
async function step(){
 if(busy)return;busy=true;$("step").disabled=true;const started=revision;
 try{const result=await request("/api/life?board="+board.toString(16)+"&steps=1");
 if(started===revision){board=BigInt("0x"+result.board);generation++;render();record("conway",result);status("life-status","Executed generation "+generation+" / finite boundaries");}}
 catch(error){stop();status("life-status",error.message,true);}
 finally{busy=false;$("step").disabled=false;if(playing)setTimeout(step,250);}
}
$("step").addEventListener("click",step);
$("play").addEventListener("click",()=>{if(playing){stop();return;}playing=true;$("play").textContent="Pause";if(!busy)step();});
$("reset").addEventListener("click",()=>reset("blinker"));
document.querySelectorAll("[data-pattern]").forEach(b=>b.addEventListener("click",()=>reset(b.dataset.pattern)));
$("pqc").addEventListener("click",async()=>{
 $("pqc").disabled=true;status("pqc-status","Generating keys and checking tampering…");
 try{const result=await request("/api/pqc");record("pqc",result);
 for(const [id,key] of [["shared","shared_secret_match"],["kem","kem_mutation_rejected"],["payload","payload_roundtrip"],["tamper","payload_tamper_rejected"]])$(id).textContent=result[key]===true?"PASS":"FAIL";
 status("pqc-status","Exchange completed / "+result.kem_ciphertext_bytes+" byte KEM ciphertext");}
 catch(error){status("pqc-status",error.message,true);for(const id of ["shared","kem","payload","tamper"])$(id).textContent="—";}
 finally{$("pqc").disabled=false;}
});
$("rpc").addEventListener("click",async()=>{
 $("rpc").disabled=true;status("rpc-status","Probing the configured endpoint…");
 try{const result=await request("/api/rpc","POST");record("rpc",result);$("chain-title").textContent=result.status==="connected"?"Connected":"Not configured";$("chain-icon").textContent=result.status==="connected"?"●":"○";$("chain-detail").textContent=result.message;$("chain-id").textContent=result.chain_id??"—";$("block-height").textContent=result.block_number??"—";status("rpc-status",result.message);}
 catch(error){record("rpc",{status:"failed",message:error.message});$("chain-title").textContent="Probe failed";$("chain-icon").textContent="○";$("chain-id").textContent="—";$("block-height").textContent="—";status("rpc-status",error.message,true);}
 finally{$("rpc").disabled=false;}
});
$("export").addEventListener("click",()=>{const blob=new Blob([JSON.stringify({project:$("project").textContent,...evidence},null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="qmoosa-evidence.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function refresh(){const result=await request("/api/health");$("project").textContent=result.project.name;document.title=result.project.name+" | QMoosa";status("rpc-status",result.rpc);}
$("unlock").addEventListener("click",async()=>{accessToken=$("token").value.trim();try{await refresh();$("token").value="";accessState(true);$("auth-status").textContent="Unlocked for this browser tab";}catch(error){accessToken="";$("auth-status").textContent=error.message;}});
$("lock").addEventListener("click",()=>{stop();accessToken="";accessState(false);for(const key of Object.keys(evidence))delete evidence[key];$("evidence").textContent='{"status":"locked"}';$("auth-status").textContent="Locked";});
accessState(false);
request("/api/config").then(async config=>{authRequired=config.auth_required;$("auth").hidden=!authRequired;$("project").textContent=config.name;if(authRequired){status("rpc-status","Unlock the workbench to run operations");}else{accessState(true);await refresh();}}).catch(error=>status("rpc-status",error.message,true));
reset("blinker");
