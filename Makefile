.PHONY: setup dev-up dev-down migrate seed api mobile-build mobile-test test lint openapi reset-db ai-redaction-check ai-eval docs-api docs-check
setup:
	cd backend && uv sync --all-groups
dev-up:
	docker compose up -d
dev-down:
	docker compose down
migrate:
	cd backend && uv run alembic upgrade head
seed:
	cd backend && uv run python -m scripts.seed
api:
	cd backend && uv run uvicorn app.main:app --reload
mobile-build:
	cd mobile && npx expo export --platform android
mobile-test:
	cd mobile && npm test
test:
	cd backend && uv run pytest --cov=app.insights --cov-fail-under=85
	cd mobile && npm test
lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd mobile && npm run typecheck
openapi:
	cd backend && uv run python -m scripts.export_openapi
docs-api: openapi
	cd backend && uv run python ../scripts/gen_api_docs.py
ai-redaction-check:
	cd backend && uv run pytest tests/test_ai_safety.py -q
ai-eval:
	cd backend && uv run pytest tests/test_ai_safety.py -q
docs-check: docs-api
	cd backend && uv run pytest tests/test_openapi_quality.py -q
	git diff --exit-code -- backend/openapi.json docs/api.md
reset-db:
	docker compose down -v
	docker compose up -d
	$(MAKE) migrate seed
