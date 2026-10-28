# Fetch Public API

Fetch is a read-only financial data API for Nigerian bank and wallet aggregation.
This page is a shareable overview; the generated [OpenAPI document](api/openapi.yaml)
is the authoritative machine-readable contract.

## Safety and privacy

- Fetch never accepts bank passwords and has no payment, transfer, or debit operations.
- BVNs are validated before Lookup and are never stored raw; only an HMAC and last four digits are retained.
- Mono account identifiers, discovered account numbers, and device tokens are encrypted at rest.
- All financial endpoints require a bearer access token issued by Fetch.
- Provider and webhook errors are intentionally generic and never return bank payloads or secrets.

## Authentication

1. `POST /auth/otp/request` with an email or E.164 phone number.
2. `POST /auth/otp/verify` with the six-digit code.
3. Use the returned bearer access token for protected endpoints.
4. Rotate refresh tokens with `POST /auth/refresh`.
5. Revoke one session with `POST /auth/logout`, or all sessions with `POST /auth/logout-all`.

OTP codes expire after five minutes, are single-use, and are limited to five attempts.

## Main API groups

| Group | Endpoints | Purpose |
|---|---|---|
| Discovery | `/onboarding/bvn/*` | Discover accounts through Mono Lookup |
| Linking | `/accounts/link*`, `/accounts/discovered/*/link` | Start hosted, read-only Mono Connect |
| Accounts | `/accounts*`, `/sync` | Read balances, freshness, pause/resume, unlink |
| Ledger | `/transactions*`, `/statements/upload` | Read and classify the unified ledger |
| Money views | `/net-position`, `/assets`, `/analytics/spending` | Cash, investments, and spending |
| Planning | `/budget*`, `/obligations*` | Budgets, velocity, and obligations |
| Insights | `/insights*`, `/insight-alerts*` | Evidence-linked findings and alerts |
| SME review | `/insight-profile`, `/business-personal/*` | Business/personal review |
| Privacy | `/consents*` | Consent status and revocation |
| Devices | `/devices*`, `/notification-preferences` | Push registration and preferences |

## Classification review

`GET /transfer-suggestions` lists the signed-in user's family and ajo suggestions.
`POST /transfer-suggestions/{id}/confirm` confirms a suggestion;
`POST /transfer-suggestions/{id}/dismiss` dismisses it. Confirmation of a family
suggestion creates a future category rule unless an explicit user rule already exists.
Suggestions remain local to the user. Ajo confirmation records the review decision.

Global rule promotion is an operator action requiring two independent confirmed
corrections. It is deliberately unavailable through public user credentials.

The optional narration classifier uses the configured AI client when
`AI_ENABLED_GLOBAL=true`. Invalid responses and provider failures retain the
deterministic result. Its normalized-narration cache is process-local.

## Insight cards and SME review

`POST /insights/run` computes Leak Finder, cash-flow and weekly health findings from
the consented ledger. Cards include `number_minor`, `why_it_matters`, `action`,
confidence, and `evidence_transaction_ids`. Amounts are integer kobo and are always
computed by backend code.

Set `PUT /insight-profile` to `{"mode":"sme"}` to enable the separator.
`GET /business-personal/review` returns business, personal or unsure suggestions and
split totals. `PUT /business-personal/transactions/{transaction_id}` records the
owner's correction. `GET /insight-alerts` lists alerts and
`POST /insight-alerts/{alert_id}/read` marks one read.

## Environments

Set the API base URL supplied by the Fetch deployment. Do not place Mono keys, JWT secrets,
encryption keys, BVNs, OTPs, or refresh tokens in a client bundle or URL.

For endpoint schemas, authentication requirements, status codes, and examples, share:

- [OpenAPI YAML](api/openapi.yaml)
- [OpenAPI JSON](api/openapi.json)
- [Postman collection](api/postman/fetch.postman_collection.json)
