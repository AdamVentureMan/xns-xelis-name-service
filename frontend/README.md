# XNS Frontend

Web-based dApp for XELIS Name Service.

## Features

- Connect to XELIS wallet via XSWD
- Search and check name availability
- Register new names
- Resolve names to addresses
- View wallet balance

## Setup

1. Make sure XELIS wallet is running
2. Enable XSWD in wallet (should be enabled by default)
3. Open `index.html` in a web browser

## Deployment

### Vercel

1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel` in the frontend directory
3. Follow prompts

Or connect GitHub repo to Vercel for auto-deploy.

### Netlify

1. Install Netlify CLI: `npm i -g netlify-cli`
2. Run: `netlify deploy` in the frontend directory
3. Follow prompts

Or drag & drop the frontend folder to https://app.netlify.com/drop

## Requirements

- XELIS wallet running locally
- XSWD enabled (port 44325)
- Modern web browser with WebSocket support

