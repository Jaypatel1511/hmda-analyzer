"""The vintage rule: the maps, the UNKNOWN state, the guard, the narrowing.

Every test here asserts a *refusal* or the precise absence of one. There are no
skip markers in this file and there must never be: a test that skips is a test
that passed by not running, and this portfolio has shipped that defect.
"""
import ast
import pathlib

import numpy as np
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
    BASIS_MAP_CONSTANT_NAMES, BASIS_STATUS_CITED, BASIS_STATUS_NO_YEAR_COLUMN,
    BASIS_STATUS_UNKNOWN, COUNTY_BOUNDARY_SCOPE, COUNTY_CODE_BASIS_BY_YEAR,
    DESERT_PERCENTILE_THRESHOLD, DESERT_TRACT_FLOOR, MSA_CODE_BASIS_BY_YEAR,
    TRACT_GEOID_BASIS_BY_YEAR, VINTAGE_COLUMN, VINTAGE_STATUS_COLUMN_BY_KEY,
    _derive_desert_floor, _years_in, basis_year, resolve_geography_vintage,
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

    2024 is the witness, and after the 2024 tract entry was removed it is a
    stronger one than it was: the maps now differ in their DOMAINS, not merely
    in their values. County and MSA carry a cited 2023 basis for 2024; the tract
    key carries no entry at all, because the citation that would establish one
    has not been read. A single collapsed map cannot represent "cited for two
    keys and unknown for the third" at one year — it would have to either invent
    a tract basis or discard two real citations.
    """
    assert 2024 not in TRACT_GEOID_BASIS_BY_YEAR
    assert COUNTY_CODE_BASIS_BY_YEAR[2024] == 2023
    assert MSA_CODE_BASIS_BY_YEAR[2024] == 2023
    assert basis_year("census_tract", 2024) is None
    assert basis_year("county_code", 2024) == 2023


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
    assert basis_year("census_tract", 2025) is None


def test_2024_is_unmapped_in_the_tract_map_and_the_last_tract_entry_is_2023():
    """The removed entry, asserted as removed.

    The 2024 tract entry shipped in build 1 as an uncited 2020, argued from
    continuity of the 2020 decennial DELINEATION. That is the wrong granularity:
    HMDA tract codes follow the FFIEC census file, which adopts a Census
    geography vintage per year. The FFIEC question is open — ffiec.gov returns
    403 to automated fetch — so no entry may stand on it, and the last cited
    tract year is 2023 (methodology §O item 10).
    """
    assert 2024 not in TRACT_GEOID_BASIS_BY_YEAR
    assert max(TRACT_GEOID_BASIS_BY_YEAR) == 2023, (
        "the tract map gained an entry past 2023 without a citation"
    )
    assert max(COUNTY_CODE_BASIS_BY_YEAR) == 2024, "the county map lost its 2024 entry"
    assert max(MSA_CODE_BASIS_BY_YEAR) == 2024, "the MSA map lost its 2024 entry"


def test_removing_the_2024_tract_entry_changed_no_refusal_decision():
    """The measurement the removal was decided on, executed rather than cited.

    Over every distinct year-pair in 2018-2025, the map WITH the uncited 2024
    entry and the map WITHOUT it accept exactly the same pairs, at both guarded
    keys. Removal cost nothing; it only stopped an uncited entry from carrying
    load. If a future edit makes this stop being true, the removal's stated
    justification has stopped being true with it.
    """
    import itertools

    def accepts(tract_map, years, key):
        maps = {"census_tract": tract_map, "county_code": COUNTY_CODE_BASIS_BY_YEAR}
        for map_key in ("census_tract", "county_code") if key == "census_tract" \
                else ("county_code",):
            m = maps[map_key]
            if any(y not in m for y in years) and len(years) > 1:
                return False
            if len({m[y] for y in years if y in m}) > 1:
                return False
        return True

    without = dict(TRACT_GEOID_BASIS_BY_YEAR)
    with_2024 = {**without, 2024: 2020}          # exactly what build 1 shipped
    assert 2024 in with_2024 and 2024 not in without

    pairs = list(itertools.combinations(range(2018, 2026), 2))
    assert len(pairs) == 28
    for key in ("census_tract", "county_code"):
        a = {p for p in pairs if accepts(with_2024, sorted(p), key)}
        b = {p for p in pairs if accepts(without, sorted(p), key)}
        assert a == b, f"{key}: removal changed the verdict on {sorted(a ^ b)}"
        assert len(a) == 7, f"{key}: expected seven accepted pairs, got {len(a)}"


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
    assert "cite it in the comment" in msg
    assert "Do NOT infer it from the data" in msg


def test_the_unmapped_message_names_a_constant_that_actually_exists():
    """The message's only actionable instruction, checked against the module.

    It used to be built as ``f"{map_key.upper()}_BASIS_BY_YEAR"``, so the tract
    case told the reader to edit ``CENSUS_TRACT_BASIS_BY_YEAR`` — a name that
    has never existed in this package. Two of the three keys round-tripped, so
    the arithmetic looked right; the one that mattered did not. The test above
    passed throughout, because it never checked the name.

    This resolves whatever the message names with ``getattr`` on the module, so
    a rename can never leave the message stale again.
    """
    import hmdaanalyzer.geography_vintage as gv

    df = frame((2024, "09110"), (2025, "09110"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    msg = str(exc.value)

    named = [w.strip(".,;:") for w in msg.split() if w.strip(".,;:").endswith("_BY_YEAR")]
    assert named, f"the message names no basis-map constant at all: {msg}"
    for name in named:
        resolved = getattr(gv, name, None)
        assert resolved is not None, (
            f"the refusal message tells the reader to edit {name!r}, which does "
            f"not exist in hmdaanalyzer.geography_vintage. Names that do: "
            f"{sorted(n for n in dir(gv) if n.endswith('_BY_YEAR'))}"
        )
        assert isinstance(resolved, dict) and resolved is not gv.BASIS_MAPS

    # ...and it names the RIGHT one: the map that actually refused.
    assert "TRACT_GEOID_BASIS_BY_YEAR" in named, msg


def test_every_map_constant_name_resolves_and_is_the_map_it_claims():
    """The lookup table behind the message, checked end to end."""
    import hmdaanalyzer.geography_vintage as gv

    assert set(BASIS_MAP_CONSTANT_NAMES) == set(gv.BASIS_MAPS)
    for column, const_name in BASIS_MAP_CONSTANT_NAMES.items():
        assert getattr(gv, const_name) is gv.BASIS_MAPS[column], (
            f"{const_name} is not the map that governs {column}"
        )
    # The arithmetic that produced the defect, shown producing it.
    assert "census_tract".upper() + "_BASIS_BY_YEAR" == "CENSUS_TRACT_BASIS_BY_YEAR"
    assert not hasattr(gv, "CENSUS_TRACT_BASIS_BY_YEAR")


def test_the_message_does_not_send_the_reader_to_a_series_that_stopped():
    """The CFPB *Summary of ... Data* series stops at 2023, which this module's
    own comments record. Sending every reader there as the sole instruction is a
    dead end for exactly the years that can be unmapped."""
    df = frame((2024, "09110"), (2025, "09110"))
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    msg = str(exc.value)
    assert "FFIEC" in msg, (
        "the tract instruction must name the FFIEC census file, which is what "
        "HMDA tract codes actually follow: " + msg
    )
    if "Summary of" in msg:
        assert "does not continue past 2023" in msg, (
            "the message cites the CFPB Summary series without saying it stops: "
            + msg
        )


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
def test_tract_sites_refuse_the_connecticut_case_via_the_unknown_rule(fn):
    """Connecticut 2023+2024, and the mechanism that ACTUALLY refuses it.

    This test asserted a county-map attribution until the uncited 2024 tract
    entry was removed. It now asserts the UNKNOWN rule, because that is what
    fires: ``resolve_geography_vintage`` iterates ``CONSULTED_MAPS`` for the
    unmapped-year check BEFORE it reaches the basis comparison, and 2024 is
    unmapped in the tract map. The frame never reaches the county comparison.

    Asserting the county attribution here would now be asserting a mechanism the
    call does not exercise — a test named for a guarantee it does not provide,
    which is the misdescribed-gate defect this engagement keeps closing. The
    county-consult limb is still real and still the only thing that can catch a
    same-tract-basis county re-scheme; it is exercised by
    ``test_the_county_consult_still_catches_connecticut_if_2024_is_ever_cited``
    below, which is the only remaining way to reach it.
    """
    df = frame((2023, "09001"), (2024, "09110"))
    # Preconditions: 2024 is unmapped for tracts, and the county map does carry
    # a real basis change here — so the refusal could in principle come from
    # either limb, and which one it comes from is the thing under test.
    assert 2024 not in TRACT_GEOID_BASIS_BY_YEAR
    assert COUNTY_CODE_BASIS_BY_YEAR[2023] != COUNTY_CODE_BASIS_BY_YEAR[2024]

    with pytest.raises(GeographyVintageError) as exc:
        fn(df)
    msg = str(exc.value)
    assert "no cited census_tract basis exists" in msg, (
        "the refusal did not attribute itself to the tract map's UNKNOWN rule: "
        + msg
    )
    assert "2024" in msg and "2023" in msg, msg
    assert "A single unmapped year on its own is fine" in msg, msg
    # ...and NOT the basis comparison, which this frame never reaches.
    assert "spans more than one" not in msg, (
        "the frame reached the basis comparison; CONSULTED_MAPS is supposed to "
        "be iterated for the unmapped-year check first: " + msg
    )


@pytest.mark.parametrize(
    "fn",
    [lending_by_tract, lending_desert_score, racial_composition_by_tract,
     lender_summary],
)
def test_the_county_consult_still_catches_connecticut_if_2024_is_ever_cited(
    fn, monkeypatch
):
    """The county-consult limb, exercised — and the ONLY way left to exercise it.

    Removing the uncited 2024 tract entry left no shipped year-pair where the
    tract bases agree and the county bases do not, so the limb that consults the
    county map from the tract key has no live case. It is not dead code and must
    not be deleted: the moment a human reads the FFIEC vintage for 2024 and adds
    a cited tract entry, Connecticut goes back to being invisible to the tract
    map and this limb becomes the only thing standing between a user and a
    silently wrong 2023+2024 tract analysis.

    So the entry is restored for the duration of this test — exactly the value
    build 1 shipped — and the county attribution is asserted. Falsify the
    attribution string in ``resolve_geography_vintage`` and this fails.
    """
    monkeypatch.setitem(TRACT_GEOID_BASIS_BY_YEAR, 2024, 2020)
    assert TRACT_GEOID_BASIS_BY_YEAR[2023] == TRACT_GEOID_BASIS_BY_YEAR[2024] == 2020

    df = frame((2023, "09001"), (2024, "09110"))
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


def test_the_nationwide_county_refusal_prices_itself():
    """The 2023->2024 refusal fires in all 50 states for a cause in one of them.

    Alaska 2023+2024 shares 30 of 30 county keys and 168 of 170 tracts — the
    same ground, both years — and `lending_by_county` refuses anyway, because a
    national key scheme did change. That call stands. What did not stand was the
    message: it printed the shared-key count as evidence, refused, and left the
    user to work out from that count whether their analysis had ever been at
    risk. A refusal a user cannot act on is a refusal they route around.
    """
    df = frame((2023, "51001"), (2024, "51002"))     # Virginia, no CT rows
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_county(df)
    msg = str(exc.value)

    assert "CONNECTICUT-CONFINED" in msg, msg
    assert "only state whose county_code SCHEME changes" in msg, msg
    assert "87 FR 34235" in msg, "the scope claim must carry its citation: " + msg
    # "set" would be false: SD 46017 and TX 48269 each have zero 2024 rows, so
    # their county SETS differ across the boundary with no boundary change.
    assert "county_code set changes" not in msg, (
        "the message claims no other county SET changes, which is measurably "
        "false and falsifiable by a user in one query: " + msg
    )
    # The two real paths, both exact, both named.
    assert "state_code" in msg and "!= 'CT'" in msg, (
        "the message does not give the exclude-and-re-run path: " + msg
    )
    assert "two panels" in msg and "§M5.2 option 1" in msg, (
        "the message does not give the endorsed split-at-the-boundary path: " + msg
    )
    # ...and it does not soften the refusal into a suggestion.
    assert "It is still a refusal, deliberately" in msg, msg


def test_the_scope_note_is_declarative_and_fires_only_at_its_own_boundary():
    """The note is keyed to the boundary it describes, not pasted onto every
    county refusal. A decennial-boundary refusal must not claim Connecticut."""
    assert list(COUNTY_BOUNDARY_SCOPE) == [(2020, 2023)], (
        "a boundary scope note was added; it needs a 50-state measurement "
        "behind it, exactly as the 2020->2023 one has"
    )
    df = frame((2021, "51001"), (2022, "51001"))     # the 2010->2020 boundary
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_county(df)
    msg = str(exc.value)
    assert "county_code basis" in msg
    assert "CONNECTICUT" not in msg.upper(), (
        "the 2010->2020 boundary claimed Connecticut's scope: " + msg
    )


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


# ── B2: a missing or oddly-typed activity_year cell ──────────────────────────
#
# `_years_in` is the guard's only input. Every one of these is a frame the guard
# once read as a *different* frame than the one it was handed.

def test_a_null_activity_year_is_unmapped_and_cannot_be_pooled():
    """NaN is not "no row here" — it is a row whose year nobody knows.

    `_years_in` called `.dropna()` before parsing, so null-year rows were
    invisible to the guard entirely: they were pooled in silently while a
    non-numeric *string* in the same position correctly became None and blocked
    pooling. Two spellings of "this row has no usable year", opposite outcomes.
    """
    known = frame((2023, "09001"))
    unknown = frame((2024, "09110"))
    unknown["activity_year"] = np.nan
    df = pd.concat([known, unknown], ignore_index=True)

    # Precondition: the null rows are really there and really null.
    assert df["activity_year"].isna().sum() == len(unknown)

    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    assert "unparseable" in str(exc.value), str(exc.value)


@pytest.mark.parametrize("null", [np.nan, None, pd.NA, pd.NaT])
def test_every_spelling_of_null_reads_the_same_as_a_corrupt_string(null):
    """A guard whose verdict depends on which null the frame happens to carry is
    a guard a `pd.concat` can turn off."""
    known = frame((2023, "09001"))
    unknown = frame((2024, "09110")).astype({"activity_year": object})
    unknown["activity_year"] = null
    df = pd.concat([known, unknown], ignore_index=True)
    with pytest.raises(GeographyVintageError, match="unparseable"):
        lending_by_tract(df)


def test_a_wholly_null_activity_year_column_is_one_unmapped_year_not_a_refusal():
    """The other half. A single unmapped year is allowed; that is the UNKNOWN
    rule and a null year is an unmapped year, not a special case."""
    df = frame((2023, "09001"))
    df["activity_year"] = np.nan
    out = lending_by_tract(df)
    assert len(out) == 6
    assert VINTAGE_COLUMN not in out.columns


def test_one_blank_year_does_not_disarm_the_guard_by_flipping_the_dtype():
    """The worse half of the same defect, and the one the null fix alone leaves.

    A single blank ``activity_year`` cell is enough to make ``read_csv`` hand
    back ``float64``. Every year then reads ``2021.0``, ``int("2021.0")`` raises,
    EVERY year collapses to None, the Nones dedupe to a single unmapped year, and
    the guard lets a decennial-spanning frame through as a coherent single-year
    analysis. Silent wrong answer, not a refusal — the exact defect this module
    exists to prevent, reached by one empty cell.
    """
    df = frame((2021, "51001"), (2022, "51001"))
    df["activity_year"] = pd.to_numeric(df["activity_year"])
    df.loc[df.index[0], "activity_year"] = np.nan
    assert df["activity_year"].dtype.kind == "f", "the blank cell must force float64"

    with pytest.raises(GeographyVintageError) as exc:
        lending_by_tract(df)
    msg = str(exc.value)
    assert "2021" in msg and "2022" in msg, (
        "the guard did not see the two real years through the float dtype: " + msg
    )


@pytest.mark.parametrize("dtype", ["float64", "Int64", "object", "int64", "string"])
def test_the_guard_sees_the_same_years_whatever_dtype_carries_them(dtype):
    """One frame, five spellings of the same two years. The guard's verdict may
    not depend on which one pandas happened to choose."""
    df = frame((2021, "51001"), (2022, "51001"))
    df["activity_year"] = pd.to_numeric(df["activity_year"]).astype(dtype)
    assert _years_in(df) == [2021, 2022], (dtype, _years_in(df))
    with pytest.raises(GeographyVintageError, match="census_tract basis"):
        lending_by_tract(df)


@pytest.mark.parametrize("dtype", ["float64", "Int64", "object", "int64", "string"])
def test_narrowing_works_whatever_dtype_carries_the_year(dtype):
    """Narrowing compared ``astype(str)`` against ``str(year)``, so a float64
    column offered ``'2021.0'`` where ``'2021'`` was wanted, matched nothing, and
    a perfectly answerable narrowing raised 'selected no rows' — the message
    reserved for a malformed question."""
    df = frame((2021, "51001"), (2022, "51001"))
    df["activity_year"] = pd.to_numeric(df["activity_year"]).astype(dtype)
    out = lending_by_tract(df, vintage=2010)
    assert len(out) == 6
    assert (out[VINTAGE_COLUMN] == 2010).all()
    assert (out["vintage_dropped_rows"] == 24).all()


def test_years_in_maps_every_unusable_cell_to_none():
    """The parser, directly. Its docstring makes a claim about every value that
    is not an integer year; this is that claim, enumerated."""
    unusable = [np.nan, None, pd.NA, pd.NaT, "", "  ", "not-a-year", "20x1",
                float("inf"), float("-inf"), 2021.5, "2021.5", True]
    for v in unusable:
        got = _years_in(pd.DataFrame({"activity_year": [v]}))
        assert got == [None], f"{v!r} parsed to {got}, expected [None]"

    usable = {2021: 2021, "2021": 2021, " 2021 ": 2021, 2021.0: 2021,
              "2021.0": 2021, np.int64(2021): 2021, np.float64(2021.0): 2021}
    for v, want in usable.items():
        got = _years_in(pd.DataFrame({"activity_year": [v]}))
        assert got == [want], f"{v!r} parsed to {got}, expected [{want}]"


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


# ── B3: a tract output is governed by TWO maps and must stamp both ───────────

def test_a_tract_aggregation_stamps_the_county_basis_it_is_also_governed_by():
    """`lending_by_tract` consults two maps and used to stamp one."""
    out = lending_by_tract(frame((2023, "09001")))
    assert out[VINTAGE_COLUMN].eq(2020).all()
    assert "county_code_vintage" in out.columns, (
        "the tract aggregation is governed by the county map — a county-scheme "
        "change is necessarily a tract-key change — and does not say so"
    )
    assert out["county_code_vintage"].eq(2020).all()


def test_reconcatenating_the_two_endorsed_panels_yields_disagreeing_provenance():
    """The endorsed escape route must not produce a self-certifying artefact.

    §M5.2 option 1 sends a user across the Connecticut boundary to two panels.
    Nothing stops them from `pd.concat`-ing those panels afterwards — and when
    the tract output stamped only `tract_geoid_vintage`, both panels carried
    `2020` (truthfully; the tract basis really does agree), so the concatenation
    of two halves the guard had just refused came out labelled coherent by its
    own provenance. The county basis is what disagrees, so the county basis has
    to be on the output.
    """
    a = lending_by_tract(frame((2023, "09001")))
    b = lending_by_tract(frame((2024, "09110")))
    both = pd.concat([a, b], ignore_index=True)

    disagreements = [
        col for col in ("tract_geoid_vintage", "tract_geoid_vintage_status",
                        "county_code_vintage", "county_code_vintage_status")
        if col in both.columns and both[col].nunique(dropna=False) > 1
    ]
    assert disagreements, (
        "two guarded outputs from opposite sides of the boundary agree on every "
        "provenance column. Re-concatenating them produces a frame the guard "
        "refuses, labelled coherent:\n"
        + both.filter(regex="vintage").drop_duplicates().to_string()
    )
    assert "county_code_vintage" in disagreements, (
        "the county basis is the fact that differs across this boundary and it "
        "is not what disagrees: " + str(disagreements)
    )


def test_the_two_panels_disagree_even_when_both_tract_bases_are_cited(monkeypatch):
    """The sharper version of the case above.

    With 2024 unmapped, panel B's tract status is UNKNOWN and the panels visibly
    differ for that reason alone. Restore a cited 2024 tract entry and the tract
    basis genuinely agrees at 2020 on both sides — which is the exact
    configuration build 1 shipped, and the one in which the old single-stamp
    output was indistinguishable from a coherent frame.
    """
    monkeypatch.setitem(TRACT_GEOID_BASIS_BY_YEAR, 2024, 2020)
    a = lending_by_tract(frame((2023, "09001")))
    b = lending_by_tract(frame((2024, "09110")))

    # The premise: the tract stamp alone says these are the same vintage.
    assert a[VINTAGE_COLUMN].eq(2020).all() and b[VINTAGE_COLUMN].eq(2020).all()
    assert a["tract_geoid_vintage_status"].eq("CITED").all()
    assert b["tract_geoid_vintage_status"].eq("CITED").all()

    # ...and the county stamp is what tells the truth about them.
    assert a["county_code_vintage"].eq(2020).all()
    assert b["county_code_vintage"].eq(2023).all()
    both = pd.concat([a, b], ignore_index=True)
    assert both["county_code_vintage"].nunique() == 2

    # The frame that concatenation produces is one the guard refuses.
    with pytest.raises(GeographyVintageError):
        lending_by_tract(frame((2023, "09001"), (2024, "09110")))


# ── B3: UNKNOWN and NO_YEAR_COLUMN are different facts ───────────────────────

def test_unknown_year_and_no_year_column_are_distinguishable_in_the_frame():
    """Two epistemic situations that used to produce byte-identical output.

    "There is a year and nobody has cited its basis" and "there is no year to
    derive a basis from" are different facts, and the only thing separating them
    was the absence of a column — a signal that reaches the artefact and cannot
    be read there.
    """
    unknown = lending_by_tract(frame((2025, "09110")))
    no_year = lending_by_tract(
        frame((2023, "09001")).drop(columns=["activity_year", VINTAGE_COLUMN])
    )
    # The premise: everything else about them is identical.
    assert list(unknown.columns) == list(no_year.columns)
    assert unknown.shape == no_year.shape
    assert VINTAGE_COLUMN not in unknown.columns
    assert VINTAGE_COLUMN not in no_year.columns

    status = VINTAGE_STATUS_COLUMN_BY_KEY["census_tract"]
    assert unknown[status].eq(BASIS_STATUS_UNKNOWN).all()
    assert no_year[status].eq(BASIS_STATUS_NO_YEAR_COLUMN).all()
    assert not unknown[status].equals(no_year[status])


def test_unknown_year_and_no_year_column_are_distinguishable_in_the_dict():
    """The dict channel had the identical defect and needs the identical fix."""
    unknown = lender_summary(frame((2025, "09110")))
    no_year = lender_summary(
        frame((2023, "09001")).drop(columns=["activity_year", VINTAGE_COLUMN])
    )
    assert unknown["census_tract_basis_status"] == BASIS_STATUS_UNKNOWN
    assert no_year["census_tract_basis_status"] == BASIS_STATUS_NO_YEAR_COLUMN
    assert "census_tract_basis_year" not in unknown
    assert "census_tract_basis_year" not in no_year
    assert unknown != no_year


def test_the_status_column_is_always_present_including_when_the_basis_is_cited():
    """A status that appeared only in the unhappy cases would re-create the
    original defect one level up, with its own absence as the signal."""
    for out in (lending_by_tract(frame((2023, "09001"))),
                lending_by_tract(frame((2025, "09110"))),
                lending_by_county(frame((2023, "09001")))):
        present = [c for c in VINTAGE_STATUS_COLUMN_BY_KEY.values()
                   if c in out.columns]
        assert present, f"no status column at all on {list(out.columns)}"
        for col in present:
            assert out[col].map(type).eq(str).all(), (
                f"{col} is not a string column; a nullable numeric would bring "
                f"back the NaN-dtype problem the status exists to avoid"
            )
            assert out[col].isin({BASIS_STATUS_CITED, BASIS_STATUS_UNKNOWN,
                                  BASIS_STATUS_NO_YEAR_COLUMN}).all()
    cited = lending_by_tract(frame((2023, "09001")))
    assert cited[VINTAGE_STATUS_COLUMN_BY_KEY["census_tract"]].eq(
        BASIS_STATUS_CITED).all()


def test_the_status_survives_a_csv_round_trip(tmp_path):
    """It is a string precisely so this holds. A nullable numeric would not."""
    out = lending_by_tract(frame((2025, "09110")))
    path = tmp_path / "out.csv"
    out.to_csv(path, index=False)
    back = pd.read_csv(path)
    col = VINTAGE_STATUS_COLUMN_BY_KEY["census_tract"]
    assert back[col].eq(BASIS_STATUS_UNKNOWN).all()


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


def test_narrowing_that_leaves_an_incoherent_frame_still_refuses(monkeypatch):
    """Narrowing is not an override and cannot be used as one.

    vintage=2020 on a 2022+2023+2024 frame selects all three years by TRACT
    basis — and they still span two COUNTY bases, so it refuses. A narrowing may
    never produce a number that pools two delineations.

    Reaching this at all now requires a 2024 tract entry, which was removed as
    uncited: with 2024 unmapped, vintage=2020 selects only 2022+2023 and the
    result is coherent (see the sibling test below, which pins that as the new
    shipped behaviour). The entry is restored here because the property under
    test — the guard runs AFTER the narrowing — is a property of the code, not
    of the current map contents, and it must not become untested just because
    today's maps happen not to reach it.
    """
    monkeypatch.setitem(TRACT_GEOID_BASIS_BY_YEAR, 2024, 2020)
    df = frame((2022, "09001"), (2023, "09001"), (2024, "09110"))
    with pytest.raises(GeographyVintageError, match="county_code basis"):
        lending_by_tract(df, vintage=2020)


def test_narrowing_past_the_removed_2024_entry_now_answers_instead_of_refusing():
    """The one behaviour change the 2024 removal produced, pinned.

    With the uncited entry gone, ``vintage=2020`` on a 2022+2023+2024 frame
    selects the two years that actually carry a cited 2020 tract basis, drops
    2024, and answers — where build 1 selected all three and then refused on the
    county map. Removal is a net ACCEPT here and costs the user nothing: the
    dropped rows are reported on the returned object, not swallowed.
    """
    df = frame((2022, "09001"), (2023, "09001"), (2024, "09110"))
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df)                       # unnarrowed: still refuses
    out = lending_by_tract(df, vintage=2020)
    assert len(out) == 6                           # 09001's six tracts, both years
    assert (out[VINTAGE_COLUMN] == 2020).all()
    assert (out["vintage_dropped_rows"] == 24).all(), (
        "the 2024 rows must be dropped and REPORTED, not silently absent"
    )


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


def test_the_floor_is_five_at_the_shipped_threshold_and_the_floor_works():
    """The shipped values, pinned — and pinned to each other, not to a literal.

    ``DESERT_TRACT_FLOOR == 5`` is asserted as a CONSEQUENCE of the shipped
    threshold rather than as a free-standing fact, so that moving the threshold
    changes what this test expects instead of leaving it asserting a stale
    number. The old version re-hardcoded 25 in its own body and never read the
    comparison site at all; an injection that moved the site's threshold to 10
    left the floor arithmetically wrong and this file green.
    """
    assert DESERT_PERCENTILE_THRESHOLD == 25, "the shipped threshold moved"
    assert DESERT_TRACT_FLOOR == 5, "the floor derived from 25 is 5"

    out = lending_desert_score(
        frame((2023, "09001"), tracts_per_county=DESERT_TRACT_FLOOR,
              vary_volume=True)
    )
    assert len(out) == DESERT_TRACT_FLOOR
    # 100/n with distinct volumes — the minimum the flag's threshold needs.
    assert out["app_percentile"].min() == pytest.approx(
        round(100 / DESERT_TRACT_FLOOR, 1)
    )


def test_the_floor_is_derived_from_the_threshold_not_chosen():
    """Pins the arithmetic the constant comes from, reading BOTH numbers from
    the module.

    The threshold is not written down here. It was, and that was the defect:
    with 25 re-hardcoded in this body, moving the comparison site's threshold to
    10 left ``DESERT_TRACT_FLOOR`` at 5 — a window in which every frame of 5..10
    tracts returned ``is_lending_desert=False`` for every tract, the exact
    fabricated negative ``UnreachableFlagError`` exists to prevent — and all 176
    tests passed.
    """
    for n in range(1, DESERT_TRACT_FLOOR + 5):
        s = pd.Series(range(1, n + 1))
        reachable = (s.rank(pct=True) * 100).round(1).min() < DESERT_PERCENTILE_THRESHOLD
        assert reachable == (n >= DESERT_TRACT_FLOOR), (
            f"n={n}: reachable={reachable} at threshold "
            f"{DESERT_PERCENTILE_THRESHOLD}, but DESERT_TRACT_FLOOR is "
            f"{DESERT_TRACT_FLOOR}. The floor and the threshold have drifted."
        )


def test_the_derivation_tracks_a_moved_threshold():
    """The floor is a function, so a moved threshold moves the floor.

    Exercises the derivation directly at thresholds the package does not ship,
    because the shipped pair alone cannot distinguish "derived" from "chosen and
    happens to agree".
    """
    assert _derive_desert_floor(DESERT_PERCENTILE_THRESHOLD) == DESERT_TRACT_FLOOR
    assert _derive_desert_floor(25) == 5
    assert _derive_desert_floor(10) == 11      # the injected threshold
    assert _derive_desert_floor(50) == 3
    assert _derive_desert_floor(100) == 2
    for threshold in (5, 10, 25, 33, 50, 100):
        floor = _derive_desert_floor(threshold)
        below = pd.Series(range(1, floor))
        at = pd.Series(range(1, floor + 1))
        assert (below.rank(pct=True) * 100).round(1).min() >= threshold, threshold
        assert (at.rank(pct=True) * 100).round(1).min() < threshold, threshold
    with pytest.raises(ValueError, match="unreachable at any tract count"):
        _derive_desert_floor(0)


def test_the_desert_flag_site_uses_the_same_threshold_as_the_floor():
    """The link the four scattered literals never had.

    ``DESERT_TRACT_FLOOR`` is the point below which the flag is unreachable, so
    AT the floor the flag must be reachable *at the comparison site* — not
    merely in a percentile arithmetic this test recomputes for itself. This runs
    ``lending_desert_score`` at exactly the floor and asserts a tract is
    actually flagged. A comparison site whose threshold has drifted below the
    one the floor was derived from flags nothing here, and this fails.
    """
    out = lending_desert_score(
        frame((2023, "09001"), tracts_per_county=DESERT_TRACT_FLOOR,
              vary_volume=True)
    )
    assert (out["app_percentile"] < DESERT_PERCENTILE_THRESHOLD).any(), (
        f"no tract clears the threshold at n={DESERT_TRACT_FLOOR}, which is the "
        f"floor: the floor and the threshold disagree"
    )
    assert out["is_lending_desert"].any(), (
        f"lending_desert_score flagged NO tract at n={DESERT_TRACT_FLOOR}, the "
        f"floor at which the flag is supposed to become reachable. The site's "
        f"threshold has drifted from DESERT_PERCENTILE_THRESHOLD "
        f"({DESERT_PERCENTILE_THRESHOLD}), and every frame from "
        f"{DESERT_TRACT_FLOOR} tracts upward is now returning fabricated "
        f"negatives with no signal."
    )


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
