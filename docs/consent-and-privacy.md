cashlens is designed to minimise identity and financial data while preserving user control. This document is for users, reviewers and implementers.

# Consent and privacy

BVN is an identity key only. The service stores a salted hash and the last four digits, never the raw BVN, and does not use BVN to fetch transactions. Transactions enter only through Mock, Mono or bounded CSV provider interfaces tied to consent.

Consent records capture institution, scope, grant, expiry and revocation times. Revocation is checked when accounts, transactions and summaries are read. The intended production flow also unlinks at Mono after local revocation; see known gaps.

Logs must not contain raw BVN, narrations, balances, provider keys or provider bodies. CSV content is parsed in memory and bounded to 2 MB and 10,000 rows. Access tokens are short-lived; refresh token values are stored only as hashes.

These controls are design intent aligned with data minimisation, purpose limitation and data-subject control under the Nigeria Data Protection Act. They are not a claim of legal compliance or certification. A Nigerian privacy professional should review retention, lawful basis, notices and operational processes before launch.

## Related docs

- [Architecture](architecture.md)
- [Security policy](../SECURITY.md)
- [Known gaps](KNOWN_GAPS.md)
