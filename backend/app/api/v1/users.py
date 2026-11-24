from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import PermissionDeniedError
from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.user import (
    UserCreateRequest,
    UserDetailResponse,
    UserListResponse,
    UserUpdateRequest,
)
from backend.app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["2. User Management"])


@router.get("", response_model=UserListResponse)
def list_users(
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List users with filtering by role, status, search term, and pagination."""
    users, total = UserService.list_users(
        db, role=role, is_active=is_active, search=search, page=page, page_size=page_size
    )
    items = []
    for u in users:
        perms = u.custom_permissions_json if isinstance(u.custom_permissions_json, list) else []
        items.append(UserDetailResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            email_verified_at=u.email_verified_at,
            custom_permissions=perms,
            failed_login_attempts=u.failed_login_attempts,
            locked_until=u.locked_until,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
        ))
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a user with explicit role and settings (Admin only)."""
    user = UserService.create_user(db, payload, creator_id=current_admin.id)
    perms = user.custom_permissions_json if isinstance(user.custom_permissions_json, list) else []
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        email_verified_at=user.email_verified_at,
        custom_permissions=perms,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/{id}", response_model=UserDetailResponse)
def get_user_detail(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get user details (Admin or Self)."""
    if current_user.role != UserRole.ADMIN and current_user.id != id:
        raise PermissionDeniedError("You can only access your own profile.")

    user = UserService.get_user_by_id(db, id)
    perms = user.custom_permissions_json if isinstance(user.custom_permissions_json, list) else []
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        email_verified_at=user.email_verified_at,
        custom_permissions=perms,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/{id}", response_model=UserDetailResponse)
def update_user(
    id: int,
    payload: UserUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update user metadata, role, status, or permissions (Admin only)."""
    user = UserService.update_user(db, id, payload, updater_id=current_admin.id)
    perms = user.custom_permissions_json if isinstance(user.custom_permissions_json, list) else []
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        email_verified_at=user.email_verified_at,
        custom_permissions=perms,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/{id}/deactivate", response_model=AuthMessageResponse)
def deactivate_user(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft-disable user account and revoke all active refresh tokens."""
    user = UserService.deactivate_user(db, id, admin_id=current_admin.id)
    return AuthMessageResponse(message=f"User {user.email} deactivated successfully.", is_active=user.is_active)


@router.post("/{id}/reactivate", response_model=AuthMessageResponse)
def reactivate_user(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Re-enable user account."""
    user = UserService.reactivate_user(db, id, admin_id=current_admin.id)
    return AuthMessageResponse(message=f"User {user.email} reactivated successfully.", is_active=user.is_active)


@router.post("/{id}/unlock", response_model=AuthMessageResponse)
def unlock_user(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Clear failed login counters and lockout timestamp."""
    user = UserService.unlock_user(db, id, admin_id=current_admin.id)
    return AuthMessageResponse(message=f"User {user.email} unlocked successfully.")


@router.post("/{id}/force-password-reset", response_model=AuthMessageResponse)
def force_password_reset(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Force password reset token generation and revoke all current sessions (Tier 2)."""
    token = UserService.force_password_reset(db, id, admin_id=current_admin.id)
    return AuthMessageResponse(
        message="Force password reset token generated and sessions revoked.",
        action_token=token,
    )


@router.delete("/{id}", response_model=AuthMessageResponse)
def delete_user(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Hard-delete user record if unreferenced by foreign keys (Tier 2)."""
    UserService.delete_user(db, id, admin_id=current_admin.id)
    return AuthMessageResponse(message=f"User {id} deleted successfully.")
