from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    ConflictError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from backend.app.core.security import generate_secure_token, hash_password, hash_token
from backend.app.models.schema import (
    AuditLog,
    OptimizationRun,
    PurchaseOrder,
    RefreshToken,
    User,
    UserActionToken,
    UserActionTokenPurpose,
    UserRole,
)
from backend.app.schemas.user import UserCreateRequest, UserUpdateRequest


class UserService:
    @staticmethod
    def list_users(
        db: Session,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        query = db.query(User)
        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if search:
            s = f"%{search.strip().lower()}%"
            query = query.filter(or_(User.email.ilike(s), User.full_name.ilike(s)))

        total = query.count()
        users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return users, total

    @staticmethod
    def create_user(
        db: Session,
        payload: UserCreateRequest,
        creator_id: Optional[int] = None,
    ) -> User:
        email = payload.email.lower().strip()
        if db.query(User).filter(User.email == email).first():
            raise ConflictError(f"User with email '{email}' already exists.")

        user = User(
            email=email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
            created_by_user_id=creator_id,
            custom_permissions_json=payload.custom_permissions or [],
        )
        db.add(user)
        db.flush()

        db.add(AuditLog(
            user_id=creator_id or user.id,
            action="USER_CREATED_BY_ADMIN",
            entity_type="users",
            entity_id=str(user.id),
            new_value_json={"email": email, "role": payload.role.value},
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise EntityNotFoundError("User", user_id)
        return user

    @staticmethod
    def update_user(
        db: Session,
        user_id: int,
        payload: UserUpdateRequest,
        updater_id: Optional[int] = None,
    ) -> User:
        user = UserService.get_user_by_id(db, user_id)
        updated_fields = {}

        if payload.full_name is not None:
            user.full_name = payload.full_name
            updated_fields["full_name"] = payload.full_name
        if payload.role is not None:
            user.role = payload.role
            updated_fields["role"] = payload.role.value
        if payload.is_active is not None:
            user.is_active = payload.is_active
            updated_fields["is_active"] = payload.is_active
        if payload.custom_permissions is not None:
            user.custom_permissions_json = payload.custom_permissions
            updated_fields["custom_permissions"] = payload.custom_permissions

        db.add(AuditLog(
            user_id=updater_id or user.id,
            action="USER_UPDATED",
            entity_type="users",
            entity_id=str(user.id),
            new_value_json=updated_fields,
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def deactivate_user(db: Session, user_id: int, admin_id: int) -> User:
        user = UserService.get_user_by_id(db, user_id)
        user.is_active = False

        # Revoke all tokens
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.now(timezone.utc)})

        db.add(AuditLog(
            user_id=admin_id,
            action="USER_DEACTIVATED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reactivate_user(db: Session, user_id: int, admin_id: int) -> User:
        user = UserService.get_user_by_id(db, user_id)
        user.is_active = True
        db.add(AuditLog(
            user_id=admin_id,
            action="USER_REACTIVATED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def unlock_user(db: Session, user_id: int, admin_id: int) -> User:
        user = UserService.get_user_by_id(db, user_id)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.add(AuditLog(
            user_id=admin_id,
            action="USER_UNLOCKED",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def force_password_reset(db: Session, user_id: int, admin_id: int) -> str:
        user = UserService.get_user_by_id(db, user_id)
        now = datetime.now(timezone.utc)

        # Revoke all current sessions
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})

        raw_token = generate_secure_token()
        action_token = UserActionToken(
            user_id=user.id,
            purpose=UserActionTokenPurpose.PASSWORD_RESET,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(hours=24),
        )
        db.add(action_token)

        db.add(AuditLog(
            user_id=admin_id,
            action="USER_FORCE_PASSWORD_RESET",
            entity_type="users",
            entity_id=str(user.id),
        ))
        db.commit()
        return raw_token

    @staticmethod
    def delete_user(db: Session, user_id: int, admin_id: int) -> None:
        user = UserService.get_user_by_id(db, user_id)

        # Check references in business tables (PurchaseOrder, OptimizationRun)
        po_count = db.query(PurchaseOrder).filter(PurchaseOrder.ordered_by_user_id == user.id).count()
        run_count = db.query(OptimizationRun).filter(OptimizationRun.triggered_by_user_id == user.id).count()

        if po_count > 0 or run_count > 0:
            raise ConflictError(
                f"Cannot delete user {user_id}: user is referenced by {po_count} purchase orders and {run_count} optimization runs. Use deactivation instead."
            )

        db.add(AuditLog(
            user_id=admin_id,
            action="USER_HARD_DELETED",
            entity_type="users",
            entity_id=str(user.id),
            new_value_json={"email": user.email},
        ))
        db.delete(user)
        db.commit()
