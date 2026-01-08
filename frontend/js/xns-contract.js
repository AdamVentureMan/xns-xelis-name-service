// XNS Contract Interaction
// Handles all contract function calls and serialization

const CONTRACT_ADDRESS = "eb7a0d88c570da29201f26d29896a9b6e604c5ea9259b596cea1e9763bb6f097";
const XEL_ASSET = "0000000000000000000000000000000000000000000000000000000000000000";
const ATOMIC_UNIT = 100000000;

// Entry function IDs (from contract)
const ENTRY_IDS = {
    register: 25,
    renew: 26,
    transfer_name: 27,
    set_target: 28,
    check_available: 29,
    resolve: 30,
    get_price: 31,
    get_renew_price: 32,
    withdraw: 33,
    set_fees: 34,
    transfer_ownership: 35
};

class XNSContract {
    constructor(xswdClient) {
        this.xswd = xswdClient;
    }

    // Serialize string to bytes (UTF-8)
    serializeString(str) {
        const encoder = new TextEncoder();
        return Array.from(encoder.encode(str));
    }

    // Serialize u64 to little-endian bytes
    serializeU64(value) {
        const bytes = [];
        for (let i = 0; i < 8; i++) {
            bytes.push(value & 0xff);
            value = value >>> 8;
        }
        return bytes;
    }

    // Serialize arguments for contract call
    serializeArgs(entryId, args) {
        // Format: [entry_id (u8), arg_count (u8), ...args]
        const serialized = [entryId];
        serialized.push(args.length);
        
        for (const arg of args) {
            if (typeof arg === 'string') {
                const strBytes = this.serializeString(arg);
                serialized.push(strBytes.length);
                serialized.push(...strBytes);
            } else if (typeof arg === 'number') {
                serialized.push(...this.serializeU64(arg));
            }
        }
        
        return serialized;
    }

    // Check if name is available
    async checkAvailable(name) {
        const args = this.serializeArgs(ENTRY_IDS.check_available, [name]);
        const result = await this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.check_available,
            args
        );
        return result;
    }

    // Get registration price
    async getPrice(name) {
        const args = this.serializeArgs(ENTRY_IDS.get_price, [name]);
        const result = await this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.get_price,
            args
        );
        return result;
    }

    // Register a name
    async register(name, targetAddress = null) {
        const isShort = name.length >= 3 && name.length <= 4;
        const price = isShort ? 50 * ATOMIC_UNIT : 10 * ATOMIC_UNIT;
        
        const args = this.serializeArgs(ENTRY_IDS.register, [name]);
        const deposits = {};
        deposits[XEL_ASSET] = { amount: price };
        
        const result = await this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.register,
            args,
            deposits,
            100000000 // max_gas
        );
        return result;
    }

    // Resolve a name to address
    async resolve(name) {
        const args = this.serializeArgs(ENTRY_IDS.resolve, [name]);
        const result = await this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.resolve,
            args
        );
        return result;
    }

    // Renew a name
    async renew(name) {
        const isShort = name.length >= 3 && name.length <= 4;
        const price = isShort ? 20 * ATOMIC_UNIT : 5 * ATOMIC_UNIT;
        
        const args = this.serializeArgs(ENTRY_IDS.renew, [name]);
        const deposits = {};
        deposits[XEL_ASSET] = { amount: price };
        
        const result = await this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.renew,
            args,
            deposits,
            100000000
        );
        return result;
    }

    // Format atomic units to XEL
    formatXEL(atomicUnits) {
        return (atomicUnits / ATOMIC_UNIT).toFixed(8);
    }
}

// Export
window.XNSContract = XNSContract;
window.CONTRACT_ADDRESS = CONTRACT_ADDRESS;

