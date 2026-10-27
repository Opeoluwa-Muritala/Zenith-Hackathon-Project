# API guide

The generated source of truth is [OpenAPI JSON](api/openapi.json) and [YAML](api/openapi.yaml), with Swagger at `/docs` in development and ReDoc at `/redoc`. Protected routes use `Authorization: Bearer <access_token>`. Responses are JSON unless a route returns `204`; application errors use `{"detail": "..."}`. Validation errors return a detail list containing loc, type and msg, with submitted sensitive values omitted. Unexpected failures return a generic JSON 500 response.

Amounts ending in `_minor` are integer minor units (NGN kobo); `fx_rate_used_ppm` is NGN per USD multiplied by one million. Timestamps are UTC ISO 8601. List endpoints use bounded `limit` and `offset` where implemented. Transactions can be filtered by account, merchant, category, date range, and `type=credit|debit`. `GET /transactions/recent` returns a cross-account feed; `GET /analytics/spending` supports this month, last month and custom dates. Own-account transfer exclusion is not implemented and is explicitly reported as unavailable. Mono real-time refresh starts a provider job and may return cached balance until a webhook arrives.

Current route groups are authentication, identity, BVN onboarding, consents, discovered-account linking, accounts, assets/FX, net position, sync/statements, transactions, category rules, spending analytics, budget, obligations, notification preferences/device registration, summaries, recurring, insights, forecast, AI, webhooks, and health. Obligation detection is limited to named recurring lenders; push delivery and alerts are not scheduled.

## Demo contracts and conventions

The [walkthrough](demo-backend-walkthrough.md) gives the exact request order. Discovery confirmation returns IDs for selection. Link-status polling returns account_id when the local account exists. `/accounts` returns a groups object, not a flat array; totals stay separated by currency. Available and cached balances may differ from an unavailable ledger balance, which remains null.

Refresh returns status `requested` for a processing Mono job, `synced` for a completed update, `cached` when Mono reports no new data, or `delayed` on failure. Processing/failed headers also return job_status. All include balance_synced_at, cache_age_minutes, sync_status and sync_message. A 429 refresh response includes Retry-After in seconds. The default one-hour cooldown can be reduced to 300 seconds for the sandbox; Mono enforces a five-minute minimum even if the setting is shorter. Mock fixtures can use 60 seconds. In-flight requests also use a process-local cooldown.

Analytics, budgets and net position aggregate NGN-linked accounts; other linked currencies are excluded from those totals. USD manual assets use their stored FX rate. Category labels are Food & Dining, Bills & Utilities, Transport, Airtime & Data, Shopping & Transfers, Transfers & Family, and Uncategorised. Legacy labels are normalised when reading transactions and analytics.

Errors documented for each demo operation are limited to its actual input, ownership, state and provider paths: 401 auth/code failures, 404 missing owned resource, 409 conflicting state, 410 expired Lookup session, 413 oversized webhook, 422 invalid input/range, 429 throttle/cooldown, 500 internal failure, 502 rejected/invalid provider result and 503 provider/delivery unavailability. There is no universal application error-code field.

Processed webhook events dedupe; failed events can retry on redelivery. Confirming an unexpired completed Lookup reuses stored results without another Mono details request. No general Idempotency-Key protocol is implemented. APIs are currently unversioned; retain operation IDs and review response changes with the mobile integrator.
