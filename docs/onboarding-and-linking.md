# Onboarding and linking

The current BVN Lookup flow uses Mono’s three documented Lookup endpoints. `POST /onboarding/bvn/start` validates an 11-digit BVN, initiates `bank_accounts` lookup, stores only the Mono session metadata, and returns method hints. Send-OTP and confirm call Mono verify/details; discovered account numbers are encrypted and responses contain last four digits only.

The Connect flow supports account selection (`POST /accounts/discovered/select`), skipped-account retrieval (`GET /accounts/skipped`), and hosted linking from selected or skipped rows. The backend requests Mono bank coverage and matches exact bank or NIP codes. If there is no unique match with one auth method, it omits the institution so the user selects a bank on Mono's hosted page. Coverage is cached in process for one hour. Optional account matching is off by default. The `account_connected` webhook marks a discovered row linked but does not fetch data; `account_updated` triggers transaction sync only when its status and `retrieved_data` permit it. This path has mocked tests, not a live Mono verification.

| Method | Path | Purpose |
|---|---|---|
| POST | `/v2/lookup/bvn/initiate` | Start BVN bank-account consent. |
| POST | `/v2/lookup/bvn/verify` | Request OTP through selected method. |
| POST | `/v2/lookup/bvn/details` | Fetch discovered bank accounts. |
| POST | `/v2/accounts/initiate` | Start Connect hosted linking. |
| GET | `/v3/institutions?scope=financial_data` | Resolve exact institution code and auth method. |
| POST | `/v2/accounts/auth` | Exchange Connect code. |
| GET | `/v2/accounts/{id}` | Read account details. |
| GET | `/v2/accounts/{id}/balance` | Request balance data, including real-time sync. |
| GET | `/v2/accounts/{id}/transactions` | Read transactions. |
| POST | `/v2/accounts/{id}/unlink` | Unlink a Mono account. |

The BVN documentation states that non-200 Lookup requests are not charged and sessions expire after ten minutes. Mono says optional account matching costs NGN 5 per match. See [Mono BVN Lookup](https://docs.mono.co/docs/lookup/bvn-igree), [Connect Link](https://docs.mono.co/docs/financial-data/connect-link), and [bank coverage](https://docs.mono.co/api/miscellaneous/bank-coverage).
