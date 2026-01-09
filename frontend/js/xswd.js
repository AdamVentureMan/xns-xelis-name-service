// XSWD (XELIS Secure WebSocket DApp) Client
// Connects to XELIS wallet via WebSocket on port 44325
// Used for write operations that require wallet signing

class XSWDClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.requestId = 0;
        this.pendingRequests = new Map();
    }

    async connect() {
        return new Promise((resolve, reject) => {
            try {
                // Check if we're on HTTPS - warn about mixed content
                if (window.location.protocol === 'https:') {
                    console.warn('XSWD: Running on HTTPS. WebSocket connection to localhost may be blocked by browser security.');
                }

                // Try to connect to XSWD
                const wsUrl = 'ws://localhost:44325/xswd';
                console.log(`XSWD: Connecting to ${wsUrl}...`);
                
                this.ws = new WebSocket(wsUrl);
                
                // Connection timeout
                const connectionTimeout = setTimeout(() => {
                    if (this.ws.readyState !== WebSocket.OPEN) {
                        this.ws.close();
                        reject(new Error(
                    'Connection timeout. Make sure:\n' +
                    '1. XELIS wallet is running\n' +
                    '2. XSWD server is enabled (run: start_xswd in wallet)\n' +
                    '3. You are accessing this page via HTTP (not HTTPS) for local testing'
                        ));
                    }
                }, 10000);

                this.ws.onopen = () => {
                    clearTimeout(connectionTimeout);
                    console.log('XSWD: WebSocket connected, registering app...');
                    this.registerApp().then(resolve).catch(reject);
                };

                this.ws.onmessage = (event) => {
                    try {
                        const response = JSON.parse(event.data);
                        this.handleMessage(response);
                    } catch (e) {
                        console.error('XSWD: Failed to parse message:', e);
                    }
                };

                this.ws.onerror = (error) => {
                    clearTimeout(connectionTimeout);
                    console.error('XSWD: WebSocket error:', error);
                    
                    // Provide helpful error message based on context
                    let errorMsg = 'Cannot connect to XELIS wallet.';
                    
                    if (window.location.protocol === 'https:') {
                        errorMsg += '\n\nYou are on HTTPS which blocks local WebSocket connections. ' +
                                   'For testing, open this page via HTTP or run locally.';
                    } else {
                    errorMsg += '\n\nMake sure:\n' +
                               '1. XELIS wallet is running\n' +
                               '2. Run "start_xswd" in your wallet';
                    }
                    
                    reject(new Error(errorMsg));
                };

                this.ws.onclose = (event) => {
                    console.log('XSWD: WebSocket closed', event.code, event.reason);
                    this.connected = false;
                    
                    // Reject pending requests
                    for (const [id, { reject, timeout }] of this.pendingRequests) {
                        clearTimeout(timeout);
                        reject(new Error('Connection closed'));
                    }
                    this.pendingRequests.clear();
                };

            } catch (error) {
                reject(new Error(`WebSocket initialization failed: ${error.message}`));
            }
        });
    }

    async registerApp() {
        const appData = {
            id: this.generateAppId(),
            name: "XNS - XELIS Name Service",
            description: "Register and manage human-readable names for XELIS addresses",
            url: window.location.origin || "https://xns-xelis-name-service.vercel.app",
            permissions: [
                "get_balance",
                "get_address",
                "invoke_contract"
            ]
        };

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(
                    'Registration timeout. Please check your XELIS wallet and approve the connection request.'
                ));
            }, 60000); // 60 second timeout for user approval

            // One-time message handler for registration response
            const registrationHandler = (event) => {
                try {
                    const response = JSON.parse(event.data);
                    
                    // Check for successful registration
                    if (response.id === null && response.result === true) {
                        clearTimeout(timeout);
                        this.ws.removeEventListener('message', registrationHandler);
                        this.connected = true;
                        console.log('XSWD: App registered successfully');
                        resolve(true);
                        return;
                    }
                    
                    // Check for error
                    if (response.error) {
                        clearTimeout(timeout);
                        this.ws.removeEventListener('message', registrationHandler);
                        reject(new Error(response.error.message || 'Registration rejected'));
                        return;
                    }
                } catch (e) {
                    // Ignore parse errors during registration
                }
            };

            this.ws.addEventListener('message', registrationHandler);
            
            console.log('XSWD: Sending app registration...', appData);
            this.ws.send(JSON.stringify(appData));
        });
    }

    async request(method, params = {}) {
        if (!this.connected) {
            throw new Error('Not connected to wallet. Please connect first.');
        }

        if (this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket connection lost. Please reconnect.');
        }

        const id = ++this.requestId;
        const request = {
            jsonrpc: "2.0",
            id: id,
            method: method,
            params: params
        };

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error('Request timeout. The wallet may need your approval.'));
            }, 120000); // 2 minute timeout for user approval

            this.pendingRequests.set(id, { resolve, reject, timeout });

            console.log('XSWD: Sending request:', method, params);
            this.ws.send(JSON.stringify(request));
        });
    }

    handleMessage(response) {
        const { id, result, error } = response;

        // Skip registration responses (id === null)
        if (id === null) return;

        if (this.pendingRequests.has(id)) {
            const { resolve, reject, timeout } = this.pendingRequests.get(id);
            clearTimeout(timeout);
            this.pendingRequests.delete(id);

            if (error) {
                console.error('XSWD: RPC error:', error);
                reject(new Error(error.message || 'RPC error'));
            } else {
                console.log('XSWD: Response received:', result);
                resolve(result);
            }
        }
    }

    // Wallet RPC methods
    async getAddress() {
        return this.request('wallet.get_address');
    }

    async getBalance(asset = "0000000000000000000000000000000000000000000000000000000000000000") {
        return this.request('wallet.get_balance', { asset });
    }

    async invokeContract(contract, entry, args = [], deposits = {}, max_gas = 100000000) {
        return this.request('wallet.invoke_contract', {
            contract,
            entry,
            args,
            deposits,
            max_gas
        });
    }

    // Daemon RPC methods (proxied through wallet)
    async getDaemonInfo() {
        return this.request('node.get_info');
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.connected = false;
        }
    }

    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    generateAppId() {
        // Generate a 64-character hex string (required by XSWD protocol)
        // This is a deterministic ID based on the app identity
        const chars = '0123456789abcdef';
        const seed = 'xns-xelis-name-service-dapp';
        
        let result = '';
        for (let i = 0; i < 64; i++) {
            // Use seed characters to generate deterministic hex
            const seedChar = seed.charCodeAt(i % seed.length);
            const index = (seedChar + i * 7) % 16;
            result += chars[index];
        }
        
        return result;
    }
}

// Export for use in other scripts
window.XSWDClient = XSWDClient;
