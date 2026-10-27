# Contributing

Use a branch and conventional commits such as `feat: add route`, `fix: correct sync status`, `test: cover webhook replay`, and `docs: update API guide`. Run `python -m pytest tests` and `ruff check app tests alembic` before review.

For an endpoint, add schemas, route metadata, ownership checks, tests, then run `python backend/scripts/export_openapi.py` and `python backend/scripts/export_postman.py`. Generated artifacts must be committed together with their source changes.

## Documentation commands

```text
python backend/scripts/export_openapi.py
python backend/scripts/export_postman.py
python backend/scripts/gen_data_model.py
python backend/scripts/gen_config_docs.py
```

CI/tests should fail when generated artifacts are stale.

Install the dev-only OpenAPI validator with `pip install -r backend/requirements-docs.txt` into your test environment. OpenAPI export writes stable JSON and YAML; the demo journey operations use named response contracts and explicit security. Run `python -m pytest tests/test_demo_journey.py` from backend for the isolated demo flow. Never exercise Neon or Mono as part of these automated tests.

Run `python backend/scripts/check_docs.py` after editing Markdown; `backend/tests/test_generated_docs.py` checks links, secret-looking values, artifact freshness and operation coverage offline.
