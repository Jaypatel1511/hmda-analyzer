import pytest
import pandas as pd
from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, disparity_ratio,
    denial_rate_by_income_band, denial_reasons_by_race,
)
from hmdaanalyzer.data.loader import _clean


def test_denial_rate_by_race_returns_df(sample_df):
    result = denial_rate_by_race(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "denial_rate" in result.columns
    assert "derived_race" in result.columns


def test_denial_rate_by_race_values_valid(sample_df):
    result = denial_rate_by_race(sample_df)
    assert (result["denial_rate"] >= 0).all()
    assert (result["denial_rate"] <= 1).all()


def test_disparity_ratio_returns_df(sample_df):
    result = disparity_ratio(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "disparity_ratio" in result.columns
    assert "disparity_level" in result.columns


def test_disparity_ratio_white_is_reference(sample_df):
    result = disparity_ratio(sample_df, reference="White")
    white_row = result[result["derived_race"] == "White"]
    assert len(white_row) == 1
    assert abs(white_row["disparity_ratio"].iloc[0] - 1.0) < 0.01


def test_disparity_levels_valid(sample_df):
    result = disparity_ratio(sample_df)
    valid = {"HIGH", "MODERATE", "LOW", "FAVORABLE", "N/A"}
    assert set(result["disparity_level"].unique()).issubset(valid)


def test_black_disparity_high(sample_df):
    result = disparity_ratio(sample_df)
    black = result[result["derived_race"] == "Black or African American"]
    if len(black) > 0:
        assert black["disparity_ratio"].iloc[0] > 1.0


def test_denial_rate_by_income_band(sample_df):
    result = denial_rate_by_income_band(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "denial_rate" in result.columns
    assert len(result) > 0


def test_denial_reasons_by_race(sample_df):
    result = denial_reasons_by_race(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    expected_cols = {"derived_race", "denial_reason_label", "count", "total", "pct"}
    assert expected_cols.issubset(result.columns)
    assert "Unknown" not in set(result["denial_reason_label"].unique())


def test_denial_reasons_by_race_handles_cfpb_hyphenated_columns():
    """CFPB Data Browser CSV names denial reason fields with hyphens
    (e.g. ``denial_reason-1``). The loader's ``_clean()`` must normalize
    these to underscores so ``denial_reasons_by_race`` can find them; if not,
    every live-data call returns an empty DataFrame."""
    raw = pd.DataFrame(
        [
            {"action_taken": "3", "derived_race": "Black or African American", "denial_reason-1": "3"},
            {"action_taken": "3", "derived_race": "Black or African American", "denial_reason-1": "1"},
            {"action_taken": "3", "derived_race": "White",                     "denial_reason-1": "4"},
            {"action_taken": "3", "derived_race": "White",                     "denial_reason-1": "3"},
            {"action_taken": "1", "derived_race": "White",                     "denial_reason-1": "10"},
        ]
    )
    df = _clean(raw)
    result = denial_reasons_by_race(df)

    assert not result.empty, "denial_reasons_by_race returned empty for CFPB-style hyphenated input"
    expected_cols = {"derived_race", "denial_reason_label", "count", "total", "pct"}
    assert expected_cols.issubset(result.columns)
    labels = set(result["denial_reason_label"].unique())
    assert "Credit history" in labels
    assert "Unknown" not in labels
