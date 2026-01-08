# XNS - XELIS Name Service

A decentralized name service (DNS) for the XELIS blockchain, allowing users to register human-readable names that map to wallet addresses.

## 🎯 Overview

XNS (XELIS Name Service) is a smart contract deployed on the XELIS blockchain that enables:
- **Human-readable names** → Wallet addresses (e.g., `alice.xns` → `xet:...`)
- **Tiered pricing** - Short names (3-4 chars) cost more than longer names
- **Name management** - Renew, transfer, and update target addresses
- **Grace period** - 30 days to renew expired names

## 📋 Contract Versions

- **XNS.silex** - Initial version
- **XNS_v2.silex** - Enhanced with dynamic fees and owner/target separation
- **XNS_v3.silex** - Current production version (deployed to testnet)

## 🚀 Deployment Status

### Testnet
- **Contract Address:** `eb7a0d88c570da29201f26d29896a9b6e604c5ea9259b596cea1e9763bb6f097`
- **Network:** XELIS Testnet
- **Explorer:** https://testnet-explorer.xelis.io/transaction/eb7a0d88c570da29201f26d29896a9b6e604c5ea9259b596cea1e9763bb6f097
- **Status:** ✅ Active and tested

### Mainnet
- **Status:** ⏳ Pending deployment

## 💰 Pricing

| Name Length | Registration | Renewal |
|-------------|-------------|---------|
| Short (3-4 chars) | 50 XEL | 20 XEL |
| Normal (5+ chars) | 10 XEL | 5 XEL |

## 🛠️ Project Structure

```
XEL/
├── XNS_v3.silex          # Main smart contract (Silex)
├── xns_client.py         # Python client for contract interaction
├── xelis-bin/            # XELIS binaries (daemon, wallet, miner)
├── docs/                 # Documentation
│   ├── TESTING_GUIDE.md
│   ├── DEVNET_SETUP.md
│   └── SETUP_XELIS.md
└── README.md             # This file
```

## 📖 Quick Start

### 1. Prerequisites

- XELIS daemon and wallet binaries
- Python 3.x
- XELIS wallet with testnet XEL

### 2. Setup

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Start testnet daemon
cd xelis-bin
.\xelis_daemon.exe --network testnet --allow-boost-sync
```

### 3. Start Wallet RPC

In your wallet CLI:
```
start_rpc_server 127.0.0.1:8081 myuser mypassword
```

### 4. Use the Client

```bash
# Check wallet status
python xns_client.py status

# Register a name
python xns_client.py register myname

# Resolve a name
python xns_client.py resolve myname

# Renew a name
python xns_client.py renew myname
```

## 🔧 Contract Functions

- `register(name, target)` - Register a new name
- `renew(name)` - Renew an expired name
- `transfer_name(name, new_owner)` - Transfer ownership
- `set_target(name, new_target)` - Update target address
- `check_available(name)` - Check if name is available
- `resolve(name)` - Get address for a name
- `get_price(name)` - Get registration price
- `get_renew_price(name)` - Get renewal price

## 📚 Documentation

- [Testing Guide](docs/TESTING_GUIDE.md) - How to test the contract
- [Devnet Setup](docs/DEVNET_SETUP.md) - Local development setup
- [XELIS Setup](docs/SETUP_XELIS.md) - XELIS installation guide

## 🌐 Frontend (Coming Soon)

A web-based dApp is planned for easy name registration and management.

See [XNS_FRONTEND_PLAN.md](XNS_FRONTEND_PLAN.md) for details.

## 🤝 Contributing

This is an open-source project. Contributions welcome!

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- XELIS blockchain team for the amazing platform
- Slixe for help with testnet deployment

---

**Built with ❤️ for the XELIS ecosystem**
