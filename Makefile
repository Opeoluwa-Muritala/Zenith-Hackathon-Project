.PHONY: setup dev-up dev-down migrate seed api mobile-build mobile-test test lint openapi reset-db
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
	cd mobile && gradlew.bat assembleDebug
mobile-test:
	cd mobile && gradlew.bat test
test:
	cd backend && uv run pytest --cov=app.insights --cov-fail-under=85
	cd mobile && gradlew.bat test
lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd mobile && gradlew.bat ktlintCheck
openapi:
	cd backend && uv run python -m scripts.export_openapi
reset-db:
	docker compose down -v
	docker compose up -d
	$(MAKE) migrate seed
