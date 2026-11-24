from __future__ import annotations

from typing import Annotated, Generator, Sequence
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.app.core.security import decode_access_token
from backend.app.database.session import get_db
from backend.app.models.schema import User, UserRole

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise AuthenticationError("Authentication token is missing.")
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Token payload is missing subject.")
    except Exception:
        raise AuthenticationError("Token is invalid or expired.")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise AuthenticationError("User not found.")
    if not user.is_active:
        raise PermissionDeniedError("User account is deactivated.")
    return user


def require_roles(*allowed_roles: UserRole):
    def role_checker(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        if current_user.role == UserRole.ADMIN:
            return current_user  # Admin has access to all protected endpoints
        if current_user.role not in allowed_roles:
            raise PermissionDeniedError(
                f"Operation requires one of the following roles: {[r.value for r in allowed_roles]}."
            )
        return current_user
    return role_checker


def require_worker_token(
    x_worker_token: Annotated[str | None, Header(alias="X-Worker-Token")] = None,
) -> str:
    if not x_worker_token or x_worker_token != settings.WORKER_SECRET_TOKEN:
        raise PermissionDeniedError("Valid X-Worker-Token header is required.")
    return x_worker_token


def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key
