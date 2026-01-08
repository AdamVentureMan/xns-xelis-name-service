# Download XELIS Software

## Quick Download Steps

1. **Visit GitHub Releases**: https://github.com/xelis-project/xelis/releases

2. **Download Latest Release**:
   - Look for the latest release (e.g., v1.0.0)
   - Download Windows binaries:
     - `xelis-daemon-windows-x64.zip` or `.exe`
     - `xelis-wallet-windows-x64.zip` or `.exe`
   - May also need `xelis-miner` if separate

3. **Extract Files**:
   - Extract to a folder like `C:\xelis` or `C:\Users\cmhbk\xelis`
   - Or keep them in `C:\Users\cmhbk` (current directory)

4. **Verify Files**:
   - You should have:
     - `xelis-daemon.exe` (or similar name)
     - `xelis-wallet.exe` (or similar name)

## Alternative: Build from Source

If you prefer to build from source:

```powershell
# Install Rust (if not already installed)
# Download from: https://www.rust-lang.org/tools/install

# Clone repository
git clone https://github.com/xelis-project/xelis.git
cd xelis

# Build (check README for exact commands)
cargo build --release

# Binaries will be in: target/release/
```

## After Download

Once you have the binaries:

1. **Option A**: Place them in `C:\Users\cmhbk` (current directory)
2. **Option B**: Place them in `C:\xelis` and update paths in scripts

Then run:
```powershell
.\start_xelis_devnet.ps1
```

Or manually:
```powershell
# Terminal 1: Start daemon
.\xelis-daemon.exe --network dev

# Terminal 2: Start wallet
.\xelis-wallet.exe --network dev
```

