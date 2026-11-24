from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs

import socketio

from backend.app.core.config import get_settings
from backend.app.core.notification_events import (
    SOCKET_EVENT_CONNECTION_STATUS,
    SOCKET_EVENT_NOTIFICATION_ACKNOWLEDGED,
    SOCKET_EVENT_NOTIFICATION_NEW,
    SOCKET_EVENT_NOTIFICATION_READ,
    SOCKET_EVENT_NOTIFICATION_UNREAD_COUNT,
)
from backend.app.core.security import decode_access_token

logger = logging.getLogger("tbo_inventoryiq.socketio")
settings = get_settings()


class SocketManager:
    """
    Centralized Socket.IO Manager for TBO InventoryIQ.
    Handles JWT authentication handshake, user-specific and role-based rooms,
    heartbeat monitoring, client acknowledgements, and reliable real-time event delivery.
    """

    def __init__(self) -> None:
        cors_origins = settings.SOCKET_IO_CORS_ORIGINS
        if isinstance(cors_origins, list) and len(cors_origins) == 1 and cors_origins[0] == "*":
            cors_origins = "*"

        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=cors_origins,
            ping_interval=settings.SOCKET_IO_PING_INTERVAL,
            ping_timeout=settings.SOCKET_IO_PING_TIMEOUT,
            logger=False,
            engineio_logger=False,
        )

        # In-memory tracking of active sessions and rooms
        self._user_sockets: Dict[int, Set[str]] = {}
        self._socket_sessions: Dict[str, Dict[str, Any]] = {}
        self._acknowledgements: Dict[str, Dict[str, Any]] = {}

        self._register_handlers()

    @property
    def asgi_app(self) -> socketio.ASGIApp:
        """Returns the ASGI wrapper app for mounting in FastAPI."""
        socket_path = settings.SOCKET_IO_PATH.lstrip("/")
        return socketio.ASGIApp(self.sio, socketio_path=socket_path)

    def _extract_token(self, environ: Dict[str, Any], auth: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Extracts JWT token from Socket.IO auth dictionary or HTTP Authorization header.
        Query-parameter token extraction is intentionally omitted to avoid token leakage
        in server access logs, proxy caches, and browser histories (CWE-598).
        """
        # 1. Primary: Socket.IO auth payload (client: io(url, { auth: { token: '...' } }))
        if auth and isinstance(auth, dict):
            for key in ["token", "jwt", "access_token"]:
                if key in auth and auth[key]:
                    token_val = auth[key]
                    if isinstance(token_val, str) and token_val.startswith("Bearer "):
                        return token_val.split(" ", 1)[1]
                    return str(token_val)

        # 2. Secondary: HTTP Authorization Header (for WebSocket/HTTP initial handshake)
        headers = environ.get("headers", [])
        if isinstance(headers, (list, tuple)):
            for h in headers:
                if len(h) >= 2:
                    name = h[0].decode("utf-8").lower() if isinstance(h[0], bytes) else str(h[0]).lower()
                    if name == "authorization":
                        val = h[1].decode("utf-8") if isinstance(h[1], bytes) else str(h[1])
                        if val.startswith("Bearer "):
                            return val.split(" ", 1)[1]
                        return val

        # 3. ASGI scope / WSGI environ HTTP_AUTHORIZATION
        http_auth = environ.get("HTTP_AUTHORIZATION")
        if http_auth and isinstance(http_auth, str):
            if http_auth.startswith("Bearer "):
                return http_auth.split(" ", 1)[1]
            return http_auth

        return None

    def _register_handlers(self) -> None:
        """Registers connection lifecycle and incoming message event handlers."""

        @self.sio.event
        async def connect(sid: str, environ: Dict[str, Any], auth: Optional[Dict[str, Any]] = None):
            return await self.handle_connect(sid, environ, auth)

        @self.sio.event
        async def disconnect(sid: str):
            return await self.handle_disconnect(sid)

        @self.sio.event
        async def notification_acknowledged(sid: str, data: Dict[str, Any]):
            return await self.handle_acknowledgement(sid, data)

    async def handle_connect(self, sid: str, environ: Dict[str, Any], auth: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handles authentication handshake, session creation, and room assignments."""
        token = self._extract_token(environ, auth)
        if not token:
            logger.warning("Socket.IO connection rejected: missing authentication token (sid=%s)", sid)
            raise socketio.exceptions.ConnectionRefusedError("Authentication failed: missing token")

        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")
            if not sub:
                raise ValueError("Token missing subject claim")
            user_id = int(sub)
            role = str(payload.get("role", "REVENUE_ANALYST")).upper()
        except Exception as e:
            logger.warning("Socket.IO connection rejected: token invalid or expired (sid=%s): %s", sid, e)
            raise socketio.exceptions.ConnectionRefusedError("Authentication failed: invalid or expired token")

        # Store active session info in manager
        session_data = {
            "user_id": user_id,
            "role": role,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }

        # Track multi-connection index for user
        if user_id not in self._user_sockets:
            self._user_sockets[user_id] = set()
        self._user_sockets[user_id].add(sid)
        self._socket_sessions[sid] = session_data

        user_room = f"user:{user_id}"
        role_room = f"role:{role}"

        # Join engine-level rooms and save engine session if supported
        try:
            await self.sio.save_session(sid, session_data)
            await self.sio.enter_room(sid, user_room)
            await self.sio.enter_room(sid, role_room)
            await self.sio.emit(
                SOCKET_EVENT_CONNECTION_STATUS,
                {
                    "status": "connected",
                    "user_id": user_id,
                    "role": role,
                    "rooms": [user_room, role_room],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                to=sid,
            )
        except Exception as e:
            logger.debug("Socket.IO engine room join skipped for sid %s: %s", sid, e)

        logger.info("Socket.IO client connected: sid=%s, user_id=%s, role=%s", sid, user_id, role)
        return session_data

    async def handle_disconnect(self, sid: str) -> Optional[Dict[str, Any]]:
        """Handles socket disconnection and cleans up active session tracking."""
        session_data = self._socket_sessions.pop(sid, None)
        if session_data:
            user_id = session_data.get("user_id")
            if user_id in self._user_sockets:
                self._user_sockets[user_id].discard(sid)
                if not self._user_sockets[user_id]:
                    del self._user_sockets[user_id]
            logger.info("Socket.IO client disconnected: sid=%s, user_id=%s", sid, user_id)
        else:
            logger.info("Socket.IO client disconnected: sid=%s", sid)
        return session_data

    async def handle_acknowledgement(self, sid: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Client acknowledgement of delivered notification."""
        session = self._socket_sessions.get(sid, {})
        user_id = session.get("user_id")
        notif_id = data.get("notification_id")
        if notif_id and user_id:
            ack_key = f"{user_id}:{notif_id}"
            ack_record = {
                "user_id": user_id,
                "notification_id": notif_id,
                "sid": sid,
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }
            self._acknowledgements[ack_key] = ack_record
            logger.debug("Notification acknowledged: user_id=%s, notif_id=%s", user_id, notif_id)
            return ack_record
        return None

    # --- Reusable Public Emitter APIs ---

    async def emit_to_user(self, user_id: int, event: str, data: Dict[str, Any]) -> bool:
        """Emits an event to all active sockets belonging to a specific user."""
        room = f"user:{user_id}"
        try:
            await self.sio.emit(event, data, room=room)
            return self.is_user_connected(user_id)
        except Exception as e:
            logger.error("Failed to emit to user %s on room %s: %s", user_id, room, e)
            return False

    async def emit_to_role(self, role: str, event: str, data: Dict[str, Any]) -> bool:
        """Emits an event to all connected users possessing a specific role."""
        room = f"role:{role.upper()}"
        try:
            await self.sio.emit(event, data, room=room)
            return True
        except Exception as e:
            logger.error("Failed to emit to role %s on room %s: %s", role, room, e)
            return False

    async def emit_to_all(self, event: str, data: Dict[str, Any]) -> bool:
        """Broadcasts an event to all currently connected clients across the application."""
        try:
            await self.sio.emit(event, data)
            return True
        except Exception as e:
            logger.error("Failed to broadcast event %s: %s", event, e)
            return False

    async def emit_notification(
        self,
        notification_payload: Dict[str, Any],
        recipient_ids: Optional[List[int]] = None,
        roles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Emits a new notification event to specified recipients and/or roles.
        Returns a delivery summary dictionary.
        """
        emitted_to_users: List[int] = []
        emitted_to_roles: List[str] = []

        if recipient_ids:
            for uid in recipient_ids:
                delivered = await self.emit_to_user(uid, SOCKET_EVENT_NOTIFICATION_NEW, notification_payload)
                if delivered:
                    emitted_to_users.append(uid)

        if roles:
            for r in roles:
                await self.emit_to_role(r, SOCKET_EVENT_NOTIFICATION_NEW, notification_payload)
                emitted_to_roles.append(r)

        return {
            "delivered_users": emitted_to_users,
            "targeted_roles": emitted_to_roles,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def emit_unread_count(self, user_id: int, count: int) -> bool:
        """Notifies a user of their updated unread notifications count."""
        return await self.emit_to_user(
            user_id,
            SOCKET_EVENT_NOTIFICATION_UNREAD_COUNT,
            {"user_id": user_id, "unread_count": count},
        )

    async def emit_notification_read(self, user_id: int, notification_id: int) -> bool:
        """Notifies user sockets that a notification was marked as read."""
        return await self.emit_to_user(
            user_id,
            SOCKET_EVENT_NOTIFICATION_READ,
            {"user_id": user_id, "notification_id": notification_id, "is_read": True},
        )

    # --- Connection Health & Inspection Queries ---

    def is_user_connected(self, user_id: int) -> bool:
        """Checks if a user has at least one active Socket.IO connection."""
        return user_id in self._user_sockets and len(self._user_sockets[user_id]) > 0

    def get_user_connection_count(self, user_id: int) -> int:
        """Returns the number of simultaneous active sockets for a user."""
        return len(self._user_sockets.get(user_id, set()))

    def get_active_users_count(self) -> int:
        """Returns the number of unique authenticated users currently connected."""
        return len(self._user_sockets)

    def get_connected_user_ids(self) -> List[int]:
        """Returns the list of connected user IDs."""
        return list(self._user_sockets.keys())

    def get_acknowledgement(self, user_id: int, notification_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves delivery acknowledgement recorded for a specific user and notification."""
        return self._acknowledgements.get(f"{user_id}:{notification_id}")

    async def shutdown(self) -> None:
        """Gracefully disconnects all connected sockets during application shutdown."""
        logger.info("Shutting down Socket.IO manager: disconnecting %d users", len(self._user_sockets))
        all_sids = list(self._socket_sessions.keys())
        for sid in all_sids:
            try:
                await self.sio.disconnect(sid)
            except Exception:
                pass
        self._user_sockets.clear()
        self._socket_sessions.clear()


# Global Singleton Instance
socket_manager = SocketManager()
