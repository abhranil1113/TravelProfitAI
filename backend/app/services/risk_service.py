from __future__ import annotations

import logging
import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from ortools.linear_solver import pywraplp
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    EntityNotFoundError,
)
from backend.app.models.schema import (
    ApprovalStatus,
    AuditLog,
    BudgetStatus,
    CVaROptimizationRecord,
    Destination,
    InventoryCategory,
    OptimizationMode,
    OptimizationRun,
    PipelineStatus,
    PolicyScope,
    PortfolioStressTest,
    ProcurementBudget,
    ProcurementRecommendation,
    RiskScenario,
    RiskScenarioType,
    SolverBackend,
    SolverStatus,
    StressTestStatus,
    Supplier,
    SupplierOffer,
    UnitType,
)
from backend.app.schemas.risk import (
    CVaROptimizationRequest,
    PortfolioRiskSummaryResponse,
    RiskAdjustedComparisonItem,
    RiskAdjustedComparisonResponse,
    RiskScenarioCreateRequest,
    RiskScenarioUpdateRequest,
    StressTestBatchResponse,
    StressTestExecuteRequest,
)
from optimization.config import FinancialAssumptions, SolverConfig, SolverBackend as OptSolverBackend
from optimization.economics.flight_economics import FlightEconomicsCalculator
from optimization.economics.hotel_economics import HotelEconomicsCalculator
from optimization.solvers.solver_factory import SolverFactory

logger = logging.getLogger(__name__)


def _compute_empirical_var_cvar(
    losses: List[float],
    weights: List[float],
    alpha: float = 0.95,
) -> Tuple[float, float]:
    """
    Computes discrete weighted Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR)
    on a loss distribution using the Rockafellar-Uryasev tail expectation definition.
    Positive loss represents downside relative to baseline or negative profit.
    """
    if not losses:
        return 0.0, 0.0
    total_w = sum(weights)
    probs = [w / total_w for w in weights] if total_w > 0 else [1.0 / len(losses)] * len(losses)

    paired = sorted(zip(losses, probs), key=lambda x: x[0])
    cum_p = 0.0
    var_val = paired[-1][0]
    for loss_val, p in paired:
        cum_p += p
        if cum_p >= alpha - 1e-12:
            var_val = loss_val
            break

    # Rockafellar-Uryasev exact CVaR: VaR + 1/(1-alpha) * E[max(0, L - VaR)]
    tail_excess = sum(p * max(0.0, loss_val - var_val) for loss_val, p in paired)
    cvar_val = var_val + tail_excess / max(1e-9, (1.0 - alpha))
    return round(var_val, 2), round(cvar_val, 2)


def _apply_correlated_factor_shocks(scenario: RiskScenario) -> Dict[str, float]:
    """
    Computes effective factor shocks using the scenario's correlation matrix (via Cholesky
    decomposition if factor_volatilities & factor_z_scores are provided in shock_parameters_json)
    combined with explicit scenario shock parameters.
    """
    demand_mult = float(scenario.demand_multiplier)
    cancel_delta = float(scenario.cancellation_delta)
    fx_shock = float(scenario.fx_shock_pct)
    cap_mult = float(scenario.supplier_capacity_multiplier)

    corr_mat = scenario.correlation_matrix_json or {}
    params = scenario.shock_parameters_json or {}
    z_map = params.get("factor_z_scores")
    vol_map = params.get("factor_volatilities")

    if corr_mat and isinstance(z_map, dict) and isinstance(vol_map, dict):
        factors = sorted(corr_mat.keys())
        mat = np.array([[float(corr_mat[r][c]) for c in factors] for r in factors], dtype=float)
        # Ensure positive semi-definite via eigenvalue floor & exact symmetry before Cholesky
        mat = 0.5 * (mat + mat.T)
        eigvals, eigvecs = np.linalg.eigh(mat)
        eigvals = np.maximum(eigvals, 1e-8)
        psd_mat = eigvecs @ np.diag(eigvals) @ eigvecs.T
        psd_mat = 0.5 * (psd_mat + psd_mat.T)
        L = np.linalg.cholesky(psd_mat)
        z_vec = np.array([float(z_map.get(f, 0.0)) for f in factors], dtype=float)
        corr_z = L @ z_vec
        for idx, f in enumerate(factors):
            shock = float(corr_z[idx]) * float(vol_map.get(f, 0.0))
            if f == "demand":
                demand_mult = max(0.05, demand_mult * (1.0 + shock))
            elif f == "cancellation":
                cancel_delta = max(-0.95, min(0.95, cancel_delta + shock))
            elif f == "fx":
                fx_shock = max(-0.90, fx_shock + shock)
            elif f == "capacity":
                cap_mult = max(0.0, min(2.0, cap_mult * (1.0 + shock)))

    return {
        "demand_multiplier": demand_mult,
        "cancellation_delta": cancel_delta,
        "fx_shock_pct": fx_shock,
        "supplier_capacity_multiplier": cap_mult,
    }


def _compute_offer_scenario_economics(
    offer: SupplierOffer,
    shocks: Dict[str, float],
    scenario: RiskScenario,
    hotel_calc: HotelEconomicsCalculator,
    flight_calc: FlightEconomicsCalculator,
    base_cancel_prob: float = 0.20,
    base_sell_through: float = 0.85,
) -> Dict[str, float]:
    """
    Calculates exact scenario-adjusted unit cost, unit contribution, effective capacity,
    and effective sell-through for an offer under a specific RiskScenario.
    """
    # Check if scenario targets a specific destination or supplier
    applies = True
    if scenario.target_dest_id and offer.dest_id != scenario.target_dest_id:
        applies = False
    if scenario.target_supplier_id and offer.supplier_id != scenario.target_supplier_id:
        applies = False

    d_mult = shocks["demand_multiplier"] if applies else 1.0
    c_delta = shocks["cancellation_delta"] if applies else 0.0
    fx_shock = shocks["fx_shock_pct"] if applies else 0.0
    cap_mult = shocks["supplier_capacity_multiplier"] if applies else 1.0

    unit_cost = float(offer.unit_cost_inr)
    list_price = float(offer.list_price_inr)

    # Apply FX shock to foreign-currency offers, or all if scenario explicitly models global FX cost pass-through
    apply_fx_all = bool((scenario.shock_parameters_json or {}).get("apply_fx_to_all", True))
    if (offer.currency_code and offer.currency_code.upper() != "INR") or apply_fx_all:
        stressed_cost = max(0.0, unit_cost * (1.0 + fx_shock))
    else:
        stressed_cost = unit_cost

    # Demand shock adjusts effective sell-through up or down (bounded in [0.05, 0.99])
    adj_sell_through = max(0.05, min(0.99, base_sell_through * d_mult))

    if offer.inventory_category == InventoryCategory.HOTEL:
        p_cancel = max(0.01, min(0.99, base_cancel_prob + c_delta))
        # Temporarily adjust hotel sell-through for scenario
        orig_theta = hotel_calc.assumptions.hotel_base_sell_through
        hotel_calc.assumptions.hotel_base_sell_through = adj_sell_through
        try:
            econ = hotel_calc.calculate_expected_contribution(
                purchase_cost=stressed_cost,
                selling_price=list_price,
                cancellation_prob=p_cancel,
                is_supplier_refundable=(offer.supplier_refund_cancelled_r_c > 0),
            )
        finally:
            hotel_calc.assumptions.hotel_base_sell_through = orig_theta
        unit_contrib = float(econ["expected_net_contribution"])
    else:
        econ = flight_calc.calculate_expected_contribution(
            purchase_cost=stressed_cost,
            contract_selling_price=list_price,
            sell_through=adj_sell_through,
        )
        unit_contrib = float(econ["expected_net_contribution"])

    eff_cap = int(math.floor(offer.max_capacity * cap_mult))
    return {
        "unit_cost": stressed_cost,
        "unit_contribution": unit_contrib,
        "effective_capacity": eff_cap,
        "effective_sell_through": adj_sell_through,
        "demand_multiplier": d_mult,
    }


class RiskService:
    """Service layer for Domain 1: Advanced Portfolio Risk & Scenario Engine."""

    @staticmethod
    def create_scenario(db: Session, req: RiskScenarioCreateRequest, user_id: int) -> RiskScenario:
        existing = db.execute(
            select(RiskScenario).where(RiskScenario.scenario_code == req.scenario_code)
        ).scalar_one_or_none()
        if existing:
            raise ConflictException(f"Risk scenario '{req.scenario_code}' already exists.")

        if req.target_dest_id:
            dest = db.execute(
                select(Destination).where(Destination.dest_id == req.target_dest_id.upper())
            ).scalar_one_or_none()
            if not dest:
                raise EntityNotFoundError("Destination", req.target_dest_id)

        if req.target_supplier_id:
            sup = db.execute(
                select(Supplier).where(Supplier.supplier_id == req.target_supplier_id.upper())
            ).scalar_one_or_none()
            if not sup:
                raise EntityNotFoundError("Supplier", req.target_supplier_id)

        scen = RiskScenario(
            scenario_code=req.scenario_code,
            name=req.name.strip(),
            description=req.description,
            scenario_type=req.scenario_type,
            probability_weight=req.probability_weight,
            demand_multiplier=req.demand_multiplier,
            cancellation_delta=req.cancellation_delta,
            fx_shock_pct=req.fx_shock_pct,
            supplier_capacity_multiplier=req.supplier_capacity_multiplier,
            correlation_matrix_json=req.correlation_matrix_json,
            shock_parameters_json=req.shock_parameters_json,
            target_dest_id=req.target_dest_id.upper() if req.target_dest_id else None,
            target_supplier_id=req.target_supplier_id.upper() if req.target_supplier_id else None,
            is_active=req.is_active,
            created_by_user_id=user_id,
        )
        db.add(scen)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="RISK_SCENARIO_CREATED",
            entity_type="risk_scenarios",
            entity_id=str(scen.id),
            new_value_json={"scenario_code": scen.scenario_code, "type": scen.scenario_type.value},
        ))
        db.commit()
        db.refresh(scen)
        return scen

    @staticmethod
    def list_scenarios(
        db: Session,
        scenario_type: Optional[RiskScenarioType] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RiskScenario], int]:
        stmt = select(RiskScenario)
        if scenario_type:
            stmt = stmt.where(RiskScenario.scenario_type == scenario_type)
        if is_active is not None:
            stmt = stmt.where(RiskScenario.is_active == is_active)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            db.execute(
                stmt.order_by(RiskScenario.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return items, total

    @staticmethod
    def get_scenario(db: Session, scenario_id: int) -> RiskScenario:
        scen = db.execute(select(RiskScenario).where(RiskScenario.id == scenario_id)).scalar_one_or_none()
        if not scen:
            raise EntityNotFoundError("RiskScenario", scenario_id)
        return scen

    @staticmethod
    def update_scenario(
        db: Session, scenario_id: int, req: RiskScenarioUpdateRequest, user_id: int
    ) -> RiskScenario:
        scen = RiskService.get_scenario(db, scenario_id)
        updates = req.model_dump(exclude_unset=True)
        if "target_dest_id" in updates and updates["target_dest_id"] is not None:
            dest_code = str(updates["target_dest_id"]).upper()
            if not db.execute(select(Destination).where(Destination.dest_id == dest_code)).scalar_one_or_none():
                raise EntityNotFoundError("Destination", dest_code)
            updates["target_dest_id"] = dest_code
        if "target_supplier_id" in updates and updates["target_supplier_id"] is not None:
            sup_code = str(updates["target_supplier_id"]).upper()
            if not db.execute(select(Supplier).where(Supplier.supplier_id == sup_code)).scalar_one_or_none():
                raise EntityNotFoundError("Supplier", sup_code)
            updates["target_supplier_id"] = sup_code
        for k, v in updates.items():
            setattr(scen, k, v)
        db.add(AuditLog(
            user_id=user_id,
            action="RISK_SCENARIO_UPDATED",
            entity_type="risk_scenarios",
            entity_id=str(scen.id),
            new_value_json=updates,
        ))
        db.commit()
        db.refresh(scen)
        return scen

    @staticmethod
    def delete_scenario(db: Session, scenario_id: int, user_id: int) -> RiskScenario:
        scen = RiskService.get_scenario(db, scenario_id)
        scen.is_active = False
        db.add(AuditLog(
            user_id=user_id,
            action="RISK_SCENARIO_DEACTIVATED",
            entity_type="risk_scenarios",
            entity_id=str(scen.id),
        ))
        db.commit()
        db.refresh(scen)
        return scen

    @staticmethod
    def run_stress_test(
        db: Session, run_id: str, req: StressTestExecuteRequest, user_id: int
    ) -> StressTestBatchResponse:
        run = db.execute(select(OptimizationRun).where(OptimizationRun.run_id == run_id)).scalar_one_or_none()
        if not run:
            raise EntityNotFoundError("OptimizationRun", run_id)

        recs = list(
            db.execute(
                select(ProcurementRecommendation).where(ProcurementRecommendation.run_id == run_id)
            ).scalars().all()
        )
        if not recs:
            raise BadRequestException(f"Optimization run '{run_id}' has no procurement recommendations to stress test.")

        scenarios = list(
            db.execute(
                select(RiskScenario).where(RiskScenario.id.in_(req.scenario_ids), RiskScenario.is_active == True)
            ).scalars().all()
        )
        if len(scenarios) != len(set(req.scenario_ids)):
            found_ids = {s.id for s in scenarios}
            missing = [sid for sid in req.scenario_ids if sid not in found_ids]
            raise EntityNotFoundError("RiskScenario", missing[0])

        offer_ids = [r.offer_id for r in recs]
        offers = {
            o.offer_id: o
            for o in db.execute(select(SupplierOffer).where(SupplierOffer.offer_id.in_(offer_ids))).scalars().all()
        }

        assumptions = FinancialAssumptions()
        hotel_calc = HotelEconomicsCalculator(assumptions)
        flight_calc = FlightEconomicsCalculator(assumptions, use_optional_salvage=(run.salvage_assumption_pct > 0))

        baseline_profit = sum(float(r.expected_total_contribution_inr) for r in recs)
        scenario_losses: List[float] = []
        scenario_weights: List[float] = []
        scenario_results_tmp: List[Tuple[RiskScenario, float, float, float, float, List[Dict[str, Any]]]] = []

        for scen in scenarios:
            shocks = _apply_correlated_factor_shocks(scen)
            stressed_profit = 0.0
            total_rec_qty = 0
            total_avail_qty = 0
            total_demand_target = 0
            total_sold_qty = 0
            line_impacts: List[Dict[str, Any]] = []

            for r in recs:
                offer = offers.get(r.offer_id)
                if not offer:
                    continue
                econ = _compute_offer_scenario_economics(
                    offer=offer,
                    shocks=shocks,
                    scenario=scen,
                    hotel_calc=hotel_calc,
                    flight_calc=flight_calc,
                    base_sell_through=float(r.sell_through_rate),
                )
                eff_qty = min(r.recommended_qty, econ["effective_capacity"])
                line_stressed_profit = eff_qty * econ["unit_contribution"]
                # Unfulfilled contracted penalty if supplier capacity cut below committed qty
                shortfall_units = max(0, r.recommended_qty - eff_qty)
                if shortfall_units > 0:
                    line_stressed_profit -= shortfall_units * float(offer.spoilage_penalty_psi_inr)

                stressed_profit += line_stressed_profit
                total_rec_qty += r.recommended_qty
                total_avail_qty += eff_qty
                demand_units = max(1, int(round(r.recommended_qty * econ["demand_multiplier"])))
                sold_units = min(eff_qty, int(round(eff_qty * econ["effective_sell_through"])))
                total_demand_target += demand_units
                total_sold_qty += sold_units

                if req.include_line_impacts:
                    line_impacts.append({
                        "recommendation_id": r.id,
                        "offer_id": r.offer_id,
                        "supplier_id": r.supplier_id,
                        "dest_id": r.dest_id,
                        "baseline_profit_inr": round(float(r.expected_total_contribution_inr), 2),
                        "stressed_profit_inr": round(line_stressed_profit, 2),
                        "effective_capacity_units": eff_qty,
                        "fulfilled_demand_units": sold_units,
                    })

            loss_val = max(0.0, baseline_profit - stressed_profit)
            avail_pct = min(100.0, (total_avail_qty / max(1, total_rec_qty)) * 100.0)
            demand_pct = min(100.0, (total_sold_qty / max(1, total_demand_target)) * 100.0)
            scenario_losses.append(loss_val)
            scenario_weights.append(float(scen.probability_weight))
            scenario_results_tmp.append(
                (scen, stressed_profit, loss_val, avail_pct, demand_pct, line_impacts)
            )

        agg_var, agg_cvar = _compute_empirical_var_cvar(scenario_losses, scenario_weights, alpha=0.95)
        persisted: List[PortfolioStressTest] = []

        for scen, stressed_profit, loss_val, avail_pct, demand_pct, line_impacts in scenario_results_tmp:
            delta = stressed_profit - baseline_profit
            drawdown_pct = ((baseline_profit - stressed_profit) / baseline_profit * 100.0) if baseline_profit > 0 else 0.0
            # Individual scenario VaR/CVaR reflects tail loss relative to portfolio distribution
            st = PortfolioStressTest(
                run_id=run_id,
                scenario_id=scen.id,
                status=StressTestStatus.COMPLETED,
                baseline_profit_inr=Decimal(str(round(baseline_profit, 2))),
                stressed_profit_inr=Decimal(str(round(stressed_profit, 2))),
                profit_delta_inr=Decimal(str(round(delta, 2))),
                profit_drawdown_pct=round(drawdown_pct, 4),
                var_95_inr=Decimal(str(round(max(loss_val, agg_var), 2))),
                cvar_95_inr=Decimal(str(round(max(loss_val, agg_cvar), 2))),
                availability_fulfillment_pct=round(avail_pct, 2),
                demand_fulfillment_pct=round(demand_pct, 2),
                line_impacts_json=line_impacts,
                executed_by_user_id=user_id,
            )
            db.add(st)
            persisted.append(st)

        # Update run's risk_metrics_json with latest stress-test VaR/CVaR
        existing_rm = dict(run.risk_metrics_json or {})
        existing_rm["var_95_inr"] = agg_var
        existing_rm["cvar_95_inr"] = agg_cvar
        existing_rm["last_stress_test_at"] = datetime.now(timezone.utc).isoformat()
        run.risk_metrics_json = existing_rm

        db.add(AuditLog(
            user_id=user_id,
            action="STRESS_TEST_EXECUTED",
            entity_type="optimization_runs",
            entity_id=run_id,
            new_value_json={"scenario_ids": req.scenario_ids, "var_95": agg_var, "cvar_95": agg_cvar},
        ))
        db.commit()
        for st in persisted:
            db.refresh(st)

        worst_profit = min(st.stressed_profit_inr for st in persisted)
        worst_dd = max(st.profit_drawdown_pct for st in persisted)
        return StressTestBatchResponse(
            run_id=run_id,
            tests_executed=len(persisted),
            worst_case_profit_inr=worst_profit,
            worst_case_drawdown_pct=round(worst_dd, 4),
            aggregate_var_95_inr=Decimal(str(agg_var)),
            aggregate_cvar_95_inr=Decimal(str(agg_cvar)),
            results=persisted,
        )

    @staticmethod
    def list_stress_tests(db: Session, run_id: str) -> List[PortfolioStressTest]:
        run = db.execute(select(OptimizationRun).where(OptimizationRun.run_id == run_id)).scalar_one_or_none()
        if not run:
            raise EntityNotFoundError("OptimizationRun", run_id)
        return list(
            db.execute(
                select(PortfolioStressTest)
                .where(PortfolioStressTest.run_id == run_id)
                .order_by(PortfolioStressTest.created_at.desc())
            ).scalars().all()
        )

    @staticmethod
    def run_cvar_optimization(
        db: Session, req: CVaROptimizationRequest, user_id: int
    ) -> CVaROptimizationRecord:
        """
        Executes a genuine Rockafellar-Uryasev MILP portfolio optimization minimizing tail CVaR
        while maximizing expected profit subject to budget, supplier/destination concentration,
        MOQ, capacity, and availability/demand fulfillment targets across correlated scenarios.
        """
        if req.idempotency_key:
            existing_run = db.execute(
                select(OptimizationRun).where(OptimizationRun.idempotency_key == req.idempotency_key)
            ).scalar_one_or_none()
            if existing_run:
                rec = db.execute(
                    select(CVaROptimizationRecord).where(CVaROptimizationRecord.run_id == existing_run.run_id)
                ).scalar_one_or_none()
                if rec:
                    return rec

        unique_scenario_ids = list(dict.fromkeys(req.scenario_ids))
        if len(unique_scenario_ids) < 2:
            raise BadRequestException("At least 2 distinct active risk scenarios are required for CVaR optimization.")

        scenarios = list(
            db.execute(
                select(RiskScenario).where(RiskScenario.id.in_(unique_scenario_ids), RiskScenario.is_active == True)
            ).scalars().all()
        )
        if len(scenarios) != len(unique_scenario_ids):
            found = {s.id for s in scenarios}
            missing = [sid for sid in unique_scenario_ids if sid not in found]
            raise EntityNotFoundError("RiskScenario", missing[0])

        # Resolve budget (require ACTIVE status if explicit budget_id is provided)
        if req.total_budget_inr is not None:
            budget_inr = req.total_budget_inr
        elif req.budget_id is not None:
            b = db.execute(select(ProcurementBudget).where(ProcurementBudget.id == req.budget_id)).scalar_one_or_none()
            if not b:
                raise EntityNotFoundError("ProcurementBudget", req.budget_id)
            if b.status != BudgetStatus.ACTIVE:
                raise BadRequestException(f"Budget {b.id} must be ACTIVE (current: {b.status.value}).")
            budget_inr = max(Decimal("0.00"), b.total_amount_inr - b.spent_amount_inr - b.reserved_amount_inr)
        else:
            budget_inr = Decimal("10000000.00")

        if budget_inr <= 0:
            raise BadRequestException("Available budget must be positive for CVaR optimization.")

        # Enforce active OPTIMIZATION_RUN policy rules before running CVaR MILP
        from backend.app.services.policy_service import PolicyService
        PolicyService.enforce_workflow_policies(
            db=db,
            scope=PolicyScope.OPTIMIZATION_RUN,
            entity_type="optimization_runs",
            entity_id=req.idempotency_key or req.scenario_name or "cvar_optimization",
            context={
                "optimization_mode": req.optimization_mode.value,
                "budget_id": req.budget_id,
                "total_budget_inr": float(budget_inr),
                "max_supplier_share": float(req.max_supplier_share),
                "max_destination_share": float(req.max_destination_share),
                "solver_backend": req.solver_backend.value,
                "cvar_alpha": float(req.confidence_level_alpha),
                "risk_aversion_lambda": float(req.risk_aversion_lambda),
            },
            user_id=user_id,
        )

        # Load active offers matching optimization mode
        offer_stmt = select(SupplierOffer).where(SupplierOffer.max_capacity >= SupplierOffer.moq)
        if req.optimization_mode == OptimizationMode.HOTEL_ONLY:
            offer_stmt = offer_stmt.where(SupplierOffer.inventory_category == InventoryCategory.HOTEL)
        elif req.optimization_mode == OptimizationMode.FLIGHT_ONLY:
            offer_stmt = offer_stmt.where(SupplierOffer.inventory_category == InventoryCategory.FLIGHT)
        offers = list(db.execute(offer_stmt).scalars().all())
        if not offers:
            raise BadRequestException("No eligible supplier offers available for CVaR optimization.")

        # Normalize scenario probabilities
        raw_probs = [float(s.probability_weight) for s in scenarios]
        prob_sum = sum(raw_probs)
        if prob_sum <= 0.0:
            raise BadRequestException("Scenario probability weights must sum to a positive value.")
        probs = [p / prob_sum for p in raw_probs]

        assumptions = FinancialAssumptions()
        hotel_calc = HotelEconomicsCalculator(assumptions)
        flight_calc = FlightEconomicsCalculator(assumptions)

        # Precompute scenario economics e_{i,s} and effective capacities
        econ_matrix: Dict[Tuple[str, int], Dict[str, float]] = {}
        min_scen_cap: Dict[str, int] = {}
        for o in offers:
            caps = []
            for s in scenarios:
                shocks = _apply_correlated_factor_shocks(s)
                econ = _compute_offer_scenario_economics(
                    offer=o,
                    shocks=shocks,
                    scenario=s,
                    hotel_calc=hotel_calc,
                    flight_calc=flight_calc,
                )
                econ_matrix[(o.offer_id, s.id)] = econ
                caps.append(econ["effective_capacity"])
            min_scen_cap[o.offer_id] = max(0, min(o.max_capacity, min(caps)))

        # Build OR-Tools MILP
        opt_backend = OptSolverBackend(req.solver_backend.value)
        solver = SolverFactory.create_solver(
            SolverConfig(backend=opt_backend),
            problem_name="CVaR_Portfolio_MILP",
        )

        q_vars: Dict[str, pywraplp.Variable] = {}
        y_vars: Dict[str, pywraplp.Variable] = {}
        for o in offers:
            upper_q = o.max_capacity
            q_vars[o.offer_id] = solver.IntVar(0, upper_q, f"q_{o.offer_id}")
            y_vars[o.offer_id] = solver.BoolVar(f"y_{o.offer_id}")
            solver.Add(q_vars[o.offer_id] <= upper_q * y_vars[o.offer_id])
            solver.Add(q_vars[o.offer_id] >= o.moq * y_vars[o.offer_id])

        # Rockafellar-Uryasev auxiliary variables: zeta (VaR of loss) and u_s >= 0 (tail excess loss)
        zeta = solver.NumVar(-1e12, 1e12, "cvar_zeta")
        u_vars: Dict[int, pywraplp.Variable] = {}
        for s in scenarios:
            u_vars[s.id] = solver.NumVar(0.0, 1e12, f"u_{s.id}")
            # Loss L_s(q) = -sum_i e_{i,s} * q_i; constraint: u_s >= L_s(q) - zeta  =>  u_s + zeta + sum_i e_{i,s}*q_i >= 0
            c_loss = solver.Constraint(0.0, solver.infinity(), f"cvar_loss_{s.id}")
            c_loss.SetCoefficient(u_vars[s.id], 1.0)
            c_loss.SetCoefficient(zeta, 1.0)
            for o in offers:
                c_loss.SetCoefficient(q_vars[o.offer_id], econ_matrix[(o.offer_id, s.id)]["unit_contribution"])

        # Budget constraint
        budget_float = float(budget_inr)
        c_budget = solver.Constraint(0.0, budget_float, "master_budget")
        for o in offers:
            c_budget.SetCoefficient(q_vars[o.offer_id], float(o.unit_cost_inr))

        # Supplier concentration
        sup_limit = float(req.max_supplier_share) * budget_float
        by_sup: Dict[str, List[SupplierOffer]] = {}
        by_dest: Dict[str, List[SupplierOffer]] = {}
        for o in offers:
            by_sup.setdefault(o.supplier_id, []).append(o)
            by_dest.setdefault(o.dest_id, []).append(o)

        for sid, sup_offers in by_sup.items():
            cs = solver.Constraint(0.0, sup_limit, f"sup_cap_{sid}")
            for o in sup_offers:
                cs.SetCoefficient(q_vars[o.offer_id], float(o.unit_cost_inr))

        dest_limit = float(req.max_destination_share) * budget_float
        for did, dest_offers in by_dest.items():
            cd = solver.Constraint(0.0, dest_limit, f"dest_cap_{did}")
            for o in dest_offers:
                cd.SetCoefficient(q_vars[o.offer_id], float(o.unit_cost_inr))

        # Availability fulfillment target: procured quantity that remains physically deliverable under worst scenario
        # sum_i min(q_i, min_scen_cap_i) approximated linearly via q_i <= min_scen_cap_i when target enforced,
        # or if min_availability_target_pct > 0, enforce worst-case available capacity cover >= target% of q
        # Specifically: sum_i q_i * (avg_avail_ratio_i - target_avail) >= 0 where avg_avail_ratio_i = min(1, min_scen_cap_i / max(1, o.max_capacity))
        target_avail_frac = req.min_availability_target_pct / 100.0
        c_avail = solver.Constraint(0.0, solver.infinity(), "availability_target")
        for o in offers:
            avail_ratio = min(1.0, min_scen_cap[o.offer_id] / max(1, o.max_capacity))
            c_avail.SetCoefficient(q_vars[o.offer_id], avail_ratio - target_avail_frac)

        # Demand fulfillment target: expected sell-through weighted units >= target_demand_frac * procured units
        target_demand_frac = req.min_demand_fulfillment_pct / 100.0
        c_dem = solver.Constraint(0.0, solver.infinity(), "demand_fulfillment_target")
        for o in offers:
            avg_st = sum(p * econ_matrix[(o.offer_id, s.id)]["effective_sell_through"] for s, p in zip(scenarios, probs))
            c_dem.SetCoefficient(q_vars[o.offer_id], min(1.0, avg_st) - target_demand_frac)

        # Objective: max (1 - lam) * E[Profit] - lam * CVaR(Loss)
        lam = float(req.risk_aversion_lambda)
        alpha = float(req.confidence_level_alpha)
        obj = solver.Objective()
        for o in offers:
            exp_e = sum(p * econ_matrix[(o.offer_id, s.id)]["unit_contribution"] for s, p in zip(scenarios, probs))
            obj.SetCoefficient(q_vars[o.offer_id], (1.0 - lam) * exp_e)
        if lam > 0.0:
            obj.SetCoefficient(zeta, -lam)
            for s, p in zip(scenarios, probs):
                obj.SetCoefficient(u_vars[s.id], -lam * (p / (1.0 - alpha)))
        obj.SetMaximization()

        status_code = solver.Solve()
        is_opt = status_code == pywraplp.Solver.OPTIMAL
        is_feas = status_code in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)
        solver_st = SolverStatus.OPTIMAL if is_opt else (SolverStatus.FEASIBLE if is_feas else SolverStatus.INFEASIBLE)

        selected_qty: Dict[str, int] = {}
        total_spend = 0.0
        hotel_spend = 0.0
        flight_spend = 0.0
        hotel_units = 0
        flight_units = 0

        if is_feas:
            for o in offers:
                q_val = int(round(q_vars[o.offer_id].solution_value()))
                if q_val > 0:
                    selected_qty[o.offer_id] = q_val
                    sp = q_val * float(o.unit_cost_inr)
                    total_spend += sp
                    if o.inventory_category == InventoryCategory.HOTEL:
                        hotel_spend += sp
                        hotel_units += q_val
                    else:
                        flight_spend += sp
                        flight_units += q_val

        # Compute exact realized scenario outcomes and empirical VaR/CVaR
        scenario_outcomes: List[Dict[str, Any]] = []
        scen_profits: List[float] = []
        scen_losses: List[float] = []
        total_procured = sum(selected_qty.values())
        avail_ratios: List[float] = []
        demand_ratios: List[float] = []

        for s, p in zip(scenarios, probs):
            sp_profit = 0.0
            avail_units = 0
            sold_units = 0
            for o in offers:
                q_val = selected_qty.get(o.offer_id, 0)
                if q_val <= 0:
                    continue
                econ = econ_matrix[(o.offer_id, s.id)]
                eff_q = min(q_val, econ["effective_capacity"])
                sp_profit += eff_q * econ["unit_contribution"]
                avail_units += eff_q
                sold_units += min(eff_q, int(round(eff_q * econ["effective_sell_through"])))
            scen_profits.append(sp_profit)
            scen_losses.append(-sp_profit)
            if total_procured > 0:
                avail_ratios.append((avail_units / total_procured) * 100.0)
                demand_ratios.append((sold_units / total_procured) * 100.0)
            scenario_outcomes.append({
                "scenario_id": s.id,
                "scenario_code": s.scenario_code,
                "probability_weight": round(p, 6),
                "profit_inr": round(sp_profit, 2),
                "loss_inr": round(-sp_profit, 2),
            })

        if is_feas:
            exp_profit = sum(p * prof for p, prof in zip(probs, scen_profits))
            var_loss, cvar_loss = _compute_empirical_var_cvar(scen_losses, probs, alpha=alpha)
            var_mag = max(0.0, var_loss)
            cvar_mag = max(0.0, cvar_loss)
            # Matches Rockafellar-Uryasev MILP objective: (1 - lam) * E[Profit] - lam * CVaR(Loss)
            risk_adj_profit = (1.0 - lam) * exp_profit - lam * cvar_loss
            achieved_avail = sum(avail_ratios) / len(avail_ratios) if avail_ratios else 0.0
            achieved_demand = sum(demand_ratios) / len(demand_ratios) if demand_ratios else 0.0
        else:
            exp_profit = 0.0
            var_mag = 0.0
            cvar_mag = 0.0
            risk_adj_profit = 0.0
            achieved_avail = 0.0
            achieved_demand = 0.0

        # Persist OptimizationRun + Recommendations + CVaROptimizationRecord
        run_id = f"cvar_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        budget_util = (total_spend / budget_float * 100.0) if budget_float > 0 else 0.0
        ros = (exp_profit / total_spend * 100.0) if total_spend > 0 else 0.0

        run = OptimizationRun(
            run_id=run_id,
            triggered_by_user_id=user_id,
            optimization_mode=req.optimization_mode,
            budget_id=req.budget_id,
            cutoff_date=req.cutoff_date or date.today(),
            total_budget_inr=budget_inr,
            solver_backend=req.solver_backend,
            salvage_assumption_pct=0.0,
            max_supplier_share=float(req.max_supplier_share),
            max_destination_share=float(req.max_destination_share),
            target_currency="INR",
            scenario_name=req.scenario_name or f"CVaR-alpha={alpha}",
            scenario_parameters_json={
                "cvar_alpha": alpha,
                "risk_aversion_lambda": lam,
                "scenario_ids": req.scenario_ids,
            },
            idempotency_key=req.idempotency_key,
            pipeline_status=PipelineStatus.SUCCESS if is_feas else PipelineStatus.FAILED,
            solver_status=solver_st,
            is_optimal=is_opt,
            best_objective_inr=Decimal(str(round(risk_adj_profit, 2))),
            total_spend_inr=Decimal(str(round(total_spend, 2))),
            budget_utilization_pct=round(budget_util, 2),
            expected_net_profit_inr=Decimal(str(round(exp_profit, 2))),
            return_on_spend_pct=round(ros, 2),
            selected_offers_count=len(selected_qty),
            rejected_offers_count=max(0, len(offers) - len(selected_qty)),
            hotel_spend_inr=Decimal(str(round(hotel_spend, 2))),
            flight_spend_inr=Decimal(str(round(flight_spend, 2))),
            hotel_units_selected=hotel_units,
            flight_units_selected=flight_units,
            risk_metrics_json={
                "cvar_alpha": alpha,
                "var_inr": round(var_mag, 2),
                "cvar_inr": round(cvar_mag, 2),
                "risk_adjusted_profit_inr": round(risk_adj_profit, 2),
                "infeasible": not is_feas,
            },
            approval_status=ApprovalStatus.PENDING,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()

        for o in offers:
            q_val = selected_qty.get(o.offer_id, 0)
            if q_val <= 0:
                continue
            avg_e = sum(p * econ_matrix[(o.offer_id, s.id)]["unit_contribution"] for s, p in zip(scenarios, probs))
            avg_st = sum(p * econ_matrix[(o.offer_id, s.id)]["effective_sell_through"] for s, p in zip(scenarios, probs))
            db.add(ProcurementRecommendation(
                run_id=run_id,
                offer_id=o.offer_id,
                supplier_id=o.supplier_id,
                dest_id=o.dest_id,
                inventory_category=o.inventory_category,
                unit_type=o.unit_type,
                recommended_qty=q_val,
                unit_cost_inr=o.unit_cost_inr,
                total_spend_inr=Decimal(str(round(q_val * float(o.unit_cost_inr), 2))),
                expected_unit_contribution_inr=Decimal(str(round(avg_e, 2))),
                expected_total_contribution_inr=Decimal(str(round(q_val * avg_e, 2))),
                sell_through_rate=round(avg_st, 4),
                moq_applied=o.moq,
                capacity_available=o.max_capacity,
                rationale=f"CVaR-optimal (alpha={alpha}, lambda={lam}) across {len(scenarios)} risk scenarios.",
                approval_status=ApprovalStatus.PENDING,
            ))

        cvar_rec = CVaROptimizationRecord(
            run_id=run_id,
            confidence_level_alpha=alpha,
            risk_aversion_lambda=lam,
            num_scenarios=len(scenarios),
            min_availability_target_pct=req.min_availability_target_pct,
            min_demand_fulfillment_pct=req.min_demand_fulfillment_pct,
            achieved_availability_pct=round(achieved_avail, 2),
            achieved_demand_fulfillment_pct=round(achieved_demand, 2),
            expected_profit_inr=Decimal(str(round(exp_profit, 2))),
            var_inr=Decimal(str(round(var_mag, 2))),
            cvar_inr=Decimal(str(round(cvar_mag, 2))),
            risk_adjusted_profit_inr=Decimal(str(round(risk_adj_profit, 2))),
            scenario_outcomes_json=scenario_outcomes,
            scenario_ids_json=req.scenario_ids,
        )
        db.add(cvar_rec)
        db.add(AuditLog(
            user_id=user_id,
            action="CVAR_OPTIMIZATION_EXECUTED",
            entity_type="optimization_runs",
            entity_id=run_id,
            new_value_json={
                "alpha": alpha,
                "lambda": lam,
                "expected_profit": round(exp_profit, 2),
                "cvar_inr": round(cvar_mag, 2),
            },
        ))
        db.commit()
        db.refresh(cvar_rec)
        return cvar_rec

    @staticmethod
    def get_portfolio_risk_summary(
        db: Session, run_id: Optional[str] = None
    ) -> PortfolioRiskSummaryResponse:
        if run_id:
            runs = list(db.execute(select(OptimizationRun).where(OptimizationRun.run_id == run_id)).scalars().all())
            if not runs:
                raise EntityNotFoundError("OptimizationRun", run_id)
        else:
            runs = list(
                db.execute(
                    select(OptimizationRun)
                    .where(OptimizationRun.pipeline_status == PipelineStatus.SUCCESS)
                    .order_by(OptimizationRun.created_at.desc())
                    .limit(25)
                ).scalars().all()
            )

        run_ids = [r.run_id for r in runs]
        total_spend = sum((r.total_spend_inr or Decimal("0.00")) for r in runs)
        exp_profit = sum((r.expected_net_profit_inr or Decimal("0.00")) for r in runs)

        st_stmt = select(PortfolioStressTest)
        if run_ids:
            st_stmt = st_stmt.where(PortfolioStressTest.run_id.in_(run_ids))
        stress_tests = list(db.execute(st_stmt).scalars().all())

        cvar_stmt = select(CVaROptimizationRecord)
        if run_ids:
            cvar_stmt = cvar_stmt.where(CVaROptimizationRecord.run_id.in_(run_ids))
        cvar_recs = list(db.execute(cvar_stmt).scalars().all())

        if stress_tests:
            var_val = max(st.var_95_inr for st in stress_tests)
            cvar_val = max(st.cvar_95_inr for st in stress_tests)
            avg_avail = sum(st.availability_fulfillment_pct for st in stress_tests) / len(stress_tests)
            avg_dem = sum(st.demand_fulfillment_pct for st in stress_tests) / len(stress_tests)
        elif cvar_recs:
            var_val = max(c.var_inr for c in cvar_recs)
            cvar_val = max(c.cvar_inr for c in cvar_recs)
            avg_avail = sum(c.achieved_availability_pct for c in cvar_recs) / len(cvar_recs)
            avg_dem = sum(c.achieved_demand_fulfillment_pct for c in cvar_recs) / len(cvar_recs)
        else:
            var_val = Decimal("0.00")
            cvar_val = Decimal("0.00")
            avg_avail = 100.0 if runs else 0.0
            avg_dem = 100.0 if runs else 0.0

        # Compute HHI from recommendations
        sup_spend: Dict[str, float] = {}
        dest_spend: Dict[str, float] = {}
        if run_ids:
            recs = list(
                db.execute(
                    select(ProcurementRecommendation).where(ProcurementRecommendation.run_id.in_(run_ids))
                ).scalars().all()
            )
            for r in recs:
                sp = float(r.total_spend_inr)
                sup_spend[r.supplier_id] = sup_spend.get(r.supplier_id, 0.0) + sp
                dest_spend[r.dest_id] = dest_spend.get(r.dest_id, 0.0) + sp

        tot_s = sum(sup_spend.values())
        sup_hhi = sum((v / tot_s) ** 2 for v in sup_spend.values()) if tot_s > 0 else 0.0
        dest_hhi = sum((v / tot_s) ** 2 for v in dest_spend.values()) if tot_s > 0 else 0.0

        active_scenarios = db.execute(
            select(func.count(RiskScenario.id)).where(RiskScenario.is_active == True)
        ).scalar_one()

        drawdown_ratio = float(cvar_val) / max(1.0, float(exp_profit)) if exp_profit > 0 else 0.0
        if sup_hhi > 0.35 or drawdown_ratio > 0.50:
            grade = "HIGH_RISK"
        elif sup_hhi > 0.20 or drawdown_ratio > 0.25:
            grade = "MODERATE_RISK"
        else:
            grade = "LOW_RISK"

        return PortfolioRiskSummaryResponse(
            run_id=run_id,
            evaluated_runs_count=len(runs),
            total_committed_spend_inr=total_spend,
            expected_profit_inr=exp_profit,
            portfolio_var_95_inr=var_val,
            portfolio_cvar_95_inr=cvar_val,
            avg_availability_fulfillment_pct=round(avg_avail, 2),
            avg_demand_fulfillment_pct=round(avg_dem, 2),
            supplier_hhi=round(sup_hhi, 4),
            destination_hhi=round(dest_hhi, 4),
            active_scenarios_count=active_scenarios,
            stress_tests_count=len(stress_tests),
            risk_grade=grade,
        )

    @staticmethod
    def compare_risk_adjusted(
        db: Session, baseline_run_id: str, compare_run_ids: List[str]
    ) -> RiskAdjustedComparisonResponse:
        all_ids = [baseline_run_id] + [rid for rid in compare_run_ids if rid != baseline_run_id]
        runs = list(db.execute(select(OptimizationRun).where(OptimizationRun.run_id.in_(all_ids))).scalars().all())
        run_map = {r.run_id: r for r in runs}
        if baseline_run_id not in run_map:
            raise EntityNotFoundError("OptimizationRun", baseline_run_id)

        items: List[RiskAdjustedComparisonItem] = []
        for rid in all_ids:
            r = run_map.get(rid)
            if not r:
                raise EntityNotFoundError("OptimizationRun", rid)
            cvar_rec = db.execute(
                select(CVaROptimizationRecord).where(CVaROptimizationRecord.run_id == rid)
            ).scalar_one_or_none()
            sts = list(
                db.execute(select(PortfolioStressTest).where(PortfolioStressTest.run_id == rid)).scalars().all()
            )

            exp_p = r.expected_net_profit_inr or Decimal("0.00")
            if cvar_rec:
                var_v = cvar_rec.var_inr
                cvar_v = cvar_rec.cvar_inr
                radj = cvar_rec.risk_adjusted_profit_inr
                avail = cvar_rec.achieved_availability_pct
                dem = cvar_rec.achieved_demand_fulfillment_pct
            elif sts:
                var_v = max(s.var_95_inr for s in sts)
                cvar_v = max(s.cvar_95_inr for s in sts)
                radj = exp_p - Decimal("0.5") * cvar_v
                avail = sum(s.availability_fulfillment_pct for s in sts) / len(sts)
                dem = sum(s.demand_fulfillment_pct for s in sts) / len(sts)
            else:
                var_v = Decimal("0.00")
                cvar_v = Decimal("0.00")
                radj = exp_p
                avail = 100.0
                dem = 100.0

            sharpe = float(exp_p) / max(1.0, float(cvar_v)) if float(cvar_v) > 0 else float(exp_p) / max(1.0, float(r.total_spend_inr or 1))
            items.append(RiskAdjustedComparisonItem(
                run_id=r.run_id,
                optimization_mode=r.optimization_mode,
                scenario_name=r.scenario_name,
                total_spend_inr=r.total_spend_inr or Decimal("0.00"),
                expected_profit_inr=exp_p,
                var_95_inr=var_v,
                cvar_95_inr=cvar_v,
                risk_adjusted_profit_inr=radj,
                sharpe_like_ratio=round(sharpe, 4),
                availability_fulfillment_pct=round(avail, 2),
                demand_fulfillment_pct=round(dem, 2),
            ))

        best = max(items, key=lambda x: x.risk_adjusted_profit_inr)
        return RiskAdjustedComparisonResponse(
            baseline_run_id=baseline_run_id,
            compared_runs=items,
            recommended_run_id=best.run_id,
            rationale=f"Run '{best.run_id}' achieves highest risk-adjusted profit INR {best.risk_adjusted_profit_inr:,.2f} (CVaR={best.cvar_95_inr:,.2f}).",
        )
