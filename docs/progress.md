# Progress

## Current implementation stage

- [x] Inventory existing detector, explainer, API, chat, model, migration and mobile surfaces before changes.
- [x] AI safety base: OpenRouter-compatible client, fake client, allow-list redaction, fidelity verifier, budgets and metadata audit.
- [x] Opt-in AI wording and aggregate-only Ask Your Money API using existing conversation tables.
- [ ] AI mobile settings and chat surface (React Native conversion does not include AI UI; see `docs/KNOWN_GAPS.md`).
- [x] Swagger/OpenAPI metadata and operation-quality checks; field examples/error model remain incomplete.
- [x] Loopback-only Mono sandbox test panel in HTML/CSS with in-memory auth, hosted-link polling, sync, consent revoke and CSP.
- [x] AI/API documentation and explicit known gaps.
- [ ] Install React Native dependencies, run Expo typecheck/bundle, check migrations and mobile CI.

- [x] Repository skeleton and root tooling
- [x] Backend core and migration scaffolding (PostgreSQL migration execution unverified locally)
- [x] Ledger, providers, and recurring detection (in-memory integration verified)
- [x] Deterministic seed personas (all three produce their expected insight kinds)
- [ ] Twelve detectors and tests (all registered; per-detector trigger/near-miss/insufficient-data matrix incomplete)
- [ ] GitHub automation
- [x] React Native mobile shell and API-backed screens (build not yet verified)
- [ ] Final verification

Verification without Docker: backend lint, format, mypy and 23 tests pass. The local test page returned HTTP 200 with no-store/CSP headers; loopback and remote-host guards are tested. OpenRouter and Mono were not called. PostgreSQL migrations, a real sandbox link/webhook, React Native dependency install/build, visual device review and CI remain unverified. No Docker command will be used for this project.
