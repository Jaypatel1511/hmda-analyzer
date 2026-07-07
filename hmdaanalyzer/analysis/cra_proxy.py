"""
CRA-proxy distribution analytics (methodology v2).

Descriptive-only borrower-income and geographic (tract-income) distribution of
HMDA mortgage originations, approximating the *distribution dimensions* a CRA
lending analysis looks at — WITHOUT being a CRA metric, rating, grade, or
performance evaluation.

This is a PROXY and the fabrication firewall is the whole point:

* **Unknown-first (CRIT-1).** ``tract_to_msa_income_percentage`` reserves ``0``
  (verified at recon as the literal string ``"0"`` in the public LAR) for
  "Unknown / not available". A literal 0 is a real number that PASSES a bare
  ``< 50`` gate and would be fabricated into Low, flatteringly inflating the
  LMI-tract share. The classifier therefore routes Unknown rows (null / blank /
  ``0``) to an excluded tally BEFORE any threshold comparison.
* **No 1111/"Exempt" drop.** ``income`` is in *thousands* and always-required
  (never Exempt); ``1111`` == a real $1,111,000 Upper-income borrower. Dropping
  it would delete real high-income originations and spuriously inflate LMI
  borrower share. Exclude on NA/blank only.
* **Missing area-median guard (recon finding).** Recon (R2) also found
  ``ffiec_msa_md_median_family_income == "0"`` in the public LAR (the same
  FFIEC-unmatched tracts). ``income / 0`` is ``inf``, which passes the ``>= 120``
  gate and would be fabricated into Upper. A 0/blank/NA area median is a missing
  denominator → excluded, never divided.

No inference, no significance, no protected-class crossing, no composite scalar,
no comparator (v1). See the bundled methodology (``get_methodology_path``).
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from hmdaanalyzer.exceptions import _require_columns

# Category order is fixed; LMI = Low + Moderate.
_CATEGORIES = ["Low", "Moderate", "Middle", "Upper"]

# ── Firewall caveat strings (bound to every table, not a strippable footer) ───
STANDARD_CRA_PROXY_CAVEAT = (
    "CRA-proxy distribution estimate — NOT a CRA metric, rating, grade, or "
    "performance evaluation. Not assessment-area-bound: HMDA has no assessment-area "
    "concept, so this proxy spans all HMDA lending in the requested geography — a "
    "different population than any CRA exam evaluates. Mortgage-only: CRA lending "
    "tests also cover small-business, small-farm, and community-development lending, "
    "invisible to HMDA. Reporter population != CRA-covered institutions."
)

_NO_COMPARATOR_LINE = (
    "Distribution only; no comparator — not interpretable as CRA performance."
)

_BORROWER_BIAS_CAVEAT = (
    "HMDA income is the income relied on in the credit decision (frequently combined "
    "co-applicant income), which pushes borrowers into higher bands and tends to "
    "UNDERSTATE the LMI borrower share."
)

_DIFFERING_DENOM_CAVEAT = (
    "Borrower and tract denominators are computed on different populations "
    "(multifamily / non-natural-person / NA-income loans are excluded from the "
    "borrower denominator but carry a valid tract) — do NOT difference the two LMI%s."
)


@dataclass
class CraProxyTable:
    """One tidy distribution table for a (dimension, universe, year) cut.

    ``distribution`` has columns ``category`` (Low/Moderate/Middle/Upper),
    ``count``, and ``cra_proxy_share`` (share over the classified denominator).
    The share column name carries ``cra_proxy`` so no extracted cell reads as a
    CRA metric. ``excluded`` maps each exclusion reason to its count.
    Deliberately no composite score/grade/rating field.
    """
    dimension: str          # "borrower" | "tract"
    universe: str           # "originated" | "purchased"
    year: Optional[str]     # None (single-year frame) or e.g. "2023"
    distribution: pd.DataFrame
    classified_denominator: int
    excluded: dict          # reason -> count
    lmi: dict               # {"cra_proxy_lmi_share": float, "note": ...}
    caveat: str


@dataclass
class CraProxyDistribution:
    """Container of :class:`CraProxyTable`. Iterable over its ``tables``.

    No composite scalar is exposed — reading a single number as a CRA grade is
    exactly what this tool refuses to enable.
    """
    tables: list
    caveat: str

    def __iter__(self):
        return iter(self.tables)

    def __len__(self):
        return len(self.tables)


# ── classifiers (Unknown-first, keyed on the condition before any comparison) ──
def _classify_tract(series: pd.Series):
    """Return (category, reason) Series for tract-income classification.

    ``series`` is the raw ``tract_to_msa_income_percentage`` (object/string or
    NaN). Unknown-first: null / blank / non-numeric / literal ``0`` → "Unknown"
    (reason ``unknown_tract``) BEFORE any threshold. A literal 0 must not reach
    the ``< 50`` gate.
    """
    num = pd.to_numeric(series, errors="coerce")  # blank / "NA" / non-numeric -> NaN
    is_unknown = num.isna() | (num == 0)

    cat = pd.Series("Unknown", index=series.index, dtype=object)
    reason = pd.Series(pd.NA, index=series.index, dtype=object)
    reason[is_unknown] = "unknown_tract"

    valid = ~is_unknown
    cat[valid & (num < 50)] = "Low"
    cat[valid & (num >= 50) & (num < 80)] = "Moderate"
    cat[valid & (num >= 80) & (num < 120)] = "Middle"
    cat[valid & (num >= 120)] = "Upper"
    return cat, reason


def _classify_borrower(income: pd.Series, area_median: pd.Series):
    """Return (category, reason) Series for borrower-income classification.

    MFI% = income * 1000 / area_median * 100, then the §4 bands. Unknown-first:
    NA/blank income → "Unknown" (reason ``na_income``); a 0/blank/NA area median
    is a MISSING DENOMINATOR → "Unknown" (reason ``missing_area_median``) and is
    NEVER divided (income/0 == inf would fabricate Upper). No 1111 handling —
    1111 is a real $1.111M Upper borrower.
    """
    inc = pd.to_numeric(income, errors="coerce")
    mfi = pd.to_numeric(area_median, errors="coerce")

    na_income = inc.isna()
    missing_median = (~na_income) & (mfi.isna() | (mfi == 0))

    cat = pd.Series("Unknown", index=income.index, dtype=object)
    reason = pd.Series(pd.NA, index=income.index, dtype=object)
    reason[na_income] = "na_income"
    reason[missing_median] = "missing_area_median"

    valid = ~na_income & ~missing_median
    pct = pd.Series(np.nan, index=income.index, dtype=float)
    pct[valid] = inc[valid] * 1000.0 / mfi[valid] * 100.0

    cat[valid & (pct < 50)] = "Low"
    cat[valid & (pct >= 50) & (pct < 80)] = "Moderate"
    cat[valid & (pct >= 80) & (pct < 120)] = "Middle"
    cat[valid & (pct >= 120)] = "Upper"
    return cat, reason


def _build_table(dimension, universe, year, cat, reason, *, both):
    classified_mask = cat != "Unknown"
    denom = int(classified_mask.sum())
    counts = {c: int((cat == c).sum()) for c in _CATEGORIES}

    dist = pd.DataFrame({
        "category": _CATEGORIES,
        "count": [counts[c] for c in _CATEGORIES],
    })
    dist["cra_proxy_share"] = (dist["count"] / denom) if denom else 0.0

    excluded = {
        str(k): int(v)
        for k, v in reason[cat == "Unknown"].value_counts().items()
    }

    lmi_count = counts["Low"] + counts["Moderate"]
    lmi = {
        "cra_proxy_lmi_share": (lmi_count / denom) if denom else float("nan"),
        "cra_proxy_lmi_count": lmi_count,
        "note": _NO_COMPARATOR_LINE,
    }

    caveat = STANDARD_CRA_PROXY_CAVEAT + "\n" + _NO_COMPARATOR_LINE
    if dimension == "borrower":
        caveat += "\n" + _BORROWER_BIAS_CAVEAT
    if both:
        caveat += "\n" + _DIFFERING_DENOM_CAVEAT

    # Bind the caveat to the frame too (defence in depth); the column name is the
    # primary, copy-proof binding.
    dist.attrs["cra_proxy_caveat"] = caveat

    return CraProxyTable(
        dimension=dimension,
        universe=universe,
        year=year,
        distribution=dist,
        classified_denominator=denom,
        excluded=excluded,
        lmi=lmi,
        caveat=caveat,
    )


def cra_proxy_distribution(
    df: pd.DataFrame,
    *,
    by: str = "borrower",
    include_purchased: bool = False,
    year_column: str = "activity_year",
) -> CraProxyDistribution:
    """Compute the CRA-proxy borrower-income and/or geographic (tract-income)
    distribution of mortgage originations from a HMDA LAR frame.

    Pure descriptive transform on a passed-in DataFrame (the frame returned by
    ``load_from_api`` or ``load_range``). No fetch, no network.

    Args:
        df: A cleaned HMDA LAR frame.
        by: ``"borrower"`` | ``"tract"`` | ``"both"``.
        include_purchased: If True, adds purchased loans (``action_taken == 6``)
            as a SEPARATE, labeled ``universe="purchased"`` cut — never blended
            into the originations distribution.
        year_column: Provenance year column. If the frame carries ≥2 distinct
            years, distributions are produced PER YEAR (each year's own annual
            ``ffiec_msa_md_median_family_income`` is applied, since classification
            is row-wise); otherwise a single table with ``year=None``.

    Returns:
        A :class:`CraProxyDistribution` — a container of tidy
        :class:`CraProxyTable` objects (one per dimension × universe × year).
        No composite scalar.

    Raises:
        ValueError: if ``by`` is not one of the accepted values.
        MissingColumnError: if a required column for the requested dimension is
            absent.
    """
    if by not in ("borrower", "tract", "both"):
        raise ValueError(
            f"by must be 'borrower', 'tract', or 'both'; got {by!r}"
        )

    dims = ["borrower", "tract"] if by == "both" else [by]

    required = ["action_taken"]
    if "borrower" in dims:
        required += ["income", "ffiec_msa_md_median_family_income"]
    if "tract" in dims:
        required += ["tract_to_msa_income_percentage"]
    _require_columns(df, required, "cra_proxy_distribution")

    # Universe cuts: originations always; purchased kept separate and labeled.
    cuts = [("originated", {1})]
    if include_purchased:
        cuts.append(("purchased", {6}))

    # Per-year grouping only when the frame spans ≥2 years.
    if year_column in df.columns:
        years = sorted(df[year_column].dropna().astype(str).unique())
    else:
        years = []
    if len(years) >= 2:
        grouping = [
            (y, df[df[year_column].astype(str) == y]) for y in years
        ]
    else:
        grouping = [(None, df)]

    both = by == "both"
    tables = []
    for universe, actions in cuts:
        for year, ydf in grouping:
            sub = ydf[ydf["action_taken"].isin(actions)]
            for dim in dims:
                if dim == "tract":
                    cat, reason = _classify_tract(
                        sub["tract_to_msa_income_percentage"]
                    )
                else:
                    cat, reason = _classify_borrower(
                        sub["income"], sub["ffiec_msa_md_median_family_income"]
                    )
                tables.append(
                    _build_table(dim, universe, year, cat, reason, both=both)
                )

    return CraProxyDistribution(
        tables=tables,
        caveat=STANDARD_CRA_PROXY_CAVEAT + "\n" + _NO_COMPARATOR_LINE,
    )
