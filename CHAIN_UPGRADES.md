# Blockchain upgrade compatibility

Reviewed 2026-10-21 UTC. This SDK integrates read-only capability detection and dynamic gas estimation. It does not implement or activate a chain's consensus upgrade.

Build once with `npm ci --ignore-scripts` and `npm run build`, then run:

```text
node tools/chain-upgrades.mjs --network sepolia
node tools/chain-upgrades.mjs --network solana-devnet
node tools/chain-upgrades.mjs --network solana-mainnet
```

Use `QMOOSA_RPC_URL` or `QMOOSA_SOLANA_RPC_URL` for an operator-configured endpoint. Keep private provider URLs on the server; browser bundles are public. Solana identity is checked against the pinned cluster genesis hash before querying consensus. Devnet can reset: review a changed hash against trusted cluster information before updating `QMOOSA_SOLANA_GENESIS_HASH`. Never accept a mismatched network silently.

Exit 0 means the tested capability was observed, 1 means not active/unverified, and 2 means configuration, required transport/RPC failure or an invalid Solana certificate. An unavailable optional Ethereum state-override probe leaves that capability unverified (exit 1). JSON distinguishes these results. None means complete protocol conformance, a cryptographic audit, or application release approval. Results describe one RPC provider at one time.

## Ethereum Glamsterdam

[EIP-7773](https://eips.ethereum.org/EIPS/eip-7773) records Sepolia activation at epoch 353024, October 6, 2026 13:53:36 UTC, and Hoodi at epoch 132352, October 26, 2026 17:42:48 UTC. Mainnet is unscheduled in this reviewed source. The earlier [EF testnet announcement](https://blog.ethereum.org/en/2026/09/17/glamsterdam-testnet-announcement) had Hoodi pending; the newer meta-EIP takes precedence for its schedule.

`probeEvmUpgrade` verifies the expected chain ID, fetches a live block and requests `eth_estimateGas` at that block. For Ethereum it also tests [EIP-7843 SLOTNUM](https://eips.ethereum.org/EIPS/eip-7843) using temporary code in `eth_call` state overrides. No contract is deployed. Unsupported overrides, invalid opcodes and unavailable historical state leave this capability unverified. One opcode is not proof that every Glamsterdam rule is implemented. Dates and client version strings never enable a capability.

`estimateEvmGas` requires the actual sender address, estimates the supplied transaction under current node rules and enforces the caller's gas ceiling. Avoid cached gas constants, fixed call stipends and assumptions about `gasleft()`. [EF repricing guidance](https://blog.ethereum.org/2026/08/24/glamsterdam-repricing-testing) covers state creation/access changes. The launchpad deployment remains restricted to Sepolia/local rehearsal and Foundry estimates its gas. Existing local contract tests use the pinned supported compiler/EVM target; they are not a Glamsterdam fork-conformance suite. Contracts need representative Sepolia transaction tests and independent review before release. Indexers must filter logs by emitting address and topic rather than assuming all transfer logs are ERC-20 events. Ethereum L2s have independent activation schedules; the helper does not label them Glamsterdam.

## Solana Alpenglow

The [Solana migration guide](https://solana.com/upgrades/alpenglow) schedules mainnet epoch 1064 for approximately October 21, 2026 13:20 UTC, with a further 5000-slot transition window. Devnet and testnet are listed active. **Query the cluster instead of using this schedule to switch behavior.** `getAgGenesisCert` returns null for TowerBFT, a certificate after migration, or method-not-found on an older RPC. The SDK distinguishes all three and validates the returned structure. It does not independently verify the BLS signature. Only a structurally valid provider-reported certificate selects `finalized`; Tower/unknown keeps the existing `confirmed` behavior.

Transaction execution, SVM programs and fee mechanics are unchanged by Alpenglow. Applications streaming Geyser data need buffers per connection and `(slot, bank_id)`; cross-provider reconciliation uses blockhash because bank IDs are node-local. Indexers must stop counting vote transactions and ticks, and review Clock timestamp assumptions. Rotor is a later phase with no activation date in the reviewed source. The advertised finality is a target, not an application latency guarantee.

## Other chains and upgrades

Use the same procedure per actual dependency: record an official specification and activation status, pin a supported SDK/client release, preserve chain/genesis identity checks, add behavior tests, then roll out the verified shared code. Do not install floating `latest` packages or apply Ethereum/Solana consensus changes to ICP, Sui, Arbitrum, Polkadot or other chains. Their project-specific compatibility reviews remain part of the portfolio mission. Forks remain upstream reference dependencies.
