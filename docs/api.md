This guide explains how to authenticate and use the current cashlens API. It is for developers and hackathon reviewers.
Swagger UI at `/docs` and ReDoc at `/redoc` expose the generated OpenAPI schema.

# API guide

## Conventions

Protected routes use `Authorization: Bearer <access_token>`. Request an OTP at `POST /auth/otp/request`, then exchange the fixed development OTP at `POST /auth/otp/verify` (development only). Amounts ending in `_minor` are integer kobo; dates and timestamps use ISO 8601, with stored timestamps in UTC. Errors currently use FastAPI `detail` responses; validation errors may differ. Transactions support `limit` and `offset`; maximums are enforced by the route. OTP and account refresh routes are rate-limited.

## Journey

The normal sequence is OTP request and verification, mocked identity verification, consent grant, account linking, sync, then summary and insight reads. Exact request bodies are defined by the live schema in Swagger. Never use a real person's BVN or contact details in examples. Mono webhooks authenticate with a configured shared-secret header, not JWT.

## Endpoint reference

Generated from `backend/openapi.json`; regenerate after route changes with `make openapi docs-api`.

<!-- GENERATED ENDPOINTS START -->
| Method | Path | Summary | Tag |
|---|---|---|---|
| `GET` | `/accounts` | Accounts | Accounts and linking |
| `POST` | `/accounts/link` | Link Mock | Accounts and linking |
| `POST` | `/accounts/link/exchange` | Exchange Link | Accounts and linking |
| `POST` | `/accounts/link/initiate` | Initiate Link | Accounts and linking |
| `GET` | `/accounts/link/status` | Link Status | Accounts and linking |
| `POST` | `/accounts/{account_id}/refresh` | Refresh Account | Accounts and linking |
| `POST` | `/ai/chat` | Ask Money | AI |
| `DELETE` | `/ai/chat/{conversation_id}` | Delete Chat | AI |
| `GET` | `/ai/chat/{conversation_id}` | Get Chat | AI |
| `POST` | `/auth/logout` | Logout | Auth |
| `POST` | `/auth/otp/request` | Request Otp | Auth |
| `POST` | `/auth/otp/verify` | Verify Otp | Auth |
| `POST` | `/auth/refresh` | Refresh | Auth |
| `GET` | `/consents` | Consents | Consents |
| `POST` | `/consents` | Create Consent | Consents |
| `DELETE` | `/consents/{consent_id}` | Revoke | Consents |
| `GET` | `/forecast/safe-to-spend` | Safe To Spend Forecast | Forecast |
| `GET` | `/health` | Health | Health |
| `POST` | `/identity/bvn/verify` | Verify Bvn | Identity |
| `GET` | `/insights` | Insights | Insights |
| `POST` | `/insights/run` | Run Insights | Insights |
| `GET` | `/insights/{insight_id}` | Insight Detail | Insights |
| `POST` | `/insights/{insight_id}/dismiss` | Dismiss | Insights |
| `GET` | `/recurring` | Recurring | Recurring |
| `PATCH` | `/settings/ai` | Set Ai Preference | AI |
| `POST` | `/statements/upload` | Upload Statement | Sync and statements |
| `GET` | `/summary/categories` | Category Summary | Summary |
| `GET` | `/summary/monthly` | Monthly Summary | Summary |
| `GET` | `/summary/overview` | Summary | Summary |
| `POST` | `/sync` | Sync | Sync and statements |
| `GET` | `/transactions` | Transactions | Transactions |
| `POST` | `/webhooks/mono` | Mono Webhook | Webhooks |
<!-- GENERATED ENDPOINTS END -->

## Current limitations

The API currently exposes simple array responses for some list routes and does not use a common error envelope. The exact `detail` error shape is framework-generated. The BVN field is intentionally present in the identity verification request because that route needs it; it is not a response field and raw BVN is not stored.

## Related docs

- [Architecture](architecture.md)
- [Consent and privacy](consent-and-privacy.md)
- [OpenAPI schema](../backend/openapi.json)
