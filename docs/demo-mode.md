# Demo mode

The developer test page is `/dev/mono-test`, excluded from OpenAPI and served only to loopback clients outside production. For local OTP testing, explicitly set `OTP_SENDER=dev_inbox` and `OTP_DEV_INBOX_ENABLED=true`; `/dev/otp-inbox?identifier=...` is a loopback-only, development-only route excluded from OpenAPI. The test page fetches the generated code from that inbox after requesting it. This is not a customer flow and must never be enabled with real users or production data.

## Hosted presenter inbox

Set `DEMO_MODE=true`, `OTP_SENDER=dev_inbox`, `OTP_DEV_INBOX_ENABLED=true`, and `DEMO_IDENTIFIERS` to comma-separated canonical E.164 phones or lowercase emails used only for the demo. Configure `DEMO_OTP_INBOX_PASSWORD` (at least 16 characters), `JWT_SECRET`, `OTP_SECRET`, and `FIELD_ENCRYPTION_KEY` through environment secrets. Demo mode refuses production startup.

Open `/dev/otp-inbox/page` over HTTPS and authenticate as `demo` with the configured password. Request a login code from the mobile app, choose that identifier on the page, and refresh to see the generated code. It expires according to `OTP_EXPIRY_SECONDS` and disappears after successful verification. Both inbox routes are excluded from OpenAPI, password-protected in demo mode, and return no-store responses. Non-allowlisted login requests return the same sent response but do not generate codes.

Run exactly one web worker: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. The inbox lives only in memory, so restarts remove codes. Persistent OTP challenges contain hashes only. This page must never be used for real users.
