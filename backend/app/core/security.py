import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)
_development_jwt_secret = secrets.token_urlsafe(48)


def _jwt_secret() -> str:
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.environment == "production":
        raise RuntimeError("JWT_SECRET is required in production")
    return _development_jwt_secret


def hash_secret(value: str, salt: str = "") -> str:
    return hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()


def access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_minutes),
            "jti": secrets.token_hex(16),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def decode_access_claims(token: str) -> dict:
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "iat", "exp", "jti", "iss", "aud"]},
        )
        UUID(payload["sub"])
        return payload
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid or expired access token") from exc


def decode_access(token: str) -> UUID:
    return UUID(decode_access_claims(token)["sub"])


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    claims = decode_access_claims(credentials.credentials)
    user = await db.get(User, UUID(claims["sub"]))
    if user is None:
        raise HTTPException(401, "Authentication required")
    if user.sessions_revoked_at:
        issued = datetime.fromtimestamp(claims["iat"], UTC)
        revoked_at = user.sessions_revoked_at
        if revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=UTC)
        if issued <= revoked_at:
            raise HTTPException(401, "Session revoked")
    return user


def new_refresh() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_secret(raw)
