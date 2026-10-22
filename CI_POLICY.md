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
| codeql | Python, JavaScript/TypeScript, Rust and GitHub Actions analysis; high/critical security findings or error-level results block release |

Actions are pinned to immutable commits and credentials are not persisted by checkout. Most jobs have read-only repository access; CodeQL upload and the Pages deployment receive only their required additional permissions.

The Required release gate runs even when a dependency fails. It requires exactly the expected jobs and every result must be success. Failed, skipped, cancelled, absent or malformed checks fail the gate. Its artifact records the repository, tested commit, run and timestamp. Tests exercise failure paths; a workflow file merely existing is not a passing run.

Only the canonical Plonky Pages site is published, after this gate succeeds on main. Pull requests cannot publish. This deploys a browser demo, not a mainnet token or a production backend. A hosted run is evidence only for its exact tested revision and environment.

Branch protection must separately require this gate on main before describing merges as enforced. Workflow gates do not configure repository branch protection themselves. The portfolio verifier must check every owned project's current revision; a successful canonical run does not prove all other repository runs passed.

The scanner policy records only exact reviewed non-secret fixtures and rejects changed content; repository-provided ignores do not suppress findings. It does not prove the absence of all confidential information on GitHub. CodeQL uses separate categories for all four configured languages so results cannot overwrite one another. Rust also uses compiler/Clippy/tests, and Solidity uses contract/fuzz tests. Independent security review, customer acceptance, licenses, real deployment/rollback evidence and monitoring remain separate requirements. No CI success awards 10/10 market readiness.

CI checks out the credential guard, trusted policy and its regression tests from immutable master security commit 9900daea33de9c723f7b3d89d09363e90e8bb84b. The trusted checkout is a sibling of the target checkout; target changes cannot replace those rules. Reviewed fixture records name their actual source repository; they are exact-content exceptions rather than general path exclusions.

Fleet replacements and backup files use owner-only POSIX access (0600, or 0700 when preserving owner execute). Timestamped backup roots are created with 0700. Windows chmod does not configure NTFS access-control lists; retain an appropriately protected user/workspace directory there.

Rust analysis supports the stable 2021/2024 editions used by the shared workspace. Official language guidance: https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/. GitHub Actions analysis also checks the workflow source. Neither substitutes for behavioral tests or contract review.

Review workflow changes before merging them. The pinned scanner prevents a target repository from weakening scan rules; it does not make repository-owned workflow edits or every local developer command independently trusted.
