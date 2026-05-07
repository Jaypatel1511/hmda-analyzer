import pytest
import pandas as pd
from hmdaanalyzer.data.loader import load_sample


def test_load_sample_returns_dataframe():
    df = load_sample(n=100)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 100


def test_load_sample_has_required_columns():
    df = load_sample(n=100)
    required = ["action_taken", "derived_race", "loan_amount",
                "income", "is_denied", "is_approved"]
    for col in required:
        assert col in df.columns


def test_load_sample_action_taken_valid():
    df = load_sample(n=500)
    valid = {1, 2, 3, 4, 5}
    assert df["action_taken"].dropna().isin(valid).all()


def test_load_sample_is_denied_bool():
    df = load_sample(n=500)
    assert str(df["is_denied"].dtype) in ("bool", "boolean")


def test_load_sample_denial_rate_realistic():
    df = load_sample(n=2000)
    actionable = df[df["action_taken"].isin([1, 2, 3])]
    overall_denial_rate = actionable["is_denied"].mean()
    assert 0.05 < overall_denial_rate < 0.35


def test_load_sample_race_disparity():
    df = load_sample(n=3000)
    actionable = df[df["action_taken"].isin([1, 2, 3])]
    black = actionable[actionable["derived_race"] == "Black or African American"]
    white = actionable[actionable["derived_race"] == "White"]
    assert black["is_denied"].mean() > white["is_denied"].mean()
