# Flagship demo: plonky

## Prepare

1. Install test dependencies with python -m pip install --require-hashes -r requirements.txt, then run cargo build --locked and python tests/reality_check_harness.py.
2. For the contract reference, run npm ci --ignore-scripts and forge test -vv.
3. Optionally configure your own EVM endpoint in .env and run python app.py rpc. Keep credentials out of screenshots.
4. Run python app.py serve and open http://127.0.0.1:8765.
5. Test once offline after dependencies have been built.

## Three-minute script

0:00–0:30 — Explain the problem: developers need inspectable execution evidence behind cryptographic and integration claims. State that this is a shared prototype core.

0:30–1:00 — Step the blinker twice: it returns to the original state. Show the glider moving after four generations. Explain finite boundaries.

1:00–1:45 — Run key exchange. Explain ML-KEM shared-secret agreement, HKDF and AES-GCM. Show the KEM mutation and payload tampering checks. Run again to show a fresh ciphertext digest.

1:45–2:15 — Optionally probe the actual configured endpoint and show chain id and block height. If unconfigured, say so and continue the offline demo.

2:15–2:45 — Download the JSON evidence. Show real tests, including reserve conservation and malicious reentrancy if contracts are relevant.

2:45–3:00 — Describe the specific customer workflow and next acceptance criterion once judging requirements are known. State the prototype boundary.

## Submission materials

Include the flagship repository and release commit once published, a short screen recording, genuine verification output, hosted CI link after execution, architecture and an implemented-capability list. Map the work to event criteria when available.

Do not claim novelty, commercial traction, security certification, or 925 different products from this shared implementation. Check every event's eligibility and reuse rules.
