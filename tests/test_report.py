import pytest
import pandas as pd
from hmdaanalyzer.report.generator import generate_disparity_report, summary_table


def test_generate_report_returns_string(sample_df):
    report = generate_disparity_report(sample_df)
    assert isinstance(report, str)
    assert len(report) > 100


def test_report_contains_sections(sample_df):
    report = generate_disparity_report(sample_df)
    assert "Denial Rate by Race" in report
    assert "Disparity Ratios" in report
    assert "Income Band" in report


def test_report_contains_black_disparity(sample_df):
    report = generate_disparity_report(sample_df)
    assert "Black or African American" in report


def test_summary_table_returns_df(sample_df):
    df = summary_table(sample_df)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
