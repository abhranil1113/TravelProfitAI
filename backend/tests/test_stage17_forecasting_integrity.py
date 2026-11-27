import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from backend.app.models.schema import MLModel, MLModelType
from backend.app.services.forecasting_service import _snapshot_velocity
from optimization.predictions.model_registry import ModelRegistry


class StubEstimator:
    def __init__(self, artifact_name: str):
        self.artifact_name = artifact_name


def test_model_registry_cache_tracks_champion_artifact_and_provenance(
    db, tmp_path, monkeypatch, request
):
    artifact_a = tmp_path / "inventory-a"
    artifact_b = tmp_path / "inventory-b"
    artifact_a.mkdir()
    artifact_b.mkdir()
    for artifact_dir, name in ((artifact_a, "lightgbm"), (artifact_b, "xgboost")):
        (artifact_dir / "metadata.json").write_text(
            json.dumps({
                "task_name": "inventory_forecasting",
                "model_name": name,
                "target_column": "future_available_quantity",
                "feature_names": ["available_quantity"],
            }),
            encoding="utf-8",
        )
        (artifact_dir / "estimator.joblib").write_bytes(name.encode("ascii"))

    model_a = MLModel(
        model_type=MLModelType.INVENTORY_FORECASTING,
        version="a1",
        algorithm="lightgbm",
        artifact_dir=str(artifact_a),
        metrics_json={},
        training_cutoff_date=date(2026, 1, 1),
        is_champion=True,
    )
    model_b = MLModel(
        model_type=MLModelType.INVENTORY_FORECASTING,
        version="b2",
        algorithm="xgboost",
        artifact_dir=str(artifact_b),
        metrics_json={},
        training_cutoff_date=date(2026, 1, 2),
        is_champion=False,
    )
    db.add_all([model_a, model_b])
    db.commit()

    loaded = []

    def load_artifact(path):
        artifact = StubEstimator(Path(path).parent.name)
        loaded.append(artifact)
        return artifact

    monkeypatch.setattr("optimization.predictions.model_registry.joblib.load", load_artifact)
    ModelRegistry.invalidate_cache("inventory_forecasting")
    request.addfinalizer(lambda: ModelRegistry.invalidate_cache("inventory_forecasting"))
    registry = ModelRegistry(db=db)
    first_estimator, _, first_metadata = registry.get_model("inventory_forecasting")
    assert first_estimator.artifact_name == "inventory-a"
    assert first_metadata["_registry_model_name"] == "lightgbm"
    assert first_metadata["_registry_model_version"] == "a1"
    assert first_metadata["_artifact_dir"] == str(artifact_a)

    model_a.is_champion = False
    db.flush()
    model_b.is_champion = True
    db.commit()

    second_estimator, _, second_metadata = registry.get_model("inventory_forecasting")
    assert second_estimator.artifact_name == "inventory-b"
    assert second_metadata["_registry_model_name"] == "xgboost"
    assert second_metadata["_registry_model_version"] == "b2"
    assert second_metadata["_artifact_dir"] == str(artifact_b)
    assert second_metadata["model_name"] == second_metadata["_registry_model_name"]
    assert registry.get_model("inventory_forecasting")[0] is second_estimator
    assert len(loaded) == 2

    ModelRegistry.invalidate_cache("inventory_forecasting")
    refreshed_estimator, _, refreshed_metadata = registry.get_model("inventory_forecasting")
    assert refreshed_estimator.artifact_name == "inventory-b"
    assert refreshed_metadata["_registry_model_version"] == "b2"
    assert len(loaded) == 3


def test_snapshot_velocity_matches_training_units_and_rejects_inconsistent_data():
    previous = type("Snapshot", (), {
        "snapshot_at": datetime(2026, 11, 25, 16, tzinfo=timezone.utc),
        "total_units": 100,
        "available_units": 70,
        "booked_units": 30,
    })()
    current = type("Snapshot", (), {
        "snapshot_at": datetime(2026, 11, 26, 16, tzinfo=timezone.utc),
        "total_units": 100,
        "available_units": 60,
        "booked_units": 40,
    })()

    elapsed, booked_change, available_change, depletion = _snapshot_velocity(current, previous)
    assert elapsed == pytest.approx(1.0)
    assert booked_change == 10.0
    assert available_change == -10.0
    assert booked_change / elapsed == pytest.approx(10.0)
    assert depletion == pytest.approx(10.0)

    current.snapshot_at = previous.snapshot_at
    elapsed, booked_change, available_change, depletion = _snapshot_velocity(current, previous)
    assert elapsed == 0.0
    assert booked_change == 10.0
    assert available_change == -10.0
    assert depletion == 0.0

    current.snapshot_at = datetime(2026, 11, 26, 16, tzinfo=timezone.utc)
    current.total_units = 99
    with pytest.raises(ValueError, match="inconsistent capacity"):
        _snapshot_velocity(current, previous)
