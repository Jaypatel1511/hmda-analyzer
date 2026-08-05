"""
The ``action_taken`` denominator, pinned across every analysis that reports a
rate — and the one that used to disagree.

**The defect (0.6.0, pre-existing, surfaced by measurement).**
``racial_composition_by_tract`` was the only analysis in the package with no
``action_taken`` filter. Its ``denial_rate`` was ``is_denied.mean()`` over every
row in the tract, so its denominator included action 4 (application withdrawn by
the applicant), action 5 (file closed for incompleteness) and action 6 (purchased
loan — an origination made by somebody else and later bought, never an
application to this lender at all).

Nine sibling analyses filter ``action_taken.isin([1, 2, 3])``. Both they and this
one emit a column called ``denial_rate``. On a tract with one row per action 1–6::

    lending_by_tract              applications = 3   denial_rate = 0.333
    racial_composition_by_tract   applications = 6   denial_rate = 0.167

Same tract, same underlying rows, same column name, half the rate. The bias has a
direction: extra non-decision rows can only inflate the denominator, so the rate
is systematically deflated — a per-(tract, race) fair-lending rate that
understates denials, which is the direction that matters most in this domain.

**The fix, and the scope of it.** 0.6.0 applies ``action_taken.isin([1, 2, 3])``
to ``racial_composition_by_tract``, and applies it to BOTH columns rather than
only to the rate. ``applications`` in this package already means *actionable*
applications everywhere else; a tenth function using the same column name for a
different population is the drift, not the fix for it. The cost is stated in the
README and the CHANGELOG: the racial composition itself is now measured over
actionable applications, so a tract's mix is comparable to the denial rate
printed beside it and to ``lending_by_tract``, and is no longer the mix of every
LAR row the lender touched.

The tests below fail if the ``isin`` is removed from either column.
"""
import pandas as pd
import pytest

from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, denial_rate_by_income_band,
)
from hmdaanalyzer.analysis.geographic import (
    lending_by_tract, lending_by_county, lending_by_state,
    racial_composition_by_tract,
)
from hmdaanalyzer.analysis.lender import lender_summary

#: The actionable set. Action 1 = originated, 2 = approved but not accepted,
#: 3 = denied. These are the three outcomes that represent a credit decision on
#: an application made to this institution.
ACTIONABLE = (1, 2, 3)

#: Everything else the LAR can carry at this level. 4 = withdrawn by applicant,
#: 5 = file closed for incompleteness, 6 = purchased loan.
NON_ACTIONABLE = (4, 5, 6)


def _one_row_per_action(actions=tuple(range(1, 7)), race="White"):
    """One row per ``action_taken`` in a single tract, single race, single year.

    Deliberately the smallest frame that exposes a denominator difference: with
    exactly one row per action, ``applications`` reads straight off as the size
    of the denominator, and ``denial_rate`` is ``1/len(denominator)`` because
    exactly one row is a denial.
    """
    n = len(actions)
    return pd.DataFrame({
        "activity_year": ["2023"] * n,
        "state_code": ["IL"] * n,
        "county_code": ["17031"] * n,
        "census_tract": ["17031010100"] * n,
        "derived_race": [race] * n,
        "action_taken": list(actions),
        "is_denied": [a == 3 for a in actions],
        "is_approved": [a == 1 for a in actions],
        "loan_amount": [200_000.0] * n,
        "income": [80.0] * n,
        "lei": ["LEI0"] * n,
    })


# --------------------------------------------------------------------------- #
# The finding itself.
# --------------------------------------------------------------------------- #

def test_racial_composition_denominator_is_the_actionable_set():
    """The load-bearing test. Fails if ``action_taken.isin([1, 2, 3])`` is
    removed from ``racial_composition_by_tract``."""
    out = racial_composition_by_tract(_one_row_per_action())
    assert len(out) == 1, out

    assert int(out["applications"].iloc[0]) == len(ACTIONABLE), (
        "racial_composition_by_tract counted non-actionable rows in "
        "'applications'; the denominator must be action_taken in "
        f"{list(ACTIONABLE)}, so 3 of the 6 rows"
    )
    assert out["denial_rate"].iloc[0] == pytest.approx(1 / 3), (
        "racial_composition_by_tract's denial_rate is not computed over the "
        "actionable set; 1 denial out of 3 actionable rows is 0.333, and the "
        "pre-0.6.0 value of 0.167 was 1 out of all 6"
    )


def test_racial_composition_agrees_with_lending_by_tract_on_the_same_frame():
    """The two functions key on the same tract and both emit columns called
    ``applications`` and ``denial_rate``. A user reads them side by side, so
    they must mean the same thing. This is the comparison that surfaced the
    defect."""
    df = _one_row_per_action()
    tract = lending_by_tract(df)
    racial = racial_composition_by_tract(df)

    assert int(tract["applications"].iloc[0]) == int(racial["applications"].iloc[0]), (
        f"applications disagree: lending_by_tract="
        f"{int(tract['applications'].iloc[0])} vs "
        f"racial_composition_by_tract={int(racial['applications'].iloc[0])}"
    )
    assert tract["denial_rate"].iloc[0] == pytest.approx(racial["denial_rate"].iloc[0]), (
        f"denial_rate disagrees: lending_by_tract="
        f"{tract['denial_rate'].iloc[0]} vs "
        f"racial_composition_by_tract={racial['denial_rate'].iloc[0]}"
    )


@pytest.mark.parametrize("action", NON_ACTIONABLE)
def test_a_single_non_actionable_row_does_not_move_racial_composition(action):
    """Per-action isolation, so a partial filter — one that dropped action 6 but
    kept 4 and 5, say — fails here rather than passing the aggregate test."""
    base = racial_composition_by_tract(_one_row_per_action(ACTIONABLE))
    widened = racial_composition_by_tract(
        _one_row_per_action(ACTIONABLE + (action,))
    )
    pd.testing.assert_frame_equal(base, widened), (
        f"adding one action_taken == {action} row changed the output"
    )


def test_racial_composition_is_empty_when_no_row_is_actionable():
    """A tract whose rows are all withdrawals and purchases has no actionable
    application, and the honest answer is an empty table — not a row asserting a
    0.0 denial rate over a denominator of withdrawals. An empty result that
    could read as "no disparity" is exactly what this package refuses to
    fabricate, and an empty *table* says "nothing here to rate" where a
    fabricated 0.0 would say "rated, and clean"."""
    out = racial_composition_by_tract(_one_row_per_action(NON_ACTIONABLE))
    assert out.empty or int(out["applications"].sum()) == 0, out


# --------------------------------------------------------------------------- #
# The siblings, so the aligned function cannot be re-orphaned by a later change
# to any single one of them.
# --------------------------------------------------------------------------- #

_RATE_ANALYSES = [
    ("lending_by_tract", lambda d: lending_by_tract(d)),
    ("lending_by_county", lambda d: lending_by_county(d)),
    ("lending_by_state", lambda d: lending_by_state(d)),
    ("racial_composition_by_tract", lambda d: racial_composition_by_tract(d)),
    ("denial_rate_by_race", lambda d: denial_rate_by_race(d)),
    ("denial_rate_by_income_band", lambda d: denial_rate_by_income_band(d)),
]


@pytest.mark.parametrize("name,fn", _RATE_ANALYSES, ids=[a[0] for a in _RATE_ANALYSES])
def test_every_rate_analysis_ignores_non_actionable_rows(name, fn):
    """One filter, asserted at every site that reports a rate. Six copies of a
    rule are six things that can drift, and this one had already drifted once."""
    actionable_only = fn(_one_row_per_action(ACTIONABLE))
    with_the_rest = fn(_one_row_per_action())
    pd.testing.assert_frame_equal(
        actionable_only.reset_index(drop=True),
        with_the_rest.reset_index(drop=True),
    )


def test_lender_summary_ignores_non_actionable_rows():
    """``lender_summary`` returns a dict, so it needs its own leg."""
    assert (lender_summary(_one_row_per_action(ACTIONABLE))
            == lender_summary(_one_row_per_action()))


def test_denial_rate_never_exceeds_one_and_denominator_never_exceeds_row_count():
    """A denominator sanity check that holds whatever the filter is, so it stays
    meaningful if the actionable set is ever revised."""
    df = _one_row_per_action()
    out = racial_composition_by_tract(df)
    assert (out["denial_rate"] <= 1.0).all()
    assert (out["applications"] <= len(df)).all()
