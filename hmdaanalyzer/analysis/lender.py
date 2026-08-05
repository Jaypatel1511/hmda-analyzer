"""
Lender-level HMDA analysis.
Compare a lender's performance against market peers.
"""
import pandas as pd
from hmdaanalyzer.analysis.disparity import denial_rate_by_race, disparity_ratio
from hmdaanalyzer.exceptions import MissingColumnError, _require_columns
from hmdaanalyzer.geography_vintage import resolve_geography_vintage


def lender_summary(df: pd.DataFrame, lei: str = None, vintage: int = None) -> dict:
    """
    Compute summary statistics for a single lender.

    Args:
        df:  HMDA LAR DataFrame (filtered to lender or full market)
        lei: Lender LEI to filter to (optional)
        vintage: Optional geography basis year to narrow to. See
            :func:`hmdaanalyzer.lending_by_tract`.

    Returns:
        Dict with key lender performance metrics. An empty dict ``{}`` means a
        *legitimate empty result* (no rows matched the lender / no actionable
        applications) — never a schema problem. A missing required column raises
        ``MissingColumnError`` instead, so an empty result can't mask a bad query.

        Geography provenance rides as explicit keys — ``census_tract_basis_year``,
        ``county_code_basis_year`` and, when ``vintage`` dropped rows,
        ``dropped_rows_by_year``. A dict cannot carry a column, so this is the
        only channel available to it, and it is a named one rather than a side
        effect (methodology §M3.3a, §M4.5).

    Raises:
        GeographyVintageError: if the frame pools data years whose census-tract
            or county keys do not mean the same thing. **Both** of this
            function's ``nunique()`` calls are geography-keyed and both
            undercount across their respective boundaries, so both are guarded
            (methodology §M4.5).
    """
    if lei is not None:
        if "lei" not in df.columns:
            raise MissingColumnError(
                f"lender_summary was given lei={lei!r} but requires column 'lei' "
                f"to filter on; got: {list(df.columns)}"
            )
        df = df[df["lei"] == lei]

    # Legitimate empty result: schema is fine, the lei filter (or input) just
    # matched no rows. Checked BEFORE the guard, deliberately: §M3.3a keeps a
    # legitimately empty INPUT frame on its current behaviour and raises only for
    # an empty result the *narrowing* caused. The two must not collapse into the
    # same return value.
    if df.empty:
        return {}

    # Two guarded sites in one function, one per key. The tract call also
    # narrows, if asked, and its guard already consults the county map — so the
    # county call below cannot fire on anything the first one missed. It is not
    # bookkeeping: it is what supplies the county provenance key, and it keeps
    # the site→guard mapping one-to-one, so a future edit that drops the
    # unique_tracts line cannot silently un-guard unique_counties.
    tract_v = resolve_geography_vintage(
        df, key="census_tract", fn_name="lender_summary", vintage=vintage
    )
    df = tract_v.frame
    county_v = resolve_geography_vintage(
        df, key="county_code", fn_name="lender_summary"
    )

    actionable = df[df["action_taken"].isin([1, 2, 3])]
    total = len(actionable)
    # Legitimate empty result: rows exist but none are actionable applications.
    if total == 0:
        return {}

    # Provenance rides as explicit keys because no column can ride on a dict
    # (§M3.3a, §M4.5). The two resolutions carry disjoint basis/status keys —
    # they are named per map — but they BOTH carry `dropped_rows_by_year`, and
    # a plain ** merge lets the last one win.
    #
    # That matters as of the fix that made the key always-present. The county
    # resolution above is deliberately not given `vintage=` (the tract call does
    # the narrowing, once), so it always reports {} — and merging it second
    # overwrote the tract narrowing's real count with an empty dict. The
    # narrowing record belongs to the call that could narrow, so that is the one
    # kept, explicitly rather than by merge order.
    tract_keys = tract_v.provenance_keys()
    county_keys = county_v.provenance_keys()
    county_keys.pop("dropped_rows_by_year", None)

    return {
        **tract_keys,
        **county_keys,
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
        DataFrame showing lender vs market denial rates by race.

        **Small-N suppression is reported for BOTH sides, separately.** The two
        frames are suppressed independently — a group can clear the
        ``MIN_APPLICATIONS_FOR_RATE`` minimum market-wide and fall below it for
        one lender, which is the normal case and the one that matters here: a
        row absent from this table is usually absent because the *lender* had
        too few applications, not because the group is unremarkable. Columns are
        prefixed ``lender_`` and ``market_`` so neither can be read as the
        other. An unprefixed ``suppressed_*`` column here would have inherited
        the lender's numbers under a name that reads as the table's.
    """
    _require_columns(df, ["lei"], "lender_vs_market")
    lender_df = df[df["lei"] == lei]

    _SUPPRESSION = ("suppressed_groups", "suppressed_applications",
                    "suppressed_group_names")

    lender_rates = denial_rate_by_race(lender_df).rename(
        columns={"denial_rate": "lender_denial_rate",
                 "applications": "lender_applications",
                 "denials": "lender_denials",
                 **{c: f"lender_{c}" for c in _SUPPRESSION}}
    )

    market_rates = denial_rate_by_race(df).rename(
        columns={"denial_rate": "market_denial_rate",
                 "applications": "market_applications",
                 "denials": "market_denials",
                 **{c: f"market_{c}" for c in _SUPPRESSION}}
    )

    market_cols = ["derived_race", "market_denial_rate"] + [
        f"market_{c}" for c in _SUPPRESSION
    ]
    result = lender_rates.merge(
        market_rates[market_cols], on="derived_race", how="left"
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
    if state is not None and "state_code" not in df.columns:
        raise MissingColumnError(
            f"top_lenders_by_volume was given state={state!r} but requires column "
            f"'state_code' to filter on; got: {list(df.columns)}"
        )
    if state is not None:
        df = df[df["state_code"] == state]

    if "lei" not in df.columns:
        raise MissingColumnError(
            f"top_lenders_by_volume requires column 'lei'; got: {list(df.columns)}"
        )

    originated = df[df["action_taken"] == 1]

    result = originated.groupby("lei").agg(
        originations=("loan_amount", "count"),
        total_volume=("loan_amount", "sum"),
        avg_loan=("loan_amount", "mean"),
    ).reset_index()

    return result.sort_values("originations", ascending=False).head(n)
