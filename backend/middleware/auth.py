"""
Authentication and authorization dependencies for FastAPI routes.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.logging import get_logger
from core.security import decode_token
from models.user import User

logger = get_logger(__name__)
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return the active User row."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory requiring the authenticated user to hold one of allowed_roles."""

    async def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "authorization_denied",
                username=current_user.username,
                role=current_user.role,
                required=list(allowed_roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return current_user

    return _role_checker


async def verify_ml_or_user(
    x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    Allow either the local ML inference service (via X-ML-API-Key) or an authenticated admin/operator.
    """
    if x_ml_api_key and settings.ML_API_KEY and x_ml_api_key == settings.ML_API_KEY:
        return "ml_service"
    if x_ml_api_key and not settings.ML_API_KEY:
        # Local dev mode when ML_API_KEY is unset
        return "ml_service"
    user = await get_current_user(credentials=credentials, db=db)
    if user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    return user.username
