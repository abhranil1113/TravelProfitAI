from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from backend.app.models.schema import (
    AuditLog,
    CurrencyExposureSnapshot,
    ExchangeRate,
    FXAlert,
    FXAlertSeverity,
    FXContractDirection,
    FXContractStatus,
    FXForwardContract,
    FXRateSource,
    HedgeEffectivenessRecord,
    MarginBreachAction,
    MarginProtectionRule,
    OfferStatus,
    POStatus,
    PolicyScope,
    PurchaseOrder,
    SupplierOffer,
)
from backend.app.schemas.treasury import (
    FXForwardCreateRequest,
    FXForwardExecuteRequest,
    HedgeEffectivenessCreateRequest,
    MarginImpactEvaluateRequest,
    MarginImpactEvaluateResponse,
    MarginProtectionRuleCreateRequest,
    MarginProtectionRuleUpdateRequest,
)

logger = logging.getLogger(__name__)


class TreasuryService:
    """Service layer for Domain 4: Multi-Currency Treasury & FX Hedging."""

    @staticmethod
    def get_verified_spot_rate(
        db: Session, base_currency: str, quote_currency: str = "INR",
        as_of_date: Optional[date] = None,
        require_fresh: bool = True,
    ) -> ExchangeRate:
        base = base_currency.strip().upper()
        quote = quote_currency.strip().upper()
        if base == quote:
            raise BadRequestException("Base and quote currency must differ to query FX spot rate.")

        stmt = select(ExchangeRate).where(
            ExchangeRate.from_currency == base,
            ExchangeRate.to_currency == quote,
        )
        if as_of_date is not None:
            stmt = stmt.where(ExchangeRate.as_of_date <= as_of_date)
        stmt = stmt.order_by(ExchangeRate.as_of_date.desc())
        row = db.execute(stmt).scalars().first()
        if not row:
            raise BadRequestException(
                f"No verified ExchangeRate record found for {base}/{quote}. Ingest rate via /exchange-rates first."
            )
        effective_today = as_of_date or date.today()
        if row.as_of_date > effective_today:
            raise BadRequestException("Exchange rate record is future-dated.")
        if require_fresh:
            from backend.app.core.config import get_settings
            max_age = get_settings().FX_RATE_MAX_AGE_DAYS
            if effective_today - row.as_of_date > timedelta(days=max_age):
                raise BadRequestException(
                    f"Exchange rate {base}/{quote} is stale: latest valid rate is from {row.as_of_date.isoformat()}."
                )
        return row

    @staticmethod
    def create_fx_forward(
        db: Session, req: FXForwardCreateRequest, user_id: int
    ) -> FXForwardContract:
        """Creates a DRAFT FX forward contract. Execution requires explicit Admin approval."""
        spot_row = TreasuryService.get_verified_spot_rate(
            db, req.base_currency, req.quote_currency, as_of_date=req.trade_date
        )
        spot_rate = spot_row.rate

        val_ts = req.valuation_timestamp or datetime.now(timezone.utc)
        mtm = TreasuryService._compute_mtm(
            direction=req.direction,
            notional_base=req.notional_amount_base,
            contracted_rate=req.contracted_forward_rate,
            current_spot=spot_rate,
        )

        contract = FXForwardContract(
            base_currency=req.base_currency,
            quote_currency=req.quote_currency,
            direction=req.direction,
            notional_amount_base=req.notional_amount_base,
            contracted_forward_rate=req.contracted_forward_rate,
            spot_rate_at_booking=spot_rate,
            rate_source=FXRateSource(spot_row.source) if spot_row.source in FXRateSource._value2member_map_ else req.rate_source,
            trade_date=req.trade_date,
            maturity_date=req.maturity_date,
            valuation_timestamp=val_ts,
            counterparty=req.counterparty.strip(),
            status=FXContractStatus.DRAFT,
            mark_to_market_inr=mtm,
            created_by_user_id=user_id,
            notes=req.notes,
        )
        db.add(contract)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="FX_FORWARD_DRAFT_CREATED",
            entity_type="fx_forward_contracts",
            entity_id=contract.contract_number,
            new_value_json={
                "pair": f"{contract.base_currency}/{contract.quote_currency}",
                "notional": str(contract.notional_amount_base),
                "forward_rate": str(contract.contracted_forward_rate),
            },
        ))
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def _compute_mtm(
        direction: FXContractDirection,
        notional_base: Decimal,
        contracted_rate: Decimal,
        current_spot: Decimal,
    ) -> Decimal:
        if direction == FXContractDirection.BUY_BASE_SELL_QUOTE:
            pnl = (current_spot - contracted_rate) * notional_base
        else:
            pnl = (contracted_rate - current_spot) * notional_base
        return pnl.quantize(Decimal("0.01"))

    @staticmethod
    def execute_fx_forward(
        db: Session, contract_id: int, req: FXForwardExecuteRequest, admin_user_id: int
    ) -> FXForwardContract:
        """Approves and executes a DRAFT FX forward contract (Admin only, Policy-enforced)."""
        contract = db.execute(
            select(FXForwardContract).where(FXForwardContract.id == contract_id).with_for_update()
        ).scalar_one_or_none()
        if not contract:
            raise EntityNotFoundError("FXForwardContract", contract_id)
        if contract.status != FXContractStatus.DRAFT:
            raise InvalidStateTransitionError(contract.status.value, FXContractStatus.ACTIVE.value)
        if contract.maturity_date < date.today():
            raise BadRequestException(
                f"Cannot execute expired FX forward contract '{contract.contract_number}' (maturity_date={contract.maturity_date})."
            )

        # Policy-as-Code enforcement for FX hedge execution
        from backend.app.services.policy_service import PolicyService
        PolicyService.enforce_workflow_policies(
            db=db,
            scope=PolicyScope.FX_HEDGE_EXECUTION,
            entity_type="fx_forward_contracts",
            entity_id=contract.contract_number,
            context={
                "base_currency": contract.base_currency,
                "quote_currency": contract.quote_currency,
                "notional_amount_base": float(contract.notional_amount_base),
                "contracted_forward_rate": float(contract.contracted_forward_rate),
                "counterparty": contract.counterparty,
            },
            user_id=admin_user_id,
        )

        # Execution requires a fresh verified spot rate; stale or missing rates block execution.
        latest_spot = TreasuryService.get_verified_spot_rate(
            db, contract.base_currency, contract.quote_currency
        )
        contract.mark_to_market_inr = TreasuryService._compute_mtm(
            contract.direction,
            contract.notional_amount_base,
            contract.contracted_forward_rate,
            latest_spot.rate,
        )
        contract.valuation_timestamp = datetime.now(timezone.utc)

        contract.status = FXContractStatus.ACTIVE
        contract.approved_by_user_id = admin_user_id
        contract.executed_at = datetime.now(timezone.utc)
        if req.approval_notes:
            contract.notes = f"{contract.notes or ''}\nExecution Approval: {req.approval_notes}".strip()

        db.add(AuditLog(
            user_id=admin_user_id,
            action="FX_FORWARD_EXECUTED",
            entity_type="fx_forward_contracts",
            entity_id=contract.contract_number,
            new_value_json={"status": FXContractStatus.ACTIVE.value, "mtm_inr": str(contract.mark_to_market_inr)},
        ))
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def settle_fx_forward(db: Session, contract_id: int, admin_user_id: int) -> FXForwardContract:
        contract = db.execute(
            select(FXForwardContract).where(FXForwardContract.id == contract_id).with_for_update()
        ).scalar_one_or_none()
        if not contract:
            raise EntityNotFoundError("FXForwardContract", contract_id)
        if contract.status != FXContractStatus.ACTIVE:
            raise InvalidStateTransitionError(contract.status.value, FXContractStatus.SETTLED.value)

        contract.status = FXContractStatus.SETTLED
        db.add(AuditLog(
            user_id=admin_user_id,
            action="FX_FORWARD_SETTLED",
            entity_type="fx_forward_contracts",
            entity_id=contract.contract_number,
        ))
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def cancel_fx_forward(db: Session, contract_id: int, admin_user_id: int) -> FXForwardContract:
        contract = db.execute(
            select(FXForwardContract).where(FXForwardContract.id == contract_id).with_for_update()
        ).scalar_one_or_none()
        if not contract:
            raise EntityNotFoundError("FXForwardContract", contract_id)
        if contract.status in (FXContractStatus.SETTLED, FXContractStatus.CANCELLED):
            raise InvalidStateTransitionError(contract.status.value, FXContractStatus.CANCELLED.value)

        contract.status = FXContractStatus.CANCELLED
        db.add(AuditLog(
            user_id=admin_user_id,
            action="FX_FORWARD_CANCELLED",
            entity_type="fx_forward_contracts",
            entity_id=contract.contract_number,
        ))
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def list_fx_forwards(
        db: Session,
        base_currency: Optional[str] = None,
        status: Optional[FXContractStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FXForwardContract], int]:
        stmt = select(FXForwardContract)
        if base_currency:
            stmt = stmt.where(FXForwardContract.base_currency == base_currency.upper())
        if status:
            stmt = stmt.where(FXForwardContract.status == status)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            db.execute(
                stmt.order_by(FXForwardContract.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return items, total

    # --- Currency Exposure Calculation & Snapshots ---

    @staticmethod
    def compute_currency_exposure(
        db: Session, currency_code: str, target_currency: str = "INR"
    ) -> CurrencyExposureSnapshot:
        ccy = currency_code.strip().upper()
        target = target_currency.strip().upper()
        spot_row = TreasuryService.get_verified_spot_rate(db, ccy, target)
        spot_rate = spot_row.rate

        # Aggregate foreign-currency exposure from active offers + open POs
        offers = list(
            db.execute(
                select(SupplierOffer).where(
                    SupplierOffer.currency_code == ccy,
                    SupplierOffer.status == OfferStatus.ACTIVE,
                )
            ).scalars().all()
        )
        offers_exposure_base = Decimal("0.00")
        for o in offers:
            unit_base = o.original_unit_cost if o.original_unit_cost is not None else (o.unit_cost_inr / spot_rate)
            offers_exposure_base += unit_base * Decimal(o.max_capacity)

        pos = list(
            db.execute(
                select(PurchaseOrder).where(
                    PurchaseOrder.currency == ccy,
                    PurchaseOrder.status.in_([POStatus.SUBMITTED, POStatus.CONFIRMED, POStatus.PARTIALLY_RECEIVED]),
                )
            ).scalars().all()
        )
        po_exposure_base = sum(
            ((p.total_committed_spend_inr / spot_rate) for p in pos),
            Decimal("0.00"),
        )

        gross_base = (offers_exposure_base + po_exposure_base).quantize(Decimal("0.01"))
        gross_inr = (gross_base * spot_rate).quantize(Decimal("0.01"))

        active_hedges = list(
            db.execute(
                select(FXForwardContract).where(
                    FXForwardContract.base_currency == ccy,
                    FXForwardContract.quote_currency == target,
                    FXForwardContract.status.in_([FXContractStatus.APPROVED, FXContractStatus.ACTIVE]),
                )
            ).scalars().all()
        )
        hedged_base = sum((h.notional_amount_base for h in active_hedges), Decimal("0.00")).quantize(Decimal("0.01"))
        unrealized_pnl = sum(
            (
                TreasuryService._compute_mtm(
                    h.direction, h.notional_amount_base, h.contracted_forward_rate, spot_rate
                )
                for h in active_hedges
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

        net_unhedged_base = (gross_base - hedged_base).quantize(Decimal("0.01"))
        net_unhedged_inr = (net_unhedged_base * spot_rate).quantize(Decimal("0.01"))
        hedge_ratio = (
            min(100.0, float(hedged_base / gross_base) * 100.0)
            if gross_base > 0
            else (100.0 if hedged_base > 0 else 0.0)
        )

        snap = CurrencyExposureSnapshot(
            currency_code=ccy,
            target_currency=target,
            spot_rate_used=spot_rate,
            rate_source=spot_row.source,
            valuation_timestamp=datetime.now(timezone.utc),
            gross_exposure_base=gross_base,
            gross_exposure_inr=gross_inr,
            hedged_amount_base=hedged_base,
            net_unhedged_base=net_unhedged_base,
            net_unhedged_inr=net_unhedged_inr,
            hedge_ratio_pct=round(hedge_ratio, 2),
            unrealized_fx_pnl_inr=unrealized_pnl,
            breakdown_json={
                "active_offers_count": len(offers),
                "offers_exposure_base": str(offers_exposure_base.quantize(Decimal("0.01"))),
                "open_pos_count": len(pos),
                "po_exposure_base": str(po_exposure_base.quantize(Decimal("0.01"))),
                "active_hedges_count": len(active_hedges),
            },
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        return snap

    @staticmethod
    def list_exposure_snapshots(
        db: Session, currency_code: Optional[str] = None
    ) -> List[CurrencyExposureSnapshot]:
        stmt = select(CurrencyExposureSnapshot)
        if currency_code:
            stmt = stmt.where(CurrencyExposureSnapshot.currency_code == currency_code.upper())
        return list(
            db.execute(stmt.order_by(CurrencyExposureSnapshot.valuation_timestamp.desc()).limit(100)).scalars().all()
        )

    # --- Hedge Effectiveness (IFRS 9 / IAS 39 Dollar-Offset) ---

    @staticmethod
    def record_hedge_effectiveness(
        db: Session, req: HedgeEffectivenessCreateRequest, user_id: int
    ) -> HedgeEffectivenessRecord:
        contract = db.execute(
            select(FXForwardContract).where(FXForwardContract.id == req.contract_id)
        ).scalar_one_or_none()
        if not contract:
            raise EntityNotFoundError("FXForwardContract", req.contract_id)
        if contract.status not in (FXContractStatus.APPROVED, FXContractStatus.ACTIVE, FXContractStatus.SETTLED):
            raise InvalidStateTransitionError(contract.status.value, "HEDGE_EFFECTIVENESS_MEASUREMENT")

        measurement_date = req.measurement_date or date.today()
        spot_row = TreasuryService.get_verified_spot_rate(
            db,
            contract.base_currency,
            contract.quote_currency,
            as_of_date=measurement_date,
            require_fresh=False,
        )
        current_spot = spot_row.rate

        # Hedging instrument fair value change since booking
        mtm_now = TreasuryService._compute_mtm(
            contract.direction, contract.notional_amount_base, contract.contracted_forward_rate, current_spot
        )
        mtm_booking = TreasuryService._compute_mtm(
            contract.direction, contract.notional_amount_base, contract.contracted_forward_rate, contract.spot_rate_at_booking
        )
        inst_fv_change = (mtm_now - mtm_booking).quantize(Decimal("0.01"))

        if req.hedged_item_fv_change_inr is not None:
            hedged_item_change = req.hedged_item_fv_change_inr.quantize(Decimal("0.01"))
        else:
            # Underlying payable value change is opposite to spot move on notional
            hedged_item_change = ((contract.spot_rate_at_booking - current_spot) * contract.notional_amount_base).quantize(Decimal("0.01"))

        if hedged_item_change == 0:
            ratio_pct = 100.0 if inst_fv_change == 0 else 0.0
        else:
            ratio_pct = round(abs(float(inst_fv_change) / float(hedged_item_change)) * 100.0, 2)

        is_eff = 80.0 <= ratio_pct <= 125.0

        rec = HedgeEffectivenessRecord(
            contract_id=contract.id,
            measurement_date=measurement_date,
            spot_rate_at_measurement=current_spot,
            hedged_item_fv_change_inr=hedged_item_change,
            hedging_instrument_fv_change_inr=inst_fv_change,
            effectiveness_ratio_pct=ratio_pct,
            is_effective=is_eff,
            notes=req.notes,
        )
        db.add(rec)
        db.add(AuditLog(
            user_id=user_id,
            action="HEDGE_EFFECTIVENESS_MEASURED",
            entity_type="hedge_effectiveness_records",
            entity_id=contract.contract_number,
            new_value_json={"ratio_pct": ratio_pct, "is_effective": is_eff},
        ))
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def list_hedge_effectiveness(
        db: Session, contract_id: Optional[int] = None
    ) -> List[HedgeEffectivenessRecord]:
        stmt = select(HedgeEffectivenessRecord)
        if contract_id:
            stmt = stmt.where(HedgeEffectivenessRecord.contract_id == contract_id)
        return list(db.execute(stmt.order_by(HedgeEffectivenessRecord.measurement_date.desc())).scalars().all())

    # --- Margin Protection Rules & Impact Evaluation ---

    @staticmethod
    def create_margin_rule(
        db: Session, req: MarginProtectionRuleCreateRequest, user_id: int
    ) -> MarginProtectionRule:
        existing = db.execute(
            select(MarginProtectionRule).where(MarginProtectionRule.rule_code == req.rule_code)
        ).scalar_one_or_none()
        if existing:
            raise ConflictException(f"Margin protection rule '{req.rule_code}' already exists.")

        rule = MarginProtectionRule(
            rule_code=req.rule_code,
            name=req.name.strip(),
            currency_code=req.currency_code,
            min_gross_margin_pct=req.min_gross_margin_pct,
            max_fx_drawdown_pct=req.max_fx_drawdown_pct,
            min_hedge_coverage_pct=req.min_hedge_coverage_pct,
            action_on_breach=req.action_on_breach,
            is_active=req.is_active,
            created_by_user_id=user_id,
        )
        db.add(rule)
        db.add(AuditLog(
            user_id=user_id,
            action="MARGIN_PROTECTION_RULE_CREATED",
            entity_type="margin_protection_rules",
            entity_id=rule.rule_code,
            new_value_json={"currency": rule.currency_code, "min_margin": rule.min_gross_margin_pct},
        ))
        db.commit()
        db.refresh(rule)
        return rule

    @staticmethod
    def update_margin_rule(
        db: Session, rule_id: int, req: MarginProtectionRuleUpdateRequest, user_id: int
    ) -> MarginProtectionRule:
        rule = db.execute(
            select(MarginProtectionRule).where(MarginProtectionRule.id == rule_id)
        ).scalar_one_or_none()
        if not rule:
            raise EntityNotFoundError("MarginProtectionRule", rule_id)
        updates = req.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(rule, k, v)
        db.add(AuditLog(
            user_id=user_id,
            action="MARGIN_PROTECTION_RULE_UPDATED",
            entity_type="margin_protection_rules",
            entity_id=rule.rule_code,
            new_value_json=updates,
        ))
        db.commit()
        db.refresh(rule)
        return rule

    @staticmethod
    def list_margin_rules(
        db: Session, currency_code: Optional[str] = None
    ) -> List[MarginProtectionRule]:
        stmt = select(MarginProtectionRule)
        if currency_code:
            stmt = stmt.where(MarginProtectionRule.currency_code == currency_code.upper())
        return list(db.execute(stmt.order_by(MarginProtectionRule.created_at.desc())).scalars().all())

    @staticmethod
    def evaluate_margin_impact(
        db: Session, req: MarginImpactEvaluateRequest, user_id: int
    ) -> MarginImpactEvaluateResponse:
        ccy = req.currency_code.upper()
        spot_row = TreasuryService.get_verified_spot_rate(db, ccy, "INR")
        spot = spot_row.rate
        shocked_spot = (spot * (Decimal("1") + Decimal(str(req.fx_shock_pct)))).quantize(Decimal("0.00000001"))

        hedge_cov_pct = 0.0
        effective_rate = shocked_spot

        if req.include_active_hedges:
            active_hedges = list(
                db.execute(
                    select(FXForwardContract).where(
                        FXForwardContract.base_currency == ccy,
                        FXForwardContract.quote_currency == "INR",
                        FXForwardContract.status.in_([FXContractStatus.APPROVED, FXContractStatus.ACTIVE]),
                    )
                ).scalars().all()
            )
            total_hedged_base = sum((h.notional_amount_base for h in active_hedges), Decimal("0.00"))
            if total_hedged_base > 0:
                weighted_fwd = sum((h.notional_amount_base * h.contracted_forward_rate for h in active_hedges), Decimal("0.00")) / total_hedged_base
                cov_frac = min(Decimal("1.0"), total_hedged_base / req.purchase_cost_base)
                hedge_cov_pct = round(float(cov_frac) * 100.0, 2)
                effective_rate = (cov_frac * weighted_fwd + (Decimal("1.0") - cov_frac) * shocked_spot).quantize(Decimal("0.00000001"))

        unshocked_cost = (req.purchase_cost_base * spot).quantize(Decimal("0.01"))
        shocked_cost = (req.purchase_cost_base * shocked_spot).quantize(Decimal("0.01"))
        hedged_cost = (req.purchase_cost_base * effective_rate).quantize(Decimal("0.01"))

        sell = req.selling_price_inr
        unhedged_margin_pct = round(float((sell - shocked_cost) / sell) * 100.0, 2)
        hedged_margin_pct = round(float((sell - hedged_cost) / sell) * 100.0, 2)
        base_margin_pct = round(float((sell - unshocked_cost) / sell) * 100.0, 2)
        erosion_pct = round(base_margin_pct - hedged_margin_pct, 2)

        rules = list(
            db.execute(
                select(MarginProtectionRule).where(
                    MarginProtectionRule.currency_code == ccy,
                    MarginProtectionRule.is_active == True,
                )
            ).scalars().all()
        )
        breached: List[str] = []
        highest_action = MarginBreachAction.ALERT_ONLY
        action_rank = {
            MarginBreachAction.ALERT_ONLY: 1,
            MarginBreachAction.REQUIRE_APPROVAL: 2,
            MarginBreachAction.BLOCK_PROCUREMENT: 3,
        }
        alerts_created = 0

        for rule in rules:
            is_breached = (
                hedged_margin_pct < rule.min_gross_margin_pct
                or abs(req.fx_shock_pct * 100.0) > rule.max_fx_drawdown_pct
                or hedge_cov_pct < rule.min_hedge_coverage_pct
            )
            if is_breached:
                breached.append(rule.rule_code)
                if action_rank[rule.action_on_breach] > action_rank[highest_action]:
                    highest_action = rule.action_on_breach
                sev = (
                    FXAlertSeverity.CRITICAL
                    if rule.action_on_breach == MarginBreachAction.BLOCK_PROCUREMENT
                    else FXAlertSeverity.WARNING
                )
                db.add(FXAlert(
                    currency_code=ccy,
                    rule_id=rule.id,
                    severity=sev,
                    title=f"Margin Protection Breach: {rule.rule_code}",
                    message=(
                        f"{ccy} margin {hedged_margin_pct}% (min {rule.min_gross_margin_pct}%), "
                        f"hedge coverage {hedge_cov_pct}% (min {rule.min_hedge_coverage_pct}%), "
                        f"FX shock {req.fx_shock_pct * 100:.2f}%."
                    ),
                    observed_margin_pct=hedged_margin_pct,
                    observed_fx_move_pct=round(req.fx_shock_pct * 100.0, 2),
                ))
                alerts_created += 1

        if alerts_created > 0:
            db.commit()

        return MarginImpactEvaluateResponse(
            currency_code=ccy,
            spot_rate_used=spot,
            effective_rate_with_hedges=effective_rate,
            hedge_coverage_pct=hedge_cov_pct,
            unshocked_cost_inr=unshocked_cost,
            shocked_cost_inr=shocked_cost,
            hedged_cost_inr=hedged_cost,
            unhedged_margin_pct=unhedged_margin_pct,
            hedged_margin_pct=hedged_margin_pct,
            fx_margin_erosion_pct=erosion_pct,
            breached_rules=breached,
            recommended_action=highest_action if breached else MarginBreachAction.ALERT_ONLY,
            alerts_generated=alerts_created,
        )

    @staticmethod
    def list_fx_alerts(
        db: Session,
        currency_code: Optional[str] = None,
        is_acknowledged: Optional[bool] = None,
    ) -> List[FXAlert]:
        stmt = select(FXAlert)
        if currency_code:
            stmt = stmt.where(FXAlert.currency_code == currency_code.upper())
        if is_acknowledged is not None:
            stmt = stmt.where(FXAlert.is_acknowledged == is_acknowledged)
        return list(db.execute(stmt.order_by(FXAlert.created_at.desc())).scalars().all())

    @staticmethod
    def acknowledge_fx_alert(db: Session, alert_id: int, user_id: int) -> FXAlert:
        alert = db.execute(select(FXAlert).where(FXAlert.id == alert_id)).scalar_one_or_none()
        if not alert:
            raise EntityNotFoundError("FXAlert", alert_id)
        alert.is_acknowledged = True
        alert.acknowledged_by_user_id = user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
        return alert
