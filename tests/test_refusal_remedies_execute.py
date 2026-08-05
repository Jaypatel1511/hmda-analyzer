"""
Every remedy a refusal message offers must clear the refusal that printed it.

**Why this file exists.** Through the 0.6.0 build, the `GeographyVintageError`
message for the 2023→2024 county boundary offered "Exclude Connecticut and
re-run: ``df[df['state_code'] != 'CT']``". So did the README, the CHANGELOG's
upgrade table and the shipped methodology document. It does not work, and it
never could: ``resolve_geography_vintage`` compares the frame's YEAR SET against
the basis maps and never inspects ``state_code`` or ``county_code``, so no row
filter changes the verdict. On a CT+IL 2023+2024 frame, after dropping every
Connecticut row, ``lending_by_county`` still refuses (spans two ``county_code``
bases) and ``lending_by_tract`` still refuses (pools 2024, unmapped for tracts).

It reached a release candidate because nothing executed it. The README block that
carried it is ``# docs-check: skip``, so the gate extracted its symbols and never
ran it; the one test that touched the message asserted the broken remedy was
**present**, which meant removing it would have broken the suite.

Making the guard honour the remedy was not an option: methodology coverage item
19 rejected state-scoping the county map precisely because a verdict that
depends on which rows a frame contains lets a user disarm the guard by
subsetting. The remedy was incompatible with the design from the outset, so it
was deleted rather than implemented.

**What this file asserts.** Not that the text is right — that the remedies RUN.
Each replacement remedy is executed against the exact frame that triggers the
refusal, on both guarded call paths, and must return a result.
"""
import pandas as pd
import pytest

from hmdaanalyzer import GeographyVintageError
from hmdaanalyzer.analysis.geographic import lending_by_county, lending_by_tract


def _ct_plus_il_across_the_boundary():
    """A CT + IL frame spanning 2023 and 2024 — the frame the Connecticut
    planning-region boundary refusal is about.

    Connecticut's 2023 rows carry legacy county ``09001``; its 2024 rows carry
    planning region ``09110``. Illinois (``17031``, Cook County) is unchanged
    across the boundary and is what makes the "your rows are unaffected"
    temptation concrete.
    """
    rows = [
        ("2023", "CT", "09001", "09001010100"),
        ("2023", "IL", "17031", "17031010100"),
        ("2023", "IL", "17031", "17031010200"),
        ("2024", "CT", "09110", "09110010100"),
        ("2024", "IL", "17031", "17031010100"),
        ("2024", "IL", "17031", "17031010200"),
    ]
    n = len(rows)
    return pd.DataFrame({
        "activity_year": [r[0] for r in rows],
        "state_code": [r[1] for r in rows],
        "county_code": [r[2] for r in rows],
        "census_tract": [r[3] for r in rows],
        "derived_race": ["White"] * n,
        "action_taken": [1, 3, 1, 1, 3, 1],
        "is_denied": [False, True, False, False, True, False],
        "is_approved": [True, False, True, True, False, True],
        "loan_amount": [200_000.0] * n,
        "income": [80.0] * n,
    })


GUARDED = [("lending_by_county", lending_by_county),
           ("lending_by_tract", lending_by_tract)]


# --------------------------------------------------------------------------- #
# The premise: both call paths refuse this frame.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,fn", GUARDED, ids=[g[0] for g in GUARDED])
def test_the_frame_is_refused_to_begin_with(name, fn):
    with pytest.raises(GeographyVintageError):
        fn(_ct_plus_il_across_the_boundary())


# --------------------------------------------------------------------------- #
# The deleted remedy: filtering does NOT clear it. Pinned so the text cannot
# come back without this failing.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,fn", GUARDED, ids=[g[0] for g in GUARDED])
def test_excluding_connecticut_does_not_clear_the_refusal(name, fn):
    """The removed remedy, executed. This is the measurement the 0.6.0 text was
    shipped without."""
    df = _ct_plus_il_across_the_boundary()
    clean = df[df["state_code"] != "CT"]
    assert len(clean) == 4 and (clean["state_code"] == "CT").sum() == 0

    with pytest.raises(GeographyVintageError):
        fn(clean)


@pytest.mark.parametrize("name,fn", GUARDED, ids=[g[0] for g in GUARDED])
def test_the_county_prefix_form_does_not_clear_it_either(name, fn):
    """The second form the old text offered, for a frame with no state column."""
    df = _ct_plus_il_across_the_boundary()
    clean = df[~df["county_code"].astype(str).str.startswith("09")]
    assert len(clean) == 4

    with pytest.raises(GeographyVintageError):
        fn(clean)


def test_filtering_is_inert_because_the_verdict_is_on_years_not_rows():
    """The mechanism, asserted directly rather than inferred from the outcome:
    the VERDICT for the filtered frame is the same one as for the full frame.

    Only the verdict line is compared, and the reason is worth recording. The
    message also carries an overlap-context line describing how many keys the
    frame's years share, and that line IS row-dependent — filtering Connecticut
    out moves it from "1 of 1 county_code keys ... 100.0%" to "1 of 3 ...
    66.7%". So a user who tries the removed remedy sees the numbers in the
    message change while the refusal stays exactly the same, which is a fair
    description of why the remedy looked plausible enough to ship four times.
    The verdict — which bases, which years, refuse — does not move.
    """
    df = _ct_plus_il_across_the_boundary()
    with pytest.raises(GeographyVintageError) as full:
        lending_by_county(df)
    with pytest.raises(GeographyVintageError) as filtered:
        lending_by_county(df[df["state_code"] != "CT"])

    full_verdict = str(full.value).splitlines()[0]
    filtered_verdict = str(filtered.value).splitlines()[0]
    assert full_verdict == filtered_verdict, (
        "removing every Connecticut row changed the verdict, so it is reading "
        f"rows after all:\n  full:     {full_verdict}\n  filtered: {filtered_verdict}"
    )
    assert "spans more than one county_code basis" in full_verdict

    # ...and the row-dependent part really is row-dependent, so the test above
    # is comparing the line that matters rather than one that cannot change.
    assert str(full.value) != str(filtered.value), (
        "the whole message is row-invariant, so splitting out the verdict line "
        "is asserting nothing — re-check what _overlap_context reports"
    )


# --------------------------------------------------------------------------- #
# Replacement remedy (a): split at the boundary into two panels.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,fn", GUARDED, ids=[g[0] for g in GUARDED])
@pytest.mark.parametrize("year", ["2023", "2024"])
def test_splitting_at_the_boundary_works(name, fn, year):
    """§M5.2 option 1, the endorsed path. Both panels, both call paths."""
    df = _ct_plus_il_across_the_boundary()
    panel = df[df["activity_year"] == year]
    out = fn(panel)
    assert not out.empty, f"{name} returned nothing for the {year} panel"


def test_the_split_keeps_connecticut_in_which_is_the_point_of_endorsing_it():
    """The reason this is the endorsed path rather than merely a working one:
    unlike a row filter it discards no jurisdiction, so neither panel is a
    non-random subset."""
    df = _ct_plus_il_across_the_boundary()
    for year, ct_county in (("2023", "09001"), ("2024", "09110")):
        out = lending_by_county(df[df["activity_year"] == year])
        assert ct_county in set(out["county_code"]), (
            f"the {year} panel dropped Connecticut ({ct_county})"
        )


# --------------------------------------------------------------------------- #
# Replacement remedy (b): vintage= narrowing.
# --------------------------------------------------------------------------- #

def test_vintage_narrowing_works_on_the_county_path_at_both_bases():
    """The county map puts 2023 on basis 2020 and 2024 on basis 2023, so both
    narrowings select a non-empty, coherent subset. The argument is the BASIS
    year, not the data year — which is why the message now spells out which is
    which."""
    df = _ct_plus_il_across_the_boundary()
    for basis, expected_year in ((2020, "2023"), (2023, "2024")):
        out = lending_by_county(df, vintage=basis)
        assert not out.empty, f"vintage={basis} returned nothing"
        assert (out["vintage_dropped_rows"]
                == (df["activity_year"] != expected_year).sum()).all()


def test_vintage_narrowing_works_on_the_tract_path():
    """The tract map has no 2024 entry, so ``vintage=2020`` selects the 2023 rows
    and drops the rest. There is no second tract basis to narrow to at this
    boundary, and asking for one is a separate, correctly-refused question —
    covered below."""
    df = _ct_plus_il_across_the_boundary()
    out = lending_by_tract(df, vintage=2020)
    assert not out.empty
    assert (out["vintage_dropped_rows"] == (df["activity_year"] == "2024").sum()).all()


def test_narrowing_to_a_basis_the_frame_does_not_have_still_refuses():
    """The remedies are narrowings, not overrides. This one selects no rows and
    must raise — a malformed question, not a finding. Included here so "the
    remedies work" is not read as "vintage= always works"."""
    df = _ct_plus_il_across_the_boundary()
    with pytest.raises(GeographyVintageError):
        lending_by_tract(df, vintage=2010)


# --------------------------------------------------------------------------- #
# The remedies as the message states them.
# --------------------------------------------------------------------------- #

def test_every_remedy_the_county_message_names_is_executed_here():
    """Ties the assertions above to the shipped text: each ``vintage=`` value the
    message prints is run against the frame that printed it."""
    df = _ct_plus_il_across_the_boundary()
    with pytest.raises(GeographyVintageError) as exc:
        lending_by_county(df)
    msg = str(exc.value)

    named = [int(m) for m in ("2020", "2023") if f"vintage={m}" in msg]
    assert named, "the message names no vintage= remedy: " + msg
    for basis in named:
        assert not lending_by_county(df, vintage=basis).empty, (
            f"the message offers vintage={basis} and it returns nothing"
        )
