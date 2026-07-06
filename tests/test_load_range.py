"""
Tests for the multi-year ``load_range`` (0.4.0).

Design of these tests (mirrors the 0.3.1 lessons in test_loader.py):

  * They are THROUGH-FUNCTION: they call ``load_range`` end-to-end and mock the
    network at ``hmdaanalyzer._http.requests.get`` (the single real network call),
    so the real per-year fetch → clean → schema-guard → concat path is exercised.
  * A per-year ``side_effect`` dispatches on the ``years`` query param, so each
    year in the range can return a distinct payload (or fail) independently.
  * EVERY network-mocking test asserts ``mock_get.called`` — the 0.3.1
    vacuous-pass guard: without it a test could pass while a live call escaped.

The raw header below is the exact 99-column CFPB Data Browser CSV header captured
from a live 2023 probe (residential Mac). ``load_from_api`` normalizes it (hyphens
→ underscores, adds ``is_approved``/``is_denied``) to the 101-column cleaned frame
that ``load_range`` validates and concatenates.
"""
import re
import pytest
import pandas as pd
import requests as req
from unittest.mock import patch, MagicMock

from hmdaanalyzer import (
    load_range, CFPBAPIError, SchemaValidationError, ActivityYearMismatchError,
)


# Exact live CFPB header (99 columns, 2018–2025 identical — empirically verified).
RAW_HEADER = (
    "activity_year,lei,derived_msa-md,state_code,county_code,census_tract,"
    "conforming_loan_limit,derived_loan_product_type,derived_dwelling_category,"
    "derived_ethnicity,derived_race,derived_sex,action_taken,purchaser_type,"
    "preapproval,loan_type,loan_purpose,lien_status,reverse_mortgage,"
    "open-end_line_of_credit,business_or_commercial_purpose,loan_amount,"
    "loan_to_value_ratio,interest_rate,rate_spread,hoepa_status,total_loan_costs,"
    "total_points_and_fees,origination_charges,discount_points,lender_credits,"
    "loan_term,prepayment_penalty_term,intro_rate_period,negative_amortization,"
    "interest_only_payment,balloon_payment,other_nonamortizing_features,"
    "property_value,construction_method,occupancy_type,"
    "manufactured_home_secured_property_type,"
    "manufactured_home_land_property_interest,total_units,"
    "multifamily_affordable_units,income,debt_to_income_ratio,"
    "applicant_credit_score_type,co-applicant_credit_score_type,"
    "applicant_ethnicity-1,applicant_ethnicity-2,applicant_ethnicity-3,"
    "applicant_ethnicity-4,applicant_ethnicity-5,co-applicant_ethnicity-1,"
    "co-applicant_ethnicity-2,co-applicant_ethnicity-3,co-applicant_ethnicity-4,"
    "co-applicant_ethnicity-5,applicant_ethnicity_observed,"
    "co-applicant_ethnicity_observed,applicant_race-1,applicant_race-2,"
    "applicant_race-3,applicant_race-4,applicant_race-5,co-applicant_race-1,"
    "co-applicant_race-2,co-applicant_race-3,co-applicant_race-4,"
    "co-applicant_race-5,applicant_race_observed,co-applicant_race_observed,"
    "applicant_sex,co-applicant_sex,applicant_sex_observed,"
    "co-applicant_sex_observed,applicant_age,co-applicant_age,"
    "applicant_age_above_62,co-applicant_age_above_62,submission_of_application,"
    "initially_payable_to_institution,aus-1,aus-2,aus-3,aus-4,aus-5,"
    "denial_reason-1,denial_reason-2,denial_reason-3,denial_reason-4,"
    "tract_population,tract_minority_population_percent,"
    "ffiec_msa_md_median_family_income,tract_to_msa_income_percentage,"
    "tract_owner_occupied_units,tract_one_to_four_family_homes,"
    "tract_median_age_of_housing_units"
)


def _csv_lines(year, n_rows=3, *, extra_cols=(), drop_cols=(), year_value=None):
    """Build fake CSV lines for one year: full header, optionally mutated.

    ``year_value`` overrides the value written into the ``activity_year`` column
    (defaults to ``year``) so a wrong-year payload can be simulated.
    """
    cols = [c for c in RAW_HEADER.split(",") if c not in drop_cols] + list(extra_cols)
    av = str(year if year_value is None else year_value)
    lines = [",".join(cols)]
    for _ in range(n_rows):
        row = []
        for c in cols:
            if c == "activity_year":
                row.append(av)
            elif c == "action_taken":
                row.append("1")
            elif c in ("loan_amount", "income"):
                row.append("100")
            else:
                row.append("x")
        lines.append(",".join(row))
    return lines


def _ok_response(lines):
    mock_r = MagicMock()
    mock_r.raise_for_status = MagicMock()          # 200 OK: no-op
    mock_r.iter_lines.return_value = iter(lines)
    mock_r.close = MagicMock()
    return mock_r


def _error_response(status_code, body):
    mock_r = MagicMock()
    mock_r.status_code = status_code
    mock_r.text = body
    mock_r.raise_for_status.side_effect = req.HTTPError(response=mock_r)
    mock_r.close = MagicMock()
    return mock_r


def _dispatcher(per_year):
    """Return a requests.get side_effect that dispatches on the ``years`` param.

    ``per_year`` maps int year -> callable() returning a mock response
    (or raising). ``load_from_api`` sends ``years`` as the single requested year.
    """
    def _get(url, params=None, **kwargs):
        y = int(str(params["years"]).split(",")[0])
        return per_year[y]()
    return _get


# ── Import surface ─────────────────────────────────────────────────────────────

def test_load_range_importable_both_aliases():
    from hmdaanalyzer import load_range as lr1
    from hmda_analyzer import load_range as lr2
    assert lr1 is lr2


# ── Happy path: concat + native provenance ─────────────────────────────────────

def test_load_range_concats_years_with_correct_provenance():
    per_year = {
        2019: lambda: _ok_response(_csv_lines(2019, n_rows=2)),
        2020: lambda: _ok_response(_csv_lines(2020, n_rows=3)),
        2021: lambda: _ok_response(_csv_lines(2021, n_rows=4)),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        df = load_range(2019, 2021, state="MA", county="25019", limit=1000)

    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2 + 3 + 4
    assert "activity_year" in df.columns
    counts = df["activity_year"].value_counts().to_dict()
    assert counts == {"2019": 2, "2020": 3, "2021": 4}
    # index reset after concat
    assert list(df.index) == list(range(9))


def test_load_range_single_year_range_works():
    per_year = {2022: lambda: _ok_response(_csv_lines(2022, n_rows=5))}
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        df = load_range(2022, 2022, state="MA")
    assert mock_get.called
    assert len(df) == 5
    assert set(df["activity_year"]) == {"2022"}


def test_load_range_forwards_filters_to_each_year():
    calls = []

    def _get(url, params=None, **kwargs):
        calls.append(dict(params))
        y = int(str(params["years"]).split(",")[0])
        return _ok_response(_csv_lines(y, n_rows=1))

    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _get
        load_range(2019, 2021, state="il", county="17031", lei="LEI000001", limit=500)

    assert mock_get.called
    years_seen = sorted(int(str(c["years"]).split(",")[0]) for c in calls)
    assert years_seen == [2019, 2020, 2021]
    for c in calls:
        assert c["states"] == "IL"          # forwarded + upper-cased identically
        assert c["counties"] == "17031"
        assert c["leis"] == "LEI000001"


# ── FAIL-LOUD, no partial ──────────────────────────────────────────────────────

def test_load_range_fail_loud_names_failing_year_no_partial():
    """Year 2020 in [2019, 2021] fails; load_range must raise, name 2020, and
    return NO frame (no partial leak)."""
    per_year = {
        2019: lambda: _ok_response(_csv_lines(2019, n_rows=2)),
        2020: lambda: _error_response(403, "<TITLE>Access Denied</TITLE>"),
        2021: lambda: _ok_response(_csv_lines(2021, n_rows=2)),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        with pytest.raises(CFPBAPIError) as excinfo:
            load_range(2019, 2021, state="MA")

    assert mock_get.called, "mock was never exercised — a live call may have escaped"
    msg = str(excinfo.value)
    assert "2020" in msg                                  # names the failing year
    assert excinfo.value.status_code == 403               # typed info preserved
    # back-compat: a plain `except RuntimeError` also catches it
    assert isinstance(excinfo.value, RuntimeError)


# ── Schema guard bites ─────────────────────────────────────────────────────────

def test_load_range_schema_guard_unexpected_column_raises():
    per_year = {
        2019: lambda: _ok_response(_csv_lines(2019, n_rows=2)),
        2020: lambda: _ok_response(_csv_lines(2020, n_rows=2, extra_cols=("surprise_new_field",))),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        with pytest.raises(SchemaValidationError) as excinfo:
            load_range(2019, 2020, state="MA")
    assert mock_get.called
    msg = str(excinfo.value)
    assert "2020" in msg
    assert "surprise_new_field" in msg


def test_load_range_schema_guard_missing_column_raises():
    per_year = {
        2019: lambda: _ok_response(_csv_lines(2019, n_rows=2, drop_cols=("income",))),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        with pytest.raises(SchemaValidationError) as excinfo:
            load_range(2019, 2019, state="MA")
    assert mock_get.called
    msg = str(excinfo.value)
    assert "2019" in msg
    assert "income" in msg


# ── Provenance: wrong-year payload caught ──────────────────────────────────────

def test_load_range_wrong_year_payload_raises():
    """Request 2020 but the API returns 2019 rows → ActivityYearMismatchError."""
    per_year = {
        2020: lambda: _ok_response(_csv_lines(2020, n_rows=3, year_value=2019)),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        with pytest.raises(ActivityYearMismatchError) as excinfo:
            load_range(2020, 2020, state="MA")
    assert mock_get.called
    msg = str(excinfo.value)
    assert "2020" in msg and "2019" in msg


# ── Legitimate-empty year is included, not raised ──────────────────────────────

def test_load_range_legitimate_empty_year_included():
    """A valid year returning zero rows (header only) is legitimate: it joins the
    concat as an empty, correctly-columned frame — NOT a fetch failure."""
    per_year = {
        2019: lambda: _ok_response(_csv_lines(2019, n_rows=3)),
        2020: lambda: _ok_response(_csv_lines(2020, n_rows=0)),   # header only, 0 rows
        2021: lambda: _ok_response(_csv_lines(2021, n_rows=2)),
    }
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        mock_get.side_effect = _dispatcher(per_year)
        df = load_range(2019, 2021, state="MA")
    assert mock_get.called
    assert len(df) == 3 + 0 + 2
    # 2020 contributed no rows but did not raise
    assert df["activity_year"].value_counts().to_dict() == {"2019": 3, "2021": 2}


# ── Year validation ────────────────────────────────────────────────────────────

def test_load_range_rejects_year_below_2018():
    with pytest.raises(ValueError, match="2018"):
        load_range(2017, 2019)


def test_load_range_rejects_start_after_end():
    with pytest.raises(ValueError):
        load_range(2021, 2019)


def test_load_range_rejects_out_of_range_high():
    with pytest.raises(ValueError):
        load_range(2018, 9999)


@pytest.mark.parametrize("bad", [2019.0, "2019", True])
def test_load_range_rejects_non_int_year(bad):
    with pytest.raises(TypeError):
        load_range(bad, 2020)
    with pytest.raises(TypeError):
        load_range(2019, bad)


def test_load_range_year_validation_happens_before_any_fetch():
    """A bad range must never touch the network."""
    with patch("hmdaanalyzer._http.requests.get") as mock_get:
        with pytest.raises((ValueError, TypeError)):
            load_range(2017, 2016)
    assert not mock_get.called
