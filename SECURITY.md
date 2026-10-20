# Security boundary

app.py is the loopback development host. service.py is the protected server: it uses a shared operator token and single-instance request limits, and requires TLS termination at the reverse proxy when exposed publicly. The crypto demo uses ephemeral keys; it is not a secure messaging service. The contract is an unaudited local/testnet reference. See PRODUCTION_GAPS.md before releasing a real service.

Keep .env and endpoint credentials private. No seed phrase or signing key is needed. The RPC probe never sends transactions.

Report vulnerabilities privately to the repository owner without publishing credentials.
