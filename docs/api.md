# API reference

This page points developers to the generated API contract. Last verified against `backend/app/main.py` and `backend/app/ai/chat/router.py`.

The current route list, request schemas and responses are in [OpenAPI JSON](api/openapi.json). Client conventions are in the [API guide](api-guide.md). Swagger UI is `/docs` and ReDoc is `/redoc` in development; production exposure depends on `API_DOCS_ENABLED`.

Protected routes use an app-issued Bearer access token. Request a random OTP with `POST /auth/otp/request`, then exchange the delivered code at `POST /auth/otp/verify`. There is no fixed development OTP. Amounts ending in `_minor` are integer minor units; UTC timestamps use ISO 8601. Error responses currently follow FastAPI's `detail` conventions rather than one universal envelope.
