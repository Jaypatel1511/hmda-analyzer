import re
import pytest
import pandas as pd
import requests as req
from unittest.mock import patch, MagicMock
from hmdaanalyzer.data.loader import load_sample, load_from_api
from hmdaanalyzer import CFPBAPIError


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
#
# The real network call lives in hmdaanalyzer._http.fetch (requests.get), so these
# patch "hmdaanalyzer._http.requests.get". That repoint from the old loader target
# is HARMLESS, not load-bearing: loader.requests, _http.requests, and the global
# requests are all the same module object, so patching either name's .get would
# have intercepted fetch()'s requests.get call either way.
#
# The real protection against a silent live call is the `assert mock_get.called`
# in every test below. Without it a test could pass vacuously if the mock ever
# stopped intercepting — e.g. test_load_from_api_limit_honored only checks
# len(df) <= 100, which a live 200 of <=100 rows would satisfy on its own.

OLD_WRONG_MESSAGE = "Check that year, state, and county values are valid."


def _fake_response(n_rows: int = 500):
    """Build a MagicMock response that streams n_rows of fake HMDA CSV (200 OK)."""
    header = "action_taken,derived_race,loan_amount,income,county_code,census_tract,state_code,lei,activity_year"
    rows = [header] + [
        f"1,White,225000,85,17031,17031{i:07d},17,LEI000001,2023"
        for i in range(n_rows)
    ]
    mock_r = MagicMock()
    mock_r.raise_for_status = MagicMock()        # 200 OK: no-op
    mock_r.iter_lines.return_value = iter(rows)
    mock_r.close = MagicMock()
    return mock_r


def _error_response(status_code: int, body: str):
    """Build a MagicMock response whose raise_for_status() raises an HTTPError."""
    mock_r = MagicMock()
    mock_r.status_code = status_code
    mock_r.text = body
    mock_r.raise_for_status.side_effect = req.HTTPError(response=mock_r)
    mock_r.close = MagicMock()
    return mock_r


def test_load_from_api_limit_honored():
    """load_from_api(limit=100) must return at most 100 rows regardless of API response size."""
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.return_value = _fake_response(500)
        df = load_from_api(year=2023, state="IL", limit=100)
    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    assert isinstance(df, pd.DataFrame)
    assert len(df) <= 100


def test_load_from_api_raises_on_timeout():
    """API timeout must raise RuntimeError, not silently return empty DataFrame.

    Timeout is NOT wrapped by fetch(); it propagates unwrapped to loader's handler.
    """
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = req.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            load_from_api(year=2023, state="IL")
    assert mock_get.called, "mock was never exercised — a live call may have escaped"


def test_load_from_api_sends_identifying_headers():
    """D-1: the outgoing request must carry the verified-passing CFPB header bundle.

    The UA regex is version-agnostic on purpose — __version__ derives from installed
    metadata, which can lag pyproject in a dev checkout; the token *shape* is what
    cleared the Akamai edge.
    """
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.return_value = _fake_response(10)
        load_from_api(year=2023, state="IL", limit=5)

    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    headers = mock_get.call_args.kwargs["headers"]
    assert re.match(
        r"^hmda-analyzer/\d+\.\d+\.\d+ \(\+https://github\.com/Jaypatel1511/",
        headers["User-Agent"],
    ), headers["User-Agent"]
    assert "text/csv" in headers["Accept"]
    assert headers["Accept-Language"] == "en-US,en;q=0.9"


def test_load_from_api_403_is_typed_edge_block():
    """D-2: a 403 must raise CFPBAPIError with honest edge-block guidance, NOT the
    old message that wrongly blamed the query's year/state/county values."""
    akamai_body = (
        "<HTML><HEAD>\n<TITLE>Access Denied</TITLE>\n</HEAD><BODY>\n"
        "<H1>Access Denied</H1>\nYou don't have permission to access this server.\n</BODY></HTML>"
    )
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.return_value = _error_response(403, akamai_body)
        # (b) back-compat: `except RuntimeError` must ALSO catch it.
        with pytest.raises(RuntimeError) as excinfo:
            load_from_api(year=2023, state="IL", county="17031", limit=100)

    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    err = excinfo.value
    assert isinstance(err, CFPBAPIError)          # (a)
    assert err.status_code == 403                 # (c)
    msg = str(err)
    assert "Akamai" in msg and "cloud" in msg.lower()   # (d) cloud/edge guidance present
    assert OLD_WRONG_MESSAGE not in msg                 # (d) old wrong string gone
    assert akamai_body[:30] in err.response_body        # (e) body surfaced


def test_load_from_api_400_surfaces_api_error_body():
    """D-3: a 400 must raise CFPBAPIError(status_code=400) and surface the API's
    structured errorType/message (folds in the old http-error test)."""
    api_body = '{"errorType":"invalid-year","message":"year 9999 is not available"}'
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.return_value = _error_response(400, api_body)
        with pytest.raises(CFPBAPIError) as excinfo:
            load_from_api(year=9999, state="IL", limit=100)

    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    err = excinfo.value
    assert err.status_code == 400
    surfaced = str(err) + (err.response_body or "")
    assert "invalid-year" in surfaced
    assert "year 9999 is not available" in surfaced
