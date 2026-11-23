"""
Tests for Date & Calendar Feature Extraction Module
"""

import pytest
import pandas as pd
from feature_engineering.date_features import extract_calendar_features


def test_extract_calendar_features():
    df = pd.DataFrame({
        "event_date": ["2026-07-04", "2026-12-25", "2026-01-01"],  # Sat (July, peak), Fri (Dec, peak), Thu (Jan, off-peak)
    })
    feats = extract_calendar_features(df, "event_date", prefix="event_")
    assert len(feats) == 3
    assert "event_year" in feats.columns
    assert "event_month" in feats.columns
    assert "event_is_weekend" in feats.columns
    assert "event_is_peak_season" in feats.columns

    # 2026-07-04 is Saturday
    assert feats.loc[0, "event_day_of_week"] == 5
    assert feats.loc[0, "event_is_weekend"] == True
    assert feats.loc[0, "event_is_peak_season"] == True

    # 2026-01-01 is Thursday
    assert feats.loc[2, "event_day_of_week"] == 3
    assert feats.loc[2, "event_is_weekend"] == False
    assert feats.loc[2, "event_is_peak_season"] == False


def test_extract_calendar_features_invalid_col():
    df = pd.DataFrame({"dummy": [1, 2]})
    with pytest.raises(ValueError, match="not found"):
        extract_calendar_features(df, "missing_col")
