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
| Reports | `/reports*`, `/report-share-links*` | Monthly reports, exports and controlled sharing |
| Bookkeeper | `/bookkeeper-invites*`, `/bookkeeper/clients/*` | One read-only delegated user |
| Insights | `/insights*`, `/insight-alerts*` | Evidence-linked findings and alerts |
| SME review | `/insight-profile`, `/business-personal/*` | Business/personal review |
| Privacy | `/consents*` | Consent status and revocation |
| Display privacy | `/privacy-preferences` | Persist the client's currency-blur toggle |
| Privacy | `/privacy/consents`, `/privacy/wipe` | Active links and irreversible full deletion |
| Plans | `/plan`, `/billing/upgrade-events` | Entitlements and upgrade intent only |
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

## Money views

`GET /net-position` includes linked cash, manual investments, the combined total,
an account/asset breakdown, paused-account flags, the valuation time and an FX warning.
Paused linked accounts remain included at their last known balance; unlinked or revoked
accounts are excluded. USD manual assets use the current configured cached reference
rate when available and retain their entry-time rate as a warned fallback.

`GET /transactions` supports account, date, category, merchant name, direction, limit
and offset filters. `GET /transactions/recent` defaults to five and accepts at most 20.
Spending analytics support this month, last month and bounded custom ranges.

Budgets accept an optional `effective_from` UTC timestamp. Obligation endpoints support
manual creation, confirmation, editing and dismissal; detected due dates are explicitly
marked as estimates and detail responses include matched payment transactions.

## Reports and delegated access

`GET /reports/monthly/{YYYY-MM}` returns income, expenses, net cash flow and the
business/personal/unsure split from the consented ledger. PDF and CSV exports come from
the same computed dataset. Unsure or sub-70% confidence classifications are labelled
and are never presented as confirmed facts.

Owners explicitly create expiring share links with
`POST /reports/monthly/{month}/share-links`; the raw secret is returned once and only a
salted hash is stored. `DELETE /report-share-links/{id}` revokes access immediately.
Public shared-report routes require the unexpired secret and stop returning data if the
underlying account consent is revoked.

An SME can maintain one bookkeeper invite. The invited user must sign in with the exact
invited email before accepting. Accepted bookkeepers receive bounded, read-only ledger
and monthly-report access; they cannot modify transactions, reports or account data.
Revocation removes access immediately.

## Notifications and scheduled work

Clients register an Android or iOS token with `POST /devices`, remove it with
`DELETE /devices/{id}`, and manage the three notification categories through
`GET`/`PUT /notification-preferences`. Tokens are encrypted at rest and never returned.
Fetch prioritises new account activity, then sends budget, repayment and investment
reminders according to the owner's preferences. Duplicate event/device delivery is
suppressed. Push delivery may be disabled by the deployment without disabling financial
sync or the API.

## Consent inventory and full deletion

`GET /privacy/consents` lists active read-only links with institution, link time, provider
data status, and the scope Fetch requested. To permanently delete an account, request a
new OTP through the normal authentication route and submit it once to `POST /privacy/wipe`.
The response reports deletion counts and whether a remote unlink remains pending. Local
access and financial data are removed even when Mono is unavailable; the encrypted unlink
target remains in a retry queue. Only a keyed user-ID hash and wipe timestamp remain as the
wipe audit record.

## Plans and upgrade intent

`GET /plan` returns the free/SME flag, live-sync trial dates, the free linked-account cap,
and feature entitlements. Free users retain statement upload, manual assets, budgets and
categories. The live-sync trial starts on the first Mono link or sync attempt and lasts 14
days for at most two live accounts. An operator-controlled paid SME flag enables continuous
sync and identifies business outcomes such as separation, reports, alerts and team access.

`POST /billing/upgrade-events` records where an authenticated user tapped upgrade. It does
not accept prices or payment details, create checkout sessions, or charge anything. Final
pricing remains intentionally outside the API while the product test is running.

## Environments

Set the API base URL supplied by the Fetch deployment. Do not place Mono keys, JWT secrets,
encryption keys, BVNs, OTPs, or refresh tokens in a client bundle or URL.

For endpoint schemas, authentication requirements, status codes, and examples, share:

- [OpenAPI YAML](api/openapi.yaml)
- [OpenAPI JSON](api/openapi.json)
- [Postman collection](api/postman/fetch.postman_collection.json)
