# Getting started

This guide describes local setup without installing or starting a database or external service. Storage configuration is defined in `backend/app/core/config.py`; application routes need an existing PostgreSQL database, while the offline tests and spec generators do not.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uv sync --all-groups
uv pip install -r requirements-docs.txt
Copy-Item ..\.env.example .env
# Fill placeholders with local test-only values; set OTP_SENDER=dev_inbox and OTP_DEV_INBOX_ENABLED=true only for local testing.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run tests and generate artifacts:

```powershell
python -m pytest tests
python scripts/export_openapi.py
python scripts/export_postman.py
python scripts/gen_data_model.py
python scripts/gen_config_docs.py
```

Swagger is available at `http://127.0.0.1:8000/docs` in development. The loopback-only Mono test page is documented in [demo mode](demo-mode.md).

## First request

With the local development inbox explicitly enabled, request a code and read it from the loopback-only inbox before verifying:

```powershell
curl -X POST http://127.0.0.1:8000/auth/otp/request -H "Content-Type: application/json" -d '{"phone":"+2348000000000"}'
curl 'http://127.0.0.1:8000/dev/otp-inbox?identifier=%2B2348000000000'
# Use the returned one-time code in POST /auth/otp/verify; do not put it in source control.
```

Do not use real personal data in development examples. For the existing Neon/Mono sandbox mobile backend, use the [hosted demo walkthrough](demo-backend-walkthrough.md) and [protected presenter inbox](demo-mode.md); the legacy Mono test panel is not the full discovery flow. The project uses uv for development dependencies and a separate dev-only requirements file for OpenAPI validation.
