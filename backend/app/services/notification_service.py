from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    NotFoundException,
)
from backend.app.models.schema import (
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from backend.app.schemas.notification import (
    NotificationPreferenceItem,
    NotificationPreferenceUpdateRequest,
)


class NotificationService:

    @staticmethod
    def list_notifications(
        db: Session,
        user_id: int,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Notification], int, int]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        unread_count = db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalar_one()

        stmt = stmt.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total, unread_count

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        return db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalar_one()

    @staticmethod
    def mark_as_read(db: Session, notif_id: int, user_id: int) -> Notification:
        notif = db.execute(
            select(Notification).where(
                Notification.id == notif_id,
                Notification.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not notif:
            raise NotFoundException(f"Notification {notif_id} not found")

        notif.is_read = True
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        notifs = db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalars().all()

        for n in notifs:
            n.is_read = True

        db.commit()
        return len(notifs)

    @staticmethod
    def delete_notification(db: Session, notif_id: int, user_id: int) -> None:
        notif = db.execute(
            select(Notification).where(
                Notification.id == notif_id,
                Notification.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not notif:
            raise NotFoundException(f"Notification {notif_id} not found")

        db.delete(notif)
        db.commit()

    @staticmethod
    def get_preferences(db: Session, user_id: int) -> List[NotificationPreferenceItem]:
        prefs = list(
            db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            ).scalars().all()
        )
        if not prefs:
            # Default preferences
            return [
                NotificationPreferenceItem(notification_type="OPTIMIZATION_COMPLETED", channel="EMAIL", is_enabled=True),
                NotificationPreferenceItem(notification_type="BUDGET_EXHAUSTION_ALERT", channel="IN_APP", is_enabled=True),
                NotificationPreferenceItem(notification_type="PURCHASE_ORDER_DISPUTE", channel="EMAIL", is_enabled=True),
            ]
        return [
            NotificationPreferenceItem(
                notification_type=p.notification_type,
                channel=p.channel,
                is_enabled=p.is_enabled,
            )
            for p in prefs
        ]

    @staticmethod
    def update_preferences(
        db: Session,
        user_id: int,
        req: NotificationPreferenceUpdateRequest,
    ) -> List[NotificationPreferenceItem]:
        # Delete existing preferences
        existing = db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        ).scalars().all()
        for p in existing:
            db.delete(p)
        db.flush()

        new_prefs = []
        for item in req.preferences:
            pref = NotificationPreference(
                user_id=user_id,
                notification_type=item.notification_type,
                channel=item.channel,
                is_enabled=item.is_enabled,
            )
            db.add(pref)
            new_prefs.append(item)

        db.commit()
        return new_prefs

    @staticmethod
    def list_deliveries(
        db: Session,
        channel: Optional[str] = None,
        delivery_status: Optional[DeliveryStatus] = None,
    ) -> List[NotificationDelivery]:
        stmt = select(NotificationDelivery)
        if channel:
            stmt = stmt.where(NotificationDelivery.channel == channel)
        if delivery_status:
            stmt = stmt.where(NotificationDelivery.delivery_status == delivery_status)

        stmt = stmt.order_by(NotificationDelivery.created_at.desc()).limit(100)
        return list(db.execute(stmt).scalars().all())
