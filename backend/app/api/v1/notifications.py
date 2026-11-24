from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import DeliveryStatus, User, UserRole
from backend.app.schemas.notification import (
    NotificationDeliveryListResponse,
    NotificationDeliveryResponse,
    NotificationListResponse,
    NotificationPreferenceItem,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    UnreadCountResponse,
)
from backend.app.services.notification_service import NotificationService

notifications_router = APIRouter(prefix="/notifications", tags=["17. Notifications"])
notification_preferences_router = APIRouter(prefix="/notification-preferences", tags=["17. Notifications"])


# --- STATIC SUB-PATHS BEFORE PARAMETERIZED PATHS ---

@notifications_router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
)
def get_unread_notification_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """156. Quick check for total unread notifications count."""
    count = NotificationService.get_unread_count(db, current_user.id)
    return UnreadCountResponse(unread_count=count)


@notifications_router.post(
    "/mark-all-read",
)
def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """158. Mark all unread notifications for current user as read."""
    count = NotificationService.mark_all_as_read(db, current_user.id)
    return {"updated": count, "message": "All notifications marked as read"}


@notifications_router.get(
    "/deliveries",
    response_model=NotificationDeliveryListResponse,
)
def list_notification_deliveries(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    channel: Optional[str] = None,
    delivery_status: Optional[DeliveryStatus] = Query(None, alias="status"),
):
    """162. System audit of notification delivery attempts across channels."""
    items = NotificationService.list_deliveries(db, channel=channel, delivery_status=delivery_status)
    return NotificationDeliveryListResponse(
        items=[NotificationDeliveryResponse.model_validate(i) for i in items],
        total=len(items),
    )


@notifications_router.get(
    "",
    response_model=NotificationListResponse,
)
def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    is_read: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """155. List notifications for current user with read/unread filter."""
    items, total, unread = NotificationService.list_notifications(db, current_user.id, is_read=is_read, page=page, page_size=page_size)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(i) for i in items],
        total=total,
        unread_count=unread,
    )


@notifications_router.post(
    "/{id}/read",
    response_model=NotificationResponse,
)
def mark_notification_read(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """157. Mark individual notification as read."""
    notif = NotificationService.mark_as_read(db, id, current_user.id)
    return NotificationResponse.model_validate(notif)


@notifications_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notification(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """159. Dismiss and delete notification."""
    NotificationService.delete_notification(db, id, current_user.id)
    return None


# --- Notification Preferences (160-161) ---

@notification_preferences_router.get(
    "",
    response_model=NotificationPreferenceResponse,
)
def get_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """160. Get user notification preferences per channel and alert type."""
    prefs = NotificationService.get_preferences(db, current_user.id)
    return NotificationPreferenceResponse(preferences=prefs)


@notification_preferences_router.put(
    "",
    response_model=NotificationPreferenceResponse,
)
def update_notification_preferences(
    req: NotificationPreferenceUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """161. Update user notification channels and subscription settings."""
    prefs = NotificationService.update_preferences(db, current_user.id, req)
    return NotificationPreferenceResponse(preferences=prefs)
