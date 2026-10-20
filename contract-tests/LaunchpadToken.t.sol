// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {LaunchpadToken} from "../contracts/LaunchpadToken.sol";

interface Vm {
    function deal(address who, uint256 amount) external;
    function prank(address who) external;
    function expectRevert(bytes4 selector) external;
    function expectRevert() external;
    function warp(uint256 timestamp) external;
}

contract RejectingSeller {
    LaunchpadToken immutable token;
    constructor(LaunchpadToken t) { token=t; }
    function buy() external payable { token.buy{value:msg.value}(1,msg.value,block.timestamp); }
    function sell() external { token.sell(1,0,block.timestamp); }
    receive() external payable { revert("reject"); }
}

contract ReenteringSeller {
    LaunchpadToken immutable token;
    bool public blocked;
    constructor(LaunchpadToken t) { token=t; }
    function buy() external payable { token.buy{value:msg.value}(2,msg.value,block.timestamp); }
    function sell() external { token.sell(1,0,block.timestamp); }
    receive() external payable {
        try token.sell(1,0,block.timestamp) { blocked=false; } catch { blocked=true; }
    }
}

contract LaunchpadTokenTest {
    Vm constant vm=Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    LaunchpadToken token;
    address constant ALICE=address(0xA11CE);
    address constant BOB=address(0xB0B);
    function setUp() public {
        token=new LaunchpadToken("Demo","DEMO");
        vm.deal(address(this),1000 ether);
        vm.deal(ALICE,1000 ether);
        vm.deal(BOB,1000 ether);
    }
    function buy(uint256 amount) internal {
        uint256 cost=token.quoteBuy(amount);
        token.buy{value:cost}(amount,cost,block.timestamp);
    }
    function testERC20TransfersAndAllowance() public {
        buy(10);
        require(token.decimals()==0);
        require(token.transfer(ALICE,3));
        require(token.approve(BOB,2));
        vm.prank(BOB); require(token.transferFrom(address(this),ALICE,2));
        require(token.balanceOf(ALICE)==5 && token.allowance(address(this),BOB)==0);
    }
    function testBuySellRoundtripAndReserve() public {
        uint256 initial=address(this).balance; buy(10);
        require(address(token).balance==token.reserveRequired(10));
        token.sell(10,token.quoteSell(10),block.timestamp);
        require(token.totalSupply()==0 && address(token).balance==0);
        require(address(this).balance==initial);
    }
    function testRejectsOverpaymentAndUnderpayment() public {
        uint256 cost=token.quoteBuy(1);
        vm.expectRevert(LaunchpadToken.IncorrectPayment.selector);
        token.buy{value:cost+1}(1,cost,block.timestamp);
        vm.expectRevert(LaunchpadToken.IncorrectPayment.selector);
        token.buy{value:cost-1}(1,cost,block.timestamp);
    }
    function testZeroCapSlippageDeadline() public {
        vm.expectRevert(LaunchpadToken.InvalidAmount.selector); token.quoteBuy(0);
        uint256 aboveCap=token.MAX_SUPPLY()+1; vm.expectRevert(LaunchpadToken.SupplyCap.selector); token.quoteBuy(aboveCap);
        uint256 cost=token.quoteBuy(2);
        vm.expectRevert(LaunchpadToken.Slippage.selector);
        token.buy{value:cost}(2,cost-1,block.timestamp);
        vm.warp(100);
        vm.expectRevert(LaunchpadToken.Expired.selector);
        token.buy{value:cost}(2,cost,99);
        buy(2);
        uint256 tooMuchRefund=token.quoteSell(1)+1;
        vm.expectRevert(LaunchpadToken.Slippage.selector);
        token.sell(1,tooMuchRefund,block.timestamp);
    }
    function testRefundFailureRollsBackBurn() public {
        RejectingSeller seller=new RejectingSeller(token);
        seller.buy{value:token.quoteBuy(1)}();
        vm.expectRevert(LaunchpadToken.RefundFailed.selector);seller.sell();
        require(token.balanceOf(address(seller))==1 && token.totalSupply()==1);
    }
    function testReentrancyIsBlocked() public {
        ReenteringSeller seller=new ReenteringSeller(token);
        seller.buy{value:token.quoteBuy(2)}(); seller.sell();
        require(seller.blocked());
        require(token.balanceOf(address(seller))==1);
        require(address(token).balance==token.reserveRequired(1));
    }
    function testNoBalanceCannotRedeem() public {
        buy(1);vm.prank(ALICE);vm.expectRevert();token.sell(1,0,block.timestamp);
    }
    function testFuzzReserveAndSplitBuy(uint32 seed,uint32 sellSeed) public {
        uint256 a=uint256(seed)%500+1;uint256 b=uint256(sellSeed)%500+1;
        uint256 combined=token.quoteBuy(a+b);
        uint256 first=token.quoteBuy(a);buy(a);
        uint256 second=token.quoteBuy(b);buy(b);
        require(first+second==combined);
        uint256 sellAmount=uint256(seed)%(a+b)+1;
        token.sell(sellAmount,0,block.timestamp);
        require(address(token).balance==token.reserveRequired(token.totalSupply()));
    }
    receive() external payable {}
}
