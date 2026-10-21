#!/usr/bin/env node
import {readOnlyRpc,probeEvmUpgrade,probeSolanaUpgrade,SOLANA_GENESIS,upgradeProbeExitCode} from '../dist/chain-upgrades.js';
const args=process.argv.slice(2);
const networks=['sepolia','ethereum-mainnet','solana-devnet','solana-mainnet'];
if(args.length!==2||args[0]!=='--network'||!networks.includes(args[1])){
 console.error('Build first: npm run build. Usage: node tools/chain-upgrades.mjs --network '+networks.join('|'));
 process.exitCode=2;
}else{
 try{
  const network=args[1];let report;
  if(network.startsWith('solana-')){
   const cluster=network==='solana-devnet'?'devnet':'mainnet-beta';
   const rpc=readOnlyRpc(process.env.QMOOSA_SOLANA_RPC_URL??`https://api.${cluster}.solana.com`,15000);
   report=await probeSolanaUpgrade(rpc,process.env.QMOOSA_SOLANA_GENESIS_HASH??SOLANA_GENESIS[cluster]);
  }else{
   const endpoint=network==='sepolia'?'https://ethereum-sepolia-rpc.publicnode.com':'https://ethereum-rpc.publicnode.com';
   report=await probeEvmUpgrade(readOnlyRpc(process.env.QMOOSA_RPC_URL??endpoint,15000),network==='sepolia'?11155111n:1n);
  }
  console.log(JSON.stringify({checkedAt:new Date().toISOString(),network,...report},null,2));
  process.exitCode=upgradeProbeExitCode(report);
 }catch{console.error('Upgrade probe failed; check configuration, provider capability and connectivity. No upgrade support is claimed.');process.exitCode=2;}
}
