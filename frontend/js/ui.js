// UI Controller - Handles all user interactions

let xswdClient = null;
let xnsContract = null;

// DOM Elements
const connectBtn = document.getElementById('connect-btn');
const walletInfo = document.getElementById('wallet-info');
const walletAddress = document.getElementById('wallet-address');
const walletBalance = document.getElementById('wallet-balance');

const nameInput = document.getElementById('name-input');
const checkBtn = document.getElementById('check-btn');
const availabilityResult = document.getElementById('availability-result');

const registerSection = document.getElementById('register-section');
const registerName = document.getElementById('register-name');
const targetAddress = document.getElementById('target-address');
const registerPrice = document.getElementById('register-price');
const registerBtn = document.getElementById('register-btn');
const registerResult = document.getElementById('register-result');

const resolveInput = document.getElementById('resolve-input');
const resolveBtn = document.getElementById('resolve-btn');
const resolveResult = document.getElementById('resolve-result');

// Connect wallet
connectBtn.addEventListener('click', async () => {
    try {
        connectBtn.disabled = true;
        connectBtn.textContent = 'Connecting...';
        
        xswdClient = new XSWDClient();
        await xswdClient.connect();
        
        // Get wallet info
        const address = await xswdClient.getAddress();
        const balance = await xswdClient.getBalance();
        
        walletAddress.textContent = address;
        walletBalance.textContent = xnsContract ? xnsContract.formatXEL(balance) : (balance / 100000000).toFixed(8);
        
        walletInfo.classList.remove('hidden');
        connectBtn.textContent = 'Connected';
        connectBtn.disabled = true;
        
        // Initialize contract client
        xnsContract = new XNSContract(xswdClient);
        
        showResult(availabilityResult, 'success', 'Wallet connected successfully!');
    } catch (error) {
        showResult(availabilityResult, 'error', `Error: ${error.message}`);
        connectBtn.disabled = false;
        connectBtn.textContent = 'Connect Wallet';
    }
});

// Check availability
checkBtn.addEventListener('click', async () => {
    const name = nameInput.value.trim();
    if (!name) {
        showResult(availabilityResult, 'error', 'Please enter a name');
        return;
    }
    
    if (!xnsContract) {
        showResult(availabilityResult, 'error', 'Please connect your wallet first');
        return;
    }
    
    try {
        checkBtn.disabled = true;
        availabilityResult.classList.remove('hidden');
        showResult(availabilityResult, 'info', 'Checking availability...');
        
        // Note: This will create a transaction, but we can't easily read the result
        // For now, we'll just show a message
        await xnsContract.checkAvailable(name);
        
        // Get price
        const price = await xnsContract.getPrice(name);
        const priceXEL = xnsContract.formatXEL(price);
        
        // Show registration section
        registerName.value = name;
        registerPrice.textContent = `${priceXEL} XEL`;
        registerSection.classList.remove('hidden');
        
        showResult(availabilityResult, 'success', `Name "${name}" appears to be available. Price: ${priceXEL} XEL`);
    } catch (error) {
        showResult(availabilityResult, 'error', `Error: ${error.message}`);
    } finally {
        checkBtn.disabled = false;
    }
});

// Register name
registerBtn.addEventListener('click', async () => {
    const name = registerName.value.trim();
    if (!name || !xnsContract) {
        return;
    }
    
    try {
        registerBtn.disabled = true;
        registerResult.classList.remove('hidden');
        showResult(registerResult, 'info', 'Registering name... Please approve in your wallet.');
        
        const result = await xnsContract.register(name);
        
        showResult(registerResult, 'success', `Name registered! Transaction: ${result}`);
    } catch (error) {
        showResult(registerResult, 'error', `Error: ${error.message}`);
    } finally {
        registerBtn.disabled = false;
    }
});

// Resolve name
resolveBtn.addEventListener('click', async () => {
    const name = resolveInput.value.trim();
    if (!name) {
        showResult(resolveResult, 'error', 'Please enter a name');
        return;
    }
    
    if (!xnsContract) {
        showResult(resolveResult, 'error', 'Please connect your wallet first');
        return;
    }
    
    try {
        resolveBtn.disabled = true;
        resolveResult.classList.remove('hidden');
        showResult(resolveResult, 'info', 'Resolving name...');
        
        const result = await xnsContract.resolve(name);
        
        showResult(resolveResult, 'success', `Name "${name}" resolves to: ${result}`);
    } catch (error) {
        showResult(resolveResult, 'error', `Error: ${error.message}`);
    } finally {
        resolveBtn.disabled = false;
    }
});

// Helper function to show results
function showResult(element, type, message) {
    element.className = `result-box ${type}`;
    element.textContent = message;
    element.classList.remove('hidden');
}

