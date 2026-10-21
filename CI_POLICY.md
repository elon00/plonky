# Required CI and deployment policy

Every shared checkout runs the same mandatory workflow on pull requests and pushes to main. Repository-name and QMOOSA_ENABLE_CI skips are removed. Manual workflow execution runs the same checks.

| Job | Required evidence |
| --- | --- |
| core | Ubuntu and Windows: formatting, Clippy, Rust/Python integration tests, JavaScript syntax and locked SDK tests |
| contracts | Locked dependencies and Foundry contract/fuzz tests |
| security | Actual dependency-advisory audit; failed or unavailable checks fail |
| credentials | Checksum-pinned scanner, regression checks, complete available history including merge diffs, commit/tag messages and staged changes |
| container | Build the real image and test authentication, execution and shutdown |
| web | Build Rust/WASM, then exercise the browser at desktop/mobile sizes |
| codeql | Python and JavaScript/TypeScript analysis; high/critical security findings or error-level results block release |

Actions are pinned to immutable commits and credentials are not persisted by checkout. Most jobs have read-only repository access; CodeQL upload and the Pages deployment receive only their required additional permissions.

The Required release gate runs even when a dependency fails. It requires exactly the expected jobs and every result must be success. Failed, skipped, cancelled, absent or malformed checks fail the gate. Its artifact records the repository, tested commit, run and timestamp. Tests exercise failure paths; a workflow file merely existing is not a passing run.

Only the canonical Plonky Pages site is published, after this gate succeeds on main. Pull requests cannot publish. This deploys a browser demo, not a mainnet token or a production backend. A hosted run is evidence only for its exact tested revision and environment.

Branch protection must separately require this gate on main before describing merges as enforced. Workflow gates do not configure repository branch protection themselves. The portfolio verifier must check every owned project's current revision; a successful canonical run does not prove all other repository runs passed.

The scanner policy records only exact reviewed non-secret fixtures and rejects changed content; repository-provided ignores do not suppress findings. It does not prove the absence of all confidential information on GitHub. CodeQL language coverage is limited to the configured languages; Rust uses compiler/Clippy/tests, and Solidity uses contract/fuzz tests. Independent security review, customer acceptance, licenses, real deployment/rollback evidence and monitoring remain separate requirements. No CI success awards 10/10 market readiness.

The credential guard and its regression tests were imported from master security commit 9900daea33de9c723f7b3d89d09363e90e8bb84b. Reviewed fixture records name their actual source repository; they are exact-content exceptions rather than general path exclusions.
