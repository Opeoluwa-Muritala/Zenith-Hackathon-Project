# Fetch backend demo implementation report

This report records code and checks performed in this workspace. The target is the mobile app backend using the user's existing Neon database and Mono sandbox configuration. No database server/container was started and no live provider was called. Neon was upgraded from revision 0003 to 0012 on 2026-10-14. The [demo walkthrough](docs/demo-backend-walkthrough.md) is the operational handoff.

| Phase | Status | Evidence / remaining work |
|---|---|---|
| 0 — verify | Partial | Test suite and offline migration SQL generated; the existing Neon database was later migrated online from 0003 to 0012. |
| 1 — security | Demo implemented | Protected allowlisted presenter inbox, active expiry, one-use hashed OTPs, configured-key validation, safe errors and owner-scoped logout exist. Redis, audit events and durable lockout are pending. |
| 2 — schema | Partial | Existing Neon schema upgraded from 0003 to 0012; revision 0004 was corrected to create PostgreSQL enum types before adding columns. Revision 0009 encrypted four populated provider IDs using a key derived from the configured Mono secret. Fresh-database and downgrade paths remain unverified. Notification logs/job runs are pending. |
| 3 — BVN discovery | Mocked journey verified | Confirmation returns selectable IDs; completed results can be reused; ownership/expiry checks and stored cooldowns cover paid attempts. Lookup is attempted once and errors omit secrets. Live behaviour remains unverified. |
| 4 — hosted linking | Mocked journey verified | Existing selection/hosted flow preserved, bank/NIP matching retained, status includes local account_id, and connection/update/replay sequencing is tested. Failed events can retry on redelivery; live coverage and matching remain unverified. |
| 5 — accounts | Demo implemented | Shared freshness, grouped currency-safe totals, pause/resume and cached refresh failures exist. Real-time headers distinguish processing/no-new-data from successful updates. Mono refresh enforces at least five minutes. Unlink retries and broad category coverage are pending. |
| 6 — assets/FX | Partial | CRUD, configured generic HTTP FX source, six-hour cache, explicit client rate fallback, reminder timestamps and net position added. No reminder worker or verified live rate provider. |
| 7 — transactions | Demo implemented | Narration parser, alias file, seven category labels, user-rule priority, untouched raw narration and legacy insight compatibility exist. Pagination is bounded and readiness requires retrieved_data. Own-transfer detection is pending. |
| 8 — budget/obligations | Partial | Monthly budget and velocity endpoints reuse the detector's projection helper. Named-lender recurring obligations, manual creation, review and payment matching exist; generic direct debits and reminders are absent. |
| 9 — notifications/scheduling | Partial | Encrypted device registration and preference endpoints exist; no FCM provider or dedicated worker. |
| 10 — consent/wipe | Partial | Consent revoke now purges linked account data and persists failed remote unlinks; complete wipe and automatic retry remain absent. |
| 11 — tests/docs | Demo verified offline | Named demo response models, explicit security, errors, generated JSON/YAML and Postman, standard validation, drift tests and an HTTP journey exist. Legacy endpoints and Postman-app import remain pending. |

## Verification

- Latest full suite: **79 passed**, four FastAPI `on_event` deprecation warnings. OpenAPI standard validation is included in the passing suite. Ruff, formatter and documentation drift/link checks pass.
- Alembic one head at `0012`; offline upgrade and downgrade SQL both generated successfully. The existing Neon database upgraded online from `0003` to `0012`. Fresh-database and downgrade execution remain unverified.
- Neon migration and encrypted-ID integrity were verified online. No live Mono, OTP sender, FX provider or push provider was exercised.

## Mono documentation findings

- [BVN Lookup](https://docs.mono.co/docs/lookup/bvn-igree) documents a ten-minute session and states that requests, including failures, are billable. This corrects the earlier report's contrary statement. No sandbox cost claim has been verified.
- [Connect Link](https://docs.mono.co/docs/financial-data/connect-link) uses `scope: auth`, `meta.ref`, an optional institution, and account-match result in `account_updated`. Matching is stated as NGN 5 per match.
- [Bank coverage](https://docs.mono.co/api/miscellaneous/bank-coverage) uses `GET /v3/institutions`; its published sample in the [integration guide](https://docs.mono.co/docs/financial-data/partners-api-guide/integration-guide) includes `nip_code` but not always `bank_code`. The code matches only exact unique bank or NIP codes and otherwise leaves institution selection to Mono. The actual unmapped-bank list is not verifiable without a live coverage response.
- [Account details](https://docs.mono.co/api/bank-data/accounts/details) documents NGN KOBO; the [balance endpoint](https://docs.mono.co/api/bank-data/accounts/account-balance) exposes one `balance` field, not separate available/ledger balances. Ledger balance remains null.
- [Real-time data](https://docs.mono.co/docs/financial-data/realtime-data) uses x-realtime, job-status/new-data headers and a five-minute interval. These headers now control refresh responses. The older [transactions reference](https://docs.mono.co/api/bank-data/transactions) mentions x-real-time; the newer real-time guide is followed. Job-update webhook tracking and reauthorisation remain pending.
- [Webhooks](https://docs.mono.co/docs/webhooks) use a shared-secret header. No signature scheme was added.

## Dependencies

The only newly declared dependency is dev-only `openapi-spec-validator>=0.7,<0.9` in `backend/requirements-docs.txt` for standard OpenAPI validation; version 0.8.5 was installed. Its installed transitive dependencies were jsonschema, jsonschema-path, jsonschema-specifications, referencing, rpds-py, attrs, lazy-object-proxy, openapi-schema-validator, pathable and rfc3339-validator. No runtime dependency was added. PyYAML was already installed/dependent on uvicorn and is reused for YAML export. cryptography, respx and aiosqlite were already present.

## Demo-specific decisions and deviations

- The mobile app and existing Mono onboarding were preserved. No runtime mock replacement or mobile UI was implemented.
- The presenter page is password-protected, allowlisted, no-store and production-disabled. It displays only app login codes, not Mono consent OTPs. One worker is required; no plaintext codes are written to the database or logs.
- The proposed 60-second sandbox refresh setting was corrected to 300 seconds after reading Mono's newer guide. Shorter settings remain usable for mock fixtures; Mono requests always have the five-minute minimum.
- Demo supplementation adds missing budget/assets/manual obligation records only, preserves edits, and stores a fictional FX rate on the sample asset without polluting the shared rate cache. It was tested on SQLite, not run against Neon.
- Related correctness fixes: family-less logout is owner-scoped, unexpected failures are generic JSON, missing data readiness no longer defaults to transactions being available, and foreign linked currencies are excluded from NGN analytics/budget/net-position totals.
- Backend CI no longer starts a PostgreSQL container and uses offline migration generation. Documentation checks now target current generated artifacts and install the dev-only validator. GitHub execution itself was not run.
- SMS/email vendor selection, live FX provider selection and production infrastructure are pending because the demo uses the presenter inbox and explicitly supplied sample rates.

## Not verified

Fresh PostgreSQL upgrade and downgrade; real Mono Lookup/Connect/account matching, actual sandbox balances and charges, live webhook delivery; mobile callback/UI integration; push or delivery vendors; actual Postman-application import; GitHub CI execution. Local mypy could not run because the virtualenv launcher was inaccessible and the active interpreter has no mypy module. No type-check success is claimed.

The legacy initial migration imports current model metadata and several subsequent revisions skip offline operations. The online 0003-to-0012 path succeeded on the existing Neon database; that does not establish a reversible or executable fresh-database history. The 0009 offline guard refuses to discard populated identifiers because Python encryption/decryption is required online.

## Remaining security and compliance risks

Demo inbox access is intentionally restricted to fictional allowlisted identities and one worker. Rate limits remain process-local. Remote unlink failures are persisted but not automatically retried. Webhook payloads are not retained, so a crash after receipt needs redelivery or manual recovery even though failure states are recorded. Narration retention, complete wipe and operational NDPA controls are pending. The four migrated provider IDs depend on preserving the configured Mono secret or its derived field key across credential rotation. See [Known gaps](docs/KNOWN_GAPS.md).

## Neon migration verification (2026-10-14)

- Before migration, Alembic reported `0003`; Neon contained six provider links, four with provider account IDs, and no duplicate user emails. Revision 0007's discovered-account table did not yet exist, so its data-preservation guard was not triggered.
- The first online upgrade failed at revision 0004 because PostgreSQL enum types had not been created. Neon still reported `0003` afterward. Revision 0004 now creates those types before adding columns; the retry exited successfully.
- Alembic now reports `0012 (head)`. All four populated provider IDs are ciphertext, decrypt successfully with the derived key, and match their stored hashes. The plaintext provider ID column is absent. Expected new tables and webhook processing columns are present.
- The key is derived with HKDF from the existing `MONO_SECRET_KEY` and marked `mono_derived_v1`. No key or account ID was printed, saved in the report, or sent to a provider. This couples decryption to retaining that Mono secret; a later credential rotation needs the derived key in `FIELD_ENCRYPTION_PREVIOUS_KEYS` or a deliberate re-encryption plan.
