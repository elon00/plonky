# Run the shared workbench locally

## About this project

This checkout contains the shared QMoosa verification workbench. It runs a finite Conway B3/S23 simulation, experimental ML-KEM-768 key establishment and authenticated encryption. Its SDK has read-only Ethereum and Solana identity/capability probes. The ERC20 launchpad is an unaudited local/testnet reference. A shared implementation in another named repository is not a separately completed product.

## Open the local browser demo

Install Git, a stable Rust toolchain with Cargo, and Python 3.11 or newer. Open a terminal in the project folder containing Cargo.toml and app.py. For the existing flagship checkout in Git Bash or PowerShell:

```text
cd ~/qmoosa-hackathon-925/plonky
cargo build --locked
python app.py serve
```

For another checkout, replace plonky with that folder's name. If Python is installed as python3, use python3 consistently.

Wait until the terminal prints the demo URL, then open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) or [http://localhost:8765/](http://localhost:8765/). Keep the terminal running. Click Step and Run key exchange to exercise the actual Rust core. The optional RPC probe requires configuration; an unconfigured provider is not a successful live connection.

No wallet or provider key is needed for the local simulation/cryptography demonstration. First-time Cargo dependency downloads require internet access; the built core then works offline.

## Run another project at the same time

Each process needs its own port. In a second terminal, enter the second project folder and run:

```text
python app.py serve --port 8766
```

Open [http://127.0.0.1:8766/](http://127.0.0.1:8766/). Use another free port if necessary. localhost always refers to the computer where the browser is running; these addresses are not public hosting links.

## Check and stop

Use the selected port in http://127.0.0.1:PORT/api/health: [8765 health](http://127.0.0.1:8765/api/health), or [8766 health](http://127.0.0.1:8766/api/health) for the second example. Replace PORT when choosing another port. The response reports the running project and configuration. Readiness claims still require the real verification commands:

```text
python -m pip install --require-hashes -r requirements.txt
python tests/reality_check_harness.py
npm ci --ignore-scripts
npm test
forge test -vv
```

Foundry supplies forge; Node.js supplies npm. See [CI policy](CI_POLICY.md) for the complete hosted checks.

Press Ctrl+C in the serving terminal to stop it. If the browser cannot connect, check that the terminal is still running and that the selected port matches the URL. A port-in-use error means another process already owns that port; choose another rather than stopping an unrelated process. A failed build must be fixed before claiming the app is running.

## Public demo and optional server

The flagship browser deployment is [Plonky on GitHub Pages](https://elon00.github.io/plonky/). Other repository names do not imply a separately deployed site. See [deployment and recovery](DEPLOYMENT.md) for the WebAssembly build, protected Waitress server, container checks and testnet deployment requirements. The local development server binds to loopback; it is not the public production server.
