This is the verified list of important omissions and shortcuts in the current cashlens repository. It is for judges, maintainers and production reviewers.
Each item includes a practical next step; none is represented as a completed security or compliance guarantee.

# Known gaps

1. **Mobile is not KMP yet.** The visible application is an Android app module; the `composeApp` directory is not configured or included as a Kotlin Multiplatform target. The AI settings and chat screens are not implemented or live-wired. Next: migrate the app to a configured KMP shared Compose target, then implement auth, settings, chat, insight wording controls and consent refresh in shared UI.
2. **AI golden evaluation is missing.** `make ai-eval` currently runs fake-client safety tests, not the requested 20 questions per persona. No real OpenRouter model has been called or evaluated. Next: build synthetic persona ledger fixtures and score tool accuracy, fact match, verification failures, usage and cost across at least three model slugs.
3. **AI provider behavior is unit-tested, not live-tested.** The OpenRouter adapter request is tested with a local HTTP mock. Privacy routing, account-level privacy controls, data residency, pricing and model fallback availability must be checked against the configured account before any real customer data is sent.
4. **AI budget and rate controls are not distributed.** Token totals use audit rows, while the per-minute rate limiter is process-local. Concurrent requests can pass a budget check before either writes its audit. Next: use an atomic shared limiter and reserve budget before model calls.
5. **OpenAPI metadata is improved but incomplete.** Routes receive summaries, descriptions, stable IDs and journey tags. Several request/response fields lack descriptions and explicit examples; error shapes are FastAPI-generated and are not unified. The identity request must include a BVN input despite broad examples of fields to omit. Next: annotate schemas endpoint by endpoint, document the sensitive input explicitly, and add an honest common error contract only alongside a behaviour change.
6. **API and mobile flow is not verified end to end.** The OpenAPI schema can be exported, but no Swagger UI click-through with a seeded authenticated user or live mobile session was performed in this work. Next: run against the configured hosted database and seeded data, then record exact responses.
7. **Database and CI checks are incomplete.** Tests ran locally, but migrations against the configured hosted database and all GitHub workflows were not run here. Next: run migrations in a non-production test database and confirm all CI jobs.
8. **AI chat keeps an owned transcript but is not a memory feature.** A conversation ID scopes persistence, but only the current user message and the current turn's tool results are supplied to the model. This avoids relying on unverified historical figures, but follow-up references such as “that amount” may not work. Next: add turn-aware context with provenance and re-verification, or disclose stateless turns in the UI.
9. **NDPA alignment is design intent only.** Retention, lawful basis, data-subject request handling, provider contracts and legal review are not complete. Do not send real customer data to a third-party model before a privacy/legal review.
10. **No certified security or operational claim is made.** Production key rotation, shared rate limiting, alerting, backups, incident response, penetration testing and operational access review remain necessary before launch.

## Related docs

- [AI boundary](ai.md)
- [Consent and privacy](consent-and-privacy.md)
- [Runbook](runbook.md)
