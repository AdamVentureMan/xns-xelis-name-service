// XNS Contract Interaction
// Simple parameter passing - xswd.js handles ValueCell formatting
console.log('[XNS UI] Loaded updated xns-contract.js');

const CONTRACT_ADDRESS = "eb7a0d88c570da29201f26d29896a9b6e604c5ea9259b596cea1e9763bb6f097";
const XEL_ASSET = "0000000000000000000000000000000000000000000000000000000000000000";
const ATOMIC_UNIT = 100000000;

// Entry function IDs (from deployed contract chunk IDs)
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

    // Register a name (costs 10 XEL for 5+ chars, 50 XEL for 3-4 chars)
    async register(name) {
        const isShort = name.length >= 3 && name.length <= 4;
        const price = isShort ? 50 * ATOMIC_UNIT : 10 * ATOMIC_UNIT;
        
        const deposits = {};
        deposits[XEL_ASSET] = { amount: price };
        
        return this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.register,
            [name],  // Just pass the name string
            deposits,
            100000000
        );
    }

    // Renew a name
    async renew(name) {
        const isShort = name.length >= 3 && name.length <= 4;
        const price = isShort ? 20 * ATOMIC_UNIT : 5 * ATOMIC_UNIT;
        
        const deposits = {};
        deposits[XEL_ASSET] = { amount: price };
        
        return this.xswd.invokeContract(
            CONTRACT_ADDRESS,
            ENTRY_IDS.renew,
            [name],
            deposits,
            100000000
        );
    }

    // Format atomic units to XEL
    formatXEL(atomicUnits) {
        return (atomicUnits / ATOMIC_UNIT).toFixed(8);
    }
}

// Export
window.XNSContract = XNSContract;
window.CONTRACT_ADDRESS = CONTRACT_ADDRESS;

