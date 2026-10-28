# Postman

Import `fetch.postman_collection.json` and either the local or staging environment. Set `base_url`; access and refresh tokens begin empty and are saved by successful OTP verification and refresh requests. The collection uses Bearer auth by default and disables it on public operations. Example bodies are generated from OpenAPI schemas and use placeholders; review and replace them with authorised test-only values before sending. The webhook request lives in a separate manual-testing folder and needs a configured test `mono-webhook-secret` header.

For a first login, run `GET /health`, `POST /auth/otp/request`, retrieve the code through your configured sender (or local development inbox), then `POST /auth/otp/verify`. For a first discovered-account link, run the three `/onboarding/bvn/*` requests, select discovered IDs, and call the discovered-account link request. Open the returned Mono URL and wait for the two webhook stages; the Postman collection does not complete hosted bank login. No live Mono calls are needed to import or inspect the collection.

For the hosted mobile demo, use the [backend walkthrough](../../demo-backend-walkthrough.md) and its password-protected presenter page for the app login OTP. Set collection variables `otp_code` and `test_bvn` only while running authorised sandbox requests; committed values are empty. Mono's BVN consent OTP comes from Mono's selected delivery method, not the presenter inbox.

The collection captures Lookup `session_id`, first discovered `row_id`, link `link_ref`, linked `account_id`, first `transaction_id`, and created asset/consent/obligation/device IDs. Review selection if more than the first discovered row should be linked. Optional query filters are disabled initially; enable the ones you need. Saved success examples are derived from response schemas, not recordings of real users. Both environments keep token variables empty and mark them secret. Import into the Postman application itself has not been verified offline.

Regenerate from the current FastAPI app:

```powershell
cd backend
python scripts/export_openapi.py
python scripts/export_postman.py
```
