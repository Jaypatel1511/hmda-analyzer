"""
``vintage_dropped_rows`` must signal by its VALUE, never by its own absence.

**The defect.** 0.6.0 added the ``*_status`` provenance columns for exactly one
reason, stated in ``VintageResolution.attach``: a column that appears only in the
unhappy cases signals by its own absence, and absence is not readable — a caller
holding one frame cannot tell "this analysis had nothing to report" from "this
analysis is an older output that never reported it" or from "this column got
dropped somewhere between here and me".

``vintage_dropped_rows`` was left one field over in that same output, still
carrying the defect the status columns had just been added to fix::

    lending_by_tract(df, vintage=2020)   # narrowing dropped nothing
    lending_by_tract(df)                 # no narrowing requested at all

Those two calls produced **byte-identical column sets**. A ``vintage=`` narrowing
that turned out to drop no rows was indistinguishable from a call that never
narrowed, in the one channel §M3.3a designates for carrying that fact — the
returned object, chosen over ``print`` and ``warnings.warn`` precisely because it
outlives the session.

**The fix.** ``vintage_dropped_rows`` is always present on a guarded frame
output, ``0`` when nothing was dropped. ``lender_summary`` returns a dict and
carries the same fact as an always-present ``dropped_rows_by_year`` key, ``{}``
when nothing was dropped — the dict channel had the identical defect and
``provenance_keys`` already says so about the status keys.

The distinction the value now carries, and which absence could not:

===========================  =========================  ======================
call                         ``vintage_dropped_rows``   ``dropped_rows_by_year``
===========================  =========================  ======================
no ``vintage=``              ``0``                      ``{}``
``vintage=`` dropped none    ``0``                      ``{}``
``vintage=`` dropped rows    the count                  ``{year: count}``
===========================  =========================  ======================

Note what is deliberately NOT claimed: the column does not distinguish "no
narrowing requested" from "narrowing requested, dropped nothing". Both are ``0``,
because in both cases zero rows were dropped and the column names exactly one
fact. What it removes is the *unreadable* signal — a caller can now always ask
the question and get an answer, rather than having to know whether the column
would have been there.
"""
import pandas as pd
import pytest

from hmdaanalyzer.analysis.geographic import (
    lending_by_tract, lending_by_county, lending_desert_score,
    racial_composition_by_tract,
)
from hmdaanalyzer.analysis.lender import lender_summary
from hmdaanalyzer.geography_vintage import (
    VINTAGE_STATUS_COLUMN_BY_KEY, resolve_geography_vintage,
)

DROPPED_COLUMN = "vintage_dropped_rows"
DROPPED_KEY = "dropped_rows_by_year"


def _frame(years, n_tracts=6):
    """``n_tracts`` tracts per year, so ``lending_desert_score`` clears its
    five-tract floor and every function has something to aggregate."""
    rows = []
    for year in years:
        for t in range(n_tracts):
            for action in (1, 3):
                rows.append((year, t, action))
    return pd.DataFrame({
        "activity_year": [str(r[0]) for r in rows],
        "state_code": ["IL"] * len(rows),
        "county_code": ["17031"] * len(rows),
        "census_tract": [f"1703101{r[1]:04d}" for r in rows],
        "derived_race": ["White"] * len(rows),
        "action_taken": [r[2] for r in rows],
        "is_denied": [r[2] == 3 for r in rows],
        "is_approved": [r[2] == 1 for r in rows],
        "loan_amount": [200_000.0] * len(rows),
        "income": [80.0] * len(rows),
        "lei": ["LEI0"] * len(rows),
    })


_FRAME_FUNCS = [
    ("lending_by_tract", lending_by_tract, 2020),
    ("lending_by_county", lending_by_county, 2020),
    ("lending_desert_score", lending_desert_score, 2020),
    ("racial_composition_by_tract", racial_composition_by_tract, 2020),
]


# --------------------------------------------------------------------------- #
# Always present, on every guarded frame output.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,fn,basis", _FRAME_FUNCS, ids=[f[0] for f in _FRAME_FUNCS])
def test_column_is_present_when_no_vintage_was_requested(name, fn, basis):
    out = fn(_frame(["2023"]))
    assert DROPPED_COLUMN in out.columns, (
        f"{name} omitted {DROPPED_COLUMN!r} on a call with no vintage=; the "
        f"column would then be signalling by its own absence, which is the "
        f"defect the *_status columns were added to fix"
    )
    assert (out[DROPPED_COLUMN] == 0).all()


@pytest.mark.parametrize("name,fn,basis", _FRAME_FUNCS, ids=[f[0] for f in _FRAME_FUNCS])
def test_column_is_present_when_narrowing_dropped_nothing(name, fn, basis):
    """The case that was indistinguishable. Every year in this frame already
    uses the requested basis, so the narrowing is a no-op."""
    out = fn(_frame(["2023"]), vintage=basis)
    assert DROPPED_COLUMN in out.columns, (
        f"{name} omitted {DROPPED_COLUMN!r} for a vintage= narrowing that "
        f"dropped no rows"
    )
    assert (out[DROPPED_COLUMN] == 0).all()


@pytest.mark.parametrize("name,fn,basis", _FRAME_FUNCS, ids=[f[0] for f in _FRAME_FUNCS])
def test_column_carries_the_count_when_narrowing_dropped_rows(name, fn, basis):
    """The always-present column must not have flattened the case it exists for."""
    df = _frame(["2021", "2023"])
    dropped = int((df["activity_year"] == "2021").sum())
    out = fn(df, vintage=basis)
    assert (out[DROPPED_COLUMN] == dropped).all(), (
        f"{name} reported {out[DROPPED_COLUMN].unique()} dropped rows, "
        f"expected {dropped}"
    )
    assert dropped > 0, "the fixture stopped exercising a real drop"


@pytest.mark.parametrize("name,fn,basis", _FRAME_FUNCS, ids=[f[0] for f in _FRAME_FUNCS])
def test_the_two_calls_are_no_longer_byte_identical(name, fn, basis):
    """The finding, stated as the comparison that produced it: a narrowing call
    and a non-narrowing call must be distinguishable somewhere in the returned
    object. They now agree on the *value* 0 — the point is that the column is
    askable in both, not that they differ."""
    plain = fn(_frame(["2023"]))
    narrowed = fn(_frame(["2023"]), vintage=basis)
    assert list(plain.columns) == list(narrowed.columns), (
        "the column sets diverge, so the column is still signalling by presence"
    )
    assert DROPPED_COLUMN in plain.columns and DROPPED_COLUMN in narrowed.columns


@pytest.mark.parametrize("name,fn,basis", _FRAME_FUNCS, ids=[f[0] for f in _FRAME_FUNCS])
def test_the_column_is_an_integer_not_a_float(name, fn, basis):
    """A row count is a count. Making it always-present must not have introduced
    the NaN-flips-to-float64 problem that is the stated reason the *basis*
    columns are omitted rather than set to NaN."""
    out = fn(_frame(["2023"]), vintage=basis)
    assert pd.api.types.is_integer_dtype(out[DROPPED_COLUMN]), (
        f"{DROPPED_COLUMN} came back as {out[DROPPED_COLUMN].dtype}"
    )


def test_it_sits_beside_the_status_columns_it_was_left_behind_by():
    """The status columns are the precedent this is being brought in line with,
    so assert they are all there together rather than asserting one in
    isolation."""
    out = lending_by_tract(_frame(["2023"]))
    for status_column in VINTAGE_STATUS_COLUMN_BY_KEY.values():
        assert status_column in out.columns
    assert DROPPED_COLUMN in out.columns


# --------------------------------------------------------------------------- #
# The dict channel — lender_summary carries the same fact as a key.
# --------------------------------------------------------------------------- #

def test_lender_summary_key_is_present_with_no_vintage():
    keys = lender_summary(_frame(["2023"]))
    assert DROPPED_KEY in keys, (
        f"lender_summary omitted {DROPPED_KEY!r}; the dict channel had the "
        f"identical absence defect and provenance_keys already says so"
    )
    assert keys[DROPPED_KEY] == {}


def test_lender_summary_key_is_present_when_narrowing_dropped_nothing():
    keys = lender_summary(_frame(["2023"]), vintage=2020)
    assert DROPPED_KEY in keys
    assert keys[DROPPED_KEY] == {}


def test_lender_summary_key_carries_the_counts_when_rows_were_dropped():
    df = _frame(["2021", "2023"])
    keys = lender_summary(df, vintage=2020)
    assert keys[DROPPED_KEY] == {"2021": int((df["activity_year"] == "2021").sum())}


# --------------------------------------------------------------------------- #
# The helper itself, so a seventh call site inherits the behaviour.
# --------------------------------------------------------------------------- #

def test_attach_writes_the_column_from_a_resolution_that_dropped_nothing():
    resolved = resolve_geography_vintage(
        _frame(["2023"]), key="census_tract", fn_name="test", vintage=2020,
    )
    assert resolved.dropped_rows_by_year == {}
    out = resolved.attach(pd.DataFrame({"census_tract": ["17031010000"]}))
    assert DROPPED_COLUMN in out.columns
    assert int(out[DROPPED_COLUMN].iloc[0]) == 0


def test_provenance_keys_carries_the_key_from_a_resolution_that_dropped_nothing():
    resolved = resolve_geography_vintage(
        _frame(["2023"]), key="census_tract", fn_name="test", vintage=2020,
    )
    assert resolved.provenance_keys()[DROPPED_KEY] == {}
