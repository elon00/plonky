# Implemented architecture: shared core 0.3

The root Cargo executable delegates to qmoosa-core. Every repository contains the same core and lockfiles. project.json changes the display name, not protocol behavior.

The static deployment runs qmoosa-core in browser WebAssembly and uses a public Sepolia endpoint only on an explicit RPC probe. Optional server deployments use service.py and Waitress with access controls, limits, readiness and redacted logs. app.py remains a loopback development host.

## Data flow

Local browser -> Python loopback host -> Rust CLI -> Conway / ML-KEM-HKDF-AES-GCM.
An explicit browser or CLI RPC probe goes from Python to the configured EVM endpoint.
Forge tests independently exercise the ERC20 reference contract.

## Conway

The u64 board maps bit (8*y+x) to cell (x,y). Outside the 8x8 board is dead. A living cell survives with two or three neighbors; a dead one becomes alive with three. Requests are bounded to 10,000 steps.

## Cryptographic demonstration

Fresh OS-random ML-KEM-768 keypairs establish matching sender/receiver secrets. Mutating the KEM ciphertext changes the decapsulated secret through implicit rejection. HKDF-SHA256 binds the payload key to the KEM ciphertext and a versioned label. AES-256-GCM uses a fresh random nonce and versioned associated data; payload mutation must fail authentication.

Private keys, shared secrets and payload keys are never returned in JSON. Results contain lengths, boolean checks and a ciphertext digest. This is an ephemeral in-process demonstration, not an authenticated transport or a FIPS-validated module.

## Local host and RPC

The Python standard-library development host binds only to 127.0.0.1. It serves fixed static routes, checks Host/Origin, adds restrictive response headers and calls the CLI with argument lists, a 20-second timeout and at most four simultaneous core executions. It is not a production multi-user runtime.

The RPC endpoint comes only from server configuration. Calls enforce HTTPS except on loopback, disable redirects, verify response ids/hex quantities, limit response size and time out. An optional expected chain id prevents silently using the wrong network. A connection result requires both eth_chainId and eth_blockNumber to succeed. URL credentials and provider error bodies are excluded from results.

## Contract accounting

The capped ERC20 has zero decimals. Its reserve function sums prices of all outstanding whole units. Purchases and redemptions use differences of that function. Exact payment, slippage bounds, deadlines, burn-before-refund, rollback on failed refund and a reentrancy guard are implemented. Transfers preserve total reserve liability. Tests exercise these behaviors and randomized reserve conservation; tests are not an audit or economic review.

## Fleet updates

Inventory records content hashes. Apply rechecks them, writes backups and a restore journal, then atomically replaces only explicit managed files. Existing .git metadata, .env and unrelated files are not targeted. A local .qmoosa-release.json records release hashes and the journal path.

Verification compares managed contents against the source and can build/run each repository. Separate worker caches prevent a Cargo output race between building and executing. Rollback refuses to replace newer user edits. GitHub publication is a separate operation.

## Evidence boundaries

Local tests, mocked RPC tests, live provider connectivity, hosted CI and independent audits are different evidence sources. None can be inferred from another. Raven/REA, x402, ML-DSA and chain-specific applications are not implemented.
