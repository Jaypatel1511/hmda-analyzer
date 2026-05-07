import pytest
import pandas as pd
from hmdaanalyzer.analysis.lender import (
    lender_summary, lender_vs_market, top_lenders_by_volume,
)


def test_lender_summary_returns_dict(sample_df):
    result = lender_summary(sample_df)
    assert isinstance(result, dict)
    assert "total_applications" in result
    assert "denial_rate" in result


def test_lender_summary_denial_rate_valid(sample_df):
    result = lender_summary(sample_df)
    assert 0 <= result["denial_rate"] <= 100


def test_lender_vs_market_returns_df(sample_df):
    lei = sample_df["lei"].iloc[0]
    result = lender_vs_market(sample_df, lei)
    assert isinstance(result, pd.DataFrame)
    assert "lender_denial_rate" in result.columns
    assert "market_denial_rate" in result.columns


def test_top_lenders_by_volume_returns_df(sample_df):
    result = top_lenders_by_volume(sample_df, n=5)
    assert isinstance(result, pd.DataFrame)
    assert len(result) <= 5


def test_top_lenders_sorted_by_volume(sample_df):
    result = top_lenders_by_volume(sample_df, n=10)
    if len(result) > 1:
        assert result["originations"].iloc[0] >= result["originations"].iloc[1]
