"""
Denial rate disparity analysis.
Computes disparate impact ratios between racial/ethnic groups.
"""
import pandas as pd
import numpy as np
from hmdaanalyzer.data.schema import (
    DISPARITY_THRESHOLDS, REFERENCE_RACE, MIN_APPLICATIONS_FOR_RATE,
)
from hmdaanalyzer.exceptions import (
    MissingColumnError, ReferenceGroupError, _require_columns, _require_numeric,
)


def denial_rate_by_race(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute denial rates by race for a HMDA LAR DataFrame.

    **Small-N suppression, and it is now visible.** A ``derived_race`` group
    with fewer than ``MIN_APPLICATIONS_FOR_RATE`` (5) actionable applications is
    dropped, because a rate over four or fewer decisions can only take the
    values 0/25/50/75/100% and a disparity ratio built on one asserts a
    precision it does not have. That rule is unchanged from every previous
    release; what changed in 0.6.0 is that the output now says it fired.

    Three columns record it on every returned row:

    * ``suppressed_groups``       — how many race groups were removed
    * ``suppressed_applications`` — how many applications those groups held
    * ``suppressed_group_names``  — which groups, ``"; "``-joined, or ``""``

    They are on the frame rather than in a warning for the reason the geography
    guard gives (§M3.2): a warning is shown once per location, so a notebook
    re-run is silent, and the artefact — the memo, the spreadsheet, the
    regulatory filing — outlives the session that produced it. A protected class
    silently absent from a disparity table is indistinguishable from one with no
    disparity.

    Known residual gap: if EVERY group falls below the threshold the returned
    frame has no rows to carry the columns, so the fact is unrecoverable from
    the frame alone. ``disparity_ratio`` raises ``ReferenceGroupError`` on that
    input, which is the loud path; ``denial_rate_by_race`` still returns empty.

    Args:
        df: Cleaned HMDA LAR DataFrame with is_denied and derived_race columns

    Returns:
        DataFrame with denial rates by race, plus the three suppression columns.

    Raises:
        MissingColumnError: if ``derived_race`` or ``is_denied`` is absent.
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

    # The suppression, and its own record. Computed BEFORE the filter, because
    # after it the removed groups are unrecoverable — which was the entire
    # defect: the frame that came back had no way to describe what left it.
    keep = result["applications"] >= MIN_APPLICATIONS_FOR_RATE
    suppressed = result[~keep]
    result = result[keep].copy()

    result["suppressed_groups"] = int(len(suppressed))
    result["suppressed_applications"] = int(suppressed["applications"].sum())
    result["suppressed_group_names"] = "; ".join(
        str(g) for g in sorted(suppressed["derived_race"])
    )

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
        # Typed (a ValueError subclass, so existing callers are unaffected) so
        # the report layer can name the one disparity failure it may render
        # without also swallowing a vintage refusal (§M3.2a).
        raise ReferenceGroupError(f"Reference group '{reference}' not found in data.")

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

    ``income`` is in thousands of dollars (HMDA FIG convention), so the band
    edges 50/80/120/200 are $50k/$80k/$120k/$200k.

    Raises:
        MissingColumnError: if ``income``, ``action_taken`` or ``is_denied`` is
            absent, or if ``income`` is not a numeric dtype.

    On the dtype check.
        ``pd.cut`` raises a **bare** ``ValueError`` on a non-numeric ``income``
        — ``"bins must be of datetime64 dtype"`` for a datetime column, and
        similarly unhelpful text for others. That exception is not
        ``MissingColumnError``, not ``ReferenceGroupError``, and not in the
        report layer's ``RENDERABLE_ERRORS``, so it propagates out of
        ``generate_disparity_report`` and destroys the entire report over one
        malformed column — measured, not theorised: a ``datetime64`` ``income``
        takes down every section, including the four that never touch income.

        The fix belongs here, at the input, not in the report layer's allowlist.
        Widening ``RENDERABLE_ERRORS`` to catch ``ValueError`` would re-admit
        the swallowing that the 0.6.0 inversion removed — ``ValueError`` is the
        base class of ``GeographyVintageError``, so a vintage refusal would once
        again be typeset into a table cell (§M3.2a). Validating the input
        converts the same condition into the package's own typed, diagnosable
        error, which the report layer is already correct about: it does not
        catch it, and the report fails loudly with a message naming the column.
    """
    _require_columns(
        df, ["income", "action_taken", "is_denied"], "denial_rate_by_income_band"
    )
    _require_numeric(df, "income", "denial_rate_by_income_band")

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
