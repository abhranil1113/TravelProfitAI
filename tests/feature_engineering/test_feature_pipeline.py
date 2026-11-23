"""
Tests for Master Feature Engineering Pipeline Runner & Report Generation Module
"""

import pytest
from feature_engineering.feature_pipeline import run_full_feature_pipeline
from feature_engineering.config import REPORTS_DIR


def test_run_full_feature_pipeline():
    result = run_full_feature_pipeline()
    assert result["status"] == "COMPLETED"
    assert result["feature_datasets_count"] == 8
    assert result["total_features_engineered"] > 100
    assert result["validations_passed"] == 7

    expected_reports = [
        "feature_dictionary.csv",
        "feature_metadata.json",
        "feature_generation_summary.json",
        "leakage_audit.md",
        "data_transformation_report.md",
        "feature_validation_report.md",
        "modeling_readiness_after_features.md",
        "dataset_split_manifest.json",
    ]

    for rep in expected_reports:
        rep_p = REPORTS_DIR / rep
        assert rep_p.exists(), f"Missing report: {rep_p}"
        assert rep_p.stat().st_size > 0
