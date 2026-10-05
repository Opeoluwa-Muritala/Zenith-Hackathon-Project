The Mono adapter connects Nigerian financial accounts without exposing Mono credentials to Android. This document is for integration and operations engineers.

# Mono Connect integration

Set `AGGREGATOR_PROVIDER=mono`, `MONO_SECRET_KEY`, `MONO_PUBLIC_KEY`, `MONO_WEBHOOK_SECRET`, and `MONO_REDIRECT_URL`. Sandbox keys begin with `test_sk_`; sandbox calls are free, while live access requires an approved, funded Mono account.

Verified current endpoints are `POST /v2/accounts/initiate`, `POST /v2/accounts/auth`, `GET /v2/accounts/{id}`, `GET /v2/accounts/{id}/transactions`, `POST /v2/accounts/{id}/transactions/categorise`, and `POST /v2/accounts/{id}/unlink`. Mono sends `mono.events.account_connected`, `mono.events.account_updated`, and `mono.events.account_unlinked`. Data status may be `AVAILABLE`, `PARTIAL`, `UNAVAILABLE` or `FAILED`.

The client sends `mono-sec-key`, uses a 15-second timeout, and retries only transport errors, 429 and 5xx responses. It follows pagination only when the next URL remains on the configured Mono origin. It never logs bodies. Configure the dashboard webhook as `https://<public-tunnel>/webhooks/mono`; use ngrok or cloudflared locally.

The repository currently contains the client but not the persistence and webhook route required for an end-to-end live link. Keep the mock provider selected until those gaps are closed.

## Related docs

- [Runbook](runbook.md)
- [Known gaps](KNOWN_GAPS.md)
- [Mono official docs](https://docs.mono.co/)
