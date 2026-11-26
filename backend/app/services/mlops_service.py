from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    EntityNotFoundError,
)
from backend.app.core.notification_events import EventTypes, NotificationCategory, RoleNames
from backend.app.models.schema import (
    AuditLog,
    DeploymentMode,
    DeploymentStatus,
    DriftSeverity,
    FeatureFreshnessMetric,
    FeatureSet,
    FreshnessStatus,
    MLModel,
    MLModelType,
    ModelDeployment,
    ModelLifecycleAction,
    ModelLifecycleEvent,
    ModelDriftReport,
    ModelTrainingRun,
    RetrainingTriggerConfig,
    RetrainingTriggerMetric,
    ShadowPredictionLog,
    TrainingStatus,
)
from backend.app.schemas.mlops import (
    DriftComputeRequest,
    FeatureFreshnessCheckRequest,
    ModelDeploymentCreateRequest,
    ModelDeploymentUpdateRequest,
    ModelPromoteGovernanceRequest,
    ModelRollbackRequest,
    RetrainingTriggerConfigRequest,
    ShadowPredictionLogRequest,
)
from backend.app.services.ml_registry_service import MLRegistryService
from backend.app.services.notification_service import NotificationService
from ml_engine.monitoring.data_drift import DataDriftDetector
from optimization.predictions.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class MLOpsService:
    """Service layer for Domain 2: MLOps Production Governance."""

    @staticmethod
    def compute_and_record_drift(
        db: Session,
        req: DriftComputeRequest,
        service_identity: str = "mlops_monitoring_worker",
    ) -> ModelDriftReport:
        """
        Trusted monitoring workflow: computes PSI & two-sample KS statistics directly
        from raw baseline and target feature arrays. Never accepts user-supplied PSI/KS values.
        """
        model = db.execute(select(MLModel).where(MLModel.id == req.model_id)).scalar_one_or_none()
        if not model:
            raise EntityNotFoundError("MLModel", req.model_id)

        common_cols = sorted(set(req.baseline_features.keys()) & set(req.target_features.keys()))
        feature_metrics: Dict[str, Any] = {}
        psi_values: List[float] = []
        ks_stats: List[float] = []
        ks_pvals: List[float] = []
        finite_b_lens: List[int] = []
        finite_t_lens: List[int] = []

        for col in common_cols:
            b_raw = np.asarray(req.baseline_features[col], dtype=float)
            t_raw = np.asarray(req.target_features[col], dtype=float)
            b_arr = b_raw[np.isfinite(b_raw)]
            t_arr = t_raw[np.isfinite(t_raw)]
            if len(b_arr) < 10 or len(t_arr) < 10:
                raise BadRequestException(
                    f"Feature '{col}' requires at least 10 finite observations per window "
                    f"(got baseline={len(b_arr)}, target={len(t_arr)})."
                )
            finite_b_lens.append(int(len(b_arr)))
            finite_t_lens.append(int(len(t_arr)))

            psi_val = DataDriftDetector.calculate_psi(b_arr, t_arr, num_buckets=req.num_buckets)
            if psi_val is None or not math.isfinite(psi_val):
                psi_val = 0.0
            ks_res = stats.ks_2samp(b_arr, t_arr)
            if not math.isfinite(ks_res.statistic) or not math.isfinite(ks_res.pvalue):
                raise BadRequestException(f"Non-finite KS statistic computed for feature '{col}'.")
            ks_stat = float(round(ks_res.statistic, 4))
            ks_pval = float(round(ks_res.pvalue, 6))

            psi_values.append(psi_val)
            ks_stats.append(ks_stat)
            ks_pvals.append(ks_pval)
            feature_metrics[col] = {
                "psi": psi_val,
                "ks_statistic": ks_stat,
                "ks_pvalue": ks_pval,
                "baseline_mean": round(float(np.mean(b_arr)), 4),
                "target_mean": round(float(np.mean(t_arr)), 4),
                "baseline_std": round(float(np.std(b_arr)), 4),
                "target_std": round(float(np.std(t_arr)), 4),
            }

        min_b_len = min(finite_b_lens)
        min_t_len = min(finite_t_lens)

        overall_psi = round(float(np.mean(psi_values)), 4)
        max_ks = round(float(max(ks_stats)), 4)
        min_pval = round(float(min(ks_pvals)), 6)

        if overall_psi >= 0.25 or (max_ks >= 0.30 and min_pval < 0.01):
            severity = DriftSeverity.SEVERE
            retrain_rec = True
        elif overall_psi >= 0.10 or (max_ks >= 0.18 and min_pval < 0.05):
            severity = DriftSeverity.MODERATE
            retrain_rec = overall_psi >= 0.20
        else:
            severity = DriftSeverity.NONE
            retrain_rec = False

        report = ModelDriftReport(
            model_id=model.id,
            model_type=model.model_type,
            baseline_window_start=req.baseline_window_start,
            baseline_window_end=req.baseline_window_end,
            target_window_start=req.target_window_start,
            target_window_end=req.target_window_end,
            sample_size_baseline=min_b_len,
            sample_size_target=min_t_len,
            overall_psi=overall_psi,
            max_ks_statistic=max_ks,
            min_ks_pvalue=min_pval,
            severity=severity,
            feature_metrics_json=feature_metrics,
            computed_by_service=service_identity,
            retraining_recommended=retrain_rec,
        )
        db.add(report)
        db.flush()

        # Check configured retraining triggers
        MLOpsService._evaluate_retraining_triggers(
            db,
            model_type=model.model_type,
            psi_val=overall_psi,
            ks_val=max_ks,
        )

        db.add(AuditLog(
            user_id=None,
            action="MODEL_DRIFT_COMPUTED",
            entity_type="model_drift_reports",
            entity_id=report.report_uid,
            new_value_json={
                "model_id": model.id,
                "overall_psi": overall_psi,
                "max_ks": max_ks,
                "severity": severity.value,
            },
        ))
        db.commit()
        db.refresh(report)

        if severity in (DriftSeverity.MODERATE, DriftSeverity.SEVERE):
            try:
                NotificationService.notify_sync(
                    event_type=EventTypes.SYSTEM_ERROR_RATE,
                    title=f"Model Drift Detected ({severity.value})",
                    message=f"Model {model.model_type.value} v{model.version} recorded PSI={overall_psi}, KS={max_ks}.",
                    roles=[RoleNames.ADMIN, RoleNames.ANALYST],
                    category=NotificationCategory.SYSTEM.value,
                    severity="WARNING" if severity == DriftSeverity.MODERATE else "CRITICAL",
                    entity_type="model_drift_report",
                    entity_id=report.report_uid,
                    source_module="mlops",
                    db=db,
                )
            except Exception as exc:
                logger.warning("Failed to dispatch drift notification: %s", exc)

        return report

    @staticmethod
    def _evaluate_retraining_triggers(
        db: Session,
        model_type: MLModelType,
        psi_val: Optional[float] = None,
        ks_val: Optional[float] = None,
        lag_seconds: Optional[int] = None,
    ) -> None:
        triggers = list(
            db.execute(
                select(RetrainingTriggerConfig).where(
                    RetrainingTriggerConfig.model_type == model_type,
                    RetrainingTriggerConfig.is_enabled == True,
                    RetrainingTriggerConfig.auto_trigger_training == True,
                )
            ).scalars().all()
        )
        now = datetime.now(timezone.utc)
        for trig in triggers:
            breached = False
            if trig.trigger_metric == RetrainingTriggerMetric.PSI and psi_val is not None:
                breached = psi_val >= trig.threshold_value
            elif trig.trigger_metric == RetrainingTriggerMetric.KS_STATISTIC and ks_val is not None:
                breached = ks_val >= trig.threshold_value
            elif trig.trigger_metric == RetrainingTriggerMetric.FEATURE_STALENESS and lag_seconds is not None:
                breached = lag_seconds >= trig.threshold_value

            if not breached:
                continue
            if trig.last_triggered_at and (_ensure_utc(trig.last_triggered_at) + timedelta(hours=trig.cooldown_hours)) > now:
                continue

            fs = db.execute(
                select(FeatureSet)
                .where(FeatureSet.is_active == True, FeatureSet.entity_type == model_type.value)
                .order_by(FeatureSet.created_at.desc())
            ).scalars().first()
            if not fs:
                fs = db.execute(
                    select(FeatureSet).where(FeatureSet.is_active == True).order_by(FeatureSet.created_at.desc())
                ).scalars().first()
            if fs:
                db.add(ModelTrainingRun(
                    model_type=model_type,
                    feature_set_id=fs.id,
                    algorithm="LightGBM",
                    hyperparameters_json={"auto_triggered_by": trig.trigger_metric.value},
                    cv_folds=5,
                    status=TrainingStatus.PENDING,
                    notes=f"Auto-triggered by {trig.trigger_metric.value} >= {trig.threshold_value}",
                ))
            trig.last_triggered_at = now

    @staticmethod
    def list_drift_reports(
        db: Session,
        model_id: Optional[int] = None,
        model_type: Optional[MLModelType] = None,
        severity: Optional[DriftSeverity] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ModelDriftReport], int]:
        stmt = select(ModelDriftReport)
        if model_id:
            stmt = stmt.where(ModelDriftReport.model_id == model_id)
        if model_type:
            stmt = stmt.where(ModelDriftReport.model_type == model_type)
        if severity:
            stmt = stmt.where(ModelDriftReport.severity == severity)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            db.execute(
                stmt.order_by(ModelDriftReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return items, total

    @staticmethod
    def check_feature_freshness(
        db: Session, req: FeatureFreshnessCheckRequest
    ) -> FeatureFreshnessMetric:
        fs: Optional[FeatureSet] = None
        if req.feature_set_id:
            fs = db.execute(select(FeatureSet).where(FeatureSet.id == req.feature_set_id)).scalar_one_or_none()
            if not fs:
                raise EntityNotFoundError("FeatureSet", req.feature_set_id)

        now = datetime.now(timezone.utc)
        last_upd = _ensure_utc(req.last_updated_at)
        lag = max(0, int((now - last_upd).total_seconds()))
        sla = req.sla_threshold_seconds

        if lag > sla:
            st = FreshnessStatus.STALE
        elif lag > int(sla * 0.75):
            st = FreshnessStatus.WARNING
        else:
            st = FreshnessStatus.FRESH

        metric = FeatureFreshnessMetric(
            feature_set_id=req.feature_set_id,
            feature_group_name=req.feature_group_name.strip(),
            last_updated_at=last_upd,
            evaluated_at=now,
            lag_seconds=lag,
            sla_threshold_seconds=sla,
            status=st,
            record_count=req.record_count,
            details_json=req.details_json,
        )
        db.add(metric)
        db.flush()

        # Wire FEATURE_STALENESS retraining trigger evaluation
        evaluated_types: List[MLModelType] = []
        if fs and fs.entity_type:
            try:
                evaluated_types.append(MLModelType(fs.entity_type.upper()))
            except ValueError:
                pass
        if not evaluated_types and st != FreshnessStatus.FRESH:
            evaluated_types = list(
                db.execute(
                    select(RetrainingTriggerConfig.model_type).where(
                        RetrainingTriggerConfig.trigger_metric == RetrainingTriggerMetric.FEATURE_STALENESS,
                        RetrainingTriggerConfig.is_enabled == True,
                        RetrainingTriggerConfig.auto_trigger_training == True,
                    ).distinct()
                ).scalars().all()
            )
        for mt in evaluated_types:
            MLOpsService._evaluate_retraining_triggers(db, model_type=mt, lag_seconds=lag)

        db.commit()
        db.refresh(metric)
        return metric

    @staticmethod
    def list_feature_freshness(
        db: Session,
        feature_group_name: Optional[str] = None,
        status: Optional[FreshnessStatus] = None,
    ) -> List[FeatureFreshnessMetric]:
        stmt = select(FeatureFreshnessMetric)
        if feature_group_name:
            stmt = stmt.where(FeatureFreshnessMetric.feature_group_name.ilike(f"%{feature_group_name.strip()}%"))
        if status:
            stmt = stmt.where(FeatureFreshnessMetric.status == status)
        return list(db.execute(stmt.order_by(FeatureFreshnessMetric.evaluated_at.desc())).scalars().all())

    @staticmethod
    def create_deployment(
        db: Session, req: ModelDeploymentCreateRequest, user_id: int
    ) -> ModelDeployment:
        model = db.execute(select(MLModel).where(MLModel.id == req.model_id)).scalar_one_or_none()
        if not model:
            raise EntityNotFoundError("MLModel", req.model_id)

        if req.deployment_mode == DeploymentMode.CANARY:
            # Ensure at most one active canary per model_type
            active_canary = db.execute(
                select(ModelDeployment).where(
                    ModelDeployment.model_type == model.model_type,
                    ModelDeployment.deployment_mode == DeploymentMode.CANARY,
                    ModelDeployment.status == DeploymentStatus.ACTIVE,
                )
            ).scalar_one_or_none()
            if active_canary:
                raise ConflictException(
                    f"An active canary deployment ({active_canary.deployment_uid}) already exists for {model.model_type.value}."
                )

        is_live = req.deployment_mode == DeploymentMode.CANARY
        traffic = 0.0 if req.deployment_mode == DeploymentMode.SHADOW else req.traffic_percentage

        dep = ModelDeployment(
            model_id=model.id,
            model_type=model.model_type,
            deployment_mode=req.deployment_mode,
            status=DeploymentStatus.ACTIVE,
            traffic_percentage=traffic,
            influences_live_decisions=is_live,
            deployed_by_user_id=user_id,
            notes=req.notes,
        )
        db.add(dep)
        db.flush()

        action_enum = (
            ModelLifecycleAction.SHADOW_DEPLOYED
            if req.deployment_mode == DeploymentMode.SHADOW
            else ModelLifecycleAction.CANARY_DEPLOYED
        )
        db.add(ModelLifecycleEvent(
            model_id=model.id,
            model_type=model.model_type,
            action=action_enum,
            performed_by_user_id=user_id,
            reason=req.notes or f"Deployed in {req.deployment_mode.value} mode",
            metadata_json={"deployment_uid": dep.deployment_uid, "traffic_percentage": traffic},
        ))
        db.add(AuditLog(
            user_id=user_id,
            action=f"ML_DEPLOYMENT_{req.deployment_mode.value}_CREATED",
            entity_type="model_deployments",
            entity_id=dep.deployment_uid,
            new_value_json={"model_id": model.id, "traffic_percentage": traffic, "influences_live": is_live},
        ))
        db.commit()
        db.refresh(dep)
        return dep

    @staticmethod
    def list_deployments(
        db: Session,
        model_type: Optional[MLModelType] = None,
        deployment_mode: Optional[DeploymentMode] = None,
        status: Optional[DeploymentStatus] = None,
    ) -> List[ModelDeployment]:
        stmt = select(ModelDeployment)
        if model_type:
            stmt = stmt.where(ModelDeployment.model_type == model_type)
        if deployment_mode:
            stmt = stmt.where(ModelDeployment.deployment_mode == deployment_mode)
        if status:
            stmt = stmt.where(ModelDeployment.status == status)
        return list(db.execute(stmt.order_by(ModelDeployment.activated_at.desc())).scalars().all())

    @staticmethod
    def update_deployment(
        db: Session, deployment_id: int, req: ModelDeploymentUpdateRequest, user_id: int
    ) -> ModelDeployment:
        dep = db.execute(select(ModelDeployment).where(ModelDeployment.id == deployment_id)).scalar_one_or_none()
        if not dep:
            raise EntityNotFoundError("ModelDeployment", deployment_id)

        if dep.deployment_mode == DeploymentMode.SHADOW and req.traffic_percentage is not None and req.traffic_percentage != 0.0:
            raise BadRequestException("SHADOW deployments must retain traffic_percentage=0.0 and cannot serve live traffic.")

        if req.traffic_percentage is not None:
            dep.traffic_percentage = req.traffic_percentage
        if req.status is not None:
            dep.status = req.status
            if req.status in (DeploymentStatus.ROLLED_BACK, DeploymentStatus.PROMOTED, DeploymentStatus.RETIRED):
                dep.ended_at = datetime.now(timezone.utc)
        if req.notes is not None:
            dep.notes = req.notes

        db.add(AuditLog(
            user_id=user_id,
            action="ML_DEPLOYMENT_UPDATED",
            entity_type="model_deployments",
            entity_id=dep.deployment_uid,
            new_value_json=req.model_dump(exclude_unset=True),
        ))
        db.commit()
        db.refresh(dep)
        return dep

    @staticmethod
    def select_serving_model(
        db: Session, model_type: MLModelType, entity_id: str
    ) -> Tuple[Optional[MLModel], str]:
        """
        Determines which model handles a live inference request.
        SHADOW deployments NEVER influence live routing; CANARY deployments route
        deterministically based on SHA-256 hash of entity_id.
        """
        active_canary = db.execute(
            select(ModelDeployment).where(
                ModelDeployment.model_type == model_type,
                ModelDeployment.deployment_mode == DeploymentMode.CANARY,
                ModelDeployment.status == DeploymentStatus.ACTIVE,
                ModelDeployment.influences_live_decisions == True,
            )
        ).scalar_one_or_none()

        if active_canary and active_canary.traffic_percentage > 0:
            bucket = int(hashlib.sha256(entity_id.encode("utf-8")).hexdigest()[:8], 16) % 100
            if bucket < active_canary.traffic_percentage:
                canary_model = db.execute(
                    select(MLModel).where(MLModel.id == active_canary.model_id)
                ).scalar_one_or_none()
                if canary_model:
                    return canary_model, f"CANARY:{active_canary.deployment_uid}"

        champion = db.execute(
            select(MLModel).where(
                MLModel.model_type == model_type,
                MLModel.is_champion == True,
            )
        ).scalar_one_or_none()
        return champion, "CHAMPION"

    @staticmethod
    def record_shadow_prediction(
        db: Session, deployment_id: int, req: ShadowPredictionLogRequest
    ) -> ShadowPredictionLog:
        """Records an isolated shadow prediction for offline comparison without affecting live decisions."""
        dep = db.execute(select(ModelDeployment).where(ModelDeployment.id == deployment_id)).scalar_one_or_none()
        if not dep:
            raise EntityNotFoundError("ModelDeployment", deployment_id)
        if dep.status != DeploymentStatus.ACTIVE:
            raise BadRequestException(f"Deployment {dep.deployment_uid} is not ACTIVE.")

        cand_pred = req.candidate_prediction
        if cand_pred is None:
            # Deterministic fallback evaluation if artifact not invoked directly
            raise BadRequestException("candidate_prediction must be supplied or computed by inference pipeline.")

        delta = (cand_pred - req.champion_prediction) if req.champion_prediction is not None else None
        feat_hash = hashlib.sha256(json.dumps(req.features, sort_keys=True, default=str).encode("utf-8")).hexdigest()

        log = ShadowPredictionLog(
            deployment_id=dep.id,
            model_id=dep.model_id,
            entity_id=req.entity_id,
            champion_prediction=req.champion_prediction,
            candidate_prediction=cand_pred,
            prediction_delta=round(delta, 6) if delta is not None else None,
            features_hash=feat_hash,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def list_shadow_logs(db: Session, deployment_id: int) -> List[ShadowPredictionLog]:
        dep = db.execute(select(ModelDeployment).where(ModelDeployment.id == deployment_id)).scalar_one_or_none()
        if not dep:
            raise EntityNotFoundError("ModelDeployment", deployment_id)
        return list(
            db.execute(
                select(ShadowPredictionLog)
                .where(ShadowPredictionLog.deployment_id == deployment_id)
                .order_by(ShadowPredictionLog.recorded_at.desc())
                .limit(200)
            ).scalars().all()
        )

    @staticmethod
    def promote_model_governed(
        db: Session, model_id: int, req: ModelPromoteGovernanceRequest, user_id: int
    ) -> MLModel:
        model = MLRegistryService.get_model(db, model_id)
        if req.require_no_severe_drift:
            latest_drift = db.execute(
                select(ModelDriftReport)
                .where(ModelDriftReport.model_id == model.id)
                .order_by(ModelDriftReport.created_at.desc())
            ).scalars().first()
            if latest_drift and latest_drift.severity == DriftSeverity.SEVERE:
                raise ConflictException(
                    f"Cannot promote model {model.id}: latest drift report {latest_drift.report_uid} has SEVERE drift (PSI={latest_drift.overall_psi})."
                )

        prev_champ = db.execute(
            select(MLModel).where(
                MLModel.model_type == model.model_type,
                MLModel.is_champion == True,
                MLModel.id != model.id,
            )
        ).scalar_one_or_none()

        promoted = MLRegistryService.promote_model(db, model_id, user_id=user_id)

        # Mark any active deployments for this model as PROMOTED
        active_deps = list(
            db.execute(
                select(ModelDeployment).where(
                    ModelDeployment.model_id == model.id,
                    ModelDeployment.status == DeploymentStatus.ACTIVE,
                )
            ).scalars().all()
        )
        for dep in active_deps:
            dep.status = DeploymentStatus.PROMOTED
            dep.ended_at = datetime.now(timezone.utc)

        db.add(ModelLifecycleEvent(
            model_id=promoted.id,
            model_type=promoted.model_type,
            action=ModelLifecycleAction.PROMOTED_CHAMPION,
            previous_champion_model_id=prev_champ.id if prev_champ else None,
            performed_by_user_id=user_id,
            reason=req.reason or "Promoted via MLOps governance workflow",
            metadata_json={"version": promoted.version},
        ))
        db.commit()
        db.refresh(promoted)
        return promoted

    @staticmethod
    def rollback_model(
        db: Session, model_id: int, req: ModelRollbackRequest, user_id: int
    ) -> MLModel:
        current = MLRegistryService.get_model(db, model_id)

        # Determine rollback target
        target: Optional[MLModel] = None
        if req.target_model_id:
            target = MLRegistryService.get_model(db, req.target_model_id)
            if target.model_type != current.model_type:
                raise BadRequestException("Rollback target model must have the same model_type.")
            if target.id == current.id:
                raise BadRequestException("Rollback target cannot be the same model.")
            if target.model_status == "RETIRED":
                raise BadRequestException("Cannot roll back to a RETIRED model.")
        else:
            last_prom = db.execute(
                select(ModelLifecycleEvent)
                .where(
                    ModelLifecycleEvent.model_id == current.id,
                    ModelLifecycleEvent.action == ModelLifecycleAction.PROMOTED_CHAMPION,
                    ModelLifecycleEvent.previous_champion_model_id.is_not(None),
                )
                .order_by(ModelLifecycleEvent.occurred_at.desc())
            ).scalars().first()
            if last_prom and last_prom.previous_champion_model_id:
                target = db.execute(
                    select(MLModel).where(MLModel.id == last_prom.previous_champion_model_id)
                ).scalar_one_or_none()
            if not target:
                target = db.execute(
                    select(MLModel).where(
                        MLModel.model_type == current.model_type,
                        MLModel.id != current.id,
                        MLModel.model_status != "RETIRED",
                    ).order_by(MLModel.created_at.desc())
                ).scalars().first()

        if not target:
            raise BadRequestException(f"No eligible fallback model available to roll back from model {model_id}.")

        # Demote current model AND any other active champion of this model_type (unique constraint safety)
        existing_champs = list(
            db.execute(
                select(MLModel).where(
                    MLModel.model_type == current.model_type,
                    MLModel.is_champion == True,
                )
            ).scalars().all()
        )
        for champ in existing_champs:
            if champ.id != target.id:
                champ.is_champion = False
                champ.model_status = "ROLLED_BACK" if champ.id == current.id else "ARCHIVED"
        current.is_champion = False
        current.model_status = "ROLLED_BACK"
        db.flush()

        active_deps = list(
            db.execute(
                select(ModelDeployment).where(
                    ModelDeployment.model_id == current.id,
                    ModelDeployment.status == DeploymentStatus.ACTIVE,
                )
            ).scalars().all()
        )
        for dep in active_deps:
            dep.status = DeploymentStatus.ROLLED_BACK
            dep.ended_at = datetime.now(timezone.utc)
            dep.rollback_reason = req.reason

        target.is_champion = True
        target.model_status = "PROMOTED"
        target.promoted_at = datetime.now(timezone.utc)

        db.add(ModelLifecycleEvent(
            model_id=target.id,
            model_type=target.model_type,
            action=ModelLifecycleAction.ROLLED_BACK,
            previous_champion_model_id=current.id,
            performed_by_user_id=user_id,
            reason=req.reason,
            metadata_json={"rolled_back_from": current.id, "restored_model": target.id},
        ))
        db.add(AuditLog(
            user_id=user_id,
            action="ML_MODEL_ROLLED_BACK",
            entity_type="ml_models",
            entity_id=str(target.id),
            old_value_json={"champion_id": current.id},
            new_value_json={"champion_id": target.id, "reason": req.reason},
        ))
        db.commit()

        model_type_str = target.model_type.value
        ModelRegistry.invalidate_cache(model_type_str.lower())
        try:
            from ml_engine.model_registry.registry import ModelArtifactRegistry
            ModelArtifactRegistry.invalidate_cache(model_type_str.lower())
        except Exception as exc:
            logger.warning("Cache invalidation warning on rollback: %s", exc)

        db.refresh(target)
        return target

    @staticmethod
    def list_lifecycle_history(
        db: Session,
        model_id: Optional[int] = None,
        model_type: Optional[MLModelType] = None,
    ) -> List[ModelLifecycleEvent]:
        stmt = select(ModelLifecycleEvent)
        if model_id:
            stmt = stmt.where(ModelLifecycleEvent.model_id == model_id)
        if model_type:
            stmt = stmt.where(ModelLifecycleEvent.model_type == model_type)
        return list(db.execute(stmt.order_by(ModelLifecycleEvent.occurred_at.desc())).scalars().all())

    @staticmethod
    def upsert_retraining_trigger(
        db: Session, req: RetrainingTriggerConfigRequest, user_id: int
    ) -> RetrainingTriggerConfig:
        existing = db.execute(
            select(RetrainingTriggerConfig).where(
                RetrainingTriggerConfig.model_type == req.model_type,
                RetrainingTriggerConfig.trigger_metric == req.trigger_metric,
            )
        ).scalar_one_or_none()

        if existing:
            existing.threshold_value = req.threshold_value
            existing.auto_trigger_training = req.auto_trigger_training
            existing.cooldown_hours = req.cooldown_hours
            existing.is_enabled = req.is_enabled
            cfg = existing
        else:
            cfg = RetrainingTriggerConfig(
                model_type=req.model_type,
                trigger_metric=req.trigger_metric,
                threshold_value=req.threshold_value,
                auto_trigger_training=req.auto_trigger_training,
                cooldown_hours=req.cooldown_hours,
                is_enabled=req.is_enabled,
                created_by_user_id=user_id,
            )
            db.add(cfg)

        db.add(AuditLog(
            user_id=user_id,
            action="RETRAINING_TRIGGER_UPSERTED",
            entity_type="retraining_trigger_configs",
            entity_id=f"{req.model_type.value}:{req.trigger_metric.value}",
            new_value_json={"threshold": req.threshold_value, "auto_trigger": req.auto_trigger_training},
        ))
        db.commit()
        db.refresh(cfg)
        return cfg

    @staticmethod
    def list_retraining_triggers(
        db: Session, model_type: Optional[MLModelType] = None
    ) -> List[RetrainingTriggerConfig]:
        stmt = select(RetrainingTriggerConfig)
        if model_type:
            stmt = stmt.where(RetrainingTriggerConfig.model_type == model_type)
        return list(db.execute(stmt.order_by(RetrainingTriggerConfig.model_type.asc())).scalars().all())
