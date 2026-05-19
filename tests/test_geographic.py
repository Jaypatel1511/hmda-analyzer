import pytest
import pandas as pd
from hmdaanalyzer.analysis.geographic import (
    lending_by_tract, lending_by_county, lending_by_state,
    lending_desert_score,
)


def test_lending_by_tract_returns_df(sample_df):
    result = lending_by_tract(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "denial_rate" in result.columns
    assert "census_tract" in result.columns


def test_lending_by_county_returns_df(sample_df):
    result = lending_by_county(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "denial_rate" in result.columns


def test_lending_by_state_returns_df(sample_df):
    result = lending_by_state(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0


def test_lending_desert_score_returns_df(sample_df):
    result = lending_desert_score(sample_df)
    assert isinstance(result, pd.DataFrame)
    assert "desert_score" in result.columns
    assert "is_lending_desert" in result.columns


def test_denial_rates_between_0_and_1(sample_df):
    result = lending_by_tract(sample_df)
    assert (result["denial_rate"] >= 0).all()
    assert (result["denial_rate"] <= 1).all()


def test_lending_desert_score_correctness(sample_df):
    result = lending_desert_score(sample_df)
    # Required columns
    assert "desert_score" in result.columns
    assert "is_lending_desert" in result.columns
    assert "app_percentile" in result.columns
    # desert_score is non-negative
    assert (result["desert_score"] >= 0).all()
    # app_percentile is between 0 and 100
    assert (result["app_percentile"] >= 0).all()
    assert (result["app_percentile"] <= 100).all()
    # Sorted descending by desert_score
    scores = result["desert_score"].tolist()
    assert scores == sorted(scores, reverse=True)
    # Tracts flagged as desert have low application percentile and elevated denial rate
    deserts = result[result["is_lending_desert"]]
    if not deserts.empty:
        assert (deserts["app_percentile"] < 25).all()
        assert (deserts["denial_rate"] > 0.15).all()
