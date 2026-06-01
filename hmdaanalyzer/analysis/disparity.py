"""
Denial rate disparity analysis.
Computes disparate impact ratios between racial/ethnic groups.
"""
import pandas as pd
import numpy as np
from hmdaanalyzer.data.schema import DISPARITY_THRESHOLDS, REFERENCE_RACE
from hmdaanalyzer.exceptions import MissingColumnError


def denial_rate_by_race(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute denial rates by race for a HMDA LAR DataFrame.

    Args:
        df: Cleaned HMDA LAR DataFrame with is_denied and derived_race columns

    Returns:
        DataFrame with denial rates by race
    """
    missing = [c for c in ("derived_race", "is_denied") if c not in df.columns]
    if missing:
        raise MissingColumnError(
            f"denial_rate_by_race requires columns {missing}; "
            f"got: {list(df.columns)}"
        )

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby("derived_race").agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    result = result[result["applications"] >= 5]
    result = result.sort_values("denial_rate", ascending=False)

    return result


def disparity_ratio(df: pd.DataFrame, reference: str = None) -> pd.DataFrame:
    """
    Compute disparity ratios relative to a reference group (default: White).

    Disparity ratio = group denial rate / reference group denial rate
    A ratio > 2.0 indicates high disparity (CFPB threshold).

    Args:
        df:        Cleaned HMDA LAR DataFrame
        reference: Reference race group (default: "White")

    Returns:
        DataFrame with disparity ratios and severity flags
    """
    reference = reference or REFERENCE_RACE
    denial_rates = denial_rate_by_race(df)

    ref_row = denial_rates[denial_rates["derived_race"] == reference]
    if ref_row.empty:
        raise ValueError(f"Reference group '{reference}' not found in data.")

    ref_rate = ref_row["denial_rate"].iloc[0]

    result = denial_rates.copy()
    result["reference_group"] = reference
    result["reference_denial_rate"] = ref_rate
    result["disparity_ratio"] = result["denial_rate"] / ref_rate if ref_rate > 0 else None

    def classify(ratio):
        if ratio is None or pd.isna(ratio):
            return "N/A"
        if ratio >= DISPARITY_THRESHOLDS["high"]:
            return "HIGH"
        elif ratio >= DISPARITY_THRESHOLDS["moderate"]:
            return "MODERATE"
        elif ratio < 1.0:
            return "FAVORABLE"
        return "LOW"

    result["disparity_level"] = result["disparity_ratio"].apply(classify)
    result = result.sort_values("disparity_ratio", ascending=False)

    return result


def denial_rate_by_income_band(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute denial rates by income band to identify income-based disparities.
    """
    df = df.copy()
    df["income_band"] = pd.cut(
        df["income"],
        bins=[0, 50, 80, 120, 200, float("inf")],
        labels=["<$50k", "$50-80k", "$80-120k", "$120-200k", "$200k+"],
    )

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby("income_band", observed=True).agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    return result


def denial_reasons_by_race(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze denial reasons broken down by race.
    """
    from hmdaanalyzer.data.schema import DENIAL_REASONS

    if "denial_reason_1" not in df.columns:
        raise MissingColumnError(
            f"denial_reasons_by_race requires column 'denial_reason_1'; "
            f"got: {list(df.columns)}"
        )

    denied = df[df["is_denied"] == True].copy()

    denied["denial_reason_label"] = denied["denial_reason_1"].map(
        lambda x: DENIAL_REASONS.get(int(x), "Unknown") if pd.notna(x) else "Unknown"
    )

    result = denied.groupby(
        ["derived_race", "denial_reason_label"]
    ).size().reset_index(name="count")

    totals = denied.groupby("derived_race").size().reset_index(name="total")
    result = result.merge(totals, on="derived_race")
    result["pct"] = result["count"] / result["total"] * 100
    result = result.sort_values(["derived_race", "pct"], ascending=[True, False])

    return result
