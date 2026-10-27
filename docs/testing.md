# Testing

Tests live in `backend/tests/`. Run `python -m pytest tests`. Mono HTTP calls use `respx`; AI and statement tests use local fakes/fixtures. `test_openapi_quality.py` checks generated route metadata and security declarations. Database integration tests use their configured test database/SQLite setup; no live provider calls are required.

For a new route, add a named request/response model, route-level ownership/security tests, mocked provider tests where needed, and regenerate OpenAPI/Postman artifacts.

Install `backend/requirements-docs.txt` into the test environment for OpenAPI standard validation. `test_demo_journey.py` exercises the HTTP login/discovery/link/webhook/finance/logout flow with SQLite and respx, including replay handling and cached refresh failures. Presenter-inbox tests cover password checks, allowlists and expiry. Generated JSON/YAML, model/config references and Postman coverage are checked for drift. Actual Neon migrations, sandbox accounts, callback handling and provider delivery are not verified by these tests.
