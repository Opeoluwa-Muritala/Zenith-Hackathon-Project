# cashlens

Consent-first personal finance aggregation for the Zenith Bank hackathon. BVN is used only for identity matching; transactions arrive through provider interfaces.

## Five-minute quickstart

Requirements: Python 3.12, `uv`, an existing PostgreSQL database, JDK 17, and Android Studio. This quickstart does not use Docker. Put your existing `DATABASE_URL` and sandbox Mono settings in `backend/app/.env`; do not commit that file.

```sh
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run migrations only against the intended demo/development database after checking that it is not production data. Open `http://localhost:8000/docs` for Swagger or `http://localhost:8000/dev/mono-test` for the loopback-only Mono sandbox test panel. The development OTP defaults to `123456`. Seed phones end in `001` (salaried), `002` (freelancer), and `003` (student). Android debug uses `http://10.0.2.2:8000`.

The test panel needs a public HTTPS tunnel for Mono webhooks; see [Mono integration](docs/mono-integration.md). Mono keys stay on the backend and must never be placed in the Android app or browser code.
