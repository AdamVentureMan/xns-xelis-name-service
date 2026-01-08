# XELBank Contract Testing Guide

This guide will help you test your XELBank smart contract on XELIS blockchain.

## Prerequisites

1. **XELIS Software**: Download from [XELIS GitHub](https://github.com/xelis-project/xelis)
   - `xelis_daemon` (the node)
   - `xelis_wallet` (the CLI wallet)
2. **Test Coins**: Either mine locally on Devnet or get from Testnet faucet
3. **Silex Compiler**: The Silex compiler/toolchain for compiling contracts

## Step 1: Set Up Your Testing Environment

### Option A: Local Devnet (Recommended)

The most efficient way to test is to run your own local instance of the blockchain. This gives you:
- Instant block times (if configured)
- Unlimited test coins (by mining)
- Zero network latency
- Complete control over the environment

1. **Start the Daemon in Devnet Mode**:
   ```bash
   ./xelis_daemon --network dev
   ```
   This creates a private blockchain instance on your machine, completely separate from Mainnet.

2. **Create a Devnet Wallet**:
   ```bash
   ./xelis_wallet --network dev
   ```
   Create a new wallet file and connect it to your local daemon.

3. **Mine Test Coins**:
   Since you are the only miner on this private network, you can mine blocks to yourself to generate "fake" XEL coins for testing.

### Option B: Public Testnet

If testing on a public Testnet (rather than local Devnet):

1. **Get Testnet Coins from Faucet**:
   - Check XELIS Discord #faucet or #testnet channels
   - Community members or bots often distribute test coins
   - **⚠️ Warning**: Never send Mainnet XEL to a Testnet address, or vice versa. They will be lost.

2. **Connect to Testnet**:
   ```bash
   ./xelis_daemon --network testnet
   ./xelis_wallet --network testnet
   ```

## Step 2: Verify Your Contract

First, ensure your contract file `XELBank.silex` is syntactically correct:

```bash
# Navigate to your contract directory
cd C:\Users\cmhbk

# Verify the file exists
ls XELBank.silex
# On Windows PowerShell:
Get-ChildItem XELBank.silex
```

## Step 3: Compile the Contract

Compile your Silex contract. The exact command depends on the XELIS toolchain:

```bash
# Example compilation command (verify with XELIS docs)
xelis-compile XELBank.silex

# Or if using a different tool:
silex compile XELBank.silex
```

This should generate:
- Bytecode for deployment
- An ABI (Application Binary Interface) file
- Any compilation errors/warnings

## Step 4: Deploy the Contract

### Using XELIS CLI Wallet

1. **Ensure Daemon is Running**:
   ```bash
   # For Devnet
   ./xelis_daemon --network dev
   
   # For Testnet
   ./xelis_daemon --network testnet
   ```

2. **Deploy via CLI Wallet**:
   ```bash
   # Connect wallet to daemon
   ./xelis_wallet --network devnet  # or --network testnet
   
   # Use deploy_contract command with your compiled bytecode
   # Include invoke: { max_gas: u64 } parameter for constructor
   ```

### Important XELIS-Specific Considerations

**BlockDAG Architecture**: XELIS uses a BlockDAG (not a linear blockchain), so be aware:
- Blocks are not strictly linear
- Test how your DApp handles "orphaned" blocks or re-orgs
- Monitor Topoheight changes, not just "block height"
- Transaction finality may work differently than linear chains

**RPC Integration**: Ensure your DApp communicates correctly with the XELIS Daemon API:
- Default RPC port: `127.0.0.1:8080`
- Review [XELIS API Documentation](https://docs.xelis.io) for correct JSON-RPC calls
- Test `get_balance`, `submit_transaction`, etc.

**Account-Based Structure**: XELIS uses account-based (not UTXO) structure, similar to Ethereum but with BlockDAG.

## Step 5: Test Individual Functions

### Test 1: Owner Supplies Liquidity

```bash
# Call supply_liquidity entry function
# Send XEL with the transaction (e.g., 1000 XEL)
# Expected: total_liquidity increases, event emitted
```

**Test Case**:
- **Action**: Owner sends 1000 XEL and calls `supply_liquidity()`
- **Expected Result**: 
  - `total_liquidity` = 1000
  - Event "LiquiditySupplied" logged
  - Return code: 0

**Error Cases to Test**:
- Non-owner tries to supply → Should return error code 1
- Zero amount sent → Should return error code 2

### Test 2: User Deposits Collateral

```bash
# Call deposit_collateral entry function
# Send XEL with transaction (e.g., 150 XEL)
# Expected: collateral[user] increases
```

**Test Case**:
- **Action**: User sends 150 XEL and calls `deposit_collateral()`
- **Expected Result**:
  - `collateral[user_address]` = 150
  - Event "CollateralDeposited" logged
  - Return code: 0

### Test 3: User Borrows XEL

```bash
# Call borrow(amount) entry function
# Amount: 100 XEL
# Expected: User receives 100 XEL, loan created, total_borrowed increases
```

**Test Case**:
- **Prerequisites**: User has 150 XEL collateral deposited
- **Action**: User calls `borrow(100)`
- **Expected Result**:
  - User receives 100 XEL
  - `total_borrowed` = 100
  - `loans[user_address]` contains loan with principal=100
  - Event "Borrowed" logged
  - Return code: 0

**Error Cases to Test**:
- Borrow without collateral → Error code 3
- Borrow more than available liquidity → Error code 2
- Borrow amount requiring >150% collateral → Error code 4

### Test 4: User Repays Loan

```bash
# Call repay() entry function
# Send principal + interest with transaction
# Expected: Loan removed, total_borrowed decreases
```

**Test Case**:
- **Prerequisites**: User has active loan
- **Action**: Calculate interest, send total amount, call `repay()`
- **Expected Result**:
  - Loan removed from `loans` map
  - `total_borrowed` decreases by principal
  - `total_liquidity` increases by principal
  - Event "Repaid" logged
  - Return code: 0

**Interest Calculation Verification**:
- Loan principal: 100 XEL
- Time elapsed: 1 year
- Expected interest: 100 * 1000 * 31536000 / (31536000 * 10000) = 10 XEL
- Total repayment: 110 XEL

### Test 5: User Withdraws Collateral

```bash
# Call withdraw_collateral(amount) entry function
# Expected: Collateral decreases, XEL sent to user
```

**Test Case**:
- **Prerequisites**: User has collateral, no active loan (or sufficient remaining)
- **Action**: User calls `withdraw_collateral(50)`
- **Expected Result**:
  - `collateral[user_address]` decreases by 50
  - User receives 50 XEL
  - Event "CollateralWithdrawn" logged
  - Return code: 0

**Error Cases**:
- Withdraw more than available → Error code 3
- Withdraw violates 150% ratio → Error code 4

### Test 6: Liquidation

```bash
# Call liquidate(user_address) entry function
# Expected: Under-collateralized loan liquidated, collateral seized
```

**Test Case**:
- **Setup**: 
  - User borrows 100 XEL with 150 XEL collateral (150% ratio)
  - Simulate collateral value drop (or manually reduce collateral)
  - Ratio drops below 110%
- **Action**: Anyone calls `liquidate(user_address)`
- **Expected Result**:
  - Loan removed
  - Collateral seized (up to debt amount)
  - `total_liquidity` increases
  - `total_borrowed` decreases
  - Event "Liquidated" logged
  - Return code: 0

**Error Cases**:
- Loan doesn't exist → Error code 1
- Loan is sufficiently collateralized → Error code 3

### Test 7: Owner Withdraws Interest

```bash
# Call withdraw_interest(amount) entry function
# Expected: Interest withdrawn to owner
```

**Test Case**:
- **Prerequisites**: Interest has accrued from loans
- **Action**: Owner calls `withdraw_interest(amount)`
- **Expected Result**:
  - Owner receives interest amount
  - Event "InterestWithdrawn" logged
  - Return code: 0

## Step 6: Integration Testing Scenarios

### Scenario 1: Complete Lending Cycle

1. Owner supplies 10,000 XEL liquidity
2. User A deposits 1,500 XEL collateral
3. User A borrows 1,000 XEL
4. Wait some time (simulate or use testnet time manipulation)
5. User A repays loan with interest
6. User A withdraws remaining collateral
7. Owner withdraws accrued interest

**Expected**: All steps succeed, state updates correctly

### Scenario 2: Multiple Users

1. Owner supplies liquidity
2. User A deposits collateral and borrows
3. User B deposits collateral and borrows
4. User A repays
5. User B's loan gets liquidated (if under-collateralized)

**Expected**: Each user's state tracked independently

### Scenario 3: Edge Cases

- Borrow maximum available liquidity
- Multiple borrows from same user (should accumulate)
- Repay more than owed (should still work)
- Try to withdraw all collateral with active loan (should fail)

## Step 7: Security Testing

### Access Control Tests

- ✅ Non-owner cannot supply liquidity
- ✅ Non-owner cannot withdraw liquidity
- ✅ Non-owner cannot withdraw interest
- ✅ Users can only access their own loans/collateral

### Collateralization Tests

- ✅ Cannot borrow without sufficient collateral (150%)
- ✅ Cannot withdraw collateral if it violates ratio
- ✅ Liquidation triggers at correct threshold (110%)

### Arithmetic Tests

- ✅ No overflow in interest calculations
- ✅ No underflow in withdrawals
- ✅ Division by zero protection

### State Consistency Tests

- ✅ `total_borrowed <= total_liquidity` always maintained
- ✅ Loan removal works correctly
- ✅ Collateral tracking accurate

## Step 8: Monitoring and Debugging

### XELIS-Specific Monitoring

**Topoheight Tracking**: Monitor Topoheight changes rather than just block height:
- Topoheight represents the topological order in the BlockDAG
- Your DApp should listen for Topoheight changes
- Handle potential re-orgs gracefully

**Transaction Finality**: 
- Understand XELIS transaction finality model
- Test how your contract handles transaction confirmations
- Account for BlockDAG structure in your logic

### Check Contract State

After each transaction, verify:
- State variables are updated correctly
- Events are emitted
- Return codes are correct

### Debugging Tips

1. **Use println statements**: Already included in `emit_event()` function
2. **Check transaction logs**: Review events and return codes
3. **Verify calculations**: Manually verify interest calculations
4. **Test incrementally**: Test one function at a time

## Step 9: Common Issues and Solutions

### Issue: "Only owner can..." errors

**Solution**: Ensure you're calling from the owner address set in constructor

### Issue: "Insufficient collateral" errors

**Solution**: Verify collateral amount meets 150% requirement:
- Required = borrow_amount * 15000 / 10000
- Example: Borrow 100 → Need 150 collateral

### Issue: Interest calculation seems wrong

**Solution**: Verify calculation:
```
interest = principal * INTEREST_RATE * elapsed_seconds / (SECONDS_IN_YEAR * 10000)
```

### Issue: Map operations fail

**Solution**: Verify map syntax matches Silex Standard Library:
- `.get(key)` returns `optional<T>`
- `.insert(key, value)` updates map
- `.remove(key)` removes entry

## Step 10: Next Steps

After successful testing:

1. **Code Review**: Review all functions for security
2. **Gas Optimization**: Check if any operations can be optimized
3. **Documentation**: Document any Standard Library functions used
4. **Mainnet Deployment**: Once confident, deploy to mainnet

## Additional Resources

- [XELIS Documentation](https://docs.xelis.io)
- [Silex Language Docs](https://docs.xelis.io/features/smart-contracts/silex)
- [XELIS GitHub](https://github.com/xelis-project/xelis)
- [XELIS API Documentation](https://docs.xelis.io) - JSON-RPC API reference
- **XELIS Discord**: Join for #dev channel support and #faucet for test coins
- **GitHub Issues**: Report bugs in node software on XELIS GitHub Issues page

## Pre-Testing Checklist

Before starting your tests, verify:

- [ ] **Network**: Are you connected to `--network devnet` (or `--network testnet`)?
- [ ] **Funds**: Do you have test coins (mined locally on Devnet or from faucet)?
- [ ] **RPC**: Is your DApp pointing to `127.0.0.1:8080` (default RPC port)?
- [ ] **Topoheight**: Is your DApp listening for Topoheight changes rather than just "block height"?
- [ ] **Daemon Running**: Is `xelis_daemon` running and synced?
- [ ] **Wallet Connected**: Is `xelis_wallet` connected to your daemon?
- [ ] **Contract Compiled**: Is your contract compiled successfully?
- [ ] **Contract Deployed**: Is your contract deployed and address saved?

## Notes

⚠️ **Important**: Some functions in the contract have commented-out transfer calls:
- `Transfer::send()` calls need to be uncommented once Standard Library transfer functions are confirmed
- Contract balance queries may need Standard Library functions
- Event system may need adjustment based on XELIS event implementation

Make sure to verify these with the XELIS Standard Library documentation before final deployment.

## Getting Help

If you encounter issues during testing:

1. **XELIS Discord**: Join the #dev channel for direct help from core developers
2. **GitHub Issues**: Report bugs in the node software on the XELIS GitHub Issues page
3. **Documentation**: Check the [XELIS documentation](https://docs.xelis.io) for API details
4. **Community**: The XELIS ecosystem is still evolving - community support is valuable

Remember: The best way to troubleshoot specific errors is to talk directly to the core developers in the Discord #dev channel.

