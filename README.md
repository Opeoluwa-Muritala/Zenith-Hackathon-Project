# Fetch backend / cashlens

Phase 4 classification review: operators can promote an agreed correction with
`cd backend` then `python -m scripts.review_classification "normalized shop" "Transport"`.
The command requires two independent users' confirmed corrections. Review the key and
category before running it; global rules store a hash of the key. User rules always win.

| Requirement | Status |
|---|---|
| NDL-5 | Family suggestions, user confirmation, future category override |
| NDL-6 | Weekly/monthly ajo detection, confirm/dismiss review |
| NDL-7 | Configured AI adapter, validated JSON, bounded cache and failure fallback |
| NDL-8 | Correction history, independent-user threshold, operator-reviewed promotion |
| INS-1 | Leak Finder headline, duplicate/increase/subscription values and evidence |
| INS-2 | SME business/personal/unsure suggestions, split totals and owner correction |
| INS-3 | 90-day inflow/outflow rhythm, best/worst weeks and simple runway |
| INS-4 | Weekly consumer/SME health score with three disclosed drivers |
| INS-5 | Cards expose number, rationale, action, confidence and evidence IDs |
| INS-6 | Persisted alerts for leaks, unusual transfers, overspending and repayments |
| INS-7 | Low-confidence labels and owner-correctable SME suggestions |
| INS-8 | Code-only calculations; validated phrasing retries once then uses templates |
| NET-1–5 | Account/asset breakdown, paused balances, read-time FX and reminders |
| NET-6 | Persisted privacy-blur preference for clients |
| SPD-1–3 | Filtered/recent transactions, spending ranges and reusable category rules |
| BUD-1 | Effective-date budgets and deterministic spending velocity |
| OBL-1–3 | Generic repayment detection, owner review and matched payment history |
| RPT-1 | Deterministic monthly income, expenses, use split and cash-flow report |
| RPT-2 | PDF/CSV exports and expiring, revocable owner-created share links |
| RPT-3 | One revocable bookkeeper invite with read-only ledger/report access |
| RPT-4 | Unsure and low-confidence report items are explicitly labelled |
| NTF-1 | Encrypted device registration, removal and invalid-token handling |
| NTF-2 | Owner-controlled overspend, repayment and investment preferences |
| NTF-3 | Idempotent push log and separately deployed, locked scheduler worker |
| NTF-4 | New-money activity alerts take priority during scheduled sync |
| PRV-1 | Active-link consent inventory with institution, date, status and scope |
| PRV-2 | Immediate account purge with encrypted durable unlink retry |
| PRV-3 | Fresh-OTP complete wipe with session revocation and deletion report |
| PRV-4 | Minimal keyed user hash and wipe timestamp retained |
| BIL-1 | Free local tools plus a 14-day, two-account live-sync trial |
| BIL-2 | Operator-controlled paid SME entitlement for continuous sync and outcomes |
| BIL-3 | Entitlements separate free tools from business reports, separation and team access |
| BIL-4 | Upgrade-tap intent logging without prices or payment processing |

Public review routes and API artifacts are linked from [Public API](docs/public-api.md).

Fetch is a FastAPI backend for consented personal-finance data. It authenticates email or phone users with one-time codes and app-issued JWT/refresh tokens, and integrates Mono BVN Lookup and hosted Connect Link. It exposes accounts, manual assets, net position, transactions, recurring-series detection, statements, and optional AI tools; remaining MVP gaps are listed in [Known gaps](docs/KNOWN_GAPS.md).

See [docs/README.md](docs/README.md) for the complete documentation index and [docs/api/openapi.json](docs/api/openapi.json) for the generated API specification.

For the mobile backend demo with Mono sandbox and an existing Neon database, follow the [backend demo walkthrough](docs/demo-backend-walkthrough.md). The presenter can read generated login codes from a protected backend page; finance endpoints continue using the existing Mono integration. Neon was verified at Phase 9 revision 0024 with rollback-only smoke inserts. Mono sandbox behavior remains unverified.

## Five-minute quickstart

Requirements: Python 3.12 and the project’s Python dependencies. Configure a local `.env` from `.env.example`; do not commit secrets.

```sh
cd backend
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# In a second process:
python -m app.scheduler.worker
```

The scheduler process runs account sync, stale marking, pending-unlink retries,
asset and obligation reminders, overspending alerts, and retention cleanup. Configure
`FCM_CREDENTIALS_JSON` for push delivery; when absent, push is disabled with one warning
while all non-push jobs continue.

Install development dependencies with `uv sync --all-groups` and documentation validation with `uv pip install -r requirements-docs.txt`. Run tests with `uv run python -m pytest tests` from `backend`. Open `http://localhost:8000/docs` for Swagger. OTP delivery must be explicitly configured; demo inboxes must never be used with real users.

For multi-worker or production authentication limits, configure `REDIS_URL`. Without it,
the API uses a process-local limiter and emits a warning. Production requires a dedicated
`FIELD_ENCRYPTION_KEY`; deriving it from Mono credentials is development-only.

The test panel needs a public HTTPS tunnel for Mono webhooks; see [Mono integration](docs/mono-integration.md). Mono keys stay on the backend and must never be placed in the Android app or browser code.
