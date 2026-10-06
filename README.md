# cashlens

Consent-first personal finance aggregation for the Zenith Bank hackathon. BVN is used only for identity matching; transactions arrive through provider interfaces.

## Five-minute quickstart

Requirements: Python 3.12, `uv`, an existing PostgreSQL database, Node.js LTS, Android Studio and an Android emulator. This quickstart does not use Docker. Put your existing `DATABASE_URL` and sandbox Mono settings in `backend/app/.env`; do not commit that file.

```sh
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run migrations only against the intended demo/development database after checking that it is not production data. Open `http://localhost:8000/docs` for Swagger or `http://localhost:8000/dev/mono-test` for the loopback-only Mono sandbox test panel. The development OTP defaults to `123456`; no SMS is sent. Seed phones end in `001` (salaried), `002` (freelancer), and `003` (student). Start the React Native app with `cd mobile; npm install; npx expo start --android`; the Android emulator uses `http://10.0.2.2:8000` by default. Set the backend port/base URL as needed in `mobile/.env`.

The test panel needs a public HTTPS tunnel for Mono webhooks; see [Mono integration](docs/mono-integration.md). Mono keys stay on the backend and must never be placed in the Android app or browser code.
