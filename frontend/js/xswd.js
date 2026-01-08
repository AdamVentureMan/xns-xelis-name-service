// XSWD (XELIS Secure WebSocket DApp) Client
// Connects to XELIS wallet via WebSocket on port 44325

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
                this.ws = new WebSocket('ws://localhost:44325/xswd');
                
                this.ws.onopen = () => {
                    console.log('XSWD: Connected');
                    this.registerApp().then(resolve).catch(reject);
                };

                this.ws.onmessage = (event) => {
                    const response = JSON.parse(event.data);
                    this.handleMessage(response);
                };

                this.ws.onerror = (error) => {
                    console.error('XSWD: Connection error', error);
                    reject(new Error('Failed to connect to XELIS wallet. Make sure the wallet is running and XSWD is enabled.'));
                };

                this.ws.onclose = () => {
                    console.log('XSWD: Disconnected');
                    this.connected = false;
                };
            } catch (error) {
                reject(error);
            }
        });
    }

    async registerApp() {
        const appData = {
            id: this.generateId(),
            name: "XNS - XELIS Name Service",
            description: "Register and manage human-readable names for XELIS addresses",
            url: window.location.origin,
            permissions: [
                "get_balance",
                "get_address",
                "invoke_contract"
            ]
        };

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('XSWD registration timeout. Please approve the connection in your wallet.'));
            }, 30000);

            const messageHandler = (event) => {
                const response = JSON.parse(event.data);
                if (response.id === null && response.result === true) {
                    clearTimeout(timeout);
                    this.ws.removeEventListener('message', messageHandler);
                    this.connected = true;
                    resolve(true);
                } else if (response.error) {
                    clearTimeout(timeout);
                    this.ws.removeEventListener('message', messageHandler);
                    reject(new Error(response.error.message || 'XSWD registration failed'));
                }
            };

            this.ws.addEventListener('message', messageHandler);
            this.ws.send(JSON.stringify(appData));
        });
    }

    async request(method, params = {}) {
        if (!this.connected) {
            throw new Error('Not connected to wallet');
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
                reject(new Error('Request timeout'));
            }, 60000);

            this.pendingRequests.set(id, { resolve, reject, timeout });

            this.ws.send(JSON.stringify(request));
        });
    }

    handleMessage(response) {
        const { id, result, error } = response;

        if (this.pendingRequests.has(id)) {
            const { resolve, reject, timeout } = this.pendingRequests.get(id);
            clearTimeout(timeout);
            this.pendingRequests.delete(id);

            if (error) {
                reject(new Error(error.message || 'RPC error'));
            } else {
                resolve(result);
            }
        }
    }

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

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.connected = false;
        }
    }

    generateId() {
        return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    }
}

// Export for use in other scripts
window.XSWDClient = XSWDClient;

