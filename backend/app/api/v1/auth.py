from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.auth import (
    AuthMessageResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserProfileResponse,
    VerifyEmailRequest,
)
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["1. Authentication & Session"])


@router.post("/register", response_model=AuthMessageResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Admin-only account creation; creates user and sends/generates verification email."""
    user, token = AuthService.register_user(db, payload, creator_id=current_admin.id)
    return AuthMessageResponse(
        message=f"User {user.email} registered successfully.",
        action_token=None,  # Do not expose sensitive token in HTTP response
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Email + password login returning JWT access and refresh tokens."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return AuthService.login(db, payload, ip_address=client_ip, user_agent=user_agent)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Rotate refresh token with automated token family reuse detection."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return AuthService.rotate_refresh_token(
        db, payload.refresh_token, ip_address=client_ip, user_agent=user_agent
    )


@router.post("/logout", response_model=AuthMessageResponse)
def logout(
    payload: RefreshTokenRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Revoke current refresh token."""
    AuthService.logout(db, payload.refresh_token, current_user.id)
    return AuthMessageResponse(message="Successfully logged out.")


@router.post("/logout-all", response_model=AuthMessageResponse)
def logout_all(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Revoke all sessions for current user."""
    revoked = AuthService.logout_all(db, current_user.id)
    return AuthMessageResponse(message=f"All sessions ({revoked}) successfully revoked.")


@router.post("/verify-email", response_model=AuthMessageResponse)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Consume UserActionToken to verify account email."""
    user = AuthService.verify_email(db, payload.token)
    return AuthMessageResponse(message=f"Email for {user.email} successfully verified.")


@router.post("/forgot-password", response_model=AuthMessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Initiate password reset flow; returns reset token."""
    token = AuthService.forgot_password(db, payload.email)
    return AuthMessageResponse(
        message="If the email is registered, password reset instructions have been generated.",
        action_token=None,  # Do not expose sensitive token in HTTP response
    )


@router.post("/reset-password", response_model=AuthMessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Consume reset token and update user password."""
    user = AuthService.reset_password(db, payload)
    return AuthMessageResponse(message=f"Password for {user.email} successfully reset.")


@router.post("/change-password", response_model=AuthMessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Authenticated user password change."""
    AuthService.change_password(db, current_user, payload)
    return AuthMessageResponse(message="Password successfully changed.")


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Current user profile, role, and custom permissions."""
    permissions = current_user.custom_permissions_json if isinstance(current_user.custom_permissions_json, list) else []
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        email_verified_at=current_user.email_verified_at,
        custom_permissions=permissions,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )
