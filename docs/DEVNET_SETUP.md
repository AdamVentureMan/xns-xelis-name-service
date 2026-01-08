# XELIS Devnet Setup Guide for XELBank Testing

This guide walks you through setting up a local XELIS Devnet for testing your XELBank contract.

## Why Use Local Devnet?

- ✅ **Instant block times** (if configured)
- ✅ **Unlimited test coins** (mine to yourself)
- ✅ **Zero network latency**
- ✅ **Complete control** over the environment
- ✅ **No need for faucets** or external dependencies

## Step 1: Download XELIS Software

1. Visit [XELIS GitHub](https://github.com/xelis-project/xelis)
2. Download the latest release for your platform
3. Extract the files - you'll need:
   - `xelis_daemon` (the blockchain node)
   - `xelis_wallet` (the CLI wallet)

## Step 2: Start the Daemon in Devnet Mode

Open a terminal/command prompt and run:

```bash
# Linux/Mac
./xelis_daemon --network devnet

# Windows
xelis_daemon.exe --network devnet
```

This creates a **private blockchain instance** on your machine, completely separate from Mainnet.

**What happens:**
- A new blockchain starts from genesis
- You are the only miner/validator
- Blocks are created instantly (or as configured)
- All data is stored locally

## Step 3: Create and Configure Wallet

Open a **new terminal window** and start the wallet:

```bash
# Linux/Mac
./xelis_wallet --network dev

# Windows
xelis_wallet.exe --network dev
```

**First time setup:**
1. Create a new wallet file (or open existing)
2. The wallet will connect to your local daemon automatically
3. Save your wallet seed phrase securely

## Step 4: Mine Test Coins

Since you're the only miner on your private Devnet, you can mine blocks to yourself:

```bash
# In the wallet CLI, use mining commands
# (Exact commands depend on wallet interface)
mine
# or
start_mining
```

**Result:**
- Blocks are mined instantly (or very quickly)
- Rewards go to your wallet address
- You now have unlimited test XEL coins!

## Step 5: Verify Your Setup

Check that everything is working:

```bash
# Check daemon is running
# Should see block height increasing

# Check wallet balance
# In wallet CLI:
balance
# or
get_balance
```

## Step 6: Deploy Your Contract

Now you're ready to deploy XELBank:

1. **Compile your contract** (if not already done):
   ```bash
   # Use XELIS compiler tool
   xelis-compile XELBank.silex
   ```

2. **Deploy via wallet**:
   ```bash
   # In wallet CLI, use deploy_contract command
   deploy_contract <bytecode> --invoke '{"max_gas": 1000000}'
   ```

3. **Save contract address** for testing

## Step 7: Test Your Contract

Now you can test all XELBank functions:

- Supply liquidity (as owner)
- Deposit collateral (as users)
- Borrow XEL
- Repay loans
- Test liquidation
- Withdraw interest

All transactions will be instant since you control the network!

## Troubleshooting

### Daemon won't start
- Check if port 8080 (or configured RPC port) is available
- Ensure no other XELIS daemon is running
- Check firewall settings

### Wallet can't connect
- Verify daemon is running first
- Check network flag matches (`--network devnet` in both)
- Ensure RPC endpoint is correct (default: `127.0.0.1:8080`)

### Can't mine blocks
- Verify daemon is running and synced
- Check mining configuration in daemon
- Ensure wallet is connected to daemon

### Contract deployment fails
- Verify contract compiled successfully
- Check gas limit is sufficient
- Ensure you have enough balance for deployment fees

## Advanced Configuration

### Custom Block Times

You can configure block times in devnet mode (check XELIS documentation for exact parameters):

```bash
./xelis_daemon --network devnet --block-time 1
# Creates blocks every 1 second
```

### Multiple Wallets

You can create multiple wallets for testing different users:

```bash
# Create wallet 1 (owner)
./xelis_wallet --network devnet --wallet owner.wallet

# Create wallet 2 (user)
./xelis_wallet --network devnet --wallet user.wallet
```

### Reset Devnet

To start fresh, simply:
1. Stop the daemon
2. Delete the devnet data directory (check XELIS docs for location)
3. Restart daemon - it will create a new blockchain

## Next Steps

Once your Devnet is running:
1. Deploy XELBank contract
2. Test all functions systematically
3. Run integration tests
4. Verify security checks
5. When ready, test on public Testnet before Mainnet

## Resources

- [XELIS GitHub](https://github.com/xelis-project/xelis)
- [XELIS Documentation](https://docs.xelis.io)
- [XELIS Discord](https://discord.gg/xelis) - #dev channel for help

