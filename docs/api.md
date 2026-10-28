# API reference

This page points developers to the generated API contract. Last verified against the merged FastAPI application. The interactive Swagger UI is available at `/api-docs` when API documentation is enabled.

The current route list, request schemas and responses are in [OpenAPI JSON](api/openapi.json). Client conventions are in the [API guide](api-guide.md). Swagger UI is `/docs` and ReDoc is `/redoc` in development; production exposure depends on `API_DOCS_ENABLED`.

Protected routes use an app-issued Bearer access token. Request a random OTP with `POST /auth/otp/request`, then exchange the delivered code at `POST /auth/otp/verify`. There is no fixed development OTP. Amounts ending in `_minor` are integer minor units; UTC timestamps use ISO 8601. Error responses currently follow FastAPI's `detail` conventions rather than one universal envelope.

## Generated endpoint inventory

<!-- GENERATED ENDPOINTS START -->
| Method | Path | Summary | Tag |
|---|---|---|---|
| `GET` | `/accounts` | List accounts grouped by category | Accounts and linking |
| `POST` | `/accounts/discovered/select` | Select discovered accounts | Accounts and linking |
| `POST` | `/accounts/discovered/{row_id}/link` | Link a selected discovered account | Accounts and linking |
| `POST` | `/accounts/link` | Link a mock fixture account | Accounts and linking |
| `POST` | `/accounts/link/exchange` | Exchange a Connect authorisation code | Accounts and linking |
| `POST` | `/accounts/link/initiate` | Initiate hosted Connect Link | Accounts and linking |
| `GET` | `/accounts/link/status` | Read link and data status | Accounts and linking |
| `GET` | `/accounts/skipped` | List skipped accounts | Accounts and linking |
| `POST` | `/accounts/skipped/{row_id}/link` | Link a skipped account | Accounts and linking |
| `GET` | `/accounts/{account_id}` | Read account balance and freshness | Accounts and linking |
| `POST` | `/accounts/{account_id}/pause` | Pause account sync | Accounts and linking |
| `POST` | `/accounts/{account_id}/refresh` | Refresh one account | Accounts and linking |
| `POST` | `/accounts/{account_id}/resume` | Resume account sync | Accounts and linking |
| `POST` | `/accounts/{account_id}/unlink` | Unlink and purge one account | Accounts and linking |
| `POST` | `/ai/chat` | Ask Money | AI |
| `DELETE` | `/ai/chat/{conversation_id}` | Delete Chat | AI |
| `GET` | `/ai/chat/{conversation_id}` | Get Chat | AI |
| `GET` | `/analytics/spending` | Read spending by period and category | Analytics |
| `GET` | `/assets` | List manual assets | Assets |
| `POST` | `/assets` | Create a manual asset | Assets |
| `DELETE` | `/assets/{asset_id}` | Delete a manual asset | Assets |
| `PUT` | `/assets/{asset_id}` | Update a manual asset | Assets |
| `POST` | `/auth/logout` | Log out a refresh-token family | Auth |
| `POST` | `/auth/logout-all` | Revoke all user sessions | Auth |
| `POST` | `/auth/otp/request` | Request a login OTP | Auth |
| `POST` | `/auth/otp/verify` | Verify login OTP | Auth |
| `POST` | `/auth/refresh` | Rotate refresh token | Auth |
| `POST` | `/billing/upgrade-events` | Record an upgrade tap | Accounts and linking |
| `GET` | `/bookkeeper-invites` | Get Bookkeeper Invite | Accounts and linking |
| `POST` | `/bookkeeper-invites` | Invite Bookkeeper | Accounts and linking |
| `DELETE` | `/bookkeeper-invites/{invite_id}` | Revoke Bookkeeper Invite | Accounts and linking |
| `POST` | `/bookkeeper-invites/{token}/accept` | Accept Bookkeeper Invite | Accounts and linking |
| `GET` | `/bookkeeper/clients/{owner_id}/reports/monthly/{month}` | Bookkeeper Report | Accounts and linking |
| `GET` | `/bookkeeper/clients/{owner_id}/transactions` | Bookkeeper Ledger | Accounts and linking |
| `GET` | `/budget` | Read the effective monthly budget | Budget |
| `PUT` | `/budget` | Set a monthly budget | Budget |
| `GET` | `/budget/velocity` | Read spending velocity | Budget |
| `GET` | `/business-personal/review` | Business Personal Review | Accounts and linking |
| `PUT` | `/business-personal/transactions/{transaction_id}` | Review Transaction Use | Accounts and linking |
| `GET` | `/category-rules` | List counterparty category rules | Category rules |
| `DELETE` | `/category-rules/{rule_id}` | Delete a category rule | Category rules |
| `POST` | `/classification-corrections/{correction_id}/confirm` | Confirm Classification Correction | Accounts and linking |
| `GET` | `/consents` | List stored consents | Consents |
| `POST` | `/consents` | Create local consent | Consents |
| `DELETE` | `/consents/{consent_id}` | Revoke consent and purge linked accounts | Consents |
| `POST` | `/devices` | Register Device | Notifications |
| `DELETE` | `/devices/{device_id}` | Unregister Device | Notifications |
| `GET` | `/forecast/safe-to-spend` | Safe To Spend Forecast | Forecast |
| `GET` | `/health` | Check API liveness | Health |
| `POST` | `/identity/bvn/verify` | Verify Bvn | Identity |
| `GET` | `/insight-alerts` | List Insight Alerts | Accounts and linking |
| `POST` | `/insight-alerts/{alert_id}/read` | Mark Insight Alert Read | Accounts and linking |
| `PUT` | `/insight-profile` | Set Insight Profile | Accounts and linking |
| `GET` | `/insights` | Insights | Insights |
| `POST` | `/insights/run` | Run Insights | Insights |
| `GET` | `/insights/{insight_id}` | Insight Detail | Insights |
| `POST` | `/insights/{insight_id}/dismiss` | Dismiss | Insights |
| `GET` | `/net-position` | Read cash and investment position | Assets |
| `GET` | `/notification-preferences` | Get Notification Preferences | Notifications |
| `PUT` | `/notification-preferences` | Put Notification Preferences | Notifications |
| `GET` | `/obligations` | List upcoming obligations | Obligations |
| `POST` | `/obligations` | Create a manual obligation | Obligations |
| `GET` | `/obligations/{obligation_id}` | Read an obligation and repayments | Obligations |
| `PATCH` | `/obligations/{obligation_id}` | Review or edit an obligation | Obligations |
| `POST` | `/onboarding/bvn/confirm` | Confirm BVN discovery | Onboarding |
| `POST` | `/onboarding/bvn/send-otp` | Send Mono consent OTP | Onboarding |
| `POST` | `/onboarding/bvn/start` | Start BVN bank-account discovery | Onboarding |
| `GET` | `/plan` | Read plan and entitlements | Accounts and linking |
| `GET` | `/privacy-preferences` | Get Privacy Preferences | Consents |
| `PUT` | `/privacy-preferences` | Put Privacy Preferences | Consents |
| `GET` | `/privacy/consents` | List active read-only links | Accounts and linking |
| `POST` | `/privacy/wipe` | Revoke all access and wipe user data | Accounts and linking |
| `GET` | `/recurring` | Recurring | Recurring |
| `GET` | `/report-share-links` | List Report Share Links | Accounts and linking |
| `DELETE` | `/report-share-links/{link_id}` | Revoke Report Share Link | Accounts and linking |
| `GET` | `/reports/monthly/{month}` | Monthly Report | Accounts and linking |
| `GET` | `/reports/monthly/{month}/export` | Export Monthly Report | Accounts and linking |
| `POST` | `/reports/monthly/{month}/share-links` | Create Report Share Link | Accounts and linking |
| `PATCH` | `/settings/ai` | Set Ai Preference | AI |
| `GET` | `/shared/reports/{token}` | Shared Report | Accounts and linking |
| `GET` | `/shared/reports/{token}/export` | Export Shared Report | Accounts and linking |
| `POST` | `/statements/upload` | Upload Statement | Sync and statements |
| `GET` | `/summary/categories` | Category Summary | Summary |
| `GET` | `/summary/monthly` | Monthly Summary | Summary |
| `GET` | `/summary/overview` | Summary | Summary |
| `POST` | `/sync` | Sync eligible linked accounts | Sync and statements |
| `GET` | `/transactions` | List filtered transactions | Transactions |
| `GET` | `/transactions/recent` | Read recent cross-account activity | Transactions |
| `PATCH` | `/transactions/{transaction_id}/category` | Reclassify a transaction | Transactions |
| `GET` | `/transfer-suggestions` | List Suggestions | Accounts and linking |
| `POST` | `/transfer-suggestions/{suggestion_id}/{action}` | Review Suggestion | Accounts and linking |
| `POST` | `/webhooks/mono` | Receive verified Mono events | Webhooks |
<!-- GENERATED ENDPOINTS END -->
