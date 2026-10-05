# Progress

- [x] Repository skeleton and root tooling
- [x] Backend core and migration scaffolding (PostgreSQL migration execution unverified locally)
- [x] Ledger, providers, and recurring detection (in-memory integration verified)
- [x] Deterministic seed personas (all three produce their expected insight kinds)
- [ ] Twelve detectors and tests (all registered; per-detector trigger/near-miss/insufficient-data matrix incomplete)
- [ ] GitHub automation
- [ ] Android application
- [ ] Final verification

Verification without Docker: backend Ruff, mypy, and pytest pass (10 tests). PostgreSQL migration, live Mono sandbox, and mobile build are not yet verified. No Docker command will be used for this project.
