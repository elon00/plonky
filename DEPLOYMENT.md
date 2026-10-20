# Deployment and recovery

## Public demo: GitHub Pages

The browser deployment runs the same Rust qmoosa-core through qmoosa-wasm. Conway, key exchange, encryption and tampering checks execute locally in the visitor's browser. Only the explicit Sepolia probe contacts the public RPC provider. No backend account, wallet, funds, private API key or application database is needed.

Expected flagship URL: https://elon00.github.io/plonky/

The deploy job runs only for the flagship after the core, contract, dependency, container and browser jobs succeed. It publishes the generated site directory; it does not publish .env files or backend credentials.

Build locally:

    npm ci --ignore-scripts
    python tools/build_web.py --install-tools
    python -m pip install --require-hashes -r requirements-browser.txt
    python -m playwright install chromium
    python tools/web_check.py --live-rpc

The build tool derives the exact wasm-bindgen CLI version from Cargo.lock. First-time compilation can take several minutes. requirements-browser.txt hash-locks browser-test packages. The static artifact contains a CSP that permits its own WebAssembly and the explicitly configured public testnet endpoint.

Rollback the public demo by reverting the release commit through a pull request and waiting for the same CI/deploy gates, or by preparing a pull request that restores a previously reviewed release. Record the release SHA and deployed URL.

## Optional protected server

This option is for an operator who chooses to host a server. GitHub Pages does not need it.

    python -m venv .venv
    .venv/Scripts/python -m pip install --require-hashes -r requirements.txt

Use .venv/bin/python on Unix. Build the core with cargo build --locked. Set QMOOSA_ACCESS_TOKEN to a securely generated value of at least 32 characters and QMOOSA_ALLOWED_HOSTS to explicit hostnames. Run service.py inside that environment. QMOOSA_PUBLIC_DEMO=false is the default; invalid protected configuration fails startup.

The browser accepts the access token in a password field and keeps it in tab memory. Tokens do not enter URLs, cookies, browser persistent storage or the exported execution evidence. This is a shared operator token, not a user-account system.

For containers, copy .env.production.example to .env.production, supply your token, then:

    docker compose -f deploy/compose.yml up --build -d

The sample publishes only to loopback. A public server needs an HTTPS reverse proxy and firewall configuration appropriate to the actual hosting environment. Do not trust arbitrary forwarded headers. The service uses REMOTE_ADDR for conservative single-instance limits; clients behind one proxy may share a limit.

The container runs as a non-root user with a read-only root filesystem, dropped capabilities, bounded process count and memory/CPU limits in Compose. Its core is prebuilt; startup performs real core self-checks. /healthz is liveness and /readyz is readiness. Neither endpoint exposes credentials.

Validate the image:

    docker build -t qmoosa:local .
    python tools/container_check.py --image qmoosa:local

The test creates and removes only its own labeled container. It checks authentication, actual cryptographic execution, bounded concurrent work and graceful shutdown. It is not an independent penetration test.

## Sepolia contract

The deployment script refuses mainnet and permits only Sepolia (11155111) or a local chain (31337). No public contract deployment is claimed without a transaction receipt.

Preview the script with a local test chain or Foundry simulation. A real Sepolia broadcast requires your own funded testnet wallet and an appropriate RPC. Use an encrypted Foundry account or hardware wallet; keep signing keys out of chat, source code and command-line arguments.

    forge script script/DeployLaunchpad.s.sol:DeployLaunchpad --rpc-url YOUR_SEPOLIA_RPC --account YOUR_ENCRYPTED_ACCOUNT --broadcast

Review the chain id, sender, gas and deployment transaction before signing. Save and verify the resulting receipt/address and deployed bytecode. No mainnet funds are needed for the workbench. The token remains unaudited.

## Runtime operations

Logs contain route labels, response status, duration and request ids. They exclude tokens, query strings, request bodies, endpoint URLs and provider error bodies. Configure retention and monitoring on the chosen platform.

For a server deployment, monitor readiness, 5xx, 429 and busy responses, request latency and process memory. Set provider quotas and access-token rotation procedures. Public Pages has client-side compute; its availability and delivery are provided by GitHub Pages and external RPC availability is a separate state.

The rate limiter is in process and intended for a single instance. A multi-instance service needs a shared limiter and a reviewed ingress identity policy. Load-check results describe only the actual test machine/configuration, not a production SLA.
