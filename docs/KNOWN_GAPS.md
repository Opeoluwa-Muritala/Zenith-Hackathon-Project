# Known gaps

This table records MVP features that are still missing or only partially implemented. Last verified against `backend/app/`, `backend/alembic/versions/`, and `backend/tests/`.

| Item | Status | Notes |
|---|---|---|
| Production OTP delivery | pending | Hosted demo uses a protected allowlisted presenter page. Generic HTTP delivery exists, but real SMS/email delivery is outside the demo verification. |
| Distributed rate limiting and lockout | partial | Redis-backed limits are used when configured, with a warned process-local fallback. OTP identifier lockout is durable; IP limits remain rate-limit-window based. |
| Authentication audit events | partial | Metadata-only OTP request, login failure, login, logout and logout-all events are append-only. Lookup/link/unlink/wipe/rule audit events land in their owning phases. |
| Mono BVN discovery and hosted account linking | partial | Full mocked HTTP journey passes, including selectable discovery IDs and link/account status. Live sandbox delivery and coverage remain unverified. |
| Account match | partial | Optional chargeable match is off by default; mismatches stop sync but are not automatically unlinked. |
| Account categories and grouped totals | partial | Grouped totals separate currencies; mapping includes a few known names and fictional fixture banks. Unknown names are flagged. Broader coverage is pending. |
| Balance freshness | partial | List/detail/refresh share freshness fields. Real-time job headers prevent cached processing data from looking fresh. Mono cooldown is at least five minutes; durable job tracking and reauthorisation are pending. Ledger balance stays null. |
| Single-account unlink | partial | Account unlink and consent revoke purge linked local data before attempting Mono unlink; the scheduler retries durable `pending_unlink` records. Live Mono unlink remains unverified. |
| Manual assets and FX | partial | CRUD, write-time rate, generic HTTP rate source, cache and reminder scheduling exist; no live FX provider is configured. |
| Transaction enrichment | partial | Format parsing, merchant aliases, seven category labels, user-rule priority and unchanged raw narration exist. Wider merchant coverage is pending. |
| Transaction analytics | partial | Direction filter, recent feed, spending periods and reclassification exist; own-account transfers cannot yet be identified reliably and account display names are not stored. |
| Budget | partial | Monthly limit, velocity and scheduled overspending alerts exist; category-specific budgets remain outside MVP. |
| Obligations | partial | Detected lender debits, historical payment matching, manual review and scheduled reminders exist; bank mandate data is unavailable. |
| Push notifications and scheduler | partial | FCM adapter, duplicate-safe log, invalid-token handling and seven locked jobs exist. Live FCM credentials and delivery remain unverified. |
| Consent wipe | pending | No complete user wipe endpoint. Pending remote unlinks are persisted and retried by the worker. |
| Privacy retention and NDPA operations | pending | No raw-narration retention enforcement, DPIA or operational subject-rights workflow. |
| OpenAPI and Postman detail | partial | Demo operations have named responses, explicit security and documented errors. JSON/YAML standard validation and drift checks pass; Postman covers each operation. Other legacy operation modelling and actual Postman-app import remain pending. |
| Webhook recovery | partial | Failed or abandoned processing can retry on redelivery. Event bodies are not retained, so receipt acknowledged before a crash still needs external redelivery/manual recovery; no worker exists. |
| PostgreSQL migration execution | partial | The configured Neon database upgraded through Phase 7 revision 0022 online; Phase 4–7 tables passed rollback-only PostgreSQL smoke inserts. Fresh-database upgrade and full-chain downgrades remain unverified. Revision 0001 still uses current model metadata, and several historical revisions skip offline work. |
| Live Neon and sandbox checks | partial | Neon connectivity, revision and migrated schema were verified. Mono sandbox balances, webhook delivery and charges were not exercised. |
| Derived field key rotation | partial | Neon provider IDs use a key derived from the existing Mono secret. Preserve that secret or the derived key under `mono_derived_v1` before rotating Mono credentials; a dedicated field key is preferable. |
