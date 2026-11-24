from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from backend.app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from backend.app.models.schema import (
    AuditLog,
    RefreshToken,
    User,
    UserActionToken,
    UserActionTokenPurpose,
    UserRole,
)
from backend.app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

settings = get_settings()


class AuthService:
    @staticmethod
    def register_user(
        db: Session,
        payload: RegisterRequest,
        creator_id: Optional[int] = None,
    ) -> tuple[User, str]:
        email = payload.email.lower().strip()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ConflictError(f"User with email '{email}' already exists.")

        user = User(
            email=email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=payload.role,
            is_active=True,
            created_by_user_id=creator_id,
            custom_permissions_json=payload.custom_permissions or [],
        )
        db.add(user)
        db.flush()

        # Generate email verification action token
        raw_token = generate_secure_token()
        action_token = UserActionToken(
            user_id=user.id,
            purpose=UserActionTokenPurpose.EMAIL_VERIFICATION,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.ACTION_TOKEN_EXPIRE_HOURS),
        )
        db.add(action_token)

        # Audit log
        db.add(AuditLog(
            user_id=creator_id or user.id,
            action="USER_REGISTERED",
            entity_type="users",
            entity_id=str(user.id),
            details_json={"email": email, "role": payload.role.value},
        ))
        db.commit()
        db.refresh(user)
        return user, raw_token

    @staticmethod
    def login(
        db: Session,
        payload: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        email = payload.email.lower().strip()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise AuthenticationError("Invalid email or password.")

        # Check account lockout
        now = datetime.now(timezone.utc)
        if user.locked_until and user.locked_until > now:
            raise PermissionDeniedError(
                f"Account is temporarily locked until {user.locked_until.isoformat()} due to failed login attempts."
            )

        if not verify_password(payload.password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                db.add(AuditLog(
                    user_id=user.id,
                    action="USER_LOCKED_OUT",
                    entity_type="users",
                    entity_id=str(user.id),
                    details_json={"failed_attempts": user.failed_login_attempts},
                    ip_address=ip_address,
                ))
            db.commit()
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise PermissionDeniedError("Account is inactive.")

        # Successful login: reset lockouts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now

        # Generate tokens
        permissions = user.custom_permissions_json if isinstance(user.custom_permissions_json, list) else []
        access_token = create_access_token(
            subject=user.id,
            role=user.role.value,
            permissions=permissions,
        )

        raw_refresh_token = generate_secure_token()
        token_family = uuid.uuid4().hex
        db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            token_family_id=token_family,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(db_refresh_token)

        db.add(AuditLog(
            user_id=user.id,
            action="USER_LOGGED_IN",
            entity_type="users",
            entity_id=str(user.id),
            ip_address=ip_address,
        ))
        db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def rotate_refresh_token(
        db: Session,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        t_hash = hash_token(raw_refresh_token)
        token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == t_hash).first()

        if not token_record:
            raise AuthenticationError("Invalid refresh token.")

        now = datetime.now(timezone.utc)

        # Token Reuse Detection: if already revoked, revoke the whole family!
        if token_record.revoked_at is not None:
            db.query(RefreshToken).filter(
                RefreshToken.token_family_id == token_record.token_family_id,
                RefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": now})
            db.add(AuditLog(
                user_id=token_record.user_id,
                action="REFRESH_TOKEN_REUSE_DETECTED",
                entity_type="refresh_tokens",
                entity_id=str(token_record.id),
                details_json={"token_family_id": token_record.token_family_id},
                ip_address=ip_address,
            ))
            db.commit()
            raise AuthenticationError("Revoked refresh token presented. Security alert: entire session family terminated.")

        if token_record.expires_at < now:
            raise AuthenticationError("Refresh token has expired.")

        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user or not user.is_active:
            raise PermissionDeniedError("User account is inactive or not found.")

        # Revoke old token
        token_record.revoked_at = now

        # Create new rotated token in same family
        new_raw_token = generate_secure_token()
        new_token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_raw_token),
            token_family_id=token_record.token_family_id,
            replaced_by_token_id=token_record.id,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_token_record)

        permissions = user.custom_permissions_json if isinstance(user.custom_permissions_json, list) else []
        new_access_token = create_access_token(
            subject=user.id,
            role=user.role.value,
            permissions=permissions,
        )
        db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_raw_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def logout(db: Session, raw_refresh_token: str, user_id: int) -> None:
        t_hash = hash_token(raw_refresh_token)
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token_hash == t_hash,
            RefreshToken.user_id == user_id,
        ).first()
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def logout_all(db: Session, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})
        db.add(AuditLog(
            user_id=user_id,
            action="USER_LOGGED_OUT_ALL_SESSIONS",
            entity_type="users",
            entity_id=str(user_id),
            details_json={"revoked_sessions": count},
        ))
        db.commit()
        return count

    @staticmethod
    def verify_email(db: Session, raw_token: str) -> User:
        t_hash = hash_token(raw_token)
        action_token = db.query(UserActionToken).filter(
            UserActionToken.token_hash == t_hash,
            UserActionToken.purpose == UserActionTokenPurpose.EMAIL_VERIFICATION,
        ).first()

        if not action_token:
            raise AuthenticationError("Invalid email verification token.")

        now = datetime.now(timezone.utc)
        if action_token.used_at is not None:
            raise ConflictError("Verification token has already been consumed.")
        if action_token.expires_at < now:
            raise AuthenticationError("Verification token has expired.")

        user = db.query(User).filter(User.id == action_token.user_id).first()
        if not user:
            raise EntityNotFoundError("User", action_token.user_id)

        action_token.used_at = now
        user.email_verified_at = now
        db.add(AuditLog(
            user_id=user.id,
            action="EMAIL_VERIFIED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def forgot_password(db: Session, email: str) -> Optional[str]:
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        if not user:
            return None  # Return None to avoid user enumeration

        raw_token = generate_secure_token()
        action_token = UserActionToken(
            user_id=user.id,
            purpose=UserActionTokenPurpose.PASSWORD_RESET,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db.add(action_token)
        db.add(AuditLog(
            user_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        return raw_token

    @staticmethod
    def reset_password(db: Session, payload: ResetPasswordRequest) -> User:
        t_hash = hash_token(payload.token)
        action_token = db.query(UserActionToken).filter(
            UserActionToken.token_hash == t_hash,
            UserActionToken.purpose == UserActionTokenPurpose.PASSWORD_RESET,
        ).first()

        if not action_token:
            raise AuthenticationError("Invalid or expired password reset token.")

        now = datetime.now(timezone.utc)
        if action_token.used_at is not None:
            raise ConflictError("Password reset token has already been consumed.")
        if action_token.expires_at < now:
            raise AuthenticationError("Password reset token has expired.")

        user = db.query(User).filter(User.id == action_token.user_id).first()
        if not user:
            raise EntityNotFoundError("User", action_token.user_id)

        action_token.used_at = now
        user.hashed_password = hash_password(payload.new_password)
        user.password_changed_at = now
        user.failed_login_attempts = 0
        user.locked_until = None

        # Revoke all existing sessions for security
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})

        db.add(AuditLog(
            user_id=user.id,
            action="PASSWORD_RESET_COMPLETED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, payload: ChangePasswordRequest) -> None:
        if not verify_password(payload.old_password, user.hashed_password):
            raise AuthenticationError("Current password incorrect.")

        now = datetime.now(timezone.utc)
        user.hashed_password = hash_password(payload.new_password)
        user.password_changed_at = now

        # Revoke other sessions
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})

        db.add(AuditLog(
            user_id=user.id,
            action="PASSWORD_CHANGED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
