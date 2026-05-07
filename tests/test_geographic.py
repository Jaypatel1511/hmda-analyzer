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
