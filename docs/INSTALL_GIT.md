# Install Git to Clone XELIS Repository

## Option 1: Install Git for Windows (Recommended)

1. **Download Git for Windows**:
   - Visit: https://git-scm.com/download/win
   - Download the latest version
   - Run the installer
   - Use default settings (recommended)

2. **After Installation**:
   - Restart PowerShell or open a new terminal
   - Verify installation:
     ```powershell
     git --version
     ```

3. **Then Clone the Repository**:
   ```powershell
   git clone https://github.com/xelis-project/xelis-blockchain.git
   cd xelis-blockchain
   ```

## Option 2: Download ZIP Instead

If you don't want to install Git, you can download the repository as a ZIP:

1. Visit: https://github.com/xelis-project/xelis-blockchain
2. Click the green "Code" button
3. Select "Download ZIP"
4. Extract the ZIP file to `C:\Users\cmhbk\xelis-blockchain`

## Option 3: Use GitHub Desktop

1. Download GitHub Desktop: https://desktop.github.com/
2. Install and sign in
3. Use "Clone a repository from the Internet"
4. Enter: `https://github.com/xelis-project/xelis-blockchain.git`

## After Cloning/Building

Once you have the repository:

1. **Build from Source** (requires Rust):
   ```powershell
   cd xelis-blockchain
   cargo build --release
   ```

2. **Binaries will be in**:
   - `target/release/xelis-daemon.exe`
   - `target/release/xelis-wallet.exe`
   - `target/release/xelis-miner.exe`

3. **Then you can start devnet**:
   ```powershell
   .\target\release\xelis-daemon.exe --network dev
   ```

