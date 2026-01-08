# XELIS Devnet Setup - Step by Step

## Step 1: Download XELIS Software

### Option A: Download from GitHub Releases

1. Visit: https://github.com/xelis-project/xelis/releases
2. Download the latest release for Windows:
   - `xelis-daemon-windows-x64.exe` (or similar)
   - `xelis-wallet-windows-x64.exe` (or similar)
3. Extract to a folder (e.g., `C:\xelis`)

### Option B: Build from Source

If you prefer to build from source:
```bash
git clone https://github.com/xelis-project/xelis.git
cd xelis
# Follow build instructions in README
```

## Step 2: Start the Daemon

Open PowerShell or Command Prompt and navigate to where you extracted XELIS:

```powershell
# Navigate to XELIS directory
cd C:\xelis

# Start daemon in devnet mode
.\xelis-daemon.exe --network devnet
```

**What to expect:**
- Daemon will start initializing
- You'll see logs about creating the devnet blockchain
- It will start listening on port 8080 (default RPC port)
- Keep this terminal window open

## Step 3: Create Wallet and Mine Coins

Open a **NEW** PowerShell/Command Prompt window:

```powershell
# Navigate to XELIS directory
cd C:\xelis

# Start wallet in devnet mode
.\xelis-wallet.exe --network devnet
```

**First time setup:**
1. Choose to create a new wallet
2. Save your seed phrase securely
3. Set a password for your wallet
4. Wallet will connect to your local daemon

**Mine coins:**
Once wallet is running, you can mine blocks:
```bash
# In wallet CLI, use mining commands
mine
# or check balance first
balance
```

## Step 4: Verify Setup

Check that everything is working:

```bash
# In wallet CLI:
balance
# Should show your mined coins

# Check daemon is running (in daemon terminal)
# Should see blocks being created
```

## Troubleshooting

### Port Already in Use
If port 8080 is busy:
```powershell
.\xelis-daemon.exe --network devnet --rpc-bind-port 8081
```

### Wallet Can't Connect
- Make sure daemon is running first
- Check both are using `--network devnet`
- Verify daemon is listening on correct port

### Can't Mine Blocks
- Ensure daemon is fully started
- Check wallet is connected to daemon
- Verify you're on devnet (not mainnet/testnet)

## Next Steps

Once devnet is running:
1. ✅ Daemon running on devnet
2. ✅ Wallet created and connected
3. ✅ Test coins mined
4. → Ready to deploy XELBank contract!

