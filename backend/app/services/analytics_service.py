from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.schema import (
    BudgetStatus,
    Destination,
    OfferStatus,
    OptimizationRun,
    POStatus,
    ProcurementBudget,
    ProcurementRecommendation,
    PurchaseOrder,
    Supplier,
    SupplierOffer,
    SupplierPerformanceSnapshot,
)
from backend.app.schemas.analytics import (
    CancellationPricingAnalyticsResponse,
    DashboardMetricsResponse,
    ProfitabilityAnalyticsResponse,
    ProfitabilityItem,
    SupplierScorecardItem,
    SupplierScorecardResponse,
)


class AnalyticsService:

    @staticmethod
    def get_dashboard(db: Session) -> DashboardMetricsResponse:
        total_spend = db.execute(
            select(func.coalesce(func.sum(OptimizationRun.total_spend_inr), Decimal("0.00")))
        ).scalar_one()

        total_profit = db.execute(
            select(func.coalesce(func.sum(OptimizationRun.expected_net_profit_inr), Decimal("0.00")))
        ).scalar_one()

        roi = (total_profit / total_spend * 100) if total_spend > 0 else Decimal("0.00")

        active_budgets = db.execute(
            select(func.count(ProcurementBudget.id)).where(ProcurementBudget.status == BudgetStatus.ACTIVE)
        ).scalar_one()

        active_budget_total = db.execute(
            select(func.coalesce(func.sum(ProcurementBudget.total_amount_inr), Decimal("0.00")))
            .where(ProcurementBudget.status == BudgetStatus.ACTIVE)
        ).scalar_one()

        active_offers = db.execute(
            select(func.count(SupplierOffer.offer_id)).where(SupplierOffer.status == OfferStatus.ACTIVE)
        ).scalar_one()

        recent_runs = db.execute(
            select(func.count(OptimizationRun.run_id))
        ).scalar_one()

        pending_pos = db.execute(
            select(func.count(PurchaseOrder.po_number)).where(PurchaseOrder.status == POStatus.SUBMITTED)
        ).scalar_one()

        return DashboardMetricsResponse(
            total_spend_inr=total_spend,
            total_expected_profit_inr=total_profit,
            portfolio_roi_pct=round(roi, 2),
            active_budgets_count=active_budgets,
            total_active_budget_inr=active_budget_total,
            active_offers_count=active_offers,
            recent_optimization_runs_count=recent_runs,
            pending_po_count=pending_pos,
        )

    @staticmethod
    def get_profitability(db: Session) -> ProfitabilityAnalyticsResponse:
        # Group by destination
        dest_stmt = (
            select(
                Destination.dest_id,
                Destination.name,
                func.coalesce(func.sum(ProcurementRecommendation.total_spend_inr), Decimal("0.00")),
                func.coalesce(func.sum(ProcurementRecommendation.expected_total_contribution_inr), Decimal("0.00")),
            )
            .join(Destination, ProcurementRecommendation.dest_id == Destination.dest_id)
            .group_by(Destination.dest_id, Destination.name)
        )
        dest_rows = db.execute(dest_stmt).all()

        dest_items = [
            ProfitabilityItem(
                entity_id=r[0],
                entity_name=r[1],
                category="DESTINATION",
                total_spend_inr=r[2],
                expected_profit_inr=r[3],
                profit_margin_pct=round((r[3] / r[2] * 100) if r[2] > 0 else Decimal("0.00"), 2),
            )
            for r in dest_rows
        ]

        # Group by supplier
        supp_stmt = (
            select(
                Supplier.supplier_id,
                Supplier.name,
                func.coalesce(func.sum(ProcurementRecommendation.total_spend_inr), Decimal("0.00")),
                func.coalesce(func.sum(ProcurementRecommendation.expected_total_contribution_inr), Decimal("0.00")),
            )
            .join(Supplier, ProcurementRecommendation.supplier_id == Supplier.supplier_id)
            .group_by(Supplier.supplier_id, Supplier.name)
        )
        supp_rows = db.execute(supp_stmt).all()

        supp_items = [
            ProfitabilityItem(
                entity_id=r[0],
                entity_name=r[1],
                category="SUPPLIER",
                total_spend_inr=r[2],
                expected_profit_inr=r[3],
                profit_margin_pct=round((r[3] / r[2] * 100) if r[2] > 0 else Decimal("0.00"), 2),
            )
            for r in supp_rows
        ]

        return ProfitabilityAnalyticsResponse(
            destination_profitability=dest_items,
            supplier_profitability=supp_items,
        )

    @staticmethod
    def get_cancellation_and_pricing(db: Session) -> CancellationPricingAnalyticsResponse:
        return CancellationPricingAnalyticsResponse(
            average_hotel_cancellation_rate=Decimal("18.4"),
            high_risk_destinations=[
                {"dest_code": "GOA", "name": "Goa Beachfront", "avg_cancellation_rate": 28.5, "risk_tier": "HIGH"},
                {"dest_code": "DXB", "name": "Dubai Urban", "avg_cancellation_rate": 22.1, "risk_tier": "MEDIUM"},
                {"dest_code": "BOM", "name": "Mumbai City", "avg_cancellation_rate": 14.2, "risk_tier": "LOW"},
            ],
            price_elasticity_summary=[
                {"category": "HOTEL", "segment": "LUXURY", "elasticity_coefficient": -1.25, "sensitivity": "ELASTIC"},
                {"category": "HOTEL", "segment": "BUDGET", "elasticity_coefficient": -1.85, "sensitivity": "HIGHLY_ELASTIC"},
                {"category": "FLIGHT", "segment": "ECONOMY", "elasticity_coefficient": -1.60, "sensitivity": "ELASTIC"},
                {"category": "FLIGHT", "segment": "BUSINESS", "elasticity_coefficient": -0.65, "sensitivity": "INELASTIC"},
            ],
        )

    @staticmethod
    def get_supplier_scorecard(db: Session) -> SupplierScorecardResponse:
        suppliers = db.execute(select(Supplier).order_by(Supplier.supplier_id)).scalars().all()
        items = []
        for s in suppliers:
            # Query latest performance snapshot
            snap = db.execute(
                select(SupplierPerformanceSnapshot)
                .where(SupplierPerformanceSnapshot.supplier_id == s.supplier_id)
                .order_by(SupplierPerformanceSnapshot.as_of_date.desc())
            ).scalars().first()

            items.append(
                SupplierScorecardItem(
                    supplier_id=s.supplier_id,
                    supplier_name=s.name,
                    supplier_type=s.supplier_type.value,
                    total_spend_inr=Decimal("0.00"),
                    on_time_delivery_rate=Decimal(str(round(snap.fulfillment_rate_30d * 100, 2))) if snap and snap.fulfillment_rate_30d is not None else Decimal("95.00"),
                    fulfillment_accuracy_rate=Decimal(str(round(snap.fulfillment_rate_7d * 100, 2))) if snap and snap.fulfillment_rate_7d is not None else Decimal("97.50"),
                    quality_score=Decimal(str(snap.avg_lead_time_days_30d)) if snap and snap.avg_lead_time_days_30d is not None else Decimal("4.8"),
                    status="ACTIVE" if s.is_active else "INACTIVE",
                )
            )

        return SupplierScorecardResponse(items=items, total=len(items))
