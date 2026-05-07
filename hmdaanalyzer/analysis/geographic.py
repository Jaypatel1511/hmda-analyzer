"""
Geographic analysis of HMDA lending patterns.
Identifies lending deserts and maps activity by census tract.
"""
import pandas as pd
import numpy as np


def lending_by_tract(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate HMDA lending activity by census tract.

    Returns:
        DataFrame with application counts, denial rates, and loan volumes by tract
    """
    if "census_tract" not in df.columns:
        raise ValueError("DataFrame must have 'census_tract' column")

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby("census_tract").agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
        originations=("is_approved", "sum"),
        avg_loan_amount=("loan_amount", "mean"),
        median_income=("income", "median"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    result["origination_rate"] = result["originations"] / result["applications"]

    return result.sort_values("applications", ascending=False)


def lending_by_county(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate HMDA lending activity by county.
    """
    if "county_code" not in df.columns:
        raise ValueError("DataFrame must have 'county_code' column")

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby("county_code").agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
        originations=("is_approved", "sum"),
        total_loan_volume=("loan_amount", "sum"),
        avg_loan_amount=("loan_amount", "mean"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    result["state_code"] = result["county_code"].str[:2]

    return result.sort_values("applications", ascending=False)


def lending_desert_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify census tracts with abnormally low application volumes.
    A 'lending desert' is a tract with very few mortgage applications
    relative to its expected volume based on housing units.

    Returns:
        DataFrame with lending desert scores by census tract
    """
    tract_df = lending_by_tract(df)

    # Percentile rank by application volume
    tract_df["app_percentile"] = (
        tract_df["applications"].rank(pct=True) * 100
    ).round(1)

    # Low denial rate + low application volume = potential lending desert
    # (lenders may be avoiding the area entirely)
    tract_df["desert_score"] = (
        (100 - tract_df["app_percentile"]) * 0.6 +
        tract_df["denial_rate"] * 100 * 0.4
    ).round(1)

    tract_df["is_lending_desert"] = (
        (tract_df["app_percentile"] < 25) &
        (tract_df["denial_rate"] > 0.15)
    )

    return tract_df.sort_values("desert_score", ascending=False)


def racial_composition_by_tract(df: pd.DataFrame) -> pd.DataFrame:
    """
    Show racial composition of applicants by census tract.
    Useful for identifying tracts where lending may differ by applicant race.
    """
    if "derived_race" not in df.columns or "census_tract" not in df.columns:
        return pd.DataFrame()

    result = df.groupby(
        ["census_tract", "derived_race"]
    ).agg(
        applications=("is_denied", "count"),
        denial_rate=("is_denied", "mean"),
    ).reset_index()

    return result.sort_values(["census_tract", "applications"], ascending=[True, False])


def lending_by_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate lending activity by state.
    """
    state_col = "state_code" if "state_code" in df.columns else None
    if state_col is None:
        return pd.DataFrame()

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby(state_col).agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
        originations=("is_approved", "sum"),
        total_volume=("loan_amount", "sum"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    return result.sort_values("applications", ascending=False)
