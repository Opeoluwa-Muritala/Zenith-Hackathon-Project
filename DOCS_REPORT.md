# Documentation status

The docs were reconciled with current backend code where changed. Generated artifacts are produced offline from the FastAPI app and SQLAlchemy/Settings metadata:

| Artifact | Regeneration command |
|---|---|
| `docs/api/openapi.json` | `python backend/scripts/export_openapi.py` |
| `docs/api/openapi.yaml` | Same export command; uses existing PyYAML. |
| `docs/api/postman/fetch.postman_collection.json` | `python backend/scripts/export_postman.py` |
| `docs/api/data-model-generated.md` | `python backend/scripts/gen_data_model.py` |
| `docs/api/config-generated.md` | `python backend/scripts/gen_config_docs.py` |

`backend/tests/test_generated_docs.py` compares all four committed artifacts to in-memory regeneration and checks each OpenAPI operation appears once in Postman. `backend/scripts/check_docs.py` checks relative links, index coverage, Mermaid keywords, selected API path/settings references and obvious secret patterns. The Postman converter is a small in-repository Python script; no Node or converter dependency was added.

Demo operations now use named Pydantic response contracts, explicit security and a shared safe error model. Their summaries describe side effects, ownership, throttles and provider calls. Postman uses those contracts for fake success examples, captures session/link/resource IDs and tokens, orders the main journey, and starts with optional query filters disabled. OpenAPI JSON/YAML parity, standard validation and operation coverage pass. Legacy operations outside the demo still have incomplete modelling; actual import into Postman was not exercised.

New dependency: `openapi-spec-validator>=0.7,<0.9`, dev-only in `backend/requirements-docs.txt`, installed as 0.8.5 to validate the generated standard. PyYAML was already present and is reused. No converter or runtime dependency was added. The most recent full suite was 77 passed; Ruff, formatting and the offline docs checker passed. PostgreSQL execution, live Mono, OTP/FX vendor delivery, Postman-app import, GitHub CI and local mypy remain unverified; see [implementation report](REPORT.md).

## Changed documentation and contradictions

- Added `docs/demo-backend-walkthrough.md` with the backend-only request sequence, protected OTP page, repeatable fixture command and explicit operator checks. Updated root README and docs index.
- Updated authentication, API guide, configuration, testing, contributing, data model, webhooks, runbook, security/privacy, Mono integration, Postman README and known gaps. Data-model generation now marks encrypted and hashed columns.
- Corrected older claims that sandbox calls are free or failed Lookup responses are not billed. The current Mono guide says failures are billable; costs remain unverified.
- Corrected loopback-only OTP guidance for the hosted presenter page while preserving local tools. The legacy Mono panel's mock BVN button is disabled in Mono mode and is not the supported discovery walkthrough.
- Corrected refresh guidance: Mono enforces a five-minute minimum and processing headers do not represent fresh balance data. Current cached, requested, synced and delayed responses are documented.
- Corrected webhook receipt/replay guidance: completed processing dedupes, failures can retry on redelivery, and a 200 receipt is not sync success. No automatic worker is claimed.
- Recorded historical migration limitations instead of implying SQL-generation success proves PostgreSQL execution. Production features outside the mobile demo are marked pending.
- CI checks install the new validator and use current artifact drift tests without a database container. These workflow edits were inspected locally, not executed on GitHub.
