from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from backend.app.models.schema import NotificationType, UserRole


class NotificationCategory(str, Enum):
    AUTH = "AUTH"
    INVENTORY = "INVENTORY"
    PRICING = "PRICING"
    OPTIMIZATION = "OPTIMIZATION"
    PROCUREMENT = "PROCUREMENT"
    SYSTEM = "SYSTEM"


class NotificationSeverity(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"


# Standardized Socket.IO Event Names
SOCKET_EVENT_NOTIFICATION_NEW = "notification:new"
SOCKET_EVENT_NOTIFICATION_READ = "notification:read"
SOCKET_EVENT_NOTIFICATION_UNREAD_COUNT = "notification:unread_count"
SOCKET_EVENT_NOTIFICATION_ACKNOWLEDGED = "notification:acknowledged"
SOCKET_EVENT_CONNECTION_STATUS = "connection:status"


# Standard Business & System Event Names
class EventTypes:
    # A. Authentication & Security
    AUTH_SUSPICIOUS_LOGIN = "auth.suspicious_login"
    AUTH_FAILED_LOGINS = "auth.failed_logins"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    AUTH_ACCOUNT_STATUS = "auth.account_status"
    AUTH_UNAUTHORIZED_ACCESS = "auth.unauthorized_access"

    # B. Inventory Management
    INVENTORY_UNAVAILABILITY = "inventory.unavailability"
    INVENTORY_LOW_THRESHOLD = "inventory.low_threshold"
    INVENTORY_SYNC_FAILURE = "inventory.sync_failure"
    INVENTORY_PRICE_CHANGE = "inventory.price_change"
    INVENTORY_ALLOCATION_FAILURE = "inventory.allocation_failure"
    INVENTORY_STALE_DATA = "inventory.stale_data"

    # C. Pricing & Profitability
    PRICING_MARGIN_LOW = "pricing.margin_low"
    PRICING_COST_INCREASE = "pricing.cost_increase"
    PRICING_UNPROFITABLE = "pricing.unprofitable"
    PRICING_CURRENCY_IMPACT = "pricing.currency_impact"
    PRICING_BUDGET_THRESHOLD = "pricing.budget_threshold"

    # D. Optimization
    OPTIMIZATION_COMPLETED = "optimization.completed"
    OPTIMIZATION_FAILED = "optimization.failed"
    OPTIMIZATION_INFEASIBLE = "optimization.infeasible"
    OPTIMIZATION_PROFIT_IMPROVEMENT = "optimization.profit_improvement"
    OPTIMIZATION_REALLOCATION = "optimization.reallocation"
    OPTIMIZATION_APPROVAL_REQUIRED = "optimization.approval_required"

    # E. Procurement & Supplier Operations
    PROCUREMENT_PO_CREATED = "procurement.po_created"
    PROCUREMENT_PO_APPROVED = "procurement.po_approved"
    PROCUREMENT_PO_REJECTED = "procurement.po_rejected"
    PROCUREMENT_FULFILLMENT_DELAYED = "procurement.fulfillment_delayed"
    PROCUREMENT_SUPPLIER_UNAVAILABLE = "procurement.supplier_unavailable"
    PROCUREMENT_SUPPLIER_DROP = "procurement.supplier_performance_drop"
    PROCUREMENT_DISPUTE_ATTENTION = "procurement.dispute_attention"

    # F. System & Pipeline Monitoring
    SYSTEM_ERROR_RATE = "system.error_rate_threshold"
    SYSTEM_DB_CONNECTIVITY = "system.db_connectivity"
    SYSTEM_DATA_INGESTION = "system.data_ingestion_failure"
    SYSTEM_PIPELINE_FAILURE = "system.pipeline_failure"
    SYSTEM_HEALTH_DEGRADATION = "system.health_degradation"
    SYSTEM_BACKGROUND_FAILURE = "system.background_failure"


EVENT_CATEGORY_MAP: Dict[str, NotificationCategory] = {
    # Auth
    EventTypes.AUTH_SUSPICIOUS_LOGIN: NotificationCategory.AUTH,
    EventTypes.AUTH_FAILED_LOGINS: NotificationCategory.AUTH,
    EventTypes.AUTH_PASSWORD_RESET: NotificationCategory.AUTH,
    EventTypes.AUTH_ACCOUNT_STATUS: NotificationCategory.AUTH,
    EventTypes.AUTH_UNAUTHORIZED_ACCESS: NotificationCategory.AUTH,
    # Inventory
    EventTypes.INVENTORY_UNAVAILABILITY: NotificationCategory.INVENTORY,
    EventTypes.INVENTORY_LOW_THRESHOLD: NotificationCategory.INVENTORY,
    EventTypes.INVENTORY_SYNC_FAILURE: NotificationCategory.INVENTORY,
    EventTypes.INVENTORY_PRICE_CHANGE: NotificationCategory.INVENTORY,
    EventTypes.INVENTORY_ALLOCATION_FAILURE: NotificationCategory.INVENTORY,
    EventTypes.INVENTORY_STALE_DATA: NotificationCategory.INVENTORY,
    # Pricing
    EventTypes.PRICING_MARGIN_LOW: NotificationCategory.PRICING,
    EventTypes.PRICING_COST_INCREASE: NotificationCategory.PRICING,
    EventTypes.PRICING_UNPROFITABLE: NotificationCategory.PRICING,
    EventTypes.PRICING_CURRENCY_IMPACT: NotificationCategory.PRICING,
    EventTypes.PRICING_BUDGET_THRESHOLD: NotificationCategory.PRICING,
    # Optimization
    EventTypes.OPTIMIZATION_COMPLETED: NotificationCategory.OPTIMIZATION,
    EventTypes.OPTIMIZATION_FAILED: NotificationCategory.OPTIMIZATION,
    EventTypes.OPTIMIZATION_INFEASIBLE: NotificationCategory.OPTIMIZATION,
    EventTypes.OPTIMIZATION_PROFIT_IMPROVEMENT: NotificationCategory.OPTIMIZATION,
    EventTypes.OPTIMIZATION_REALLOCATION: NotificationCategory.OPTIMIZATION,
    EventTypes.OPTIMIZATION_APPROVAL_REQUIRED: NotificationCategory.OPTIMIZATION,
    # Procurement
    EventTypes.PROCUREMENT_PO_CREATED: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_PO_APPROVED: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_PO_REJECTED: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_FULFILLMENT_DELAYED: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_SUPPLIER_UNAVAILABLE: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_SUPPLIER_DROP: NotificationCategory.PROCUREMENT,
    EventTypes.PROCUREMENT_DISPUTE_ATTENTION: NotificationCategory.PROCUREMENT,
    # System
    EventTypes.SYSTEM_ERROR_RATE: NotificationCategory.SYSTEM,
    EventTypes.SYSTEM_DB_CONNECTIVITY: NotificationCategory.SYSTEM,
    EventTypes.SYSTEM_DATA_INGESTION: NotificationCategory.SYSTEM,
    EventTypes.SYSTEM_PIPELINE_FAILURE: NotificationCategory.SYSTEM,
    EventTypes.SYSTEM_HEALTH_DEGRADATION: NotificationCategory.SYSTEM,
    EventTypes.SYSTEM_BACKGROUND_FAILURE: NotificationCategory.SYSTEM,
}

# Standard Roles supported across business notifications
class RoleNames:
    ADMIN = "ADMIN"
    PROCUREMENT_MANAGER = "PROCUREMENT_MANAGER"
    ANALYST = "ANALYST"


EVENT_DEFAULT_ROLES: Dict[str, List[str]] = {
    # Auth
    EventTypes.AUTH_SUSPICIOUS_LOGIN: [RoleNames.ADMIN],
    EventTypes.AUTH_FAILED_LOGINS: [RoleNames.ADMIN],
    EventTypes.AUTH_PASSWORD_RESET: [RoleNames.ADMIN],
    EventTypes.AUTH_ACCOUNT_STATUS: [RoleNames.ADMIN],
    EventTypes.AUTH_UNAUTHORIZED_ACCESS: [RoleNames.ADMIN],
    # Inventory
    EventTypes.INVENTORY_UNAVAILABILITY: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ANALYST],
    EventTypes.INVENTORY_LOW_THRESHOLD: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ANALYST],
    EventTypes.INVENTORY_SYNC_FAILURE: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.INVENTORY_PRICE_CHANGE: [RoleNames.ANALYST, RoleNames.PROCUREMENT_MANAGER],
    EventTypes.INVENTORY_ALLOCATION_FAILURE: [RoleNames.PROCUREMENT_MANAGER],
    EventTypes.INVENTORY_STALE_DATA: [RoleNames.ADMIN, RoleNames.ANALYST],
    # Pricing
    EventTypes.PRICING_MARGIN_LOW: [RoleNames.ANALYST, RoleNames.ADMIN],
    EventTypes.PRICING_COST_INCREASE: [RoleNames.ANALYST, RoleNames.PROCUREMENT_MANAGER],
    EventTypes.PRICING_UNPROFITABLE: [RoleNames.ANALYST, RoleNames.ADMIN],
    EventTypes.PRICING_CURRENCY_IMPACT: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.PRICING_BUDGET_THRESHOLD: [RoleNames.ADMIN, RoleNames.PROCUREMENT_MANAGER],
    # Optimization
    EventTypes.OPTIMIZATION_COMPLETED: [RoleNames.ANALYST, RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    EventTypes.OPTIMIZATION_FAILED: [RoleNames.ANALYST, RoleNames.ADMIN],
    EventTypes.OPTIMIZATION_INFEASIBLE: [RoleNames.ANALYST, RoleNames.PROCUREMENT_MANAGER],
    EventTypes.OPTIMIZATION_PROFIT_IMPROVEMENT: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.OPTIMIZATION_REALLOCATION: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ANALYST],
    EventTypes.OPTIMIZATION_APPROVAL_REQUIRED: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    # Procurement
    EventTypes.PROCUREMENT_PO_CREATED: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    EventTypes.PROCUREMENT_PO_APPROVED: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    EventTypes.PROCUREMENT_PO_REJECTED: [RoleNames.PROCUREMENT_MANAGER],
    EventTypes.PROCUREMENT_FULFILLMENT_DELAYED: [RoleNames.PROCUREMENT_MANAGER],
    EventTypes.PROCUREMENT_SUPPLIER_UNAVAILABLE: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ANALYST],
    EventTypes.PROCUREMENT_SUPPLIER_DROP: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    EventTypes.PROCUREMENT_DISPUTE_ATTENTION: [RoleNames.PROCUREMENT_MANAGER, RoleNames.ADMIN],
    # System
    EventTypes.SYSTEM_ERROR_RATE: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.SYSTEM_DB_CONNECTIVITY: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.SYSTEM_DATA_INGESTION: [RoleNames.ADMIN, RoleNames.ANALYST],
    EventTypes.SYSTEM_PIPELINE_FAILURE: [RoleNames.ANALYST, RoleNames.ADMIN],
    EventTypes.SYSTEM_HEALTH_DEGRADATION: [RoleNames.ADMIN],
    EventTypes.SYSTEM_BACKGROUND_FAILURE: [RoleNames.ADMIN, RoleNames.ANALYST],
}



def map_event_to_orm_type(event_type: str) -> NotificationType:
    """
    Safely maps rich fine-grained event types to existing SQLAlchemy ORM NotificationType enum.
    Guarantees strict database integrity without requiring DDL alterations.
    """
    evt = event_type.lower()
    if "completed" in evt:
        return NotificationType.RUN_COMPLETED
    if "failed" in evt or "infeasible" in evt:
        return NotificationType.RUN_FAILED
    if "approval" in evt or "pending" in evt or "created" in evt:
        return NotificationType.RECOMMENDATION_PENDING
    if "approved" in evt:
        return NotificationType.RECOMMENDATION_APPROVED
    if "overdue" in evt or "delayed" in evt or "dispute" in evt or "rejected" in evt:
        return NotificationType.PO_OVERDUE
    if "supplier" in evt or "drop" in evt:
        return NotificationType.SUPPLIER_PERFORMANCE_DROP
    if "drift" in evt or "margin" in evt or "price" in evt:
        return NotificationType.MODEL_DRIFT
    # Default fallback for system/data/alert events
    return NotificationType.DATA_QUALITY_ALERT
