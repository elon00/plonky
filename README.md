# QMoosa verification workbench

See [blockchain upgrade compatibility](CHAIN_UPGRADES.md) for the current Glamsterdam and Alpenglow integration, commands and verification limits.

## About

A local demo of Conway B3/S23, ML-KEM-768 key establishment, authenticated payload encryption and an optional EVM RPC probe.

**Status: deployable developer workbench; independent review and owner acceptance remain.** This is one shared implementation distributed to multiple repositories. Repository names do not make separate products or separate chain integrations. See [PRODUCTION_GAPS.md](PRODUCTION_GAPS.md).

## Public browser demo

The flagship deploys to https://elon00.github.io/plonky/ after its CI gates pass. The same Rust core runs in the browser through WebAssembly; no backend account is required. The explicit RPC probe uses public Sepolia infrastructure. See DEPLOYMENT.md for build, hosting, protected-server and rollback instructions.

## Start locally

[Open localhost:8765](http://localhost:8765/) after starting the server. Follow the [step-by-step local guide](LOCAL_DEVELOPMENT.md) for setup, another port, health checks and shutdown.

Install a current stable Rust toolchain with Cargo and Python 3.11 or newer.

    cargo build --locked
    python app.py serve

Open **http://127.0.0.1:8765**. Click Step, Run key exchange and optionally Probe endpoint. After the first Cargo build, the core demo works offline without credentials, wallets or Python package installation. If the port is busy, use python app.py serve --port 8766.

## Implemented behavior

| Capability | Actual behavior | Boundary |
| --- | --- | --- |
| Conway | Finite 8x8 B3/S23 transitions | Simulation, not cryptography |
| ML-KEM-768 | OS-random key generation, encapsulation, decapsulation and mutated ciphertext check | Ephemeral native/browser self-check; no peer authentication |
| Encryption | HKDF-SHA256 and AES-256-GCM roundtrip plus tamper rejection | Ephemeral keys; no deployed transport |
| EVM RPC | eth_chainId and eth_blockNumber over HTTP JSON-RPC | One configured endpoint; read-only |
| Contract | OpenZeppelin ERC20 and redeemable linear discrete bonding curve | Unaudited local/testnet reference |
| Agents, ML-DSA, x402 | Not implemented | No passing claims made |

## Verify

    python -m pip install --require-hashes -r requirements.txt
    python tests/reality_check_harness.py

This runs the Rust suite, real CLI and Python API/RPC integration tests. RPC tests use a local mock server, which does not establish live provider connectivity.

For the complete checks, also install Node.js and Foundry:

    python tools/verify.py

This adds formatting, Clippy, JavaScript syntax, locked OpenZeppelin installation and Forge tests including randomized reserve checks. A failed check or missing tool returns a nonzero exit code. Evidence goes to reports/verification.json.

## Optional live RPC

Copy .env.example to .env. Set QMOOSA_RPC_URL to your own HTTPS EVM endpoint. Optionally set QMOOSA_EXPECTED_CHAIN_ID; for Sepolia it is 11155111. Restart after changing .env.

    python app.py rpc
    python tools/verify.py --live-rpc

Without configuration, the state is not_configured. URLs and provider error bodies are excluded from browser results. Redirects are refused. HTTP is allowed only for loopback development endpoints. No transactions are sent.

## TypeScript SDK and runtime

The SDK uses the correctly spelled quickNodeRpcUrl configuration, real finite Conway rules and validated read-only RPC. The Rust atomic engine delegates to the core and advances safely under concurrent calls. Both are compiled by the release checks.

    npm ci --ignore-scripts
    npm test

SDK tests compare TypeScript against Rust on varied 64-bit boards. The old fake x402-header generator has been removed.

## Contract reference

    npm ci --ignore-scripts
    forge test -vv

The token uses zero decimals, whole units and a supply cap of 1,000,000. Price of the next unit at supply S is BASE_PRICE + PRICE_STEP*S. Reserve R(S) = BASE_PRICE*S + PRICE_STEP*S*(S-1)/2. Buying costs R(S+n)-R(S); selling refunds R(S)-R(S-n).

buy(amount,maxCost,deadline) requires exact payment. sell(amount,minRefund,deadline) burns before refund and rolls back if payment fails. Both enforce slippage and deadlines. Standard ERC20 transfers/allowances are inherited. No administrator can withdraw the reserve. Independent review is required before real funds.

## One master for all repositories

Use plonky as the canonical source. Edit and test there, inventory the fleet, inspect the inventory, apply with backups, then verify:

    python tools/fleet.py inventory --root ../ --report reports/inventory.json
    python tools/fleet.py apply --root ../ --snapshot reports/inventory.json --backup-root ../../qmoosa-fleet-backups --report reports/apply.json
    python tools/fleet.py verify --root ../ --build --workers 2 --report reports/fleet-build.json

Run from the flagship. Default fleet size is 925 Git repositories. The updater protects changes since inventory, checks paths, refuses unreviewed AGENTS.md instructions and backs up managed files before replacing them. It never commits or pushes.

For rollback, use the exact timestamped backup path printed by apply:

    python tools/fleet.py rollback --root ../ --backup-root EXACT_TIMESTAMPED_BACKUP_PATH --report reports/rollback.json

Rollback refuses to overwrite newer edits. Preserve the backup directory.

## CI and references

The [required CI policy](CI_POLICY.md) rejects failed, skipped or missing gates before deployment. Every owned checkout still needs its own passing hosted run; no portfolio completion is implied.

CI runs core checks on Ubuntu and Windows, plus Forge contract tests. CodeQL has a separate initialized Python/JavaScript workflow. Hosted workflows must actually run before claiming hosted CI success. Static passing badges and invented scores have been removed.

- [RustCrypto ML-KEM 0.3.3](https://docs.rs/ml-kem/0.3.3/ml_kem/)
- [OpenZeppelin ERC20](https://docs.openzeppelin.com/contracts/5.x/api/token/erc20)
- [QuickNode eth_chainId](https://www.quicknode.com/docs/ethereum/eth_chainId)

RustCrypto documents its ML-KEM implementation as unaudited. Implementing a FIPS algorithm is not FIPS module validation.

## Deployment and security evidence

See [DEPLOYMENT.md](DEPLOYMENT.md), [AUDIT_PACKET.md](AUDIT_PACKET.md) and [RELEASE_PLAN.md](RELEASE_PLAN.md). Official NIST sample-vector tests are included. Python runtime/browser dependencies are hash-locked and CI actions are pinned by commit. The protected service uses Waitress with explicit access mode and bounded work; the public Pages demo uses client-side computation. Source licensing and actual event/customer acceptance remain owner decisions.
