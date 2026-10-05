This is the honest list of work the current repository does not yet demonstrate. It is for judges, maintainers and production reviewers.

# Known gaps

1. Mono link persistence, webhook route, idempotency and local-first unlink orchestration are not yet wired to API routes. Add `provider_links` and `webhook_events`, constant-time secret verification, and `respx` route tests.
2. `/sync`, account link endpoints, refresh, insight persistence runner and forecast route are not complete. Connect the implemented providers and detector registry through consent-filtered services.
3. Seed generation and persona integration assertions are not complete. Build deterministic six-month fixtures and assert planted detector kinds.
4. Android screens are present as an initial Compose shell but are not yet live-wired through ViewModels, Koin, auth, Custom Tabs or complete screen states. Add the Gradle wrapper before CI can build it.
5. Refresh-token exchange, rotation and reuse detection are not exposed as an endpoint. The verifier issues a hashed refresh token only.
6. Detector coverage is below the requested trigger/near-miss/insufficient matrix for every detector. Some heuristics are simplified, especially temporal buckets and typical velocity.
7. PostgreSQL migrations, quickstart, CI, Android and docs commands have not been verified end to end in a clean clone in this environment.
8. Data retention/deletion policy, production rate-limit storage, audit-log export, key management and legal review remain production work.

## Related docs

- [Architecture](architecture.md)
- [Testing](testing.md)
- [Consent and privacy](consent-and-privacy.md)
