"""
Tests for cra_proxy_distribution — the CRA-proxy borrower-income and geographic
(tract-income) distribution transform (methodology v2).

Pure transform: no network, so no mock_get. Fixtures are DataFrames shaped like
``_clean`` output — ``income`` float64 (NaN for NA), ``tract_to_msa_income_percentage``
and ``ffiec_msa_md_median_family_income`` as strings/object (NOT numeric-coerced,
per the loader), ``action_taken`` Int64, ``activity_year`` string.

Negative-case-first: each firewall test names the mutation that makes it bite.
"""
import numpy as np
import pandas as pd
import pytest

from hmdaanalyzer import (
    cra_proxy_distribution, STANDARD_CRA_PROXY_CAVEAT, get_methodology_path,
)
from hmdaanalyzer.analysis.cra_proxy import _classify_tract, _classify_borrower


# ── fixture builder ───────────────────────────────────────────────────────────
def _row(*, action=1, income=np.nan, tract_pct="100", mfi="100000", year="2023"):
    """One LAR-shaped record. Defaults land a row in Middle/Middle."""
    return {
        "action_taken": action,
        "income": float(income) if income is not None and not (isinstance(income, float) and np.isnan(income)) else np.nan,
        "tract_to_msa_income_percentage": tract_pct,
        "ffiec_msa_md_median_family_income": mfi,
        "activity_year": year,
    }


def _frame(rows):
    df = pd.DataFrame(rows)
    # mirror _clean dtypes
    df["action_taken"] = df["action_taken"].astype("Int64")
    df["income"] = pd.to_numeric(df["income"], errors="coerce")
    df["tract_to_msa_income_percentage"] = df["tract_to_msa_income_percentage"].astype("object")
    df["ffiec_msa_md_median_family_income"] = df["ffiec_msa_md_median_family_income"].astype("object")
    df["activity_year"] = df["activity_year"].astype("object")
    return df


def _table(result, dimension, year=None, universe="originated"):
    for t in result.tables:
        if t.dimension == dimension and t.year == year and t.universe == universe:
            return t
    raise AssertionError(
        f"no table for dimension={dimension!r} year={year!r} universe={universe!r}; "
        f"have {[(t.dimension, t.year, t.universe) for t in result.tables]}"
    )


def _count(table, category):
    row = table.distribution.loc[table.distribution["category"] == category]
    return int(row["count"].iloc[0]) if len(row) else 0


# ── CRIT-1: fabrication firewall — literal '0' tract pct is Unknown, not Low ──
def test_tract_pct_literal_zero_is_unknown_not_low():
    """A tract pct of the string '0' (the FFIEC public-LAR Unknown sentinel,
    verified at recon) must route to the excluded Unknown tally, NOT pass the
    <50 gate into Low. Mutation that bites: drop the Unknown-first check → the 0
    lands in Low → Low count becomes 1 and unknown_tract excluded becomes 0."""
    df = _frame([_row(tract_pct="0")])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert _count(t, "Low") == 0
    assert t.excluded.get("unknown_tract", 0) == 1


# ── HIGH: deletion firewall — income == 1111 is a real $1.111M Upper borrower ──
def test_income_1111_is_upper_not_dropped():
    """income is in thousands and always-required (never Exempt); 1111 == a real
    $1,111,000 Upper-income borrower. Mutation that bites: re-add an income==1111
    drop → Upper count falls to 0 and na_income excluded rises."""
    df = _frame([_row(income=1111, mfi="100000")])  # 1111*1000/100000*100 = 1111% → Upper
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Upper") == 1
    assert t.excluded.get("na_income", 0) == 0
    assert t.classified_denominator == 1


# ── NaN / blank inputs land in the excluded tally, never a band ───────────────
def test_nan_tract_pct_is_excluded_not_a_band():
    df = _frame([_row(tract_pct=np.nan)])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert t.classified_denominator == 0
    assert t.excluded.get("unknown_tract", 0) == 1
    assert t.distribution["count"].sum() == 0


def test_na_income_is_excluded_not_a_band():
    df = _frame([_row(income=np.nan, mfi="100000")])
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert t.classified_denominator == 0
    assert t.excluded.get("na_income", 0) == 1
    assert t.distribution["count"].sum() == 0


# ── recon surprise: ffiec MFI == '0' is a missing denominator, NOT inf→Upper ──
def test_zero_area_median_is_excluded_not_upper():
    """Recon (R2) found ffiec_msa_md_median_family_income == '0' in the public LAR
    (FFIEC-unmatched tracts). income/0 == inf, which passes the >=120 gate and
    would be FABRICATED into Upper. It must be excluded as a missing denominator.
    Mutation that bites: remove the zero/missing-denominator guard → the row's
    inf lands in Upper."""
    df = _frame([_row(income=50, mfi="0")])
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Upper") == 0
    assert t.classified_denominator == 0
    assert t.excluded.get("missing_area_median", 0) == 1


# ── boundary conventions (lower-inclusive, upper-exclusive) ───────────────────
def test_tract_boundaries():
    df = _frame([
        _row(tract_pct="50"),   # Moderate (50 inclusive)
        _row(tract_pct="80"),   # Middle   (80 inclusive)
        _row(tract_pct="120"),  # Upper    (120 inclusive)
        _row(tract_pct="49.99"),# Low
        _row(tract_pct="79.99"),# Moderate
        _row(tract_pct="119.99"),# Middle
    ])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert _count(t, "Low") == 1
    assert _count(t, "Moderate") == 2      # 50 and 79.99
    assert _count(t, "Middle") == 2        # 80 and 119.99
    assert _count(t, "Upper") == 1         # 120


def test_borrower_boundaries():
    # MFI% = income*1000/mfi*100; mfi=100000 → MFI% == income
    df = _frame([
        _row(income=50, mfi="100000"),   # Moderate
        _row(income=80, mfi="100000"),   # Middle
        _row(income=120, mfi="100000"),  # Upper
        _row(income=49.99, mfi="100000"),# Low
    ])
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Low") == 1
    assert _count(t, "Moderate") == 1
    assert _count(t, "Middle") == 1
    assert _count(t, "Upper") == 1


# ── differing denominators (borrower vs tract populations differ) ─────────────
def test_borrower_and_tract_denominators_differ():
    """A multifamily/NA-income row with a VALID tract counts in the tract
    denominator but is excluded from the borrower denominator, so the two
    denominators legitimately differ — callers must not difference the LMI%s."""
    df = _frame([
        _row(income=40, tract_pct="40", mfi="100000"),   # classifiable both sides
        _row(income=np.nan, tract_pct="40", mfi="100000"),  # NA income, valid tract
    ])
    result = cra_proxy_distribution(df, by="both")
    bt = _table(result, "borrower")
    tt = _table(result, "tract")
    assert bt.classified_denominator == 1
    assert tt.classified_denominator == 2
    assert bt.classified_denominator != tt.classified_denominator


# ── no composite scalar / score / grade ──────────────────────────────────────
def test_no_composite_scalar():
    df = _frame([_row(income=40, tract_pct="40")])
    result = cra_proxy_distribution(df, by="both")
    banned = {"score", "grade", "rating", "composite", "index", "overall"}
    for obj in [result, *result.tables]:
        attrs = {a.lower() for a in dir(obj) if not a.startswith("_")}
        assert not (attrs & banned), f"composite-scalar-looking attr on {type(obj).__name__}: {attrs & banned}"
    # result is not itself a bare number
    assert not isinstance(result, (int, float))


# ── firewall strings bound to every table ────────────────────────────────────
def test_every_table_carries_caveat_and_no_comparator_line():
    df = _frame([_row(income=40, tract_pct="40", year="2022"),
                 _row(income=40, tract_pct="40", year="2023")])
    result = cra_proxy_distribution(df, by="both", include_purchased=False)
    assert result.tables, "expected at least one table"
    for t in result.tables:
        assert STANDARD_CRA_PROXY_CAVEAT in t.caveat
        assert "no comparator" in t.caveat.lower()
        # share column carries the proxy qualifier so no extracted cell reads as CRA
        assert any("cra_proxy" in c for c in t.distribution.columns)
        # "CRA" never appears in a column without "proxy" adjacent
        for c in t.distribution.columns:
            if "cra" in c.lower():
                assert "cra_proxy" in c.lower()


def test_standard_caveat_content():
    assert "not assessment-area" in STANDARD_CRA_PROXY_CAVEAT.lower()
    assert "performance" in STANDARD_CRA_PROXY_CAVEAT.lower()


# ── multi-year: per-year distributions, each year's MFI applied ──────────────
def test_multi_year_per_year_distributions():
    """Two years with DIFFERENT area medians. income=60k → 2022 (mfi=100k) is
    Moderate (60%); 2023 (mfi=50k) is Upper (120%). Proves each year's MFI is
    applied, never one year's across the panel."""
    df = _frame([
        _row(income=60, mfi="100000", year="2022"),  # 60% → Moderate
        _row(income=60, mfi="50000", year="2023"),   # 120% → Upper
    ])
    result = cra_proxy_distribution(df, by="borrower")
    t22 = _table(result, "borrower", year="2022")
    t23 = _table(result, "borrower", year="2023")
    assert _count(t22, "Moderate") == 1
    assert _count(t22, "Upper") == 0
    assert _count(t23, "Upper") == 1
    assert _count(t23, "Moderate") == 0


# ── universe: originations only; purchased kept separate ─────────────────────
def test_purchased_excluded_by_default():
    df = _frame([
        _row(action=1, tract_pct="40"),
        _row(action=6, tract_pct="40"),  # purchased — must not enter default dist
    ])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert t.classified_denominator == 1


def test_purchased_is_separate_labeled_cut_when_enabled():
    df = _frame([
        _row(action=1, tract_pct="40"),
        _row(action=6, tract_pct="40"),
    ])
    result = cra_proxy_distribution(df, by="tract", include_purchased=True)
    orig = _table(result, "tract", universe="originated")
    purch = _table(result, "tract", universe="purchased")
    assert orig.classified_denominator == 1
    assert purch.classified_denominator == 1
    # never blended
    assert orig.classified_denominator == 1


# ── share sums to 1 over the classified denominator ──────────────────────────
def test_shares_sum_to_one_over_classified_denominator():
    df = _frame([
        _row(tract_pct="40"), _row(tract_pct="60"),
        _row(tract_pct="100"), _row(tract_pct="130"),
        _row(tract_pct="0"),  # excluded, not in share denominator
    ])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    share_col = [c for c in t.distribution.columns if "cra_proxy" in c][0]
    assert t.classified_denominator == 4
    assert t.distribution[share_col].sum() == pytest.approx(1.0)


# ── bundled methodology accessor (travels with the installed tool) ───────────
def test_get_methodology_path_returns_bundled_file():
    p = get_methodology_path()
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    # the firewall + limitations travel with the tool
    assert "PROXY" in text
    assert "assessment-area" in text.lower()


def test_get_methodology_path_missing_raises():
    with pytest.raises(FileNotFoundError):
        get_methodology_path("does_not_exist.md")


# ── Fix 1 (MED-2 + LOW-1): out-of-range clamp — never fabricate a band ────────
# §5: negative / non-finite / above-ceiling(1000) tract pct → excluded, not a band.
def test_tract_special_sentinel_out_of_range_is_excluded_not_upper():
    """A special/underwater-tract sentinel (e.g. 9999.99, above the §5 ceiling of
    1000) must route to the excluded tally, NOT satisfy the >=120 gate as Upper.
    Mutation that bites: remove the out-of-range guard → 9999.99 lands in Upper."""
    df = _frame([_row(tract_pct="9999.99")])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert _count(t, "Upper") == 0
    assert t.excluded.get("out_of_range_tract_pct", 0) == 1


def test_tract_inf_is_excluded():
    df = _frame([_row(tract_pct="inf")])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert t.classified_denominator == 0
    assert t.excluded.get("out_of_range_tract_pct", 0) == 1


def test_tract_negative_is_excluded_not_low():
    """A negative tract pct is outside every band's domain (§4) — it must not
    inflate LMI by landing in Low. Mutation that bites: drop the negative guard
    → -5 passes the <50 gate into Low."""
    df = _frame([_row(tract_pct="-5")])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert _count(t, "Low") == 0
    assert t.excluded.get("out_of_range_tract_pct", 0) == 1


def test_tract_legit_high_still_upper_clamp_does_not_over_exclude():
    """Recon max was ~276; a legitimate high value (450) must still classify as
    Upper — the clamp must not over-exclude real tracts."""
    df = _frame([_row(tract_pct="450")])
    t = _table(cra_proxy_distribution(df, by="tract"), "tract")
    assert _count(t, "Upper") == 1
    assert t.excluded.get("out_of_range_tract_pct", 0) == 0


def test_borrower_negative_income_is_excluded_not_low():
    """Recon: negative income is REAL in the LAR (business loss; 46/60k rows).
    A negative MFI% is outside every band's domain (§4) and must not inflate LMI
    by landing in Low. Mutation that bites: drop the negative guard → -500 →
    negative MFI% passes the <50 gate into Low."""
    df = _frame([_row(income=-500, mfi="100000")])
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Low") == 0
    assert t.excluded.get("out_of_range_income", 0) == 1


def test_borrower_inf_income_is_excluded_not_upper():
    df = _frame([_row(income=np.inf, mfi="100000")])
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Upper") == 0
    assert t.excluded.get("out_of_range_income", 0) == 1


def test_borrower_legit_income_unaffected_by_clamp():
    df = _frame([_row(income=40, mfi="100000")])  # legitimate Low
    t = _table(cra_proxy_distribution(df, by="borrower"), "borrower")
    assert _count(t, "Low") == 1
    assert t.excluded.get("out_of_range_income", 0) == 0


# ── Fix 2 (MED-1): multi-year NA activity_year → unknown_year, never vanish ────
def test_multi_year_na_year_routes_to_unknown_year_not_vanish():
    """The audit repro: a 3-origination multi-year frame with one NA-year row.
    The NA-year row must land in excluded[unknown_year], not silently vanish, so
    per-year denominators + all excluded reconcile to the universe (3). Mutation
    that bites: revert to dropna()-only grouping → the NA row vanishes → total 2."""
    df = _frame([
        _row(tract_pct="40", year="2022"),
        _row(tract_pct="40", year="2023"),
        _row(tract_pct="40", year=np.nan),  # NA-year origination
    ])
    result = cra_proxy_distribution(df, by="tract")
    total = (sum(t.classified_denominator for t in result.tables)
             + sum(sum(t.excluded.values()) for t in result.tables))
    assert total == 3, f"universe not reconciled: {total} != 3"
    unknown_year_total = sum(t.excluded.get("unknown_year", 0) for t in result.tables)
    assert unknown_year_total == 1


def test_single_year_unaffected_by_unknown_year_rule():
    """Single-year mode must be unchanged — no unknown_year table, one None-year
    table, all rows accounted."""
    df = _frame([_row(tract_pct="40"), _row(tract_pct="0")])
    result = cra_proxy_distribution(df, by="tract")
    assert [t.year for t in result.tables] == [None]
    t = result.tables[0]
    assert t.classified_denominator + sum(t.excluded.values()) == 2
    assert "unknown_year" not in t.excluded


# ── Fix 3 (LOW-2): pin the Middle/Upper boundary on BOTH classifiers ──────────
def test_boundary_pin_tract_119_99_middle_120_upper():
    """Pin 119.99→Middle and 120.0→Upper so a future reorder of the assignment
    block cannot silently move the boundary. Mutation that bites: Middle upper
    bound <120 → <=120 AND remove/reorder the Upper overwrite → 120 → Middle."""
    cat, _ = _classify_tract(pd.Series(["119.99", "120"], dtype=object))
    assert list(cat) == ["Middle", "Upper"]


def test_boundary_pin_borrower_119_99_middle_120_upper():
    inc = pd.Series([119.99, 120.0], dtype=float)
    mfi = pd.Series(["100000", "100000"], dtype=object)
    cat, _ = _classify_borrower(inc, mfi)
    assert list(cat) == ["Middle", "Upper"]
