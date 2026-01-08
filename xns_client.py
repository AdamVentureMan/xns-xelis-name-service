#!/usr/bin/env python3
"""
XNS Client v2.1 - XELIS Name Service Interaction Tool
Interact with the deployed XNS v2.1 contract via XELIS Wallet RPC

New in v2.1:
- Dynamic fees (adjustable by owner)
- Target address separation (owner vs target)
- Grace period for renewals
- Tiered pricing (short names cost more)
"""

import requests
import json
import argparse
import sys
import os
from base64 import b64encode

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.system('')  # Enable ANSI escape sequences

# =============================================================================
# CONFIGURATION
# =============================================================================

# Wallet RPC endpoint (start with: start_rpc_server 127.0.0.1:8081 myuser mypassword)
WALLET_RPC_URL = "http://127.0.0.1:8081/json_rpc"
WALLET_RPC_USER = "myuser"
WALLET_RPC_PASSWORD = "mypassword"

# Network configuration - change CONTRACT_ADDRESS when deploying to different networks
# DEVNET contract (XNS v2.1)
DEVNET_CONTRACT = "cca58df1a4fb50fbdcc3d9b189ae9185599523db36c39b490ceded4c10ffa5a9"

# TESTNET contract (deployed 2026-01-08)
TESTNET_CONTRACT = "eb7a0d88c570da29201f26d29896a9b6e604c5ea9259b596cea1e9763bb6f097"

# MAINNET contract (set this after deploying to mainnet)  
MAINNET_CONTRACT = ""  # TODO: Set after mainnet deployment

# Active contract address - change this to switch networks
CONTRACT_ADDRESS = TESTNET_CONTRACT  # Using TESTNET

# Native XEL asset hash (all zeros)
XEL_ASSET = "0000000000000000000000000000000000000000000000000000000000000000"

# Fees in atomic units (1 XEL = 100,000,000 atomic units)
ATOMIC_UNIT = 100_000_000

# v2.1 Tiered pricing (defaults from contract)
FEE_SHORT_REG = 50 * ATOMIC_UNIT      # 50 XEL for 3-4 char names
FEE_SHORT_RENEW = 20 * ATOMIC_UNIT    # 20 XEL renewal for short names
FEE_NORMAL_REG = 10 * ATOMIC_UNIT     # 10 XEL for 5+ char names
FEE_NORMAL_RENEW = 5 * ATOMIC_UNIT    # 5 XEL renewal for normal names
DEFAULT_MAX_GAS = 1 * ATOMIC_UNIT     # 1 XEL max gas

# Entry function IDs (from inspect_contract on daemon)
# Order in v2.1: register, renew, transfer_name, set_target, check_available,
#                resolve, get_price, get_renew_price, withdraw, set_fees, transfer_ownership
ENTRY_IDS = {
    "register": 25,
    "renew": 26,
    "transfer_name": 27,
    "set_target": 28,
    "check_available": 29,
    "resolve": 30,
    "get_price": 31,
    "get_renew_price": 32,
    "withdraw": 33,
    "set_fees": 34,
    "transfer_ownership": 35,
}

# Error codes for v2.1
ERROR_CODES = {
    0: "Success",
    1: "No transaction context",
    2: "Invalid name format",
    3: "Name not available",
    4: "Insufficient payment",
    5: "Refund failed",
    6: "Name not found",
    7: "Not the owner",
    8: "Name expired beyond grace period",
    9: "Transfer failed",
    10: "Nothing to withdraw",
}

# =============================================================================
# RPC HELPERS
# =============================================================================

def get_auth_header():
    """Create Basic Auth header for wallet RPC"""
    credentials = f"{WALLET_RPC_USER}:{WALLET_RPC_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

def rpc_call(method: str, params: dict = None):
    """Make an RPC call to the wallet"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1
    }
    if params:
        payload["params"] = params
    
    try:
        response = requests.post(
            WALLET_RPC_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                **get_auth_header()
            },
            timeout=30
        )
        result = response.json()
        
        if "error" in result:
            print(f"❌ RPC Error: {result['error']}")
            return None
        
        return result.get("result")
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure:")
        print("   1. Wallet is running")
        print(f"   2. RPC server is started: start_rpc_server 127.0.0.1:8081 {WALLET_RPC_USER} {WALLET_RPC_PASSWORD}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def build_and_broadcast_tx(tx_type: dict, broadcast: bool = True):
    """Build a transaction and optionally broadcast it"""
    params = {**tx_type}
    if broadcast:
        params["broadcast"] = True
    result = rpc_call("build_transaction", params)
    return result

# =============================================================================
# CONTRACT PARAMETER BUILDERS
# =============================================================================

def string_param(value: str) -> dict:
    """Build a string parameter"""
    return {
        "type": "primitive",
        "value": {"type": "string", "value": value}
    }

def u64_param(value: int) -> dict:
    """Build a u64 parameter (value must be passed as string)"""
    return {
        "type": "primitive",
        "value": {"type": "u64", "value": str(value)}
    }

def address_param(address: str) -> dict:
    """Build an address parameter"""
    # Try passing address as object with array value [type_name, fields...]
    return {
        "type": "object",
        "value": ["Address", address]
    }

def invoke_contract(entry_name: str, parameters: list = None, deposit_amount: int = 0, max_gas: int = DEFAULT_MAX_GAS) -> dict:
    """Build invoke_contract transaction type"""
    entry_id = ENTRY_IDS.get(entry_name)
    if entry_id is None:
        raise ValueError(f"Unknown entry function: {entry_name}")
    
    tx_type = {
        "invoke_contract": {
            "contract": CONTRACT_ADDRESS,
            "entry_id": entry_id,
            "parameters": parameters or [],
            "max_gas": max_gas,
            "permission": "none"
        }
    }
    
    if deposit_amount > 0:
        tx_type["invoke_contract"]["deposits"] = {
            XEL_ASSET: {"amount": deposit_amount}
        }
    
    return tx_type

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_short_name(name: str) -> bool:
    """Check if name is short (3-4 chars) for premium pricing"""
    return len(name) <= 4

def get_reg_fee(name: str) -> int:
    """Get registration fee based on name length"""
    return FEE_SHORT_REG if is_short_name(name) else FEE_NORMAL_REG

def get_renew_fee(name: str) -> int:
    """Get renewal fee based on name length"""
    return FEE_SHORT_RENEW if is_short_name(name) else FEE_NORMAL_RENEW

# =============================================================================
# XNS FUNCTIONS
# =============================================================================

def register_name(name: str, broadcast: bool = True):
    """Register a new name"""
    fee = get_reg_fee(name)
    tier = "SHORT (3-4 chars)" if is_short_name(name) else "NORMAL (5+ chars)"
    
    print(f"\n📝 Registering name: '{name}'")
    print(f"   Tier: {tier}")
    print(f"   Fee: {fee / ATOMIC_UNIT} XEL")
    
    tx_type = invoke_contract("register", [string_param(name)], deposit_amount=fee)
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def renew_name(name: str, broadcast: bool = True):
    """Renew an existing name"""
    fee = get_renew_fee(name)
    
    print(f"\n🔄 Renewing name: '{name}'")
    print(f"   Fee: {fee / ATOMIC_UNIT} XEL")
    
    tx_type = invoke_contract("renew", [string_param(name)], deposit_amount=fee)
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def transfer_name(name: str, new_owner: str, broadcast: bool = True):
    """Transfer name ownership (also resets target to new owner)"""
    print(f"\n🔀 Transferring name: '{name}'")
    print(f"   New owner: {new_owner}")
    print(f"   Note: Target address will reset to new owner")
    
    tx_type = invoke_contract("transfer_name", [string_param(name), address_param(new_owner)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def set_target(name: str, target_address: str, broadcast: bool = True):
    """Set target address (where resolve points to, different from owner)"""
    print(f"\n🎯 Setting target for: '{name}'")
    print(f"   Target address: {target_address}")
    
    tx_type = invoke_contract("set_target", [string_param(name), address_param(target_address)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def resolve_name(name: str, broadcast: bool = True):
    """Resolve a name (check if valid)"""
    print(f"\n🔍 Resolving name: '{name}'")
    
    tx_type = invoke_contract("resolve", [string_param(name)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        print(f"   Result codes: 0=valid, 1=not found, 2=expired")
        return result
    return None

def check_available(name: str, broadcast: bool = True):
    """Check if a name is available"""
    print(f"\n❓ Checking availability: '{name}'")
    
    tx_type = invoke_contract("check_available", [string_param(name)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        print(f"   Result codes: 0=available, 1=invalid format, 2=taken, 3=in grace period")
        return result
    return None

def get_price(name: str, broadcast: bool = True):
    """Get registration price for a name"""
    print(f"\n💲 Getting price for: '{name}'")
    
    tx_type = invoke_contract("get_price", [string_param(name)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        print(f"   Check transaction result for price in atomic units")
        return result
    return None

def get_renew_price(name: str, broadcast: bool = True):
    """Get renewal price for a name"""
    print(f"\n💲 Getting renewal price for: '{name}'")
    
    tx_type = invoke_contract("get_renew_price", [string_param(name)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def withdraw_fees(broadcast: bool = True):
    """Withdraw accumulated fees (owner only)"""
    print(f"\n💰 Withdrawing accumulated fees")
    
    tx_type = invoke_contract("withdraw")
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def set_fees(short_reg: float, short_renew: float, normal_reg: float, normal_renew: float, broadcast: bool = True):
    """Set all fees at once (owner only)"""
    print(f"\n⚙️ Setting fees:")
    print(f"   Short name (3-4 chars) registration: {short_reg} XEL")
    print(f"   Short name renewal: {short_renew} XEL")
    print(f"   Normal name (5+ chars) registration: {normal_reg} XEL")
    print(f"   Normal name renewal: {normal_renew} XEL")
    
    tx_type = invoke_contract("set_fees", [
        u64_param(int(short_reg * ATOMIC_UNIT)),
        u64_param(int(short_renew * ATOMIC_UNIT)),
        u64_param(int(normal_reg * ATOMIC_UNIT)),
        u64_param(int(normal_renew * ATOMIC_UNIT)),
    ])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

def transfer_contract_ownership(new_owner: str, broadcast: bool = True):
    """Transfer contract ownership (owner only)"""
    print(f"\n👑 Transferring contract ownership")
    print(f"   New owner: {new_owner}")
    
    tx_type = invoke_contract("transfer_ownership", [address_param(new_owner)])
    result = build_and_broadcast_tx(tx_type, broadcast)
    
    if result:
        print(f"✅ Transaction submitted!")
        print(f"   TX Hash: {result.get('hash', 'N/A')}")
        return result
    return None

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_wallet_status():
    """Get wallet status"""
    print("\n📊 Wallet Status:")
    result = rpc_call("get_address")
    if result:
        print(f"   Address: {result}")
    
    result = rpc_call("get_balance")
    if result is not None:
        if isinstance(result, dict):
            balance = result.get("balance", 0) / ATOMIC_UNIT
        else:
            balance = result / ATOMIC_UNIT
        print(f"   Balance: {balance:.8f} XEL")
    
    return result

def show_contract_info():
    """Show contract information"""
    print("\n📋 XNS v2.1 Contract Info:")
    print(f"   Contract Address: {CONTRACT_ADDRESS}")
    print(f"\n   Pricing Tiers:")
    print(f"   ┌─────────────────┬──────────────┬─────────────┐")
    print(f"   │ Name Length     │ Registration │ Renewal     │")
    print(f"   ├─────────────────┼──────────────┼─────────────┤")
    print(f"   │ Short (3-4)     │ {FEE_SHORT_REG/ATOMIC_UNIT:>10} XEL │ {FEE_SHORT_RENEW/ATOMIC_UNIT:>9} XEL │")
    print(f"   │ Normal (5+)     │ {FEE_NORMAL_REG/ATOMIC_UNIT:>10} XEL │ {FEE_NORMAL_RENEW/ATOMIC_UNIT:>9} XEL │")
    print(f"   └─────────────────┴──────────────┴─────────────┘")
    print(f"\n   Features:")
    print(f"   • Grace period: 30 days for renewals")
    print(f"   • Owner/Target separation for cold wallet support")
    print(f"   • Overpayment refunds")

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="XNS Client v2.1 - Interact with XELIS Name Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python xns_client.py status                    # Check wallet status
  python xns_client.py info                      # Show contract info
  python xns_client.py check alice               # Check if 'alice' is available
  python xns_client.py register alice            # Register 'alice' (10 XEL for 5+ chars)
  python xns_client.py register bob              # Register 'bob' (50 XEL for 3-4 chars)
  python xns_client.py renew alice               # Renew 'alice'
  python xns_client.py resolve alice             # Check if 'alice' is valid
  python xns_client.py set-target alice xet:...  # Point 'alice' to different wallet
  python xns_client.py transfer alice xet:...    # Transfer ownership (resets target)
  python xns_client.py get-price alice           # Get registration price
  python xns_client.py withdraw                  # Withdraw fees (owner only)
  python xns_client.py set-fees 50 20 10 5       # Set fees (owner only)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status command
    subparsers.add_parser("status", help="Check wallet status")
    
    # Info command
    subparsers.add_parser("info", help="Show contract info")
    
    # Check available command
    check_parser = subparsers.add_parser("check", help="Check if name is available")
    check_parser.add_argument("name", help="Name to check")
    
    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new name")
    register_parser.add_argument("name", help="Name to register")
    
    # Renew command
    renew_parser = subparsers.add_parser("renew", help="Renew an existing name")
    renew_parser.add_argument("name", help="Name to renew")
    
    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a name")
    resolve_parser.add_argument("name", help="Name to resolve")
    
    # Set target command (NEW in v2.1)
    target_parser = subparsers.add_parser("set-target", help="Set target address for a name")
    target_parser.add_argument("name", help="Name to update")
    target_parser.add_argument("target", help="Target address")
    
    # Transfer name command
    transfer_parser = subparsers.add_parser("transfer", help="Transfer name ownership")
    transfer_parser.add_argument("name", help="Name to transfer")
    transfer_parser.add_argument("new_owner", help="New owner address")
    
    # Get price command (NEW in v2.1)
    price_parser = subparsers.add_parser("get-price", help="Get registration price for a name")
    price_parser.add_argument("name", help="Name to check price")
    
    # Get renew price command (NEW in v2.1)
    renew_price_parser = subparsers.add_parser("get-renew-price", help="Get renewal price for a name")
    renew_price_parser.add_argument("name", help="Name to check price")
    
    # Withdraw command (owner only)
    subparsers.add_parser("withdraw", help="Withdraw accumulated fees (owner only)")
    
    # Set fees command (NEW in v2.1 - replaces set-reg-fee and set-renew-fee)
    fees_parser = subparsers.add_parser("set-fees", help="Set all fees (owner only)")
    fees_parser.add_argument("short_reg", type=float, help="Short name registration fee (XEL)")
    fees_parser.add_argument("short_renew", type=float, help="Short name renewal fee (XEL)")
    fees_parser.add_argument("normal_reg", type=float, help="Normal name registration fee (XEL)")
    fees_parser.add_argument("normal_renew", type=float, help="Normal name renewal fee (XEL)")
    
    # Transfer ownership (owner only)
    ownership_parser = subparsers.add_parser("transfer-ownership", help="Transfer contract ownership (owner only)")
    ownership_parser.add_argument("new_owner", help="New owner address")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("=" * 60)
    print("🏷️  XNS Client v2.1 - XELIS Name Service")
    print("=" * 60)
    
    if args.command == "status":
        get_wallet_status()
    elif args.command == "info":
        show_contract_info()
    elif args.command == "check":
        check_available(args.name)
    elif args.command == "register":
        register_name(args.name)
    elif args.command == "renew":
        renew_name(args.name)
    elif args.command == "resolve":
        resolve_name(args.name)
    elif args.command == "set-target":
        set_target(args.name, args.target)
    elif args.command == "transfer":
        transfer_name(args.name, args.new_owner)
    elif args.command == "get-price":
        get_price(args.name)
    elif args.command == "get-renew-price":
        get_renew_price(args.name)
    elif args.command == "withdraw":
        withdraw_fees()
    elif args.command == "set-fees":
        set_fees(args.short_reg, args.short_renew, args.normal_reg, args.normal_renew)
    elif args.command == "transfer-ownership":
        transfer_contract_ownership(args.new_owner)
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
