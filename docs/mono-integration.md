The Mono adapter connects Nigerian financial accounts without exposing Mono credentials to Android. This document is for integration and operations engineers.

# Mono Connect integration

Set `AGGREGATOR_PROVIDER=mono`, `MONO_SECRET_KEY`, the separate `MONO_LOOKUP_SECRET_KEY`, `WEBHOOK_SECURE_KEY`, and `MONO_REDIRECT_URL`. `WEBHOOK_SECURE_KEY` is the shared secret the backend compares against Mono's `mono-webhook-secret` header. Use the sandbox app keys and test details supplied in your Mono dashboard. Costs and sandbox availability have not been verified; do not assume all sandbox calls are free. The current [Lookup guide](https://docs.mono.co/docs/lookup/bvn-igree) states that requests including failures are billable.

Verified current endpoints are `POST /v2/accounts/initiate`, `POST /v2/accounts/auth`, `GET /v2/accounts/{id}`, `GET /v2/accounts/{id}/transactions`, `POST /v2/accounts/{id}/transactions/categorise`, and `POST /v2/accounts/{id}/unlink`. Mono sends `mono.events.account_connected`, `mono.events.account_updated`, and `mono.events.account_unlinked`. Data status may be `AVAILABLE`, `PARTIAL`, `UNAVAILABLE` or `FAILED`.

The client sends `mono-sec-key` and uses a 15-second timeout. Read requests use bounded transport/429/5xx retries; Lookup and hosted-link initiation do not transparently retry. Transaction pagination is limited to 100 pages and the same origin/account transaction path; repeated URLs are rejected. It never logs bodies. Configure the Mono webhook for your publicly reachable backend with the matching secret.

## Local sandbox test panel

Run the API locally with `AGGREGATOR_PROVIDER=mono`, a sandbox `MONO_SECRET_KEY`, and `WEBHOOK_SECURE_KEY` configured in `backend/app/.env`. Do not put credentials in the page or Android app. Apply database migrations only to the intended development/demo database.

From PowerShell:

```powershell
Set-Location backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/dev/mono-test`. The page is only served to loopback clients when `ENVIRONMENT` is not `production`. Set `OTP_SENDER=dev_inbox` and `OTP_DEV_INBOX_ENABLED=true` for local testing. Enter synthetic details, request a random OTP, and let the page read it from the local development inbox before verifying. Grant consent, start hosted linking, then return to the page and wait for its status poll. The default redirect is a `cashlens://` app deep link; if no app handles it on desktop, return to the test tab. The webhook still needs to reach the backend.

For local webhooks, expose the backend port through a temporary HTTPS tunnel you control and configure the Mono sandbox dashboard to send events to `https://<tunnel-host>/webhooks/mono`. Set `WEBHOOK_SECURE_KEY` to the same value configured as Mono's webhook secret. A local browser can initiate Mono Connect, but the hosted account is not marked connected until the backend receives a valid webhook. After status becomes connected, select “Sync connected accounts”. A pending data status means wait for Mono processing/webhook delivery; do not repeatedly refresh a real-time endpoint.

The panel never displays access/refresh tokens and keeps the access token only in tab memory. It is a legacy developer test tool, not the mobile demo flow. Its identity shortcut is disabled in Mono mode; do not use that button as a real BVN verification step. Use the existing Lookup API sequence in the [backend demo walkthrough](demo-backend-walkthrough.md), with the protected presenter inbox for app login.

## Related docs

- [Runbook](runbook.md)
- [Known gaps](KNOWN_GAPS.md)
- [Mono official docs](https://docs.mono.co/)
