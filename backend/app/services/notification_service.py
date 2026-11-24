from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import NotFoundException
from backend.app.core.notification_events import (
    EVENT_CATEGORY_MAP,
    EVENT_DEFAULT_ROLES,
    EventTypes,
    NotificationCategory,
    NotificationSeverity,
    SOCKET_EVENT_NOTIFICATION_NEW,
    SOCKET_EVENT_NOTIFICATION_READ,
    SOCKET_EVENT_NOTIFICATION_UNREAD_COUNT,
    map_event_to_orm_type,
)
from backend.app.core.socket_manager import socket_manager
from backend.app.models.schema import (
    DeliveryStatus,
    Notification,
    NotificationChannel,
    NotificationDelivery,
    NotificationPreference,
    User,
    UserRole,
)
from backend.app.schemas.notification import (
    NotificationCreateRequest,
    NotificationDispatchResult,
    NotificationPreferenceItem,
    NotificationPreferenceUpdateRequest,
)

logger = logging.getLogger("tbo_inventoryiq.notifications")


def _schedule_background(coro):
    """Safely schedules an async coroutine on the running event loop if one exists."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        coro.close()


class NotificationService:
    """
    Centralized Notification Service for TBO InventoryIQ.
    Manages persistent notification storage, user preference filtering,
    idempotent event dispatching, and real-time Socket.IO delivery.
    """

    # In-memory idempotency cache: key -> timestamp (seconds)
    _idempotency_cache: Dict[str, float] = {}
    _idempotency_ttl_seconds: float = 30.0

    @classmethod
    def create_notification_object(
        cls,
        event_type: str,
        title: str,
        message: str,
        recipient_id: Optional[int] = None,
        category: Optional[str] = None,
        severity: str = "INFO",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source_module: Optional[str] = None,
        actor_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs a consistent, standardized notification dictionary object."""
        resolved_category = category or EVENT_CATEGORY_MAP.get(event_type, NotificationCategory.SYSTEM).value
        return {
            "event_type": event_type,
            "title": title,
            "message": message,
            "category": resolved_category,
            "severity": severity.upper(),
            "recipient_id": recipient_id,
            "actor_id": actor_id,
            "source_module": source_module,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_read": False,
        }

    @classmethod
    async def notify(
        cls,
        event_type: str,
        title: str,
        message: str,
        recipient_ids: Optional[List[int]] = None,
        roles: Optional[List[str]] = None,
        category: Optional[str] = None,
        severity: str = "INFO",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source_module: Optional[str] = None,
        actor_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        idempotency_key: Optional[str] = None,
    ) -> NotificationDispatchResult:
        """
        Primary reusable notification function.
        Validates event, resolves recipients, applies preferences, enforces idempotency,
        persists to database, and delivers real-time Socket.IO notifications.
        """
        now = time.time()
        # 1. Clean stale idempotency keys
        stale_keys = [k for k, ts in cls._idempotency_cache.items() if (now - ts) > cls._idempotency_ttl_seconds * 10]
        for k in stale_keys:
            cls._idempotency_cache.pop(k, None)

        # 2. Check Idempotency
        target_recipients_pre = set(recipient_ids or [])
        idemp_token = idempotency_key or f"{event_type}:{entity_type}:{entity_id}:{sorted(list(target_recipients_pre))}"
        if idemp_token in cls._idempotency_cache and (now - cls._idempotency_cache[idemp_token]) < cls._idempotency_ttl_seconds:
            logger.info("Notification deduplicated via idempotency: %s", idemp_token)
            return NotificationDispatchResult(
                event_type=event_type,
                persisted_count=0,
                emitted_count=0,
                targeted_recipients=list(target_recipients_pre),
                delivery_status="DEDUPLICATED",
                details={"reason": "idempotency_hit", "key": idemp_token},
            )
        cls._idempotency_cache[idemp_token] = now

        # 3. Resolve Recipients
        target_recipients: Set[int] = set(recipient_ids or [])
        resolved_roles: Set[str] = set([r.upper() for r in (roles or [])])

        if not target_recipients and not resolved_roles:
            default_roles = EVENT_DEFAULT_ROLES.get(event_type, [])
            for dr in default_roles:
                resolved_roles.add(dr.upper())

        if resolved_roles and db is not None:
            try:
                role_users = db.execute(
                    select(User.id).where(
                        User.is_active == True,
                        User.role.in_(list(resolved_roles)),
                    )
                ).scalars().all()
                for uid in role_users:
                    target_recipients.add(uid)
            except Exception as e:
                logger.warning("Failed to resolve users for roles %s: %s", resolved_roles, e)

        # 4. Filter by Notification Preferences (In-App Channel)
        skipped_recipients: List[int] = []
        final_recipients: List[int] = []

        if db is not None and target_recipients:
            try:
                disabled_users = set(
                    db.execute(
                        select(NotificationPreference.user_id).where(
                            NotificationPreference.user_id.in_(list(target_recipients)),
                            NotificationPreference.channel == NotificationChannel.IN_APP,
                            NotificationPreference.is_enabled == False,
                        )
                    ).scalars().all()
                )
                for uid in target_recipients:
                    if uid in disabled_users:
                        skipped_recipients.append(uid)
                    else:
                        final_recipients.append(uid)
            except Exception as e:
                logger.warning("Failed to check notification preferences: %s", e)
                final_recipients = list(target_recipients)
        else:
            final_recipients = list(target_recipients)

        persisted_records: Dict[int, Notification] = {}
        persisted_count = 0

        # 5. Database Persistence (Safe and Non-Blocking)
        if db is not None and final_recipients:
            try:
                orm_type = map_event_to_orm_type(event_type)
                for uid in final_recipients:
                    notif = Notification(
                        user_id=uid,
                        type=orm_type,
                        title=title,
                        message=message,
                        entity_type=entity_type,
                        entity_id=str(entity_id) if entity_id is not None else None,
                        is_read=False,
                    )
                    db.add(notif)
                    db.flush()
                    persisted_records[uid] = notif
                    persisted_count += 1

                    # Record in-app delivery attempt
                    is_online = socket_manager.is_user_connected(uid)
                    delivery = NotificationDelivery(
                        notification_id=notif.id,
                        channel=NotificationChannel.IN_APP,
                        delivery_status=DeliveryStatus.SENT if is_online else DeliveryStatus.PENDING,
                        attempt_count=1 if is_online else 0,
                        last_attempt_at=datetime.now(timezone.utc) if is_online else None,
                        delivered_at=datetime.now(timezone.utc) if is_online else None,
                    )
                    db.add(delivery)

                db.commit()
            except Exception as e:
                logger.error("Failed to persist notification records in DB: %s", e)
                db.rollback()

        # 6. Real-Time Socket.IO Emission
        emitted_count = 0
        resolved_category = category or EVENT_CATEGORY_MAP.get(event_type, NotificationCategory.SYSTEM).value

        for uid in final_recipients:
            notif_orm = persisted_records.get(uid)
            payload = {
                "id": notif_orm.id if notif_orm else None,
                "notification_id": notif_orm.id if notif_orm else None,
                "event_type": event_type,
                "title": title,
                "message": message,
                "category": resolved_category,
                "severity": severity.upper(),
                "recipient_id": uid,
                "actor_id": actor_id,
                "source_module": source_module,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_read": False,
            }

            try:
                delivered = await socket_manager.emit_to_user(uid, SOCKET_EVENT_NOTIFICATION_NEW, payload)
                if delivered:
                    emitted_count += 1

                # Update recipient's unread count via socket
                if db is not None:
                    try:
                        unread_c = cls.get_unread_count(db, uid)
                        await socket_manager.emit_unread_count(uid, unread_c)
                    except Exception:
                        pass
            except Exception as e:
                logger.error("Socket.IO emission error for user %s: %s", uid, e)

        # Broadcast to role rooms if roles targeted
        if resolved_roles:
            broadcast_payload = {
                "id": None,
                "notification_id": None,
                "event_type": event_type,
                "title": title,
                "message": message,
                "category": resolved_category,
                "severity": severity.upper(),
                "recipient_id": None,
                "actor_id": actor_id,
                "source_module": source_module,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_read": False,
            }
            for r in resolved_roles:
                try:
                    await socket_manager.emit_to_role(r, SOCKET_EVENT_NOTIFICATION_NEW, broadcast_payload)
                except Exception as e:
                    logger.error("Socket.IO role broadcast error for role %s: %s", r, e)

        return NotificationDispatchResult(
            event_type=event_type,
            persisted_count=persisted_count,
            emitted_count=emitted_count,
            targeted_recipients=final_recipients,
            skipped_recipients=skipped_recipients,
            delivery_status="DELIVERED" if emitted_count > 0 else ("PERSISTED_OFFLINE" if persisted_count > 0 else "COMPLETED"),
            details={
                "persisted_ids": [n.id for n in persisted_records.values()],
                "roles_targeted": list(resolved_roles),
            },
        )

    @classmethod
    def notify_sync(
        cls,
        event_type: str,
        title: str,
        message: str,
        recipient_ids: Optional[List[int]] = None,
        roles: Optional[List[str]] = None,
        category: Optional[str] = None,
        severity: str = "INFO",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source_module: Optional[str] = None,
        actor_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """
        Synchronous non-blocking helper for triggering notifications from synchronous business code.
        Safely schedules async notify on the active event loop if present.
        """
        _schedule_background(
            cls.notify(
                event_type=event_type,
                title=title,
                message=message,
                recipient_ids=recipient_ids,
                roles=roles,
                category=category,
                severity=severity,
                entity_type=entity_type,
                entity_id=entity_id,
                source_module=source_module,
                actor_id=actor_id,
                metadata=metadata,
                db=db,
                idempotency_key=idempotency_key,
            )
        )

    # --- Existing Notification REST Query & Mutation Methods ---

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

        # Notify active client sockets of read status update
        _schedule_background(socket_manager.emit_notification_read(user_id, notif_id))
        unread = NotificationService.get_unread_count(db, user_id)
        _schedule_background(socket_manager.emit_unread_count(user_id, unread))

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

        # Update active client sockets unread count to 0
        _schedule_background(socket_manager.emit_unread_count(user_id, 0))

        return len(notifs)

    @staticmethod
    def acknowledge_notification(db: Session, notif_id: int, user_id: int) -> Optional[NotificationDelivery]:
        """Updates NotificationDelivery status to DELIVERED upon receipt confirmation."""
        notif = db.execute(
            select(Notification).where(
                Notification.id == notif_id,
                Notification.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not notif:
            raise NotFoundException(f"Notification {notif_id} not found")

        delivery = db.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.notification_id == notif_id,
                NotificationDelivery.channel == NotificationChannel.IN_APP,
            )
        ).scalar_one_or_none()

        if delivery:
            delivery.delivery_status = DeliveryStatus.DELIVERED
            delivery.delivered_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(delivery)
        return delivery

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

        unread = NotificationService.get_unread_count(db, user_id)
        _schedule_background(socket_manager.emit_unread_count(user_id, unread))

    @staticmethod
    def get_preferences(db: Session, user_id: int) -> List[NotificationPreferenceItem]:
        prefs = list(
            db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            ).scalars().all()
        )
        if not prefs:
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
