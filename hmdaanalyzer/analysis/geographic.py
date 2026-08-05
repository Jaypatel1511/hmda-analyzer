"""
Geographic analysis of HMDA lending patterns.
Identifies lending deserts and maps activity by census tract.
"""
import pandas as pd
import numpy as np
from hmdaanalyzer.exceptions import MissingColumnError, UnreachableFlagError
from hmdaanalyzer.geography_vintage import (
    DESERT_TRACT_FLOOR, resolve_geography_vintage,
)


def lending_by_tract(
    df: pd.DataFrame, vintage: int = None, _refusing_as: str = None
) -> pd.DataFrame:
    """
    Aggregate HMDA lending activity by census tract.

    Args:
        df: Cleaned HMDA LAR DataFrame.
        vintage: Optional tract basis year to narrow to (e.g. ``2020``). Selects
            the rows whose data year uses that basis and aggregates only those,
            instead of refusing a vintage-spanning frame. This is a *narrowing*,
            not an override: it cannot produce a wrong number because it never
            merges two delineations, and the guard still runs afterwards.
            Selecting no rows raises rather than returning an empty result
            (methodology §M3.3, §M3.3a).
        _refusing_as: Internal. The public function to name in a refusal, when
            this one is reached indirectly. ``lending_desert_score`` inherits its
            guard from here, and a message naming ``lending_by_tract`` for a call
            the user never made is a message about the wrong function
            (methodology §M3.1 item 1).

    Returns:
        DataFrame with application counts, denial rates, and loan volumes by
        tract, carrying a ``tract_geoid_vintage`` provenance column.

    Raises:
        GeographyVintageError: if the frame pools data years whose census-tract
            GEOIDs do not mean the same thing — either because the tract
            delineation basis differs, or because the *county* basis differs
            (the county code is the tract GEOID's first five digits, so a
            county-scheme change is necessarily a tract-key change).
    """
    if "census_tract" not in df.columns:
        raise MissingColumnError(
            f"lending_by_tract requires column 'census_tract'; "
            f"got: {list(df.columns)}"
        )

    resolved = resolve_geography_vintage(
        df, key="census_tract", fn_name=_refusing_as or "lending_by_tract",
        vintage=vintage,
    )
    df = resolved.frame

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

    # .agg() dropped the provenance column, so the helper re-attaches it here.
    # This is the concrete reason the guard is one helper called from N places:
    # re-attachment is part of the same job, and six hand-written re-attachments
    # would drift exactly as six hand-written checks would (§M3.3, §M4.1).
    result = resolved.attach(result)

    return result.sort_values("applications", ascending=False)


def lending_by_county(df: pd.DataFrame, vintage: int = None) -> pd.DataFrame:
    """
    Aggregate HMDA lending activity by county.

    Args:
        df: Cleaned HMDA LAR DataFrame.
        vintage: Optional county basis year to narrow to. See
            :func:`lending_by_tract`.

    Raises:
        GeographyVintageError: if the frame pools data years whose county codes
            do not mean the same thing. Aggregating up from tract to county is
            NOT an escape route from the tract rule — the county key moves at
            2021→2022 (Alaska ``02261`` splitting into ``02063`` + ``02066``) and
            again at 2023→2024 (Connecticut's planning regions), which is why
            this site is guarded too (methodology §M2.3, §M5.2 option 2).
    """
    if "county_code" not in df.columns:
        raise MissingColumnError(
            f"lending_by_county requires column 'county_code'; "
            f"got: {list(df.columns)}"
        )

    resolved = resolve_geography_vintage(
        df, key="county_code", fn_name="lending_by_county", vintage=vintage
    )
    df = resolved.frame

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

    result = resolved.attach(result)

    return result.sort_values("applications", ascending=False)


def lending_desert_score(df: pd.DataFrame, vintage: int = None) -> pd.DataFrame:
    """
    Identify census tracts with abnormally low application volumes.
    A 'lending desert' is a tract with very few mortgage applications
    relative to its expected volume based on housing units.

    Args:
        df: Cleaned HMDA LAR DataFrame.
        vintage: Optional tract basis year to narrow to. See
            :func:`lending_by_tract`.

    Returns:
        DataFrame with lending desert scores by census tract.

    Raises:
        GeographyVintageError: inherited from :func:`lending_by_tract`. This is
            the worst-affected of the guarded sites, and not only for the rows
            that collide: ``app_percentile`` is a percentile over the *collapsed*
            tract set, so pooling alters the reference distribution every tract
            is scored against. Measured on Connecticut 2023+2024, where NO tract
            collides at all (intersection 0 of 872), 845 of 871 tracts still get
            a wrong percentile and 25 get a wrong ``is_lending_desert`` verdict —
            while the aggregate desert count moves only 384 → 381, so nothing in
            the output looks anomalous enough to prompt a second look (§M6.1,
            §M6.5).
        UnreachableFlagError: if fewer than ``DESERT_TRACT_FLOOR`` (5) tracts
            remain, where the flag is arithmetically unreachable (§M3.3a).
    """
    tract_df = lending_by_tract(
        df, vintage=vintage, _refusing_as="lending_desert_score"
    )

    # The flag's floor is five tracts, derived from the threshold rather than
    # from intuition: min(app_percentile) is 100/n and the flag needs < 25, so it
    # is unreachable for n <= 4 whatever the data says. Returning
    # is_lending_desert=False for every tract there is a FABRICATED NEGATIVE, and
    # a fabricated negative is precisely what exceptions.py exists to prevent —
    # an empty or vacuous result must never silently read as "no disparity" in a
    # fair-lending context. Ties only raise the minimum percentile, so the floor
    # holds unconditionally (§M3.3a).
    n_tracts = len(tract_df)
    if n_tracts < DESERT_TRACT_FLOOR:
        floor_math = (
            f"rank(pct=True) over n rows has minimum 100/n = "
            f"{100 / n_tracts:.1f} for n={n_tracts}"
            if n_tracts else "there are no tracts to rank"
        )
        raise UnreachableFlagError(
            f"lending_desert_score refused: {n_tracts} tract(s) in this frame, "
            f"below the floor of {DESERT_TRACT_FLOOR}.\n"
            f"  is_lending_desert requires app_percentile < 25, and {floor_math}. "
            f"The flag is ARITHMETICALLY UNREACHABLE here, so every tract would be "
            f"returned as is_lending_desert=False whatever the data says — a "
            f"fabricated negative, not a finding that the tracts were examined and "
            f"cleared.\n"
            f"  This is neither a small-N suppression rule nor a claim that five "
            f"tracts is statistically adequate; it is only the point below which a "
            f"positive is impossible. Use lending_by_tract() for the underlying "
            f"counts. (methodology §M3.3a)"
        )

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


def racial_composition_by_tract(df: pd.DataFrame, vintage: int = None) -> pd.DataFrame:
    """
    Show racial composition of applicants by census tract.
    Useful for identifying tracts where lending may differ by applicant race.

    Args:
        df: Cleaned HMDA LAR DataFrame.
        vintage: Optional tract basis year to narrow to. See
            :func:`lending_by_tract`.

    Raises:
        GeographyVintageError: if the frame pools data years whose census-tract
            GEOIDs do not mean the same thing.
    """
    missing = [c for c in ("derived_race", "census_tract") if c not in df.columns]
    if missing:
        raise MissingColumnError(
            f"racial_composition_by_tract requires columns {missing}; "
            f"got: {list(df.columns)}"
        )

    resolved = resolve_geography_vintage(
        df, key="census_tract", fn_name="racial_composition_by_tract", vintage=vintage
    )
    df = resolved.frame

    result = df.groupby(
        ["census_tract", "derived_race"]
    ).agg(
        applications=("is_denied", "count"),
        denial_rate=("is_denied", "mean"),
    ).reset_index()

    result = resolved.attach(result)

    return result.sort_values(["census_tract", "applications"], ascending=[True, False])


def lending_by_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate lending activity by state.

    **This site is deliberately UNGUARDED, on an argument from absence.** It is a
    geography-keyed aggregation like the other six and the AST site-list test
    enumerates it, but ``state_code`` gets no basis map because nothing was
    measured to move a state code in 2018–2025. That is not a demonstration that
    they cannot move. If a state-level equivalent of Connecticut's
    county restructuring occurs, this key fails exactly as the county key did and
    nothing here would notice (methodology coverage item 3).
    """
    if "state_code" not in df.columns:
        raise MissingColumnError(
            f"lending_by_state requires column 'state_code'; "
            f"got: {list(df.columns)}"
        )

    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby("state_code").agg(
        applications=("is_denied", "count"),
        denials=("is_denied", "sum"),
        originations=("is_approved", "sum"),
        total_volume=("loan_amount", "sum"),
    ).reset_index()

    result["denial_rate"] = result["denials"] / result["applications"]
    return result.sort_values("applications", ascending=False)
