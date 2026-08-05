"""
``include_purchased=True`` on a frame with no purchased loans raises.

**What it did before.** It returned a table. Not an empty result — a fully
populated four-row distribution::

    -- universe=purchased  denominator=0
    category  count  cra_proxy_share
         Low      0              0.0
    Moderate      0              0.0
      Middle      0              0.0
       Upper      0              0.0

in the identical shape as the real ``originated`` distribution printed beside
it. Read by a human, that says "this lender purchased no LMI loans". The truth
was "purchased loans were never fetched": ``load_from_api`` and ``load_range``
query the CFPB Data Browser with ``actions_taken=1,2,3,4,5`` and ``load_sample``
generates only 1, 3 and 4, so **no loader in this package can produce an
``action_taken == 6`` row at all.** The flag could never be honoured on a frame
the package itself produced.

The mitigation shipped through the 0.6.0 build was an ``EMPTY PURCHASED CUT``
caveat. It is attached to ``table.caveat`` — a *sibling attribute* of
``table.distribution``. Everything a user actually does with the result (chart
it, ``to_csv`` it, ``pd.concat`` the distributions, read a cell) carries the four
zeros and leaves the caveat behind.

**Why this raises rather than returning the table.** The README states the design
commitment in its first section: "In a fair lending context an empty or
silently-narrowed result reads as 'no disparity.' This library therefore refuses
rather than guesses: a schema problem raises, a frame that pools incompatible
census geographies raises, **an arithmetically impossible flag raises**." A
purchased cut over a frame that structurally cannot contain a purchased loan is
that third clause. It is the same argument ``UnreachableFlagError`` already makes
for ``is_lending_desert``: returning ``False`` for every tract where the flag
cannot be ``True`` is a fabricated negative, and four zeros over a denominator of
zero is a fabricated distribution.

**The objection, and the answer.** The README also says "A well-formed query that
simply matches no rows is not an error" — ``lender_summary(df, lei=...)`` with an
unknown LEI returns an empty dict rather than raising, and that is deliberate.
This is not that case, and the difference is the *shape of the output*, not the
emptiness. ``lender_summary`` returns nothing: zero rows, nothing to misread.
``cra_proxy_distribution`` returned four category rows asserting a distribution.
An empty result cannot be mistaken for a finding; a populated table of zeros is
built to be.

**Boundary, stated.** The check is on the frame, not on each year. A frame that
does contain purchased loans but has a year with none still produces that year's
empty cut with the caveat: there, the user has direct evidence in the sibling
tables that the universe is real, so the zero is interpretable in context rather
than fabricated.
"""
import pandas as pd
import pytest

import hmdaanalyzer
from hmdaanalyzer import EmptyUniverseError, cra_proxy_distribution, load_sample


def _frame(actions, n_each=6):
    rows = [a for a in actions for _ in range(n_each)]
    n = len(rows)
    return pd.DataFrame({
        "activity_year": ["2023"] * n,
        "action_taken": rows,
        "income": [80.0] * n,
        "ffiec_msa_md_median_family_income": [90_000.0] * n,
        "tract_to_msa_income_percentage": [95.0] * n,
        "is_denied": [a == 3 for a in rows],
        "is_approved": [a == 1 for a in rows],
    })


# --------------------------------------------------------------------------- #
# The refusal.
# --------------------------------------------------------------------------- #

def test_raises_when_the_frame_has_no_purchased_loans():
    with pytest.raises(EmptyUniverseError) as exc:
        cra_proxy_distribution(_frame([1, 3, 4]), by="borrower",
                               include_purchased=True)
    msg = str(exc.value)
    assert "include_purchased" in msg
    assert "action_taken" in msg and "6" in msg


def test_the_message_names_load_from_file_as_the_way_in():
    """A refusal a user cannot act on is a refusal they route around. The only
    way to get purchased loans into this package today is to supply the frame
    yourself, so the message has to say so."""
    with pytest.raises(EmptyUniverseError) as exc:
        cra_proxy_distribution(_frame([1, 3]), include_purchased=True)
    assert "load_from_file" in str(exc.value)


def test_the_message_explains_that_the_loaders_cannot_produce_the_rows():
    """The distinction that decides what the user should do next: a frame from
    this package's loaders can NEVER contain a purchased loan, which is a
    different situation from a supplied frame that happens to contain none."""
    with pytest.raises(EmptyUniverseError) as exc:
        cra_proxy_distribution(_frame([1, 3]), include_purchased=True)
    msg = str(exc.value)
    assert "actions_taken=1,2,3,4,5" in msg or "API_ACTIONS_TAKEN" in msg


def test_it_subclasses_valueerror_like_every_other_data_refusal():
    assert issubclass(EmptyUniverseError, ValueError)


def test_a_package_loader_frame_raises_because_no_loader_can_satisfy_the_flag():
    """Through the package's own documented workflow, end to end."""
    df = load_sample(n=200, seed=42)
    df["ffiec_msa_md_median_family_income"] = 90_000.0
    df["tract_to_msa_income_percentage"] = 95.0
    assert (df["action_taken"] == 6).sum() == 0, "load_sample started emitting action 6"

    with pytest.raises(EmptyUniverseError):
        cra_proxy_distribution(df, by="borrower", include_purchased=True)


# --------------------------------------------------------------------------- #
# What must NOT have changed.
# --------------------------------------------------------------------------- #

def test_the_default_is_unaffected():
    """``include_purchased`` defaults to False, and the overwhelming majority of
    calls never touch this path. A frame with no purchased loans is the normal
    case and must keep working."""
    out = cra_proxy_distribution(_frame([1, 3, 4]), by="borrower")
    assert out.tables
    assert all(t.universe == "originated" for t in out.tables)


def test_a_frame_that_does_contain_purchased_loans_still_works():
    """The flag is fully functional on a frame that can honour it. This is the
    case the refusal exists to distinguish itself from."""
    out = cra_proxy_distribution(_frame([1, 3, 6]), by="borrower",
                                 include_purchased=True)
    universes = {t.universe for t in out.tables}
    assert universes == {"originated", "purchased"}

    purchased = next(t for t in out.tables if t.universe == "purchased")
    assert purchased.classified_denominator > 0, (
        "the purchased cut is empty on a frame that contains purchased loans"
    )


def test_one_purchased_row_is_enough_to_answer_the_question():
    """The check is 'can this question be answered at all', not 'is there enough
    data to be interesting'. This is not a small-N suppression rule, exactly as
    the tract floor is not one."""
    out = cra_proxy_distribution(_frame([1, 3]) .pipe(
        lambda d: pd.concat([d, _frame([6], n_each=1)], ignore_index=True)
    ), by="borrower", include_purchased=True)
    purchased = next(t for t in out.tables if t.universe == "purchased")
    assert purchased.classified_denominator == 1


@pytest.mark.parametrize("by", ["borrower", "tract", "both"])
def test_the_refusal_applies_to_every_dimension(by):
    with pytest.raises(EmptyUniverseError):
        cra_proxy_distribution(_frame([1, 3]), by=by, include_purchased=True)


def test_a_year_with_no_purchases_inside_a_frame_that_has_them_is_not_refused():
    """The stated boundary. Per-year emptiness inside a frame whose purchased
    universe is demonstrably real stays a caveated table: the sibling years give
    the reader direct evidence that the zero is a fact about that year rather
    than a fact about the fetch."""
    a = _frame([1, 3, 6])
    b = _frame([1, 3])
    b["activity_year"] = "2024"
    out = cra_proxy_distribution(pd.concat([a, b], ignore_index=True),
                                 by="borrower", include_purchased=True)
    years = {(t.universe, t.year) for t in out.tables}
    assert ("purchased", "2023") in years and ("purchased", "2024") in years

    # The EMPTY PURCHASED CUT caveat is still the right instrument here and is
    # still reachable — this is the path that keeps it alive now that the
    # frame-wide case raises.
    empty_year = next(t for t in out.tables
                      if t.universe == "purchased" and t.year == "2024")
    assert empty_year.classified_denominator == 0
    assert "EMPTY PURCHASED CUT" in empty_year.caveat

    populated_year = next(t for t in out.tables
                          if t.universe == "purchased" and t.year == "2023")
    assert populated_year.classified_denominator > 0
    assert "EMPTY PURCHASED CUT" not in populated_year.caveat


# --------------------------------------------------------------------------- #
# Exported and documented.
# --------------------------------------------------------------------------- #

def test_it_is_exported_from_both_import_names():
    import hmda_analyzer

    assert hmda_analyzer.EmptyUniverseError is EmptyUniverseError
    assert "EmptyUniverseError" in hmdaanalyzer.__all__
