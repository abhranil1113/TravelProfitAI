from __future__ import annotations

from fastapi import APIRouter

# Stage 1: Auth & User Management (1-19)
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.users import router as users_router

# Stage 2: Destinations, Suppliers, Inventory, Offers (20-54)
from backend.app.api.v1.destinations import router as destinations_router
from backend.app.api.v1.suppliers import (
    router as suppliers_router,
    contacts_router as supplier_contacts_router,
)
from backend.app.api.v1.inventory import (
    router as inventory_router,
    snapshots_router as inventory_snapshots_router,
)
from backend.app.api.v1.supplier_offers import router as supplier_offers_router

# Stage 3: Reference Data, Data Pipeline, Quality, Search Events (55-69, 163-165, 180)
from backend.app.api.v1.reference_data import (
    signals_router as market_signals_router,
    rates_router as exchange_rates_router,
    baselines_router as market_segment_baselines_router,
)
from backend.app.api.v1.pipelines import router as pipelines_router
from backend.app.api.v1.search_events import router as search_events_router

# Stage 4: Feature Sets, ML Registry, Predictions & Forecasts (70-87)
from backend.app.api.v1.ml_registry import router as ml_registry_router
from backend.app.api.v1.forecasts import (
    predictions_router,
    forecasts_router,
)

# Stage 5: Admin Config & Budgets (88-105)
from backend.app.api.v1.admin_config import router as admin_config_router
from backend.app.api.v1.budgets import router as budgets_router

# Stage 6: Optimization Runs & Recommendations (106-132, 176, 178, 179)
from backend.app.api.v1.optimization import router as optimization_router
from backend.app.api.v1.recommendations import (
    recommendations_router,
    run_recommendations_router,
)

# Stage 7: Purchase Orders & Fulfillment (133-143)
from backend.app.api.v1.procurement import (
    router as purchase_orders_router,
    fulfillments_router as purchase_order_fulfillments_router,
)

# Stage 8: Reports, Notifications & Audit Logs (144-162, 166-167)
from backend.app.api.v1.reports import (
    reports_router,
    report_schedules_router,
)
from backend.app.api.v1.notifications import (
    notifications_router,
    notification_preferences_router,
)
from backend.app.api.v1.audit_logs import router as audit_logs_router

# Stage 9: Analytics, Economics & Health (168-175, 177)
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.economics import router as economics_router
from backend.app.api.v1.health import router as health_router

api_router = APIRouter()

# Stage 1: Auth & User Management (1-19)
api_router.include_router(auth_router)
api_router.include_router(users_router)

# Stage 2: Destinations, Suppliers, Inventory, Offers (20-54)
api_router.include_router(destinations_router)
api_router.include_router(suppliers_router)
api_router.include_router(supplier_contacts_router)
api_router.include_router(inventory_router)
api_router.include_router(inventory_snapshots_router)
api_router.include_router(supplier_offers_router)

# Stage 3: Reference Data, Pipeline, Quality, Search Events (55-69, 163-165, 180)
api_router.include_router(market_signals_router)
api_router.include_router(exchange_rates_router)
api_router.include_router(market_segment_baselines_router)
api_router.include_router(pipelines_router)
api_router.include_router(search_events_router)

# Stage 4: Feature Sets, ML Registry, Predictions & Forecasts (70-87)
api_router.include_router(ml_registry_router)
api_router.include_router(predictions_router)
api_router.include_router(forecasts_router)

# Stage 5: Admin Config & Budgets (88-105)
api_router.include_router(admin_config_router)
api_router.include_router(budgets_router)

# Stage 6: Optimization Runs & Recommendations (106-132, 176, 178, 179)
api_router.include_router(optimization_router)
api_router.include_router(recommendations_router)
api_router.include_router(run_recommendations_router)

# Stage 7: Purchase Orders & Fulfillment (133-143)
api_router.include_router(purchase_orders_router)
api_router.include_router(purchase_order_fulfillments_router)

# Stage 8: Reports, Notifications & Audit Logs (144-162, 166-167)
api_router.include_router(reports_router)
api_router.include_router(report_schedules_router)
api_router.include_router(notifications_router)
api_router.include_router(notification_preferences_router)
api_router.include_router(audit_logs_router)

# Stage 9: Analytics, Economics & Health (168-175, 177)
api_router.include_router(analytics_router)
api_router.include_router(economics_router)
api_router.include_router(health_router)
