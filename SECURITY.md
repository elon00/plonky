# Security boundary

The server is a loopback development host. The crypto demo is ephemeral and unauthenticated. The contract is an unaudited local/testnet reference. See PRODUCTION_GAPS.md before releasing a real service.

Keep .env and endpoint credentials private. No seed phrase or signing key is needed. The RPC probe never sends transactions.

Report vulnerabilities privately to the repository owner without publishing credentials.
