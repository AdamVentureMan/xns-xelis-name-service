// UI Controller - Handles all user interactions
// Hybrid mode: Public read operations + XSWD for write operations

// Global state
let xswdClient = null;
let xnsContract = null;
let daemonRPC = null;
let xnsReader = null;
let walletConnected = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize public daemon RPC for read operations
    daemonRPC = new DaemonRPC();
    xnsReader = new XNSReader(daemonRPC, CONTRACT_ADDRESS);
    
    // Check daemon connectivity
    updateConnectionStatus();
    
    // Set up event listeners
    setupEventListeners();
});

// Update connection status display
async function updateConnectionStatus() {
    const statusBadge = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    
    // Default to showing "connect wallet" message
    // Direct daemon RPC from browser is blocked by CORS
    statusBadge.className = 'status-badge status-offline';
    statusText.textContent = 'Connect wallet to use';
}

// Set up all event listeners
function setupEventListeners() {
    // DOM Elements
    const connectBtn = document.getElementById('connect-btn');
    const nameInput = document.getElementById('name-input');
    const checkBtn = document.getElementById('check-btn');
    const registerBtn = document.getElementById('register-btn');
    const resolveInput = document.getElementById('resolve-input');
    const resolveBtn = document.getElementById('resolve-btn');

    // Connect wallet button
    connectBtn.addEventListener('click', connectWallet);

    // Check availability (works without wallet)
    checkBtn.addEventListener('click', checkAvailability);

    // Register name (requires wallet)
    registerBtn.addEventListener('click', registerName);

    // Resolve name (works without wallet)
    resolveBtn.addEventListener('click', resolveName);

    // Input validation on typing
    nameInput.addEventListener('input', (e) => {
        const name = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
        e.target.value = name;
        
        // Show live price estimate
        if (name.length >= 3) {
            const price = xnsReader.getPrice(name);
            document.getElementById('live-price').textContent = `Estimated price: ${price.xel} XEL`;
            document.getElementById('live-price').classList.remove('hidden');
        } else {
            document.getElementById('live-price').classList.add('hidden');
        }
    });

    resolveInput.addEventListener('input', (e) => {
        e.target.value = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
    });
}

// Connect wallet via XSWD
async function connectWallet() {
    const connectBtn = document.getElementById('connect-btn');
    const walletInfo = document.getElementById('wallet-info');
    const walletAddress = document.getElementById('wallet-address');
    const walletBalance = document.getElementById('wallet-balance');
    const statusBadge = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');

    try {
        connectBtn.disabled = true;
        connectBtn.textContent = 'Connecting...';
        showResult('availability-result', 'info', 'Connecting to wallet... Please approve the connection in your XELIS wallet.');

        xswdClient = new XSWDClient();
        await xswdClient.connect();

        // Get wallet info
        const address = await xswdClient.getAddress();
        const balance = await xswdClient.getBalance();

        walletAddress.textContent = truncateAddress(address);
        walletAddress.title = address;
        walletBalance.textContent = formatXEL(balance);

        walletInfo.classList.remove('hidden');
        connectBtn.textContent = 'Connected';
        connectBtn.classList.add('btn-success');
        walletConnected = true;

        // Initialize contract client for write operations
        xnsContract = new XNSContract(xswdClient);

        // Update status
        statusBadge.className = 'status-badge status-connected';
        statusText.textContent = 'Connected - Wallet linked';

        showResult('availability-result', 'success', 'Wallet connected! You can now register names.');

        // Enable register section
        document.getElementById('register-section').classList.remove('disabled');

    } catch (error) {
        console.error('Wallet connection error:', error);
        
        let errorMsg = error.message;
        if (error.message.includes('WebSocket')) {
            errorMsg = 'Cannot connect to XELIS wallet. Make sure your wallet is running and XSWD is enabled (run: start_xswd)';
        }

        showResult('availability-result', 'error', errorMsg);
        connectBtn.disabled = false;
        connectBtn.textContent = 'Connect Wallet';
    }
}

// Check name availability
async function checkAvailability() {
    const nameInput = document.getElementById('name-input');
    const checkBtn = document.getElementById('check-btn');
    const registerSection = document.getElementById('register-section');
    const registerNameEl = document.getElementById('register-name');
    const registerPrice = document.getElementById('register-price');
    
    const name = nameInput.value.trim().toLowerCase();

    // Validate
    const validation = xnsReader.validateName(name);
    if (!validation.valid) {
        showResult('availability-result', 'error', validation.error);
        return;
    }

    try {
        checkBtn.disabled = true;
        checkBtn.textContent = 'Checking...';
        showResult('availability-result', 'info', `Checking availability for "${name}"...`);

        const price = xnsReader.getPrice(name);
        let isAvailable = true;

        // Try to check via wallet XSWD if connected (routes through daemon)
        // Contract stores names with "n:" prefix
        if (walletConnected && xswdClient) {
            try {
                // Use daemon RPC through XSWD - query with "n:" prefix
                const result = await xswdClient.request('node.get_contract_data', {
                    contract: CONTRACT_ADDRESS,
                    key: { type: "primitive", value: { type: "string", value: `n:${name}` } }
                });
                // If we got a result, the name exists (taken)
                isAvailable = false;
            } catch (e) {
                // "No data found" or "-32004" means name is available!
                if (e.message.includes('No data found') || e.message.includes('-32004') || e.message.includes('not found')) {
                    isAvailable = true;
                } else {
                    throw e;
                }
            }
        } else {
            // No wallet - show estimated price but can't verify
            showResult('availability-result', 'info', 
                `Connect your wallet to check if "${name}" is available. Estimated price: ${price.xel} XEL`);
            
            registerNameEl.value = name;
            registerPrice.textContent = `${price.xel} XEL`;
            registerSection.classList.remove('hidden');
            showResult('register-result', 'info', 
                'Connect your wallet to check availability and register.');
            return;
        }

        if (isAvailable) {
            showResult('availability-result', 'success', 
                `✓ "${name}" is available! Price: ${price.xel} XEL`);
            
            // Show register section with the name
            registerNameEl.value = name;
            registerPrice.textContent = `${price.xel} XEL`;
            registerSection.classList.remove('hidden');
            
            // Scroll to register section smoothly
            setTimeout(() => {
                registerSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        } else {
            showResult('availability-result', 'error', 
                `"${name}" is already taken.`);
            registerSection.classList.add('hidden');
        }

    } catch (error) {
        console.error('Check availability error:', error);
        showResult('availability-result', 'error', formatError(error, 'check'));
    } finally {
        checkBtn.disabled = false;
        checkBtn.textContent = 'Check Availability';
    }
}

// Register name (requires wallet)
async function registerName() {
    if (!walletConnected || !xnsContract) {
        showResult('register-result', 'error', 
            'Please connect your wallet first to register names.');
        return;
    }

    const registerBtn = document.getElementById('register-btn');
    const name = document.getElementById('register-name').value.trim();
    const targetAddress = document.getElementById('target-address').value.trim() || null;

    try {
        registerBtn.disabled = true;
        registerBtn.textContent = 'Registering...';
        showResult('register-result', 'info', 
            'Submitting registration... Please approve in your wallet.');

        const result = await xnsContract.register(name, targetAddress);
        
        // Extract tx hash from result (could be string or object)
        const txHash = typeof result === 'string' ? result : (result?.hash || result?.tx_hash || JSON.stringify(result));

        showResult('register-result', 'success', 
            `Name "${name}" registered! Transaction: ${truncateHash(txHash)}`);

        // Clear form
        document.getElementById('name-input').value = '';
        document.getElementById('register-section').classList.add('hidden');

    } catch (error) {
        console.error('Register error:', error);
        showResult('register-result', 'error', formatError(error, 'register'));
    } finally {
        registerBtn.disabled = false;
        registerBtn.textContent = 'Register Name';
    }
}

// Resolve name
async function resolveName() {
    const resolveInput = document.getElementById('resolve-input');
    const resolveBtn = document.getElementById('resolve-btn');
    const name = resolveInput.value.trim().toLowerCase();

    // Validate
    const validation = xnsReader.validateName(name);
    if (!validation.valid) {
        showResult('resolve-result', 'error', validation.error);
        return;
    }

    // Need wallet connection to query
    if (!walletConnected || !xswdClient) {
        showResult('resolve-result', 'error', 
            'Connect your wallet to resolve names.');
        return;
    }

    try {
        resolveBtn.disabled = true;
        resolveBtn.textContent = 'Resolving...';
        showResult('resolve-result', 'info', `Resolving "${name}"...`);

        // Use daemon RPC through XSWD - query with "n:" prefix
        const result = await xswdClient.request('node.get_contract_data', {
            contract: CONTRACT_ADDRESS,
            key: { type: "primitive", value: { type: "string", value: `n:${name}` } }
        });

        if (result && result.data) {
            // Parse the result - it's an object array: [owner, target, expires_at, registered_at]
            // The value is in result.data.value (array of ValueCells)
            const data = result.data;
            let targetAddress = 'Unknown';
            
            if (data.type === 'object' && Array.isArray(data.value)) {
                // Second element is target address
                const targetCell = data.value[1];
                if (targetCell?.value?.value?.value) {
                    targetAddress = targetCell.value.value.value;
                }
            }
            
            showResult('resolve-result', 'success', 
                `"${name}" resolves to: ${targetAddress}`);
        } else {
            showResult('resolve-result', 'error', 
                `"${name}" is not registered.`);
        }

    } catch (error) {
        console.error('Resolve error:', error);
        
        // "No data found" or "-32004" means name is not registered
        if (error.message.includes('No data found') || error.message.includes('-32004') || error.message.includes('not found')) {
            showResult('resolve-result', 'info', `"${name}" is not registered yet. You can register it!`);
        } else {
            showResult('resolve-result', 'error', `Error: ${error.message}`);
        }
    } finally {
        resolveBtn.disabled = false;
        resolveBtn.textContent = 'Resolve';
    }
}

// Helper: Show result message
function showResult(elementId, type, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.className = `result-box ${type}`;
        element.textContent = message;
        element.classList.remove('hidden');
    }
}

// Helper: Format atomic units to XEL
function formatXEL(atomicUnits) {
    return (atomicUnits / 100000000).toFixed(2);
}

// Helper: Truncate address for display
function truncateAddress(address) {
    if (!address || address.length < 20) return address;
    return `${address.substring(0, 12)}...${address.substring(address.length - 8)}`;
}

// Helper: Truncate hash for display
function truncateHash(hash) {
    if (!hash || hash.length < 20) return hash;
    return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
}

// Helper: Format errors to human-readable messages
function formatError(error, context = '') {
    const msg = error.message || error.toString();
    
    // Common error patterns and friendly messages
    const errorMap = {
        'No data found': 'This name is not registered yet.',
        'insufficient balance': 'Not enough XEL in your wallet. Please add more funds.',
        'Insufficient balance': 'Not enough XEL in your wallet. Please add more funds.',
        'already registered': 'This name is already taken by someone else.',
        'name too short': 'Name must be at least 3 characters long.',
        'name too long': 'Name must be 32 characters or less.',
        'invalid characters': 'Name can only contain lowercase letters, numbers, and underscores.',
        'expired': 'This name registration has expired.',
        'not owner': 'You do not own this name.',
        'Permission denied': 'You denied the transaction in your wallet.',
        'rejected': 'Transaction was rejected. Please try again.',
        'timeout': 'Request timed out. Please check your wallet and try again.',
        'WebSocket': 'Connection to wallet lost. Please reconnect.',
        'Invalid params': 'There was a technical error. Please try again or contact support.',
        'Method': 'Wallet communication error. Please reconnect.',
    };

    for (const [pattern, friendly] of Object.entries(errorMap)) {
        if (msg.includes(pattern)) {
            return friendly;
        }
    }

    // If no pattern matched, return a cleaner version
    if (msg.includes('Server returned error')) {
        return 'Server error. Please try again in a moment.';
    }

    return `Error: ${msg}`;
}
