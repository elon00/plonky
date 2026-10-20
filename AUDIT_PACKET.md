# Security review packet

## Product and data boundary

The current product is a developer verification workbench. It executes deterministic Conway transitions, ephemeral cryptographic self-checks, an optional read-only testnet probe and local contract tests. It is not a messenger, wallet, custodian or token sale.

The crypto demo encrypts a fixed demonstration message using a newly generated ML-KEM shared secret, HKDF and AES-GCM. No user message or persistent private key is accepted. Peer identity, encrypted storage and account recovery are outside this product's current data flow.

## Evidence

- Pattern and concurrent-engine tests compare actual behavior to known results.
- Official NIST ACVP sample vectors are pinned by source commit and whole-file SHA-256. Selected ML-KEM-768 cases check full key generation, exact encapsulation outputs, decapsulation including implicit rejection, and key validity checks. These tests do not constitute an ACVP validation or FIPS certification.
- Secret/shared-key buffers exported to application code use explicit zeroizing wrappers. Complete compiler/process/OS memory erasure is not asserted.
- AES-GCM payload mutation must fail authentication.
- Protected-service tests cover fail-closed configuration, bearer authentication, readiness, limits, origin/host handling, input boundaries and redaction.
- The container check exercises the deployed runtime and graceful shutdown.
- Dependency checks query current OSV advisories for locked versions and fail if the query is unavailable or reports findings.
- CI action references are immutable commit hashes. Production and browser Python dependencies are hash-locked.
- The SDK's Conway outputs are compared with Rust, and RPC schema/chain checks include negative cases.
- ERC20 tests cover reserve accounting, transfers/allowances, exact payment, slippage/deadlines, refund rollback, reentrancy and randomized reserve cases.

## Threat assumptions

Static hosting serves trusted release artifacts over HTTPS. The browser/OS and cryptographic libraries remain part of the trust boundary. An attacker who replaces a published artifact or compromises a browser can undermine the demo.

A protected server's operator controls environment configuration and deployment ingress. No endpoint accepts an arbitrary destination URL from an HTTP client. TLS terminates at a reviewed reverse proxy if the server is exposed. Per-process limits are not a distributed denial-of-service defense.

The public testnet provider is an external dependency. Connection success means the configured chain-id and block-height calls succeeded at that time. It does not establish provider reliability, historical-state completeness, transaction execution or a sponsor partnership.

## Independent work still required

An independent reviewer must evaluate cryptographic integration, library internals/side channels, deployment controls and the token's economics before real user secrets or real funds are involved. Automated tests and advisory scans are not independent audits.

A real Sepolia broadcast needs the owner's funded testnet signer. Mainnet use requires a separate security/economic decision. Event rules, licensing choice, product/customer acceptance and commercial/legal review are owner decisions.
