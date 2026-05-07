"""
Lender-level HMDA analysis.
Compare a lender's performance against market peers.
"""
import pandas as pd
from hmdaanalyzer.analysis.disparity import denial_rate_by_race, disparity_ratio


def lender_summary(df: pd.DataFrame, lei: str = None) -> dict:
    """
    Compute summary statistics for a single lender.

    Args:
        df:  HMDA LAR DataFrame (filtered to lender or full market)
        lei: Lender LEI to filter to (optional)

    Returns:
        Dict with key lender performance metrics
    """
    if lei and "lei" in df.columns:
        df = df[df["lei"] == lei]

    if df.empty:
        return {}

    actionable = df[df["action_taken"].isin([1, 2, 3])]
    total = len(actionable)
    if total == 0:
        return {}

    return {
        "total_applications":   total,
        "originations":         int(actionable["is_approved"].sum()),
        "denials":              int(actionable["is_denied"].sum()),
        "approval_rate":        round(actionable["is_approved"].mean() * 100, 2),
        "denial_rate":          round(actionable["is_denied"].mean() * 100, 2),
        "avg_loan_amount":      round(actionable["loan_amount"].mean(), 0),
        "median_loan_amount":   round(actionable["loan_amount"].median(), 0),
        "avg_applicant_income": round(actionable["income"].mean(), 0),
        "unique_tracts":        actionable["census_tract"].nunique(),
        "unique_counties":      actionable["county_code"].nunique(),
    }


def lender_vs_market(
    df: pd.DataFrame,
    lei: str,
) -> pd.DataFrame:
    """
    Compare a lender's denial rates against the overall market
    by racial group.

    Args:
        df:  Full market HMDA LAR DataFrame
        lei: Lender LEI to compare

    Returns:
        DataFrame showing lender vs market denial rates by race
    """
    lender_df = df[df["lei"] == lei] if "lei" in df.columns else df

    lender_rates = denial_rate_by_race(lender_df).rename(
        columns={"denial_rate": "lender_denial_rate",
                 "applications": "lender_applications",
                 "denials": "lender_denials"}
    )

    market_rates = denial_rate_by_race(df).rename(
        columns={"denial_rate": "market_denial_rate",
                 "applications": "market_applications",
                 "denials": "market_denials"}
    )

    result = lender_rates.merge(
        market_rates[["derived_race", "market_denial_rate"]],
        on="derived_race", how="left"
    )

    result["vs_market"] = (
        result["lender_denial_rate"] - result["market_denial_rate"]
    )
    result["vs_market_pct"] = (result["vs_market"] * 100).round(2)

    return result.sort_values("lender_denial_rate", ascending=False)


def top_lenders_by_volume(
    df: pd.DataFrame,
    n: int = 10,
    state: str = None,
) -> pd.DataFrame:
    """
    Rank lenders by origination volume.
    """
    if state and "state_code" in df.columns:
        df = df[df["state_code"] == state]

    originated = df[df["action_taken"] == 1]

    if "lei" not in originated.columns:
        return pd.DataFrame()

    result = originated.groupby("lei").agg(
        originations=("loan_amount", "count"),
        total_volume=("loan_amount", "sum"),
        avg_loan=("loan_amount", "mean"),
    ).reset_index()

    return result.sort_values("originations", ascending=False).head(n)
