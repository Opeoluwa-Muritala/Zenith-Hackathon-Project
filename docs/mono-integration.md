The Mono adapter connects Nigerian financial accounts without exposing Mono credentials to Android. This document is for integration and operations engineers.

# Mono Connect integration

Set `AGGREGATOR_PROVIDER=mono`, `MONO_SECRET_KEY`, `MONO_PUBLIC_KEY`, `MONO_WEBHOOK_SECRET`, and `MONO_REDIRECT_URL`. Sandbox keys begin with `test_sk_`; sandbox calls are free, while live access requires an approved, funded Mono account.

Verified current endpoints are `POST /v2/accounts/initiate`, `POST /v2/accounts/auth`, `GET /v2/accounts/{id}`, `GET /v2/accounts/{id}/transactions`, `POST /v2/accounts/{id}/transactions/categorise`, and `POST /v2/accounts/{id}/unlink`. Mono sends `mono.events.account_connected`, `mono.events.account_updated`, and `mono.events.account_unlinked`. Data status may be `AVAILABLE`, `PARTIAL`, `UNAVAILABLE` or `FAILED`.

The client sends `mono-sec-key`, uses a 15-second timeout, and retries only transport errors, 429 and 5xx responses. It follows pagination only when the next URL remains on the configured Mono origin. It never logs bodies. Configure the dashboard webhook as `https://<public-tunnel>/webhooks/mono`; use ngrok or cloudflared locally.

## Local sandbox test panel

Run the API locally with `AGGREGATOR_PROVIDER=mono`, a sandbox `MONO_SECRET_KEY`, and `MONO_WEBHOOK_SECRET` configured in `backend/app/.env`. Do not put credentials in the page or Android app. Apply database migrations only to the intended development/demo database.

From PowerShell:

```powershell
Set-Location backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/dev/mono-test`. The page is only served to loopback clients when `ENVIRONMENT` is not `production`. Enter synthetic test identity details, request and verify the development OTP, grant consent, start the hosted link, then return to the page and wait for its status poll. The default redirect is a `cashlens://` app deep link; if no app handles it on desktop, return to the test tab. The webhook still needs to reach the backend.

For local webhooks, expose port 8000 through a temporary HTTPS tunnel you control and configure the Mono sandbox dashboard to send events to `https://<tunnel-host>/webhooks/mono`. Configure the exact shared secret in `MONO_WEBHOOK_SECRET`. A local browser can initiate Mono Connect, but the hosted account is not marked connected until the backend receives a valid webhook. After status becomes connected, select “Sync connected accounts”. A pending data status means wait for Mono processing/webhook delivery; do not repeatedly refresh a real-time endpoint.

The panel never displays access/refresh tokens and keeps the access token only in tab memory. It is a developer test tool, not a customer frontend. Its identity route is mocked, and only the configured Mono sandbox should be used.

## Related docs

- [Runbook](runbook.md)
- [Known gaps](KNOWN_GAPS.md)
- [Mono official docs](https://docs.mono.co/)
