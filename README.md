# cashlens

Consent-first personal finance aggregation for the Zenith Bank hackathon. BVN is used only for identity matching; transactions arrive through provider interfaces.

## Five-minute quickstart

Requirements: Docker, Python 3.12, `uv`, JDK 17, and Android Studio.

```sh
cp .env.example .env
make setup
make dev-up
make migrate
make seed
make api
```

Open `http://localhost:8000/docs`. The development OTP is `123456`. Seed phones end in `001` (salaried), `002` (freelancer), and `003` (student). Run `make mobile-build`; Android debug uses `http://10.0.2.2:8000`.
