"""The vintage rule: the maps, the UNKNOWN state, the guard, the narrowing.

Every test here asserts a *refusal* or the precise absence of one. There are no
skip markers in this file and there must never be: a test that skips is a test
that passed by not running, and this portfolio has shipped that defect.
"""
import ast
import pathlib

import pandas as pd
import pytest

from hmdaanalyzer.analysis.geographic import (
    lending_by_county, lending_by_state, lending_by_tract,
    lending_desert_score, racial_composition_by_tract,
)
from hmdaanalyzer.analysis.lender import lender_summary
from hmdaanalyzer.data.loader import _clean, _validate_lar_schema
from hmdaanalyzer.data.schema import (
    DERIVED_LAR_COLUMNS, EXPECTED_LAR_COLUMNS, RAW_LAR_COLUMNS,
)
from hmdaanalyzer.exceptions import (
    GeographyVintageError, SchemaValidationError, UnreachableFlagError,
)
from hmdaanalyzer.geography_vintage import (
    COUNTY_CODE_BASIS_BY_YEAR, DESERT_TRACT_FLOOR, MSA_CODE_BASIS_BY_YEAR,
    TRACT_GEOID_BASIS_BY_YEAR, VINTAGE_COLUMN, basis_year,
    resolve_geography_vintage,
)


def frame(*year_specs, tracts_per_county=6, vary_volume=False):
    """Build a LAR-shaped frame.

    ``year_specs`` are ``(year, county_code)`` pairs. Tract GEOIDs are built the
    way the LAR builds them — county code as the first five digits — so a county
    renumbering renumbers every tract, which is the Connecticut mechanism.

    Volumes are equal across tracts by default, which makes every
    ``rank(pct=True)`` a tie. ``vary_volume=True`` gives each tract a distinct
    application count, which is what a percentile floor has to be measured
    against.
    """
    rows = []
    for year, county in year_specs:
        for t in range(tracts_per_county):
            for rep in range(4 + (t if vary_volume else 0)):
                rows.append({
                    "activity_year": str(year),
                    "county_code": county,
                    "census_tract": f"{county}{100100 + t * 100}",
                    "state_code": county[:2],
                    "derived_msa_md": "12345",
                    "action_taken": 3 if rep == 0 else 1,
                    "derived_race": "White" if rep % 2 else "Asian",
                    "loan_amount": 200000 + rep * 1000,
                    "income": 80 + rep,
                    "lei": "LEI000001",
                })
    df = pd.DataFrame(rows)
    df["action_taken"] = df["action_taken"].astype("Int64")
    return _clean(df)


# ── B1: the maps ─────────────────────────────────────────────────────────────

def test_maps_are_plain_int_basis_years():
    """Not an enum, not a string, not a Categorical, not a boolean threshold."""
    for name, m in (("tract", TRACT_GEOID_BASIS_BY_YEAR),
                    ("county", COUNTY_CODE_BASIS_BY_YEAR),
                    ("msa", MSA_CODE_BASIS_BY_YEAR)):
        assert m, f"{name} map is empty"
        for year, basis in m.items():
            assert type(year) is int, f"{name}[{year!r}] key is {type(year)}"
            assert type(basis) is int, f"{name}[{year}] value is {type(basis)}"


def test_the_three_maps_are_not_collapsible_into_one():
    """A single 'geography basis year' would be wrong for at least one key.

    2024 is the witness: the tract delineation basis is unchanged at 2020 while
    the county and MSA bases move to 2023. Collapsing the maps would erase the
    Connecticut catch entirely.
    """
    assert TRACT_GEOID_BASIS_BY_YEAR[2024] == 2020
    assert COUNTY_CODE_BASIS_BY_YEAR[2024] == 2023
    assert MSA_CODE_BASIS_BY_YEAR[2024] == 2023
    assert TRACT_GEOID_BASIS_BY_YEAR[2024] != COUNTY_CODE_BASIS_BY_YEAR[2024]


def test_the_decennial_boundary_is_where_the_measurements_put_it():
    assert TRACT_GEOID_BASIS_BY_YEAR[2021] == 2010
    assert TRACT_GEOID_BASIS_BY_YEAR[2022] == 2020
    assert COUNTY_CODE_BASIS_BY_YEAR[2021] == 2010
    assert COUNTY_CODE_BASIS_BY_YEAR[2022] == 2020


def test_2025_is_unmapped_in_every_map():
    """The load-bearing case, and it is present tense, not future tense.

    The 2025 data year is already served by the CFPB API. No citation for its
    basis exists — the CFPB *Summary of ... Data* series stops at 2023 — so 2025
    is UNKNOWN in all three maps. Adding an entry here because the measurements
    "are consistent with" 2020 is precisely the inference the rule exists to
    prevent (methodology §M1.3).
    """
    for m in (TRACT_GEOID_BASIS_BY_YEAR, COUNTY_CODE_BASIS_BY_YEAR,
              MSA_CODE_BASIS_BY_YEAR):
        assert 2025 not in m
        assert max(m) == 2024, "a map gained an entry past 2024 without a citation"
    assert basis_year("census_tract", 2025) is None


def test_every_map_entry_carries_a_citation_comment():
    """The maps are a decision record, not a lookup table.

    Asserts each map's source block is commented at least as densely as it has
    entries, so an entry cannot be appended without a human writing down where it
    came from.
    """
    src = pathlib.Path(
        __import__("hmdaanalyzer").geography_vintage.__file__
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    for map_name, mapping in (("TRACT_GEOID_BASIS_BY_YEAR", TRACT_GEOID_BASIS_BY_YEAR),
                              ("COUNTY_CODE_BASIS_BY_YEAR", COUNTY_CODE_BASIS_BY_YEAR),
                              ("MSA_CODE_BASIS_BY_YEAR", MSA_CODE_BASIS_BY_YEAR)):
        node = next(
            n for n in tree.body
            if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == map_name
        )
        body = lines[node.lineno - 1:node.end_lineno]
        comments = [ln for ln in body if ln.strip().startswith("#")]
        assert len(comments) >= len(mapping), (
            f"{map_name} has {len(mapping)} entries but only {len(comments)} "
            f"comment lines — an entry was added without its citation."
        )


# ── B1: the UNKNOWN rule ─────────────────────────────────────────────────────

def test_unmapped_year_alone_is_allowed():
    """A 2025-only tract analysis is exactly as coherent as a 2023-only one.

    Refusing it would assert a problem that does not exist, and would be the
    same false-refusal shape the methodology rejects a load-time raise for.
    """
    df = frame((2025, "09110"))
    out = lending_by_tract(df)
    assert len(out) == 6
    # No basis can be asserted, so no basis is written. The column's ABSENCE is
    # the signal; writing a guess would be the defect itself.
    assert VINTAGE_COLUMN not in out.columns


def test_unmapped_year_pooled_with_any_other_year_raises():
    df = frame((2024, "09110"), (2025, "09110"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    assert "2025" in str(exc.value)
    assert "no cited" in str(exc.value)


def test_unmapped_year_pooled_with_another_unmapped_year_also_raises():
    """'Pooled with any other year' means any — two unknowns are not a match."""
    df = frame((2025, "09110"), (2026, "09110"))
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df)


def test_the_unmapped_message_says_a_human_must_add_a_citation():
    df = frame((2024, "09110"), (2025, "09110"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    msg = str(exc.value)
    assert "Summary of" in msg and "cite it in the comment" in msg
    assert "Do NOT infer it from the data" in msg


# ── B2: the guard, at all six sites ──────────────────────────────────────────

@pytest.mark.parametrize(
    "fn",
    [lending_by_tract, lending_desert_score, racial_composition_by_tract,
     lender_summary, lending_by_county],
)
def test_every_guarded_function_refuses_a_decennial_spanning_frame(fn):
    """2021+2022: both the tract basis and the county basis change."""
    df = frame((2021, "51001"), (2022, "51001"))
    with pytest.raises(GeographyVintageError):
        fn(df)


@pytest.mark.parametrize(
    "fn",
    [lending_by_tract, lending_desert_score, racial_composition_by_tract,
     lender_summary],
)
def test_tract_sites_refuse_the_connecticut_case_via_the_county_map(fn):
    """The case the tract map alone cannot see.

    CT 2023 and CT 2024 are BOTH tract basis 2020 — same delineation — while
    every tract GEOID changes, because the planning-region switch renumbers every
    county prefix and the county prefix is the tract GEOID's first five digits.
    A tract-basis comparison reports "same vintage" and lets it through.

    This test is the regression: it asserts the refusal happens AND that it is
    attributed to the county map, because a refusal arriving for the wrong reason
    would pass a weaker assertion while leaving the real hole open.
    """
    df = frame((2023, "09001"), (2024, "09110"))
    # Precondition: the tract map genuinely cannot see this.
    assert TRACT_GEOID_BASIS_BY_YEAR[2023] == TRACT_GEOID_BASIS_BY_YEAR[2024] == 2020
    with pytest.raises(GeographyVintageError) as exc:
        fn(df)
    msg = str(exc.value)
    assert "county_code basis" in msg, msg
    assert "first five digits" in msg, (
        "the refusal did not attribute itself to the county map: " + msg
    )


def test_the_refusal_names_the_function_the_caller_actually_called():
    """`lending_desert_score` inherits its guard from `lending_by_tract`, and a
    message naming a function the user never called is a message about the wrong
    function (§M3.1 item 1)."""
    df = frame((2021, "51001"), (2022, "51001"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_desert_score(df)
    assert str(exc.value).startswith("lending_desert_score refused"), str(exc.value)

    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    assert str(exc.value).startswith("lending_by_tract refused")


def test_connecticut_has_no_county_present_on_both_sides():
    """Why a per-county key comparison would never have fired at all.

    Every legacy county vanishes and every planning region appears, so there is
    nothing for an intersection test to compare. The declarative county map is
    what catches this; a measured disjointness check contributes nothing.
    """
    df = frame((2023, "09001"), (2024, "09110"))
    a = set(df[df.activity_year == "2023"]["county_code"].dropna())
    b = set(df[df.activity_year == "2024"]["county_code"].dropna())
    assert a and b and not (a & b)


def test_same_basis_years_pool_silently():
    """Over-refusing is its own defect."""
    df = frame((2022, "09001"), (2023, "09001"))
    out = lending_by_tract(df)
    assert len(out) == 6
    assert (out[VINTAGE_COLUMN] == 2020).all()


def test_a_frame_whose_counties_all_change_but_whose_bases_agree_is_NOT_refused():
    """The hand-concatenated VA-2022 + OH-2023 shape.

    Every county vanishes and every county appears — the same *shape* as
    Connecticut — and it must not raise, because 2022 and 2023 share both bases
    and the analysis is coherent. The rule distinguishes the two on a citation
    instead of on a shape, which is the whole argument for a declarative limb.
    """
    df = frame((2022, "51001"), (2023, "39035"))
    out = lending_by_tract(df)
    assert len(out) == 12
    assert (out[VINTAGE_COLUMN] == 2020).all()


def test_state_site_is_enumerated_but_unguarded():
    """Documented exposure, asserted so it cannot become accidental coverage."""
    df = frame((2021, "51001"), (2022, "51001"))
    out = lending_by_state(df)          # spans a tract AND county boundary
    assert len(out) == 1                # ...and does not raise, by decision


# ── B2/B3: the guard's mechanism is activity_year, never the column ──────────

def test_dropping_the_provenance_column_does_not_defeat_the_guard():
    """The column is provenance, not mechanism.

    `.agg()` drops it, `pd.concat` with a frame lacking it yields silent NaN, and
    a user can delete it. None of that may disarm the rule.
    """
    df = frame((2021, "51001"), (2022, "51001")).drop(columns=[VINTAGE_COLUMN])
    assert VINTAGE_COLUMN not in df.columns
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df)


def test_a_falsified_provenance_column_does_not_defeat_the_guard():
    df = frame((2021, "51001"), (2022, "51001"))
    df[VINTAGE_COLUMN] = 2020           # a user "fixes" the column
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df)


def test_agg_drops_the_column_which_is_why_the_helper_reattaches_it():
    """Pins the pandas behaviour the re-attachment exists for."""
    df = frame((2023, "09001"))
    assert VINTAGE_COLUMN in df.columns
    bare = (df[df["action_taken"].isin([1, 2, 3])]
            .groupby("census_tract")
            .agg(applications=("is_denied", "count"))
            .reset_index())
    assert VINTAGE_COLUMN not in bare.columns, "pandas .agg() kept the column"
    assert VINTAGE_COLUMN in lending_by_tract(df).columns


def test_frame_with_no_activity_year_is_not_refused_and_claims_no_basis():
    """`load_from_file` accepts an arbitrary CSV and asserts no year column.

    The guard cannot fire, and it says so by omitting the provenance rather than
    asserting a basis it cannot know. Refusing here would refuse a single-year
    CSV that was always correct (coverage item 9).
    """
    df = frame((2023, "09001")).drop(columns=["activity_year", VINTAGE_COLUMN])
    out = lending_by_tract(df)
    assert len(out) == 6
    assert VINTAGE_COLUMN not in out.columns


def test_narrowing_a_frame_with_no_activity_year_raises():
    """A `vintage=` request on such a frame IS unanswerable."""
    df = frame((2023, "09001")).drop(columns=["activity_year", VINTAGE_COLUMN])
    with pytest.raises(GeographyVintageError, match="no 'activity_year' column"):
        lending_by_tract(df, vintage=2020)


# ── B3: the provenance column and the schema split ───────────────────────────

def test_clean_derives_the_provenance_column_as_a_plain_int():
    df = frame((2023, "09001"))
    assert df[VINTAGE_COLUMN].dtype.kind == "i"
    assert set(df[VINTAGE_COLUMN]) == {2020}


def test_provenance_is_nan_for_an_unmapped_year_rather_than_guessed():
    df = frame((2025, "09110"))
    assert df[VINTAGE_COLUMN].isna().all()


def test_schema_guard_tolerates_derived_columns_and_still_catches_cfpb_drift():
    """The split, and why it had to happen (§M4.4 option 3).

    Before it, `_validate_lar_schema` compared strict two-way set equality
    against a set containing our derived names, so adding `tract_geoid_vintage`
    in `_clean` made EVERY `load_range` call raise on the first year it fetched.
    """
    ok = pd.DataFrame({c: pd.Series(dtype=object) for c in sorted(RAW_LAR_COLUMNS)})
    for derived in sorted(DERIVED_LAR_COLUMNS):
        ok[derived] = pd.Series(dtype=object)
    _validate_lar_schema(ok, 2023)      # must not raise

    # The unsplit comparison, run inline on the same frame, to show what the
    # split fixed rather than asserting it from memory.
    unsplit_unexpected = set(ok.columns) - RAW_LAR_COLUMNS
    assert unsplit_unexpected == set(DERIVED_LAR_COLUMNS)

    drifted = ok.copy()
    drifted["a_new_cfpb_column"] = pd.Series(dtype=object)
    with pytest.raises(SchemaValidationError, match="a_new_cfpb_column"):
        _validate_lar_schema(drifted, 2023)

    missing = ok.drop(columns=["income"])
    with pytest.raises(SchemaValidationError, match="income"):
        _validate_lar_schema(missing, 2023)


def test_expected_lar_columns_is_the_union_and_stays_importable():
    assert EXPECTED_LAR_COLUMNS == RAW_LAR_COLUMNS | DERIVED_LAR_COLUMNS
    assert VINTAGE_COLUMN in DERIVED_LAR_COLUMNS
    assert VINTAGE_COLUMN not in RAW_LAR_COLUMNS
    assert len(RAW_LAR_COLUMNS) == 99, "the raw CFPB header is 99 columns, 2018-2025"


def test_county_site_provenance_names_the_county_key_not_the_tract_one():
    df = frame((2023, "09001"))
    out = lending_by_county(df)
    assert "county_code_vintage" in out.columns
    assert VINTAGE_COLUMN not in out.columns, (
        "a county aggregation must not assert a tract fact about its rows"
    )


def test_lender_summary_carries_provenance_as_dict_keys():
    """A dict cannot carry a column, so provenance rides as explicit keys."""
    out = lender_summary(frame((2023, "09001")))
    assert out["census_tract_basis_year"] == 2020
    assert out["county_code_basis_year"] == 2020


def test_lender_summary_still_returns_empty_dict_for_a_legitimately_empty_frame():
    """`{}` is documented as a legitimate empty result and must stay one."""
    df = frame((2023, "09001"))
    assert lender_summary(df[df["lei"] == "NOPE"]) == {}


# ── B4: the narrowing parameter ──────────────────────────────────────────────

def test_narrowing_selects_a_coherent_subset_instead_of_refusing():
    df = frame((2021, "51001"), (2022, "51001"))
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df)
    out = lending_by_tract(df, vintage=2020)
    assert len(out) == 6
    assert (out[VINTAGE_COLUMN] == 2020).all()


def test_narrowing_reports_the_dropped_rows_on_the_returned_object():
    """Not via print and not via warnings.warn — both die on notebook re-run and
    neither reaches the artefact that outlives the session (§M3.3a)."""
    df = frame((2021, "51001"), (2022, "51001"))
    out = lending_by_tract(df, vintage=2020)
    assert "vintage_dropped_rows" in out.columns
    assert (out["vintage_dropped_rows"] == 24).all()


def test_narrowing_that_selects_no_rows_raises_rather_than_returning_empty():
    """The empty case collides head-on with this package's own philosophy.

    `exceptions.py` holds that an empty result can never silently read as "no
    disparity". A narrowing that names a basis not in the frame is a malformed
    question, and the answer is not "nothing here".
    """
    df = frame((2022, "51001"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df, vintage=2010)
    assert "selected no rows" in str(exc.value)
    assert "bases present" in str(exc.value)


def test_narrowing_that_leaves_an_incoherent_frame_still_refuses():
    """Narrowing is not an override and cannot be used as one.

    vintage=2020 on a 2022+2023+2024 frame selects all three years by TRACT
    basis — and they still span two COUNTY bases, so it refuses. A narrowing may
    never produce a number that pools two delineations.
    """
    df = frame((2022, "09001"), (2023, "09001"), (2024, "09110"))
    with pytest.raises(GeographyVintageError, match="county_code basis"):
        lending_by_tract(df, vintage=2020)


def test_narrowing_is_on_the_aggregation_functions_not_on_load_range():
    """The load contract stays intact and the user keeps all their years."""
    import inspect
    from hmdaanalyzer.data.loader import load_range
    assert "vintage" not in inspect.signature(load_range).parameters
    for fn in (lending_by_tract, lending_by_county, lending_desert_score,
               racial_composition_by_tract, lender_summary):
        assert "vintage" in inspect.signature(fn).parameters, fn.__name__


# ── B4: the five-tract desert floor ──────────────────────────────────────────

@pytest.mark.parametrize("n_tracts", [1, 2, 3, 4])
def test_desert_flag_is_unreachable_below_five_tracts_so_it_raises(n_tracts):
    """`rank(pct=True)` has minimum 100/n; the flag needs < 25.

    Returning is_lending_desert=False for every tract here is a fabricated
    negative, not a finding that the tracts were examined and cleared.
    """
    df = frame((2023, "09001"), tracts_per_county=n_tracts)
    with pytest.raises(UnreachableFlagError) as exc:
        lending_desert_score(df)
    assert "ARITHMETICALLY UNREACHABLE" in str(exc.value)
    assert f"{100 / n_tracts:.1f}" in str(exc.value)


def test_the_floor_is_exactly_five_and_five_works():
    assert DESERT_TRACT_FLOOR == 5
    out = lending_desert_score(
        frame((2023, "09001"), tracts_per_county=5, vary_volume=True)
    )
    assert len(out) == 5
    # 100/n with distinct volumes — the minimum the flag's < 25 threshold needs.
    assert out["app_percentile"].min() == pytest.approx(20.0)
    assert (out["app_percentile"] < 25).any(), "the flag became unreachable at n=5"


def test_the_floor_is_derived_from_the_threshold_not_chosen():
    """Pins the arithmetic the constant comes from, so a future edit that moves
    the `app_percentile < 25` threshold cannot leave the floor silently wrong."""
    for n in range(1, 9):
        s = pd.Series(range(1, n + 1))
        reachable = (s.rank(pct=True) * 100).round(1).min() < 25
        assert reachable == (n >= DESERT_TRACT_FLOOR), n


def test_ties_only_raise_the_minimum_percentile_so_the_floor_holds():
    """The floor is claimed to hold unconditionally; ties are the way that could
    fail, so it is checked rather than asserted."""
    for n in range(1, 9):
        tied = pd.Series([7] * n)
        distinct = pd.Series(range(1, n + 1))
        assert (tied.rank(pct=True) * 100).min() >= (distinct.rank(pct=True) * 100).min()


# ── The helper is one helper ─────────────────────────────────────────────────

def test_the_guard_rejects_a_key_it_has_no_map_for():
    df = frame((2023, "09001"))
    with pytest.raises(ValueError, match="no basis map"):
        resolve_geography_vintage(df, key="state_code", fn_name="x")
