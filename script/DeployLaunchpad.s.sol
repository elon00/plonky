// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {LaunchpadToken} from "../contracts/LaunchpadToken.sol";
interface BroadcastVm {function startBroadcast() external; function stopBroadcast() external;}
contract DeployLaunchpad {
    BroadcastVm constant vm=BroadcastVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    function run() external returns (LaunchpadToken token) {
        require(block.chainid==11155111 || block.chainid==31337,"Sepolia or local rehearsal only");
        // Sign using Foundry's encrypted keystore / hardware-wallet CLI options.
        // No private key is read from source code or chat.
        vm.startBroadcast();
        token=new LaunchpadToken("QMoosa Demo","QDEMO");
        vm.stopBroadcast();
    }
}
