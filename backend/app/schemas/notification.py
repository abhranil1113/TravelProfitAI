from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import DeliveryStatus


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    title: str
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    is_read: bool
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPreferenceItem(BaseModel):
    notification_type: str = Field(..., max_length=64)
    channel: str = Field(..., max_length=32)
    is_enabled: bool = True


class NotificationPreferenceUpdateRequest(BaseModel):
    preferences: List[NotificationPreferenceItem] = Field(..., min_length=1)


class NotificationPreferenceResponse(BaseModel):
    preferences: List[NotificationPreferenceItem]


class NotificationDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_id: int
    channel: str
    delivery_status: DeliveryStatus
    attempt_count: int
    provider_reference: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryListResponse(BaseModel):
    items: List[NotificationDeliveryResponse]
    total: int
