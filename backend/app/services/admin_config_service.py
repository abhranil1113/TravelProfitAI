from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from backend.app.models.schema import (
    AuditLog,
    OptimizationConfigTemplate,
    OptimizationRun,
    PlatformOptimizationConfig,
    SolverBackend,
)
from backend.app.schemas.admin_config import (
    OptimizationConfigTemplateCreateRequest,
    OptimizationConfigTemplateUpdateRequest,
    PlatformConfigCreateRequest,
    PlatformConfigUpdateRequest,
)


class AdminConfigService:

    @staticmethod
    def get_active_config(db: Session) -> PlatformOptimizationConfig:
        config = db.execute(
            select(PlatformOptimizationConfig).where(PlatformOptimizationConfig.is_active.is_(True))
        ).scalar_one_or_none()

        if not config:
            # Initialize default active profile if database has none
            config = PlatformOptimizationConfig(
                profile_name="Default Production Profile",
                version=1,
                status="ACTIVE",
                is_active=True,
                activated_at=datetime.utcnow(),
                default_total_budget_inr=Decimal("100000000.00"),
                max_supplier_share=Decimal("0.40"),
                max_destination_share=Decimal("0.35"),
                hotel_min_budget_share=Decimal("0.30"),
                hotel_max_budget_share=Decimal("0.70"),
                flight_min_budget_share=Decimal("0.30"),
                flight_max_budget_share=Decimal("0.70"),
                target_currency="INR",
                allow_prototype_currency_override=False,
                prototype_eur_to_inr_rate=Decimal("90.00"),
                bayesian_shrinkage_lambda=Decimal("0.30"),
                default_flight_salvage_pct=Decimal("0.10"),
                default_solver_backend=SolverBackend.SCIP,
                notes="System bootstrapped active profile",
            )
            db.add(config)
            db.commit()
            db.refresh(config)

        return config

    @staticmethod
    def list_config_history(db: Session) -> List[PlatformOptimizationConfig]:
        stmt = select(PlatformOptimizationConfig).order_by(PlatformOptimizationConfig.version.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_draft_config(
        db: Session,
        req: PlatformConfigCreateRequest,
        user_id: int,
    ) -> PlatformOptimizationConfig:
        max_version = db.execute(
            select(func.coalesce(func.max(PlatformOptimizationConfig.version), 0))
        ).scalar_one()

        new_config = PlatformOptimizationConfig(
            profile_name=req.profile_name,
            version=max_version + 1,
            status="DRAFT",
            is_active=False,
            default_total_budget_inr=req.default_total_budget_inr,
            max_supplier_share=req.max_supplier_share,
            max_destination_share=req.max_destination_share,
            hotel_min_budget_share=req.hotel_min_budget_share,
            hotel_max_budget_share=req.hotel_max_budget_share,
            flight_min_budget_share=req.flight_min_budget_share,
            flight_max_budget_share=req.flight_max_budget_share,
            target_currency=req.target_currency,
            allow_prototype_currency_override=req.allow_prototype_currency_override,
            prototype_eur_to_inr_rate=req.prototype_eur_to_inr_rate,
            bayesian_shrinkage_lambda=req.bayesian_shrinkage_lambda,
            default_flight_salvage_pct=req.default_flight_salvage_pct,
            default_solver_backend=req.default_solver_backend,
            updated_by_user_id=user_id,
            notes=req.notes,
        )
        db.add(new_config)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="PLATFORM_OPTIMIZATION_CONFIG",
            entity_id=str(new_config.id),
            new_value_json={"version": new_config.version, "profile_name": new_config.profile_name},
        )
        db.add(audit)
        db.commit()
        db.refresh(new_config)
        return new_config

    @staticmethod
    def update_draft_config(
        db: Session,
        config_id: int,
        req: PlatformConfigUpdateRequest,
        user_id: int,
    ) -> PlatformOptimizationConfig:
        config = db.execute(
            select(PlatformOptimizationConfig).where(PlatformOptimizationConfig.id == config_id)
        ).scalar_one_or_none()

        if not config:
            raise NotFoundException(f"Platform optimization config {config_id} not found")

        if config.status != "DRAFT":
            raise BadRequestException(f"Cannot edit configuration in status '{config.status}'. Only DRAFT can be modified.")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        config.updated_by_user_id = user_id
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="PLATFORM_OPTIMIZATION_CONFIG",
            entity_id=str(config.id),
            new_value_json=update_data,
        )
        db.add(audit)
        db.commit()
        db.refresh(config)
        return config

    @staticmethod
    def activate_config(db: Session, config_id: int, user_id: int) -> PlatformOptimizationConfig:
        target_config = db.execute(
            select(PlatformOptimizationConfig).where(PlatformOptimizationConfig.id == config_id)
        ).scalar_one_or_none()

        if not target_config:
            raise NotFoundException(f"Platform optimization config {config_id} not found")

        # Deactivate all active configs
        active_configs = db.execute(
            select(PlatformOptimizationConfig).where(PlatformOptimizationConfig.is_active.is_(True))
        ).scalars().all()

        for active in active_configs:
            active.is_active = False
            active.status = "ARCHIVED"

        target_config.is_active = True
        target_config.status = "ACTIVE"
        target_config.activated_at = datetime.utcnow()
        target_config.activated_by_user_id = user_id
        target_config.updated_by_user_id = user_id

        audit = AuditLog(
            user_id=user_id,
            action="ACTIVATE",
            entity_type="PLATFORM_OPTIMIZATION_CONFIG",
            entity_id=str(target_config.id),
            new_value_json={"version": target_config.version},
        )
        db.add(audit)
        db.commit()
        db.refresh(target_config)
        return target_config

    # --- Config Templates ---

    @staticmethod
    def list_templates(db: Session) -> List[OptimizationConfigTemplate]:
        stmt = select(OptimizationConfigTemplate).order_by(OptimizationConfigTemplate.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_template(
        db: Session,
        req: OptimizationConfigTemplateCreateRequest,
        user_id: int,
    ) -> OptimizationConfigTemplate:
        template = OptimizationConfigTemplate(
            template_name=req.template_name,
            description=req.description,
            default_mode=req.default_mode,
            default_solver_backend=req.default_solver_backend,
            default_salvage_rate=req.default_salvage_rate,
            default_max_supplier_share=req.default_max_supplier_share,
            default_max_destination_share=req.default_max_destination_share,
            default_budget_inr=req.default_budget_inr,
            extra_params_json=req.extra_params_json,
            is_active=req.is_active,
            created_by_user_id=user_id,
        )
        db.add(template)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="OPTIMIZATION_CONFIG_TEMPLATE",
            entity_id=str(template.id),
            new_value_json={"template_name": template.template_name},
        )
        db.add(audit)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def update_template(
        db: Session,
        template_id: int,
        req: OptimizationConfigTemplateUpdateRequest,
        user_id: int,
    ) -> OptimizationConfigTemplate:
        template = db.execute(
            select(OptimizationConfigTemplate).where(OptimizationConfigTemplate.id == template_id)
        ).scalar_one_or_none()

        if not template:
            raise NotFoundException(f"Template {template_id} not found")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="OPTIMIZATION_CONFIG_TEMPLATE",
            entity_id=str(template.id),
            new_value_json=update_data,
        )
        db.add(audit)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def delete_template(db: Session, template_id: int, user_id: int) -> None:
        template = db.execute(
            select(OptimizationConfigTemplate).where(OptimizationConfigTemplate.id == template_id)
        ).scalar_one_or_none()

        if not template:
            raise NotFoundException(f"Template {template_id} not found")

        # Check if referenced by optimization runs
        # OptimizationRun may reference template_id or extra_config
        # We safely check if template is referenced
        db.delete(template)
        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="OPTIMIZATION_CONFIG_TEMPLATE",
            entity_id=str(template_id),
            new_value_json={"template_name": template.template_name},
        )
        db.add(audit)
        db.commit()
