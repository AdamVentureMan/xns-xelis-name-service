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
    
    try {
        const ping = await daemonRPC.ping();
        if (ping.connected) {
            statusBadge.className = 'status-badge status-public';
            statusText.textContent = `Public Mode - ${ping.network} (Height: ${ping.topoheight})`;
        } else {
            statusBadge.className = 'status-badge status-offline';
            statusText.textContent = 'Offline - Cannot connect to network';
        }
    } catch (error) {
        statusBadge.className = 'status-badge status-offline';
        statusText.textContent = 'Offline - Network error';
    }
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
            errorMsg = 'Cannot connect to XELIS wallet. Make sure your wallet is running and XSWD is enabled (run: start_xswd_server)';
        }

        showResult('availability-result', 'error', errorMsg);
        connectBtn.disabled = false;
        connectBtn.textContent = 'Connect Wallet';
    }
}

// Check name availability (public - no wallet needed)
async function checkAvailability() {
    const nameInput = document.getElementById('name-input');
    const checkBtn = document.getElementById('check-btn');
    const registerSection = document.getElementById('register-section');
    const registerName = document.getElementById('register-name');
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

        // Use public daemon to check (doesn't require wallet)
        const isAvailable = await xnsReader.checkAvailability(name);
        const price = xnsReader.getPrice(name);

        if (isAvailable) {
            showResult('availability-result', 'success', 
                `"${name}" is available! Price: ${price.xel} XEL`);
            
            // Show register section
            registerName.value = name;
            registerPrice.textContent = `${price.xel} XEL`;
            registerSection.classList.remove('hidden');

            if (!walletConnected) {
                showResult('register-result', 'info', 
                    'Connect your wallet to register this name.');
            }
        } else {
            showResult('availability-result', 'error', 
                `"${name}" is already taken.`);
            registerSection.classList.add('hidden');
        }

    } catch (error) {
        console.error('Check availability error:', error);
        
        // If public node fails, show helpful message
        if (error.message.includes('CORS') || error.message.includes('Failed to fetch')) {
            showResult('availability-result', 'error', 
                'Cannot reach network. Connect your wallet to check availability.');
        } else {
            showResult('availability-result', 'error', `Error: ${error.message}`);
        }
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

        showResult('register-result', 'success', 
            `Name "${name}" registered! Transaction: ${truncateHash(result)}`);

        // Clear form
        document.getElementById('name-input').value = '';
        document.getElementById('register-section').classList.add('hidden');

    } catch (error) {
        console.error('Register error:', error);
        showResult('register-result', 'error', `Registration failed: ${error.message}`);
    } finally {
        registerBtn.disabled = false;
        registerBtn.textContent = 'Register Name';
    }
}

// Resolve name (public - no wallet needed)
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

    try {
        resolveBtn.disabled = true;
        resolveBtn.textContent = 'Resolving...';
        showResult('resolve-result', 'info', `Resolving "${name}"...`);

        const result = await xnsReader.resolveName(name);

        if (result) {
            showResult('resolve-result', 'success', 
                `"${name}" resolves to: ${result.target || result.owner || JSON.stringify(result)}`);
        } else {
            showResult('resolve-result', 'error', 
                `"${name}" is not registered.`);
        }

    } catch (error) {
        console.error('Resolve error:', error);
        
        if (error.message.includes('CORS') || error.message.includes('Failed to fetch')) {
            showResult('resolve-result', 'error', 
                'Cannot reach network. Try connecting your wallet.');
        } else if (error.message.includes('not found')) {
            showResult('resolve-result', 'error', `"${name}" is not registered.`);
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
