# Release status and owner-dependent gates

## Engineering delivered in 0.3

- A production WSGI runtime with explicit access mode, bounded concurrency/requests, host/origin checks, readiness/liveness and redacted logs.
- A non-root container and resource-limited Compose example, with image-level validation.
- Static HTTPS deployment of the same Rust core through WebAssembly; no paid backend is needed for the flagship demo.
- Selected official NIST known-answer vectors, explicit secret-buffer zeroization and negative crypto checks.
- Hash-locked Python dependencies, immutable CI action references and current advisory checks.
- Gated build, SDK, API, contract, browser and container checks; public deployment follows successful gates.
- Backup, rollback, source-integrity checks and fleet publishing controls.
- A Sepolia-only contract deployment script and operator/audit documentation.

See the actual release and CI evidence for which checks have executed on the current commit. Configuration alone is not a passing result.

## Owner-dependent items

1. A funded testnet signer is needed for an actual Sepolia contract broadcast. The workbench itself requires no wallet.
2. Independent cryptography/application/contract and economic review is required before protecting real user data or handling real funds.
3. The owner must provide each event's deadline, reuse/eligibility rules and judging/sponsor requirements before submission fit can be checked.
4. Licensing, customer acceptance, commercial/legal review and operational ownership need explicit decisions.

## Scope

This is one shared developer workbench distributed across repositories. Each directory name is not a separate finished product. Raven/REA, x402 and ML-DSA are not implemented or claimed.

The current crypto feature is ephemeral in-process/browser verification, not an authenticated messaging transport. There is no persistent secret storage or account system. If the product expands to those uses, its protocol and key lifecycle must be designed and reviewed first.
