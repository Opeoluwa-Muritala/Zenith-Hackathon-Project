import hashlib
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


def hash_secret(value: str, salt: str = "") -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_minutes),
            "jti": secrets.token_hex(16),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access(token: str) -> UUID:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid or expired access token") from exc


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    user = await db.get(User, decode_access(credentials.credentials))
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


def new_refresh() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_secret(raw)
