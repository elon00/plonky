# Release order

1. Validate the candidate locally: native tests, NIST vectors, protected-service checks, SDK/contracts, browser WASM and dependency advisories.
2. Publish the plonky candidate for hosted CI. Repair any actual runner failures.
3. Promote the reviewed candidate only after required hosted checks pass.
4. Deploy the flagship browser demo from the gated workflow and check its public URL.
5. Propagate the exact shared source to the 925-repository fleet with backups, source hashes and individual builds/self-checks.
6. Publish managed files only, with fast-forward Git updates and recorded outcomes. Never publish .env, signing keys, reports or unrelated staged work.
7. Save a release bundle, CI links, fleet report and owner-dependent checklist.

The fleet defaults to canonical hosted CI on plonky to avoid running duplicate full pipelines 925 times for identical shared code. Individual repositories can opt in with QMOOSA_ENABLE_CI=true or workflow_dispatch. Local fleet verification remains independent for every repository.
