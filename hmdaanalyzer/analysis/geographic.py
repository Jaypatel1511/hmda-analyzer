"""
Geographic analysis of HMDA lending patterns.
Identifies lending deserts and maps activity by census tract.
"""
import pandas as pd
import numpy as np
from hmdaanalyzer.exceptions import MissingColumnError, UnreachableFlagError
from hmdaanalyzer.geography_vintage import (
    DESERT_PERCENTILE_THRESHOLD, DESERT_DENIAL_RATE_FLOOR, DESERT_TRACT_FLOOR,
    resolve_geography_vintage,
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
    Score census tracts on low application volume combined with high denial rate.

    **What this actually computes** — stated exactly, because the previous
    docstring described a different function. It claimed a tract was scored
    "relative to its expected volume based on housing units". No housing-unit
    figure is read anywhere in this function, in ``lending_by_tract``, or in the
    package: ``tract_owner_occupied_units`` and
    ``tract_one_to_four_family_homes`` arrive in the LAR and are never used.
    There is no expected volume and no denominator. The description was
    aspirational and a reader who trusted it would have believed the score was
    normalised for tract size when it is not.

    Two distinct outputs, and they do not use the same rule:

    ``desert_score`` — a weighted composite on a 0–100 scale::

        desert_score = (100 - app_percentile) * 0.6 + denial_rate * 100 * 0.4

    60% low-volume, 40% high-denial. The weights are a **presentation choice
    for ranking**, not a calibrated or validated instrument: nothing was fitted,
    and no threshold on ``desert_score`` means anything. Use it to sort, not to
    decide.

    ``is_lending_desert`` — a boolean, and NOT a cut on ``desert_score``::

        is_lending_desert = (app_percentile < DESERT_PERCENTILE_THRESHOLD)
                            & (denial_rate > DESERT_DENIAL_RATE_FLOOR)

    Both conditions must hold. A tract can therefore carry a very high
    ``desert_score`` and still be ``False`` — a high score driven mostly by
    denial rate with volume above the percentile cut is the common case. Sorting
    by ``desert_score`` and reading the top rows as "the deserts" is wrong.

    ``app_percentile`` is a percentile **within the frame you passed**, not a
    national one: the same tract scores differently depending on what else is in
    the frame. That is also why the vintage guard matters here more than
    anywhere else (see Raises).

    ``DESERT_DENIAL_RATE_FLOOR`` is **unvalidated** — it is not a CFPB threshold
    and is unrelated to the disparity thresholds in
    ``schema.DISPARITY_THRESHOLDS``. Import it from
    ``hmdaanalyzer.geography_vintage`` to read the shipped value rather than
    trusting a number re-typed into prose; both this formula display and the
    comparison site below name the constant, so the two cannot drift.

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
            collides at all (intersection 0 of 872), **1,695 of 1,742 tract-years
            get a wrong percentile and 25 get a wrong ``is_lending_desert``
            verdict** — while the aggregate desert count moves only 384 → 381, so
            nothing in the output looks anomalous enough to prompt a second look
            (§M6.1, §M6.5).

            One denominator, deliberately. This sentence used to read "845 of 871
            … and 25 …", which is the 2023 half's numerator against the 2023
            half's denominator, followed by the flip count for BOTH halves. It
            understated the harm by half. Per half the figures are 845 of 871
            (2023) and 850 of 871 (2024), and 11 and 14 flips.
        UnreachableFlagError: if fewer than ``DESERT_TRACT_FLOOR`` tracts remain,
            where the flag is arithmetically unreachable. The floor is derived at
            import from ``DESERT_PERCENTILE_THRESHOLD`` — the same constant this
            function compares ``app_percentile`` against — so the two cannot
            drift apart (§M3.3a).
    """
    tract_df = lending_by_tract(
        df, vintage=vintage, _refusing_as="lending_desert_score"
    )

    # The flag's floor is derived from the threshold rather than from intuition:
    # min(app_percentile) is 100/n and the flag needs < DESERT_PERCENTILE_THRESHOLD,
    # so it is unreachable below the floor whatever the data says. Returning
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
            f"  is_lending_desert requires app_percentile < "
            f"{DESERT_PERCENTILE_THRESHOLD}, and {floor_math}. "
            f"The flag is ARITHMETICALLY UNREACHABLE here, so every tract would be "
            f"returned as is_lending_desert=False whatever the data says — a "
            f"fabricated negative, not a finding that the tracts were examined and "
            f"cleared.\n"
            f"  This is neither a small-N suppression rule nor a claim that "
            f"{DESERT_TRACT_FLOOR} tracts is statistically adequate; it is only "
            f"the point below which a positive is impossible. Use "
            f"lending_by_tract() for the underlying counts. (methodology §M3.3a)"
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

    # Both thresholds are imported, not written here. The percentile one is the
    # number DESERT_TRACT_FLOOR is derived from, and when it was a literal at
    # this line the two could — and in a demonstrated injection did — drift
    # apart while every test stayed green (§M3.3a). The denial-rate floor was
    # still a literal here through 0.5.0 and is named for the same reason.
    #
    # NOTE the conjunction: is_lending_desert is NOT a cut on desert_score. A
    # tract can rank at the top by desert_score and be False here.
    tract_df["is_lending_desert"] = (
        (tract_df["app_percentile"] < DESERT_PERCENTILE_THRESHOLD) &
        (tract_df["denial_rate"] > DESERT_DENIAL_RATE_FLOOR)
    )

    return tract_df.sort_values("desert_score", ascending=False)


def racial_composition_by_tract(df: pd.DataFrame, vintage: int = None) -> pd.DataFrame:
    """
    Show racial composition of applicants by census tract.
    Useful for identifying tracts where lending may differ by applicant race.

    **Denominator, and a change in 0.6.0.** Both returned columns are computed
    over the *actionable* rows only — ``action_taken`` in ``(1, 2, 3)``:
    originated, approved-but-not-accepted, and denied. Through 0.5.0 this
    function applied no ``action_taken`` filter at all and was the only analysis
    in the package that did not. Its denominator therefore included action 4
    (withdrawn by the applicant), action 5 (file closed for incompleteness) and
    action 6 (a purchased loan — an origination somebody else made, never an
    application to this institution).

    That produced two columns named ``denial_rate`` in one package with
    different denominators. On a tract carrying one row per action 1–6::

        lending_by_tract              applications = 3   denial_rate = 0.333
        racial_composition_by_tract   applications = 6   denial_rate = 0.167   (0.5.0)
        racial_composition_by_tract   applications = 3   denial_rate = 0.333   (0.6.0)

    The old bias had a direction: non-decision rows can only enlarge the
    denominator, so a per-(tract, race) fair-lending rate was systematically
    **understating denials**.

    The filter applies to ``applications`` as well as to ``denial_rate``,
    deliberately. ``applications`` means actionable applications at the nine
    other sites that emit it, and a tenth meaning for one column name is the
    drift rather than the cure for it — a reader comparing this table against
    ``lending_by_tract`` must be comparing like with like. The cost, stated: the
    racial *composition* is now the composition of actionable applications, not
    of every LAR row touching the tract. A tract whose rows are all withdrawals
    and purchases now yields no row here at all, which is the honest answer —
    there is no application to rate — rather than a fabricated 0.0 denial rate
    over a denominator of withdrawals.

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

    # The same filter its nine siblings use. Written as the same expression at
    # each site rather than shared, because that is how the other nine are
    # written and a single divergent copy is what this line is fixing; the suite
    # asserts all ten agree (tests/test_action_taken_denominator.py).
    actionable = df[df["action_taken"].isin([1, 2, 3])].copy()

    result = actionable.groupby(
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
