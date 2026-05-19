import pytest
import pandas as pd
import requests as req
from unittest.mock import patch, MagicMock
from hmdaanalyzer.data.loader import load_sample, load_from_api


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


def test_load_sample_loan_amount_dollar_scale():
    """loan_amount must be in dollars (consistent with live CFPB API), not thousands."""
    df = load_sample(n=500)
    originated = df[df["action_taken"] == 1]
    median_loan = originated["loan_amount"].median()
    # Real CFPB mortgages are $50K–$2M; thousands-scale would give 50–2000
    assert median_loan > 50_000, f"loan_amount looks like thousands, not dollars: median={median_loan}"


def test_load_sample_includes_real_cfpb_race_categories():
    """Sample data must include race categories that appear in live CFPB data."""
    df = load_sample(n=5000)
    races = set(df["derived_race"].unique())
    assert "2 or more minority races" in races
    assert "Race Not Available" in races
    assert "Joint" in races


# ── load_from_api tests (mocked) ───────────────────────────────────────────────

def _fake_response(n_rows: int = 500):
    """Build a MagicMock response that streams n_rows of fake HMDA CSV."""
    header = "action_taken,derived_race,loan_amount,income,county_code,census_tract,state_code,lei,activity_year"
    rows = [header] + [
        f"1,White,225000,85,17031,17031{i:07d},17,LEI000001,2023"
        for i in range(n_rows)
    ]
    mock_r = MagicMock()
    mock_r.raise_for_status = MagicMock()
    mock_r.iter_lines.return_value = iter(rows)
    mock_r.close = MagicMock()
    return mock_r


def test_load_from_api_limit_honored():
    """load_from_api(limit=100) must return at most 100 rows regardless of API response size."""
    with patch("hmdaanalyzer.data.loader.requests.get") as mock_get:
        mock_get.return_value = _fake_response(500)
        df = load_from_api(year=2023, state="IL", limit=100)
    assert isinstance(df, pd.DataFrame)
    assert len(df) <= 100


def test_load_from_api_raises_on_timeout():
    """API timeout must raise RuntimeError, not silently return empty DataFrame."""
    with patch("hmdaanalyzer.data.loader.requests.get") as mock_get:
        mock_get.side_effect = req.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            load_from_api(year=2023, state="IL")


def test_load_from_api_raises_on_http_error():
    """HTTP error from API must raise RuntimeError with status code in message."""
    with patch("hmdaanalyzer.data.loader.requests.get") as mock_get:
        mock_r = MagicMock()
        mock_r.status_code = 400
        http_err = req.HTTPError(response=mock_r)
        mock_r.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_r
        with pytest.raises(RuntimeError, match="HTTP 400"):
            load_from_api(year=9999, state="IL")
