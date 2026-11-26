from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, EntityNotFoundError, BadRequestException
from backend.app.models.schema import (
    AuditLog,
    FeatureSet,
    MLModel,
    MLModelType,
    ModelTrainingRun,
    TrainingStatus,
)
from backend.app.schemas.ml_registry import (
    FeatureSetCreateRequest,
    ModelTrainingTriggerRequest,
)
from optimization.predictions.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class MLRegistryService:
    # --- Feature Sets (70-72) ---
    @staticmethod
    def list_feature_sets(
        db: Session,
        model_type: Optional[MLModelType] = None,
        name: Optional[str] = None,
    ) -> list[FeatureSet]:
        query = db.query(FeatureSet)
        if model_type:
            query = query.filter(FeatureSet.model_type == model_type)
        if name:
            query = query.filter(FeatureSet.name.ilike(f"%{name.strip()}%"))
        return query.order_by(FeatureSet.created_at.desc()).all()

    @staticmethod
    def get_feature_set(db: Session, feature_set_id: int) -> FeatureSet:
        fs = db.query(FeatureSet).filter(FeatureSet.id == feature_set_id).first()
        if not fs:
            raise EntityNotFoundError("FeatureSet", feature_set_id)
        return fs

    @staticmethod
    def create_feature_set(db: Session, payload: FeatureSetCreateRequest, user_id: int) -> FeatureSet:
        fs = FeatureSet(
            name=payload.name.strip(),
            version=payload.version.strip(),
            entity_type=str(payload.model_type.value if hasattr(payload.model_type, "value") else payload.model_type),
            parquet_path=payload.parquet_path.strip(),
            row_count=payload.num_rows,
            feature_columns_json=payload.column_names,
            temporal_split_cutoff=payload.cutoff_date,
            is_active=True,
        )
        db.add(fs)
        db.add(AuditLog(
            user_id=user_id,
            action="FEATURE_SET_REGISTERED",
            entity_type="feature_sets",
            entity_id=fs.name,
            new_value_json={"version": fs.version},
        ))
        db.commit()
        db.refresh(fs)
        return fs

    # --- ML Models (73-77) ---
    @staticmethod
    def list_models(
        db: Session,
        model_type: Optional[MLModelType] = None,
        is_champion: Optional[bool] = None,
    ) -> list[MLModel]:
        query = db.query(MLModel)
        if model_type:
            query = query.filter(MLModel.model_type == model_type)
        if is_champion is not None:
            query = query.filter(MLModel.is_champion == is_champion)
        return query.order_by(MLModel.model_type.asc(), MLModel.is_champion.desc()).all()

    @staticmethod
    def get_model(db: Session, model_id: int) -> MLModel:
        model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            raise EntityNotFoundError("MLModel", model_id)
        return model

    @staticmethod
    def get_champions(db: Session) -> list[MLModel]:
        return db.query(MLModel).filter(MLModel.is_champion == True).all()

    @staticmethod
    def promote_model(db: Session, model_id: int, user_id: int) -> MLModel:
        model = MLRegistryService.get_model(db, model_id)

        model_type_str = (
            model.model_type.value
            if hasattr(model.model_type, "value")
            else str(model.model_type)
        )

        # Verify physical model artifacts on disk before promoting
        art_dir = model.artifact_dir
        if not art_dir or not os.path.exists(art_dir):
            # Check standard fallback directory
            fallback_dir = os.path.join("data", "models", model_type_str.lower())
            if os.path.exists(fallback_dir):
                art_dir = fallback_dir
                model.artifact_dir = fallback_dir
            else:
                raise ConflictError(
                    f"Cannot promote model {model_id}: Artifact directory '{art_dir}' not found on disk."
                )

        est_file = os.path.join(art_dir, "estimator.joblib")
        meta_file = os.path.join(art_dir, "metadata.json")

        if not os.path.exists(est_file) or not os.path.exists(meta_file):
            raise ConflictError(
                f"Cannot promote model {model_id}: Required artifact files (estimator.joblib / metadata.json) missing in '{art_dir}'."
            )

        # Calculate artifact checksum
        sha256 = hashlib.sha256()
        with open(est_file, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        model.artifact_checksum = sha256.hexdigest()

        # Demote current champion of same model_type
        db.query(MLModel).filter(
            MLModel.model_type == model.model_type,
            MLModel.id != model.id,
            MLModel.is_champion == True,
        ).update({"is_champion": False, "model_status": "EVALUATED"})

        model.is_champion = True
        model.model_status = "PROMOTED"
        model.promoted_at = datetime.now(timezone.utc)

        model_type_str = (
            model.model_type.value
            if hasattr(model.model_type, "value")
            else str(model.model_type)
        )

        db.add(AuditLog(
            user_id=user_id,
            action="ML_MODEL_PROMOTED_CHAMPION",
            entity_type="ml_models",
            entity_id=str(model.id),
            new_value_json={
                "model_type": model_type_str,
                "version": model.version,
                "artifact_checksum": model.artifact_checksum,
            },
        ))
        db.commit()

        # Invalidate in-memory ModelRegistry and ML Engine caches immediately after successful database commit
        ModelRegistry.invalidate_cache(model_type_str.lower())
        try:
            from ml_engine.model_registry.registry import ModelArtifactRegistry
            ModelArtifactRegistry.invalidate_cache(model_type_str.lower())
        except Exception as e:
            logger.warning("Failed to invalidate ModelArtifactRegistry cache for %s: %s", model_type_str, e)

        try:
            db.refresh(model)
        except Exception as e:
            logger.warning("Failed to refresh model %s after promotion commit: %s", model.id, e)

        return model

    @staticmethod
    def retire_model(db: Session, model_id: int, user_id: int) -> MLModel:
        model = MLRegistryService.get_model(db, model_id)
        model.is_champion = False
        model.model_status = "RETIRED"

        # Resolve task key before commit while model attributes are in active session scope
        model_type_str = (
            model.model_type.value
            if hasattr(model.model_type, "value")
            else str(model.model_type)
        )

        db.add(AuditLog(
            user_id=user_id,
            action="ML_MODEL_RETIRED",
            entity_type="ml_models",
            entity_id=str(model.id),
        ))
        db.commit()

        # Invalidate in-memory ModelRegistry and ML Engine caches immediately after successful database commit
        ModelRegistry.invalidate_cache(model_type_str.lower())
        try:
            from ml_engine.model_registry.registry import ModelArtifactRegistry
            ModelArtifactRegistry.invalidate_cache(model_type_str.lower())
        except Exception as e:
            logger.warning("Failed to invalidate ModelArtifactRegistry cache for %s: %s", model_type_str, e)

        try:
            db.refresh(model)
        except Exception as e:
            logger.warning("Failed to refresh model %s after retirement commit: %s", model.id, e)

        return model

    # --- Training Runs (78-81) ---
    @staticmethod
    def list_training_runs(
        db: Session,
        model_type: Optional[MLModelType] = None,
        status: Optional[TrainingStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelTrainingRun], int]:
        query = db.query(ModelTrainingRun)
        if model_type:
            query = query.filter(ModelTrainingRun.model_type == model_type)
        if status:
            query = query.filter(ModelTrainingRun.status == status)

        total = query.count()
        runs = query.order_by(ModelTrainingRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return runs, total

    @staticmethod
    def trigger_training_run(db: Session, payload: ModelTrainingTriggerRequest, user_id: int) -> ModelTrainingRun:
        # Validate feature set exists
        fs = db.query(FeatureSet).filter(FeatureSet.id == payload.feature_set_id).first()
        if not fs:
            raise EntityNotFoundError("FeatureSet", payload.feature_set_id)

        # Validate algorithm
        allowed_algorithms = {"lightgbm", "xgboost", "random_forest", "linear_regression", "logistic_regression", "naive"}
        algo_norm = payload.algorithm.lower().strip()
        if algo_norm not in allowed_algorithms:
            raise BadRequestException(f"Unsupported algorithm '{payload.algorithm}'. Allowed: {sorted(list(allowed_algorithms))}")

        batch_task = f"train-run-{uuid.uuid4().hex[:8]}"
        run_notes = (payload.notes or "").strip()
        audit_note = f"Registered training run request. Awaiting administrative execution batch. {run_notes}".strip()

        run = ModelTrainingRun(
            model_type=payload.model_type,
            feature_set_id=payload.feature_set_id,
            algorithm=payload.algorithm,
            hyperparameters_json=payload.hyperparameters or {},
            cv_folds=payload.cv_folds,
            status=TrainingStatus.PENDING,
            celery_task_id=batch_task,
            started_by_user_id=user_id,
            notes=audit_note,
        )
        db.add(run)
        db.add(AuditLog(
            user_id=user_id,
            action="ML_TRAINING_RUN_TRIGGERED",
            entity_type="model_training_runs",
            entity_id=str(batch_task),
            new_value_json={"model_type": payload.model_type.value, "algorithm": payload.algorithm, "status": "PENDING"},
        ))
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_training_run(db: Session, run_id: int) -> ModelTrainingRun:
        run = db.query(ModelTrainingRun).filter(ModelTrainingRun.id == run_id).first()
        if not run:
            raise EntityNotFoundError("ModelTrainingRun", run_id)
        return run

    @staticmethod
    def cancel_training_run(db: Session, run_id: int, user_id: int) -> ModelTrainingRun:
        run = MLRegistryService.get_training_run(db, run_id)
        if run.status in (TrainingStatus.COMPLETED, TrainingStatus.FAILED, TrainingStatus.ABORTED):
            raise ConflictError(f"Cannot cancel run {run_id} in terminal state '{run.status.value}'.")

        run.status = TrainingStatus.FAILED
        run.notes = f"Cancelled by user {user_id}. {run.notes or ''}".strip()
        db.add(AuditLog(
            user_id=user_id,
            action="ML_TRAINING_RUN_CANCELLED",
            entity_type="model_training_runs",
            entity_id=str(run.id),
        ))
        db.commit()
        db.refresh(run)
        return run
