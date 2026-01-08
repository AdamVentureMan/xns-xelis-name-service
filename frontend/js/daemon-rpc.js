// Public Daemon RPC Client
// Connects to public XELIS nodes for read-only operations
// No wallet required - anyone can query the blockchain

const TESTNET_NODES = [
    "http://74.208.251.149:8080/json_rpc",  // US testnet seed node
    "http://76.216.16.66:8080/json_rpc"      // Backup node
];

const MAINNET_NODES = [
    "http://51.210.117.23:8080/json_rpc",   // France
    "http://198.71.55.87:8080/json_rpc",    // US
    "http://162.19.249.100:8080/json_rpc"   // Germany
];

// Current network configuration
const NETWORK = "testnet";
const NODES = NETWORK === "testnet" ? TESTNET_NODES : MAINNET_NODES;

class DaemonRPC {
    constructor() {
        this.nodeIndex = 0;
        this.requestId = 0;
    }

    getCurrentNode() {
        return NODES[this.nodeIndex];
    }

    // Switch to next available node
    switchNode() {
        this.nodeIndex = (this.nodeIndex + 1) % NODES.length;
        console.log(`DaemonRPC: Switched to node ${this.getCurrentNode()}`);
    }

    // Make JSON-RPC request to daemon
    async request(method, params = {}) {
        const id = ++this.requestId;
        const payload = {
            jsonrpc: "2.0",
            id: id,
            method: method,
            params: params
        };

        let lastError = null;
        
        // Try each node
        for (let attempt = 0; attempt < NODES.length; attempt++) {
            try {
                const response = await fetch(this.getCurrentNode(), {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.error) {
                    throw new Error(data.error.message || "RPC Error");
                }

                return data.result;
            } catch (error) {
                console.warn(`DaemonRPC: Node ${this.getCurrentNode()} failed:`, error.message);
                lastError = error;
                this.switchNode();
            }
        }

        throw new Error(`All nodes failed. Last error: ${lastError?.message || "Unknown error"}`);
    }

    // Get current blockchain info
    async getInfo() {
        return this.request("get_info");
    }

    // Get contract data from storage
    async getContractData(contract, key) {
        return this.request("get_contract_data", {
            contract: contract,
            key: key
        });
    }

    // Get contract balance
    async getContractBalance(contract, asset = "0000000000000000000000000000000000000000000000000000000000000000") {
        return this.request("get_contract_balance", {
            contract: contract,
            asset: asset
        });
    }

    // Inspect contract (get metadata)
    async inspectContract(contract) {
        return this.request("inspect_contract", {
            contract: contract
        });
    }

    // Check if daemon is reachable
    async ping() {
        try {
            const info = await this.getInfo();
            return {
                connected: true,
                topoheight: info.topoheight,
                network: info.network,
                version: info.version
            };
        } catch (error) {
            return {
                connected: false,
                error: error.message
            };
        }
    }
}

// XNS-specific functions using DaemonRPC
class XNSReader {
    constructor(daemonRPC, contractAddress) {
        this.daemon = daemonRPC;
        this.contract = contractAddress;
    }

    // Encode string to hex for storage key lookup
    stringToHex(str) {
        let hex = '';
        for (let i = 0; i < str.length; i++) {
            hex += str.charCodeAt(i).toString(16).padStart(2, '0');
        }
        return hex;
    }

    // Try to resolve a name by looking up contract storage
    // Note: This requires knowing the exact storage key format
    async resolveName(name) {
        try {
            // The storage key format depends on how the contract stores data
            // Typically: "name:" + name -> owner/target address
            const key = {
                String: name
            };
            
            const result = await this.daemon.getContractData(this.contract, key);
            return result;
        } catch (error) {
            if (error.message.includes("not found") || error.message.includes("Data not found")) {
                return null; // Name not registered
            }
            throw error;
        }
    }

    // Check if name is available
    async checkAvailability(name) {
        const result = await this.resolveName(name);
        return result === null;
    }

    // Get registration price for a name
    getPrice(name) {
        const isShort = name.length >= 3 && name.length <= 4;
        return {
            atomic: isShort ? 5000000000 : 1000000000, // 50 XEL or 10 XEL
            xel: isShort ? 50 : 10
        };
    }

    // Get renewal price for a name
    getRenewalPrice(name) {
        const isShort = name.length >= 3 && name.length <= 4;
        return {
            atomic: isShort ? 2000000000 : 500000000, // 20 XEL or 5 XEL
            xel: isShort ? 20 : 5
        };
    }

    // Validate name format
    validateName(name) {
        if (!name || name.length < 3) {
            return { valid: false, error: "Name must be at least 3 characters" };
        }
        if (name.length > 32) {
            return { valid: false, error: "Name must be 32 characters or less" };
        }
        if (!/^[a-z0-9_]+$/.test(name)) {
            return { valid: false, error: "Name can only contain lowercase letters, numbers, and underscores" };
        }
        return { valid: true };
    }
}

// Export for use in other scripts
window.DaemonRPC = DaemonRPC;
window.XNSReader = XNSReader;

