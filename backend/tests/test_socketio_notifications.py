from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
import socketio

from backend.app.core.config import get_settings
from backend.app.core.notification_events import (
    EVENT_CATEGORY_MAP,
    EventTypes,
    NotificationCategory,
    NotificationSeverity,
    RoleNames,
    SOCKET_EVENT_NOTIFICATION_ACKNOWLEDGED,
    SOCKET_EVENT_NOTIFICATION_NEW,
    SOCKET_EVENT_NOTIFICATION_READ,
    SOCKET_EVENT_NOTIFICATION_UNREAD_COUNT,
)
from backend.app.core.security import create_access_token
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
from backend.app.services.notification_service import NotificationService

settings = get_settings()


@pytest.fixture(autouse=True)
def cleanup_socket_manager():
    """Ensure socket manager session state is clean before and after each test."""
    socket_manager._user_sockets.clear()
    socket_manager._socket_sessions.clear()
    socket_manager._acknowledgements.clear()
    yield
    socket_manager._user_sockets.clear()
    socket_manager._socket_sessions.clear()
    socket_manager._acknowledgements.clear()


# ==============================================================================
# SECTION 1: SOCKET.IO CONFIGURATION & HEARTBEAT TESTS
# ==============================================================================

def test_socket_manager_ping_pong_configuration():
    """Verify Socket.IO heartbeat ping/pong settings match centralized configuration."""
    assert socket_manager.sio.async_mode == "asgi"
    assert socket_manager.sio.eio.ping_interval == settings.SOCKET_IO_PING_INTERVAL
    assert socket_manager.sio.eio.ping_timeout == settings.SOCKET_IO_PING_TIMEOUT
    assert socket_manager.get_active_users_count() == 0


# ==============================================================================
# SECTION 2: AUTHENTICATION & CONNECTION LIFECYCLE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_socket_connection_successful_auth():
    """Verify client connects successfully with valid JWT and joins user and role rooms."""
    token = create_access_token(subject=101, role="ADMIN")
    session = await socket_manager.handle_connect(
        sid="test-sid-101",
        environ={},
        auth={"token": token},
    )

    assert session["user_id"] == 101
    assert session["role"] == "ADMIN"
    assert socket_manager.is_user_connected(101) is True
    assert socket_manager.get_user_connection_count(101) == 1
    assert 101 in socket_manager.get_connected_user_ids()


@pytest.mark.asyncio
async def test_socket_connection_bearer_auth_header():
    """Verify authentication succeeds when token is sent via HTTP Authorization header."""
    token = create_access_token(subject=102, role="PROCUREMENT_MANAGER")
    session = await socket_manager.handle_connect(
        sid="test-sid-102",
        environ={"headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))]},
        auth=None,
    )

    assert session["user_id"] == 102
    assert session["role"] == "PROCUREMENT_MANAGER"
    assert socket_manager.is_user_connected(102) is True


@pytest.mark.asyncio
async def test_socket_connection_query_param_auth_rejected():
    """Verify authentication via query string is refused to prevent URL token leakage (CWE-598)."""
    token = create_access_token(subject=103, role="ANALYST")
    with pytest.raises(socketio.exceptions.ConnectionRefusedError) as exc_info:
        await socket_manager.handle_connect(
            sid="test-sid-103",
            environ={"QUERY_STRING": f"token={token}"},
            auth=None,
        )
    assert "missing token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_socket_connection_missing_token_rejection():
    """Verify connection is refused when no authentication token is provided."""
    with pytest.raises(socketio.exceptions.ConnectionRefusedError) as exc_info:
        await socket_manager.handle_connect(
            sid="test-sid-bad",
            environ={},
            auth={},
        )
    assert "missing token" in str(exc_info.value)
    assert socket_manager.get_active_users_count() == 0


@pytest.mark.asyncio
async def test_socket_connection_invalid_token_rejection():
    """Verify connection is refused when token is invalid or malformed."""
    with pytest.raises(socketio.exceptions.ConnectionRefusedError) as exc_info:
        await socket_manager.handle_connect(
            sid="test-sid-invalid",
            environ={},
            auth={"token": "invalid.jwt.signature"},
        )
    assert "invalid or expired token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_socket_connection_expired_token_rejection():
    """Verify connection is refused when JWT token has expired."""
    expired_token = create_access_token(
        subject=104,
        role="ADMIN",
        expires_delta=timedelta(minutes=-30),
    )
    with pytest.raises(socketio.exceptions.ConnectionRefusedError) as exc_info:
        await socket_manager.handle_connect(
            sid="test-sid-expired",
            environ={},
            auth={"token": expired_token},
        )
    assert "invalid or expired token" in str(exc_info.value)


# ==============================================================================
# SECTION 3: MULTI-CONNECTION & DISCONNECTION LIFECYCLE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_socket_multiple_connections_per_user():
    """Verify multiple active browser tabs/devices for one user are tracked accurately."""
    token = create_access_token(subject=201, role="REVENUE_ANALYST")

    # Tab 1 connects
    await socket_manager.handle_connect(sid="tab-1", environ={}, auth={"token": token})
    assert socket_manager.get_user_connection_count(201) == 1
    assert socket_manager.is_user_connected(201) is True

    # Tab 2 connects (same user)
    await socket_manager.handle_connect(sid="tab-2", environ={}, auth={"token": token})
    assert socket_manager.get_user_connection_count(201) == 2
    assert socket_manager.is_user_connected(201) is True

    # Tab 1 closes
    await socket_manager.handle_disconnect(sid="tab-1")
    assert socket_manager.get_user_connection_count(201) == 1
    assert socket_manager.is_user_connected(201) is True

    # Tab 2 closes
    await socket_manager.handle_disconnect(sid="tab-2")
    assert socket_manager.get_user_connection_count(201) == 0
    assert socket_manager.is_user_connected(201) is False


# ==============================================================================
# SECTION 4: REAL-TIME EMITTERS & CLIENT ACKNOWLEDGEMENT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_socket_event_emitters_and_acknowledgement():
    """Verify emit methods and client delivery acknowledgement tracking."""
    token = create_access_token(subject=301, role="ADMIN")
    await socket_manager.handle_connect(sid="sid-ack", environ={}, auth={"token": token})

    # Test user emission
    delivered = await socket_manager.emit_to_user(301, "test:event", {"data": 123})
    assert delivered is True

    # Test disconnected user emission
    undelivered = await socket_manager.emit_to_user(999, "test:event", {"data": 123})
    assert undelivered is False

    # Test role emission
    role_delivered = await socket_manager.emit_to_role("ADMIN", "test:role_event", {"status": "ok"})
    assert role_delivered is True

    # Test client acknowledgement recording
    ack = await socket_manager.handle_acknowledgement(
        sid="sid-ack",
        data={"notification_id": 555},
    )
    assert ack is not None
    assert ack["user_id"] == 301
    assert ack["notification_id"] == 555

    stored_ack = socket_manager.get_acknowledgement(user_id=301, notification_id=555)
    assert stored_ack is not None
    assert stored_ack["notification_id"] == 555


# ==============================================================================
# SECTION 5: NOTIFICATION OBJECT CREATION & IDEMPOTENCY TESTS
# ==============================================================================

def test_notification_object_creation():
    """Verify standardized notification dictionary structure."""
    notif = NotificationService.create_notification_object(
        event_type=EventTypes.OPTIMIZATION_COMPLETED,
        title="Optimization Done",
        message="Optimization run completed successfully",
        recipient_id=501,
        severity=NotificationSeverity.SUCCESS.value,
        entity_type="optimization_run",
        entity_id="RUN-8888",
        source_module="optimization",
    )

    assert notif["event_type"] == EventTypes.OPTIMIZATION_COMPLETED
    assert notif["title"] == "Optimization Done"
    assert notif["category"] == NotificationCategory.OPTIMIZATION.value
    assert notif["severity"] == "SUCCESS"
    assert notif["recipient_id"] == 501
    assert notif["entity_type"] == "optimization_run"
    assert notif["entity_id"] == "RUN-8888"
    assert notif["is_read"] is False
    assert "created_at" in notif


@pytest.mark.asyncio
async def test_notification_idempotency_deduplication():
    """Verify identical notifications within the idempotency window are deduplicated."""
    res1 = await NotificationService.notify(
        event_type=EventTypes.INVENTORY_LOW_THRESHOLD,
        title="Low Inventory",
        message="Capacity is below 10%",
        recipient_ids=[701],
        idempotency_key="idemp-test-key-100",
    )
    assert res1.delivery_status in ("DELIVERED", "PERSISTED_OFFLINE", "COMPLETED")

    # Immediate second call with identical idempotency key
    res2 = await NotificationService.notify(
        event_type=EventTypes.INVENTORY_LOW_THRESHOLD,
        title="Low Inventory",
        message="Capacity is below 10%",
        recipient_ids=[701],
        idempotency_key="idemp-test-key-100",
    )
    assert res2.delivery_status == "DEDUPLICATED"
    assert res2.details.get("reason") == "idempotency_hit"


# ==============================================================================
# SECTION 6: DATABASE PERSISTENCE, PREFERENCES & READ STATUS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_notification_persistence_and_read_status(db):
    """Verify database persistence, unread counting, and read-status transitions."""
    # Create test user
    user = User(
        email="notif_test@tbo.com",
        hashed_password="hashed_pwd_placeholder",
        full_name="Notif Test User",
        role=UserRole.ANALYST,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 1. Dispatch notification for offline user
    result = await NotificationService.notify(
        event_type=EventTypes.OPTIMIZATION_COMPLETED,
        title="Test Optimization",
        message="Plan #1 ready",
        recipient_ids=[user.id],
        db=db,
    )

    assert result.persisted_count == 1
    assert result.delivery_status == "PERSISTED_OFFLINE"

    # 2. Verify in DB
    unread_count = NotificationService.get_unread_count(db, user.id)
    assert unread_count >= 1

    items, total, unread = NotificationService.list_notifications(db, user.id)
    assert total >= 1
    target_notif = items[0]
    assert target_notif.is_read is False

    # 3. Mark individual notification read
    marked = NotificationService.mark_as_read(db, target_notif.id, user.id)
    assert marked.is_read is True
    assert NotificationService.get_unread_count(db, user.id) == unread_count - 1

    # 4. Mark all read
    count_updated = NotificationService.mark_all_as_read(db, user.id)
    assert NotificationService.get_unread_count(db, user.id) == 0


@pytest.mark.asyncio
async def test_notification_preference_opt_out(db):
    """Verify users who opted out of in-app channel are skipped from in-app notifications."""
    user = User(
        email="optout_user@tbo.com",
        hashed_password="hashed_pwd_placeholder",
        full_name="Opt Out User",
        role=UserRole.PROCUREMENT_MANAGER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # User opts out of in-app notifications
    from backend.app.models.schema import NotificationType
    pref = NotificationPreference(
        user_id=user.id,
        notification_type=NotificationType.RUN_COMPLETED,
        channel=NotificationChannel.IN_APP,
        is_enabled=False,
    )
    db.add(pref)
    db.commit()

    # Trigger notification
    res = await NotificationService.notify(
        event_type=EventTypes.PRICING_MARGIN_LOW,
        title="Low Margin Alert",
        message="Margin is 2.5%",
        recipient_ids=[user.id],
        db=db,
    )

    assert user.id in res.skipped_recipients
    assert user.id not in res.targeted_recipients


# ==============================================================================
# SECTION 7: NOTIFICATION LIFECYCLE STATES & ACKNOWLEDGEMENT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_notification_full_lifecycle_states(db):
    """
    Verify complete notification lifecycle transitions:
    PENDING (persisted offline) -> SENT (emitted) -> DELIVERED (acknowledged) -> READ.
    Empirically proves that EMITTED != ACKNOWLEDGED, and ACKNOWLEDGED != READ.
    """
    user = User(
        email="lifecycle_user@tbo.com",
        hashed_password="hashed_pwd_placeholder",
        full_name="Lifecycle User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 1. Dispatch while user is OFFLINE -> Initial state is PENDING
    res = await NotificationService.notify(
        event_type=EventTypes.PROCUREMENT_PO_CREATED,
        title="PO Alert",
        message="PO-123 submitted",
        recipient_ids=[user.id],
        db=db,
    )
    notif_id = res.details["persisted_ids"][0]

    # Verify PENDING in DB
    items, _, _ = NotificationService.list_notifications(db, user.id)
    notif = items[0]
    assert notif.is_read is False

    from backend.app.models.schema import NotificationDelivery
    from sqlalchemy import select
    delivery = db.execute(
        select(NotificationDelivery).where(NotificationDelivery.notification_id == notif_id)
    ).scalar_one()
    assert delivery.delivery_status == DeliveryStatus.PENDING
    assert delivery.delivered_at is None

    # 2. Client acknowledges receipt -> DELIVERED / ACKNOWLEDGED
    acked_delivery = NotificationService.acknowledge_notification(db, notif_id, user.id)
    assert acked_delivery is not None
    assert acked_delivery.delivery_status == DeliveryStatus.DELIVERED
    assert acked_delivery.delivered_at is not None

    # Verify notification is still unread (ACKNOWLEDGED != READ)
    db.refresh(notif)
    assert notif.is_read is False

    # 3. User views/marks notification as read -> READ
    read_notif = NotificationService.mark_as_read(db, notif_id, user.id)
    assert read_notif.is_read is True


def test_rest_acknowledge_notification_endpoint(client, pm_headers, db):
    """Verify REST API acknowledgement endpoint POST /notifications/{id}/acknowledge."""
    user = db.query(User).filter(User.role == UserRole.PROCUREMENT_MANAGER).first()

    # Create notification and delivery
    from backend.app.core.notification_events import map_event_to_orm_type
    notif = Notification(
        user_id=user.id,
        type=map_event_to_orm_type("procurement.po_created"),
        title="PO Receipt Test",
        message="Testing ACK endpoint",
        is_read=False,
    )
    db.add(notif)
    db.flush()
    delivery = NotificationDelivery(
        notification_id=notif.id,
        channel=NotificationChannel.IN_APP,
        delivery_status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    db.commit()

    # Call POST /api/v1/notifications/{id}/acknowledge
    ack_res = client.post(f"/api/v1/notifications/{notif.id}/acknowledge", headers=pm_headers)
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["delivery_status"] == "DELIVERED"
    assert data["delivered_at"] is not None


# ==============================================================================
# SECTION 8: LIVE FASTAPI ASGI CLIENT-TO-SERVER INTEGRATION TEST
# ==============================================================================

@pytest.mark.asyncio
async def test_live_asgi_socketio_client_connectivity():
    """
    Spin up a real in-process Uvicorn server on an ephemeral TCP port hosting the
    FastAPI application with Socket.IO ASGI mount. Connect a real socketio.AsyncClient,
    verify handshake, room joining, server-to-client event receipt over wire, and client acknowledgement.
    """
    import asyncio
    import socket
    import threading
    import time
    import uvicorn
    from backend.app.main import app

    def get_free_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Allow server to bind and start listening
    await asyncio.sleep(0.8)

    try:
        token = create_access_token(subject=888, role="ADMIN")
        sio_client = socketio.AsyncClient()
        received_events = []

        @sio_client.on("connection:status")
        def on_status(data):
            received_events.append(("connection:status", data))

        @sio_client.on("notification:new")
        def on_new(data):
            received_events.append(("notification:new", data))

        url = f"http://127.0.0.1:{port}"
        await sio_client.connect(url, auth={"token": token}, socketio_path="socket.io")
        assert sio_client.sid is not None

        # Emit real server event to user 888
        delivered = await socket_manager.emit_to_user(888, "notification:new", {"title": "Live Wire Alert"})
        assert delivered is True

        # Wait for client receipt over wire
        await asyncio.sleep(0.5)
        assert any(e[0] == "notification:new" and e[1]["title"] == "Live Wire Alert" for e in received_events)

        # Client sends acknowledgement back
        await sio_client.emit("notification_acknowledged", {"notification_id": 777})
        await asyncio.sleep(0.3)
        ack = socket_manager.get_acknowledgement(888, 777)
        assert ack is not None
        assert ack["notification_id"] == 777

        await sio_client.disconnect()
    finally:
        server.should_exit = True

