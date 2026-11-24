from __future__ import annotations

import pytest


def test_notifications_and_preferences(client, admin_headers, pm_headers):
    """Test #155 to #162: Notifications, read status, mark-all, preferences, and delivery audits."""
    # 156. GET /notifications/unread-count
    unread_res = client.get("/api/v1/notifications/unread-count", headers=pm_headers)
    assert unread_res.status_code == 200
    assert "unread_count" in unread_res.json()

    # 155. GET /notifications (list)
    list_notifs = client.get("/api/v1/notifications", headers=pm_headers)
    assert list_notifs.status_code == 200
    assert "items" in list_notifs.json()

    # 158. POST /notifications/mark-all-read
    mark_all = client.post("/api/v1/notifications/mark-all-read", headers=pm_headers)
    assert mark_all.status_code == 200

    # 160. GET /notification-preferences
    prefs_res = client.get("/api/v1/notification-preferences", headers=pm_headers)
    assert prefs_res.status_code == 200
    assert "preferences" in prefs_res.json()

    # 161. PUT /notification-preferences
    put_prefs = client.put(
        "/api/v1/notification-preferences",
        headers=pm_headers,
        json={
            "preferences": [
                {"notification_type": "BUDGET_ALERT", "channel": "EMAIL", "is_enabled": True},
                {"notification_type": "PO_CONFIRMATION", "channel": "IN_APP", "is_enabled": False},
            ]
        }
    )
    assert put_prefs.status_code == 200
    assert len(put_prefs.json()["preferences"]) == 2

    # 162. GET /notifications/deliveries (Admin only)
    deliv_res = client.get("/api/v1/notifications/deliveries", headers=admin_headers)
    assert deliv_res.status_code == 200
    assert "items" in deliv_res.json()
