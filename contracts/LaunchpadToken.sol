// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract LaunchpadToken {
    string public name;
    string public symbol;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    event Mint(address indexed to, uint256 amount, uint256 cost);

    constructor(string memory _name, string memory _symbol) {
        name = _name;
        symbol = _symbol;
    }

    function mint(uint256 amount) external payable {
        uint256 cost = amount * 1e14;
        require(msg.value >= cost, "Underpaid");
        totalSupply += amount;
        balanceOf[msg.sender] += amount;
        emit Mint(msg.sender, amount, cost);
    }
}
