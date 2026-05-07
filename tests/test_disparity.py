import pytest
import pandas as pd
from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, disparity_ratio,
    denial_rate_by_income_band, denial_reasons_by_race,
)


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
