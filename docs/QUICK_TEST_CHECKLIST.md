# XELBank Quick Test Checklist

## Pre-Testing Setup

### Environment Choice
- [ ] **Option A (Recommended)**: Local Devnet setup
  - [ ] XELIS daemon running with `--network devnet`
  - [ ] XELIS wallet connected with `--network devnet`
  - [ ] Mined test coins locally
- [ ] **Option B**: Public Testnet setup
  - [ ] XELIS daemon running with `--network testnet`
  - [ ] XELIS wallet connected with `--network testnet`
  - [ ] Testnet XEL tokens from faucet (Discord #faucet)

### Contract Setup
- [ ] Contract compiled successfully
- [ ] Contract deployed to chosen network (dev/testnet)
- [ ] Contract address saved
- [ ] RPC endpoint configured (`127.0.0.1:8080` default)

### XELIS-Specific Checks
- [ ] Understanding BlockDAG architecture (not linear blockchain)
- [ ] DApp handles Topoheight changes (not just block height)
- [ ] RPC calls formatted correctly (JSON-RPC API)
- [ ] Transaction finality model understood

## Basic Function Tests

### Owner Functions
- [ ] `supply_liquidity()` - Owner can supply
- [ ] `supply_liquidity()` - Non-owner rejected (error 1)
- [ ] `supply_liquidity()` - Zero amount rejected (error 2)
- [ ] `withdraw_liquidity()` - Owner can withdraw available liquidity
- [ ] `withdraw_liquidity()` - Cannot withdraw more than available (error 3)
- [ ] `withdraw_interest()` - Owner can withdraw interest

### User Functions
- [ ] `deposit_collateral()` - User can deposit
- [ ] `deposit_collateral()` - Zero amount rejected (error 1)
- [ ] `borrow()` - User can borrow with sufficient collateral
- [ ] `borrow()` - Insufficient liquidity rejected (error 2)
- [ ] `borrow()` - No collateral rejected (error 3)
- [ ] `borrow()` - Insufficient collateral ratio rejected (error 4)
- [ ] `repay()` - User can repay loan with interest
- [ ] `repay()` - No loan rejected (error 1)
- [ ] `repay()` - Insufficient payment rejected (error 2)
- [ ] `withdraw_collateral()` - User can withdraw
- [ ] `withdraw_collateral()` - Violates ratio rejected (error 4)

### Liquidation
- [ ] `liquidate()` - Can liquidate under-collateralized loan
- [ ] `liquidate()` - No loan rejected (error 1)
- [ ] `liquidate()` - Sufficiently collateralized rejected (error 3)

## Integration Tests

- [ ] Complete lending cycle (deposit → borrow → repay → withdraw)
- [ ] Multiple users can interact simultaneously
- [ ] Interest accrues correctly over time
- [ ] Collateralization ratios enforced correctly
- [ ] State consistency maintained (`total_borrowed <= total_liquidity`)

## Security Checks

- [ ] Access control works (owner-only functions)
- [ ] Arithmetic overflow/underflow protection
- [ ] State invariants maintained
- [ ] Events emitted correctly

## Test Commands (Example)

Replace `CONTRACT_ADDRESS` with your deployed contract address:

```bash
# Supply liquidity (as owner)
call_contract CONTRACT_ADDRESS supply_liquidity --value 1000

# Deposit collateral (as user)
call_contract CONTRACT_ADDRESS deposit_collateral --value 150

# Borrow (as user)
call_contract CONTRACT_ADDRESS borrow 100

# Repay (as user, send principal + interest)
call_contract CONTRACT_ADDRESS repay --value 110

# Withdraw collateral (as user)
call_contract CONTRACT_ADDRESS withdraw_collateral 50

# Liquidate (anyone can call)
call_contract CONTRACT_ADDRESS liquidate USER_ADDRESS
```

*Note: Actual command syntax depends on XELIS CLI tools*

