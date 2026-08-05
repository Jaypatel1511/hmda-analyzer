"""
The README's "Output columns" table, asserted against what the functions return.

**Why this exists.** ``docs-check.toml`` names this table as its own largest
blind spot, in those words: "Nothing compares that table against what the
functions actually return … that table is where the four vintage provenance
columns and ``limit_truncated`` are documented, so the highest-value table in
this README is one the gate cannot see." It was maintained by hand and re-derived
by a human once per release.

That was survivable while the column sets were stable. It stopped being
survivable in 0.6.0 build 3, which made ``vintage_dropped_rows`` unconditional —
a change that silently invalidated three rows of a table nothing was reading.

**What this asserts.** Exact column lists, in order, for every guarded and
unguarded analysis in the table, plus ``lender_summary``'s dict keys. The lists
are written out in full rather than derived from the functions, because a test
that computes its expectation from the code under test asserts only that the code
equals itself.

Order matters and is asserted. Callers select by name — the CHANGELOG tells them
to — but a reordering is still a change to a documented interface, and catching
it costs nothing here.
"""
import pandas as pd
import pytest

from hmdaanalyzer import (
    denial_rate_by_income_band, denial_rate_by_race, denial_reasons_by_race,
    disparity_ratio, lender_summary, lender_vs_market, lending_by_county,
    lending_by_state, lending_by_tract, lending_desert_score,
    racial_composition_by_tract, top_lenders_by_volume,
)

#: The five provenance fields a guarded frame output carries. All unconditional
#: as of 0.6.0 build 3 — see tests/test_dropped_rows_always_present.py for why
#: the fifth stopped being conditional.
TRACT_PROVENANCE = [
    "tract_geoid_vintage", "tract_geoid_vintage_status",
    "county_code_vintage", "county_code_vintage_status",
    "vintage_dropped_rows",
]
COUNTY_PROVENANCE = [
    "county_code_vintage", "county_code_vintage_status", "vintage_dropped_rows",
]
SUPPRESSION = ["suppressed_groups", "suppressed_applications",
               "suppressed_group_names"]


@pytest.fixture
def df():
    """Eight tracts x two races x two actions — enough tracts to clear
    ``DESERT_TRACT_FLOOR`` and enough rows per race to clear the five-application
    suppression minimum, so every function returns a populated frame."""
    rows = [(t, a) for t in range(8) for a in (1, 3)]
    return pd.DataFrame({
        "activity_year": ["2023"] * len(rows),
        "state_code": ["IL"] * len(rows),
        "county_code": ["17031"] * len(rows),
        "census_tract": [f"1703101{t:04d}" for t, _ in rows],
        "derived_race": ["White" if t % 2 else "Black or African American"
                         for t, _ in rows],
        "action_taken": [a for _, a in rows],
        "is_denied": [a == 3 for _, a in rows],
        "is_approved": [a == 1 for _, a in rows],
        "loan_amount": [200_000.0] * len(rows),
        "income": [80.0] * len(rows),
        "lei": ["LEI0"] * len(rows),
        "denial_reason_1": [1] * len(rows),
    })


EXPECTED = {
    "denial_rate_by_race": (
        lambda d: denial_rate_by_race(d),
        ["derived_race", "applications", "denials", "denial_rate"] + SUPPRESSION,
    ),
    "disparity_ratio": (
        lambda d: disparity_ratio(d, reference="White"),
        ["derived_race", "applications", "denials", "denial_rate"] + SUPPRESSION
        + ["reference_group", "reference_denial_rate", "disparity_ratio",
           "disparity_level"],
    ),
    "denial_rate_by_income_band": (
        lambda d: denial_rate_by_income_band(d),
        ["income_band", "applications", "denials", "denial_rate"],
    ),
    "denial_reasons_by_race": (
        lambda d: denial_reasons_by_race(d),
        ["derived_race", "denial_reason_label", "count", "total", "pct"],
    ),
    "lending_by_tract": (
        lambda d: lending_by_tract(d),
        ["census_tract", "applications", "denials", "originations",
         "avg_loan_amount", "median_income", "denial_rate", "origination_rate"]
        + TRACT_PROVENANCE,
    ),
    "lending_by_county": (
        lambda d: lending_by_county(d),
        ["county_code", "applications", "denials", "originations",
         "total_loan_volume", "avg_loan_amount", "denial_rate", "state_code"]
        + COUNTY_PROVENANCE,
    ),
    "lending_by_state": (
        lambda d: lending_by_state(d),
        # No provenance: this site is deliberately unguarded (state_code gets no
        # basis map because nothing was measured to move a state code).
        ["state_code", "applications", "denials", "originations",
         "total_volume", "denial_rate"],
    ),
    "lending_desert_score": (
        lambda d: lending_desert_score(d),
        ["census_tract", "applications", "denials", "originations",
         "avg_loan_amount", "median_income", "denial_rate", "origination_rate"]
        + TRACT_PROVENANCE
        + ["app_percentile", "desert_score", "is_lending_desert"],
    ),
    "racial_composition_by_tract": (
        lambda d: racial_composition_by_tract(d),
        ["census_tract", "derived_race", "applications", "denial_rate"]
        + TRACT_PROVENANCE,
    ),
    "lender_vs_market": (
        lambda d: lender_vs_market(d, "LEI0"),
        ["derived_race", "lender_applications", "lender_denials",
         "lender_denial_rate"]
        + [f"lender_{c}" for c in SUPPRESSION]
        + ["market_denial_rate"]
        + [f"market_{c}" for c in SUPPRESSION]
        + ["vs_market", "vs_market_pct"],
    ),
    "top_lenders_by_volume": (
        lambda d: top_lenders_by_volume(d),
        ["lei", "originations", "total_volume", "avg_loan"],
    ),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_output_columns_match_the_readme_table(name, df):
    fn, expected = EXPECTED[name]
    got = list(fn(df).columns)
    assert got == expected, (
        f"{name} returns different columns from the README table.\n"
        f"  expected: {expected}\n"
        f"  got:      {got}\n"
        f"  missing:  {[c for c in expected if c not in got]}\n"
        f"  extra:    {[c for c in got if c not in expected]}"
    )


def test_lender_summary_keys_match_the_readme(df):
    """``lender_summary`` returns a dict and carries provenance as keys. The
    README documents them as ``census_tract_basis_year``,
    ``census_tract_basis_status``, ``county_code_basis_year``,
    ``county_code_basis_status`` and ``dropped_rows_by_year``."""
    assert list(lender_summary(df)) == [
        "census_tract_basis_year", "census_tract_basis_status",
        "county_code_basis_year", "county_code_basis_status",
        "dropped_rows_by_year",
        "total_applications", "originations", "denials", "approval_rate",
        "denial_rate", "avg_loan_amount", "median_loan_amount",
        "avg_applicant_income", "unique_tracts", "unique_counties",
    ]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_the_readme_table_actually_lists_these_columns(name, df):
    """The other direction: the expectations above have to match the README, or
    this file pins a table that has drifted from the document it describes.

    Checked by membership rather than by parsing rows, because two rows refer to
    another row's columns by reference ("everything ``lending_by_tract``
    returns, plus …") and resolving that is more likely to be wrong than the
    table is.

    The ``lender_vs_market`` row used to read ``lender_suppressed_*`` (3). That
    shorthand is unresolvable without knowing which three, so the row was
    expanded rather than this test taught to accept a wildcard — a documentation
    test that accepts shorthand is a test for the shorthand."""
    from pathlib import Path

    # Located from THIS FILE, not from the installed package — under the sdist
    # smoke test the package is in site-packages and the README is not, and
    # resolving it from the package made these eleven assertions skip silently.
    # A skip is not a pass; asserted rather than skipped for that reason.
    readme = Path(__file__).resolve().parent.parent / "README.md"
    assert readme.exists(), (
        f"README.md not found at {readme}. This test reads it deliberately; fix "
        f"the path rather than skipping."
    )
    text = readme.read_text(encoding="utf-8")
    section = text[text.index("### Output columns"):]
    section = section[:section.index("\n---")]

    assert f"`{name}`" in section, f"{name} has no row in the README table"
    _, expected = EXPECTED[name]
    for column in expected:
        assert f"`{column}`" in section, (
            f"the README's Output columns table does not mention {column!r}, "
            f"which {name} returns"
        )
