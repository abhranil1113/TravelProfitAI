from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr, Field

from backend.app.models.schema import UserRole


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.ANALYST
    custom_permissions: Optional[List[str]] = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    custom_permissions: Optional[List[str]] = None


class UserDetailResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    email_verified_at: Optional[datetime] = None
    custom_permissions: List[str] = Field(default_factory=list)
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserDetailResponse]
    total: int
    page: int
    page_size: int
