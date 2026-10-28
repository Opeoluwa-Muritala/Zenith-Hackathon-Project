# Fetch backend / cashlens

Phase 4 classification review: operators can promote an agreed correction with
`cd backend` then `python -m scripts.review_classification "normalized shop" "Transport"`.
The command requires two independent users' confirmed corrections. Review the key and
category before running it; global rules store a hash of the key. User rules always win.

| Requirement | Phase 4 status |
|---|---|
| NDL-5 | Family suggestions, user confirmation, future category override |
| NDL-6 | Weekly/monthly ajo detection, confirm/dismiss review |
| NDL-7 | Configured AI adapter, validated JSON, bounded cache and failure fallback |
| NDL-8 | Correction history, independent-user threshold, operator-reviewed promotion |

Public review routes and API artifacts are linked from [Public API](docs/public-api.md).

Fetch is a FastAPI backend for consented personal-finance data. It authenticates email or phone users with one-time codes and app-issued JWT/refresh tokens, and integrates Mono BVN Lookup and hosted Connect Link. It exposes accounts, manual assets, net position, transactions, recurring-series detection, statements, and optional AI tools; remaining MVP gaps are listed in [Known gaps](docs/KNOWN_GAPS.md).

See [docs/README.md](docs/README.md) for the complete documentation index and [docs/api/openapi.json](docs/api/openapi.json) for the generated API specification.

For the mobile backend demo with Mono sandbox and an existing Neon database, follow the [backend demo walkthrough](docs/demo-backend-walkthrough.md). The presenter can read generated login codes from a protected backend page; finance endpoints continue using the existing Mono integration. Neon was last verified at revision 0012; new development migrations continue from 0013. Mono sandbox behavior remains unverified.

## Five-minute quickstart

Requirements: Python 3.12 and the project’s Python dependencies. Configure a local `.env` from `.env.example`; do not commit secrets.

```sh
cd backend
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Install development dependencies with `uv sync --all-groups` and documentation validation with `uv pip install -r requirements-docs.txt`. Run tests with `uv run python -m pytest tests` from `backend`. Open `http://localhost:8000/docs` for Swagger. OTP delivery must be explicitly configured; demo inboxes must never be used with real users.

For multi-worker or production authentication limits, configure `REDIS_URL`. Without it,
the API uses a process-local limiter and emits a warning. Production requires a dedicated
`FIELD_ENCRYPTION_KEY`; deriving it from Mono credentials is development-only.

The test panel needs a public HTTPS tunnel for Mono webhooks; see [Mono integration](docs/mono-integration.md). Mono keys stay on the backend and must never be placed in the Android app or browser code.
