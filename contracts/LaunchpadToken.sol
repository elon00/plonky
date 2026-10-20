// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Unaudited, whole-unit ERC20 bonding-curve reference for local/testnet use.
/// @dev No admin withdrawal: the curve reserve backs every outstanding unit.
///      Price of the next whole token at supply S is BASE_PRICE + PRICE_STEP*S.
contract LaunchpadToken is ERC20, ReentrancyGuard {
    uint256 public constant MAX_SUPPLY = 1_000_000;
    uint256 public constant BASE_PRICE = 1e12;
    uint256 public constant PRICE_STEP = 1e9;

    error InvalidAmount();
    error SupplyCap();
    error Slippage();
    error Expired();
    error IncorrectPayment();
    error RefundFailed();
    event Purchased(address indexed buyer, uint256 amount, uint256 cost);
    event Redeemed(address indexed seller, uint256 amount, uint256 refund);

    constructor(string memory name_, string memory symbol_) ERC20(name_, symbol_) {}

    function decimals() public pure override returns (uint8) { return 0; }

    function reserveRequired(uint256 supply) public pure returns (uint256) {
        if (supply > MAX_SUPPLY) revert SupplyCap();
        if (supply == 0) return 0;
        return BASE_PRICE * supply + PRICE_STEP * supply * (supply - 1) / 2;
    }

    function quoteBuy(uint256 amount) public view returns (uint256) {
        if (amount == 0) revert InvalidAmount();
        uint256 supply = totalSupply();
        if (amount > MAX_SUPPLY - supply) revert SupplyCap();
        return reserveRequired(supply + amount) - reserveRequired(supply);
    }

    function quoteSell(uint256 amount) public view returns (uint256) {
        if (amount == 0 || amount > totalSupply()) revert InvalidAmount();
        uint256 supply = totalSupply();
        return reserveRequired(supply) - reserveRequired(supply - amount);
    }

    function buy(uint256 amount, uint256 maxCost, uint256 deadline) external payable nonReentrant {
        if (block.timestamp > deadline) revert Expired();
        uint256 cost = quoteBuy(amount);
        if (cost > maxCost) revert Slippage();
        if (msg.value != cost) revert IncorrectPayment();
        _mint(msg.sender, amount);
        emit Purchased(msg.sender, amount, cost);
    }

    function sell(uint256 amount, uint256 minRefund, uint256 deadline) external nonReentrant {
        if (block.timestamp > deadline) revert Expired();
        uint256 refund = quoteSell(amount);
        if (refund < minRefund) revert Slippage();
        _burn(msg.sender, amount);
        (bool sent,) = payable(msg.sender).call{value:refund}("");
        if (!sent) revert RefundFailed();
        emit Redeemed(msg.sender, amount, refund);
    }
}
