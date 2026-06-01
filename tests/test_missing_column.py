"""
Contract tests for MissingColumnError.

A missing required column is a *schema problem* and must raise — never return a
silent empty result that could read as "no disparity" in a fair-lending context.
A well-formed query that simply matches no rows still returns an empty result.

These are through-function tests against real ``load_sample()`` data (no mocks).
Each negative case takes an intact sample DataFrame and drops/renames exactly the
required column, then asserts ``MissingColumnError`` is raised and that its message
names the missing column.
"""
import pytest
import pandas as pd

from hmdaanalyzer import MissingColumnError
from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, denial_reasons_by_race,
)
from hmdaanalyzer.analysis.geographic import (
    lending_by_tract, lending_by_county, lending_by_state,
    racial_composition_by_tract,
)
from hmdaanalyzer.analysis.lender import (
    lender_summary, top_lenders_by_volume, lender_vs_market,
)
from hmdaanalyzer.report.generator import generate_disparity_report


# --------------------------------------------------------------------------- #
# Negative cases — missing required column must raise MissingColumnError.
# --------------------------------------------------------------------------- #

def test_lending_by_tract_missing_census_tract_raises(sample_df):
    df = sample_df.drop(columns=["census_tract"])
    with pytest.raises(MissingColumnError, match="census_tract"):
        lending_by_tract(df)


def test_lending_by_county_missing_county_code_raises(sample_df):
    df = sample_df.drop(columns=["county_code"])
    with pytest.raises(MissingColumnError, match="county_code"):
        lending_by_county(df)


def test_lending_by_state_missing_state_code_raises(sample_df):
    df = sample_df.drop(columns=["state_code"])
    with pytest.raises(MissingColumnError, match="state_code"):
        lending_by_state(df)


def test_racial_composition_missing_derived_race_raises(sample_df):
    df = sample_df.drop(columns=["derived_race"])
    with pytest.raises(MissingColumnError, match="derived_race"):
        racial_composition_by_tract(df)


def test_racial_composition_missing_census_tract_raises(sample_df):
    df = sample_df.drop(columns=["census_tract"])
    with pytest.raises(MissingColumnError, match="census_tract"):
        racial_composition_by_tract(df)


def test_denial_rate_by_race_missing_derived_race_raises(sample_df):
    df = sample_df.drop(columns=["derived_race"])
    with pytest.raises(MissingColumnError, match="derived_race"):
        denial_rate_by_race(df)


def test_denial_rate_by_race_missing_is_denied_raises(sample_df):
    df = sample_df.drop(columns=["is_denied"])
    with pytest.raises(MissingColumnError, match="is_denied"):
        denial_rate_by_race(df)


def test_denial_reasons_by_race_missing_reason_col_raises(sample_df):
    df = sample_df.drop(columns=["denial_reason_1"])
    with pytest.raises(MissingColumnError, match="denial_reason_1"):
        denial_reasons_by_race(df)


def test_top_lenders_missing_lei_raises(sample_df):
    df = sample_df.drop(columns=["lei"])
    with pytest.raises(MissingColumnError, match="lei"):
        top_lenders_by_volume(df)


# --------------------------------------------------------------------------- #
# Negative cases — silent filter-skip: an argument is passed but the column it
# filters on is absent. Previously the filter was silently ignored (a silently
# wrong answer); now it must raise.
# --------------------------------------------------------------------------- #

def test_lender_summary_lei_passed_without_lei_column_raises(sample_df):
    df = sample_df.drop(columns=["lei"])
    with pytest.raises(MissingColumnError, match="lei"):
        lender_summary(df, lei="LEI000001")


def test_top_lenders_state_passed_without_state_column_raises(sample_df):
    df = sample_df.drop(columns=["state_code"])
    with pytest.raises(MissingColumnError, match="state_code"):
        top_lenders_by_volume(df, state="17")


def test_generate_report_lei_passed_without_lei_column_raises(sample_df):
    df = sample_df.drop(columns=["lei"])
    with pytest.raises(MissingColumnError, match="lei"):
        generate_disparity_report(df, lei="LEI000001")


# --------------------------------------------------------------------------- #
# Positive regression — intact data still produces non-empty happy-path results.
# --------------------------------------------------------------------------- #

def test_lending_by_tract_happy_path(sample_df):
    assert not lending_by_tract(sample_df).empty


def test_lending_by_county_happy_path(sample_df):
    assert not lending_by_county(sample_df).empty


def test_lending_by_state_happy_path(sample_df):
    assert not lending_by_state(sample_df).empty


def test_racial_composition_happy_path(sample_df):
    assert not racial_composition_by_tract(sample_df).empty


def test_denial_rate_by_race_happy_path(sample_df):
    assert not denial_rate_by_race(sample_df).empty


def test_denial_reasons_by_race_happy_path(sample_df):
    assert not denial_reasons_by_race(sample_df).empty


def test_top_lenders_happy_path(sample_df):
    assert not top_lenders_by_volume(sample_df).empty


def test_lender_summary_happy_path_with_lei(sample_df):
    lei = sample_df["lei"].iloc[0]
    result = lender_summary(sample_df, lei=lei)
    assert result  # non-empty dict
    assert result["total_applications"] > 0


def test_top_lenders_happy_path_with_state(sample_df):
    state = sample_df["state_code"].iloc[0]
    assert not top_lenders_by_volume(sample_df, state=state).empty


def test_generate_report_happy_path_with_lei(sample_df):
    lei = sample_df["lei"].iloc[0]
    report = generate_disparity_report(sample_df, lei=lei)
    assert f"Lender: {lei}" in report


# --------------------------------------------------------------------------- #
# (B) legitimate empty results — valid schema, zero matching rows: still empty.
# --------------------------------------------------------------------------- #

def test_lender_summary_no_matching_lei_returns_empty_dict(sample_df):
    # Schema is intact; the lei just matches no rows -> legitimate empty, no raise.
    assert lender_summary(sample_df, lei="LEI_DOES_NOT_EXIST") == {}


# --------------------------------------------------------------------------- #
# Backward compatibility — MissingColumnError is a ValueError.
# --------------------------------------------------------------------------- #

def test_missing_column_error_is_valueerror():
    assert isinstance(MissingColumnError("x"), ValueError)
    assert issubclass(MissingColumnError, ValueError)


def test_except_valueerror_still_catches(sample_df):
    df = sample_df.drop(columns=["state_code"])
    try:
        lending_by_state(df)
        raised = False
    except ValueError:
        raised = True
    assert raised


# --------------------------------------------------------------------------- #
# Audit must-fix HIGH-1 — lender_vs_market silent filter-skip.
# Given a lei but no 'lei' column, 0.2.1 silently computed whole-market-vs-itself
# (all-zero vs_market = "no disparity"). Now it must raise.
# --------------------------------------------------------------------------- #

def test_lender_vs_market_missing_lei_column_raises(sample_df):
    df = sample_df.drop(columns=["lei"])
    with pytest.raises(MissingColumnError, match="lei"):
        lender_vs_market(df, lei="LEI000001")


def test_lender_vs_market_happy_path_non_empty(sample_df):
    lei = sample_df["lei"].iloc[0]
    result = lender_vs_market(sample_df, lei=lei)
    assert not result.empty
    assert "vs_market" in result.columns
    # A real lender-vs-market comparison is not identically zero (that was the
    # silent whole-market-vs-itself bug).
    assert not (result["vs_market"] == 0).all()


# --------------------------------------------------------------------------- #
# Audit must-fix HIGH-2 — generate_disparity_report swallowed MissingColumnError
# into a table cell. A missing schema column must raise up front, not render a
# misleading "no disparity" report.
# --------------------------------------------------------------------------- #

def test_generate_report_missing_derived_race_raises(sample_df):
    df = sample_df.drop(columns=["derived_race"])
    with pytest.raises(MissingColumnError, match="derived_race"):
        generate_disparity_report(df)


def test_generate_report_missing_column_does_not_render_error_cell(sample_df):
    df = sample_df.drop(columns=["derived_race"])
    try:
        report = generate_disparity_report(df)
    except MissingColumnError:
        return  # raised up front — correct
    # If it somehow returned a string, it must NOT have swallowed the error.
    assert "Error computing" not in report
    assert "| Error:" not in report
    raise AssertionError("expected MissingColumnError, got a rendered report")


def test_generate_report_happy_path_has_key_findings(sample_df):
    report = generate_disparity_report(sample_df)
    assert "## Key Findings" in report
    assert "High Disparity Groups" in report
    assert "Error computing" not in report
    assert "| Error:" not in report


# --------------------------------------------------------------------------- #
# Audit must-fix MED-1 — generate_disparity_report on a zero-match LEI (including
# lei="") must return a clean no-records report, never IndexError.
# --------------------------------------------------------------------------- #

def test_generate_report_unknown_lei_returns_no_records_report(sample_df):
    report = generate_disparity_report(sample_df, lei="ZZZZNOTREAL")
    assert "No records found" in report
    assert "**Total Records:** 0" in report


def test_generate_report_empty_string_lei_returns_no_records_report(sample_df):
    # lei="" is a real empty-matching filter value (not "all lenders"); it must
    # produce a clean no-records report, not an IndexError.
    report = generate_disparity_report(sample_df, lei="")
    assert "No records found" in report
    assert "**Total Records:** 0" in report


def test_generate_report_real_lei_returns_scoped_report(sample_df):
    lei = sample_df["lei"].iloc[0]
    report = generate_disparity_report(sample_df, lei=lei)
    assert f"Lender: {lei}" in report
    assert "No records found" not in report
