"""
ml_engine/model_registry/model_metadata.py

Metadata parsing, validation, and contract verification for serialized Phase 4 models.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from ml_engine.exceptions import ArtifactCorruptedError, SchemaMismatchError
from ml_engine.schemas import ModelMetadataSchema

logger = logging.getLogger(__name__)


class ModelMetadataValidator:
    """Validates metadata.json files against production schemas and file assets."""

    @staticmethod
    def load_and_validate(metadata_path: str) -> Tuple[ModelMetadataSchema, Dict[str, Any]]:
        """
        Loads metadata.json, validates required keys and structure, and returns typed schema.
        """
        if not os.path.exists(metadata_path):
            raise ArtifactCorruptedError(f"Model metadata file missing at '{metadata_path}'")

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as exc:
            raise ArtifactCorruptedError(f"Failed to parse JSON metadata at '{metadata_path}': {exc}") from exc

        # Validate mandatory fields
        required_keys = ["task_name", "task_type", "model_name", "feature_names", "feature_count"]
        missing_keys = [k for k in required_keys if k not in raw_data]
        if missing_keys:
            raise ArtifactCorruptedError(
                f"Metadata file '{metadata_path}' is missing mandatory fields: {missing_keys}"
            )

        declared_count = raw_data.get("feature_count", 0)
        actual_features = raw_data.get("feature_names", [])
        if declared_count != len(actual_features):
            raise SchemaMismatchError(
                f"Metadata feature count mismatch: declared {declared_count}, but listed {len(actual_features)} features"
            )

        schema = ModelMetadataSchema(
            task_name=raw_data["task_name"],
            task_type=raw_data["task_type"],
            model_name=raw_data["model_name"],
            target_column=raw_data.get("target_column"),
            feature_names=actual_features,
            feature_count=declared_count,
            saved_timestamp=raw_data.get("saved_timestamp"),
            random_seed=raw_data.get("random_seed", 42),
            artifact_checksum=raw_data.get("artifact_checksum"),
            packages=raw_data.get("packages", {}),
            test_metrics=raw_data.get("test_metrics", {}),
            cv_summary=raw_data.get("cv_summary", {}),
            business_params=raw_data.get("business_params", {}),
            selection_rationale=raw_data.get("selection_rationale"),
        )

        return schema, raw_data

    @staticmethod
    def verify_artifacts_exist(artifact_dir: str, metadata: ModelMetadataSchema) -> Tuple[str, Optional[str]]:
        """
        Confirms estimator and preprocessor files exist in the artifact directory.
        Returns:
            (estimator_path, preprocessor_path_or_none)
        """
        est_path = os.path.join(artifact_dir, "estimator.joblib")
        prep_path = os.path.join(artifact_dir, "preprocessor.joblib")

        if not os.path.exists(est_path):
            raise ArtifactCorruptedError(f"Missing required estimator artifact at '{est_path}'")

        has_preprocessor = os.path.exists(prep_path)
        return est_path, prep_path if has_preprocessor else None
