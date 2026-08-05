"""
Two documentation claims that nothing was checking: the exception hierarchy the
README promises, and threshold values re-typed into docstrings.

**Why here and not in docs-check.** ``docs-check.toml`` records both gaps in its
own scope section, explicitly:

* "THE EXCEPTION TABLE'S CONTENT. Assertion 6 checks each exception NAME
  appears. It does not check that the 'Raised when' column is true, nor that the
  ValueError subclassing the README promises still holds."
* Assertion 6 checks only that constant NAMES appear, so the README could quote
  any value and the gate stays green.

A gate that names its own blind spot has done its job; something else has to
cover the spot. ``tests/test_backlog_0_6_0.py`` already closes the README half of
the constants gap from the other side. This file closes the two that were left.

**F2 — the lede contradicted its own table.** The README said "every type
subclasses ``ValueError``, so existing ``except ValueError`` handlers keep
working unchanged", six lines above a table whose seventh row says
``CFPBAPIError`` is "A ``RuntimeError``, not a ``ValueError``." Both cannot be
true. A reader who trusts the lede writes ``except ValueError`` and every CFPB
403 escapes it — at the transport layer, where retry logic lives.

**F7/F9 — the drift tests did not cover docstrings.**
``test_desert_constants_are_not_literals_at_the_site`` splits the source on
``\"\"\"`` and checks ``[2]`` — everything AFTER the docstring. That was
deliberate and it is why two copies of the same literal survived a release that
existed to remove them:

* ``geographic.py`` wrote ``denial_rate > 0.15`` into the ``lending_desert_score``
  docstring's formula display, ninety lines above a code comment saying the
  denial-rate floor is no longer a literal.
* ``exceptions.py`` re-typed ``app_percentile < 25`` and ``For n <= 4`` into the
  ``UnreachableFlagError`` docstring.

Neither is executable, so neither changes a number — and that is the point. A
developer who moves ``DESERT_PERCENTILE_THRESHOLD`` sees two tests fail, fixes
the two sites those tests name, and leaves these two stale, in the text a user
reads to find out what the flag means.
"""
import inspect
import re
from pathlib import Path

import pytest

from hmdaanalyzer import (
    ActivityYearMismatchError, CFPBAPIError, GeographyVintageError,
    MissingColumnError, ReferenceGroupError, SchemaValidationError,
    UnreachableFlagError,
)
from hmdaanalyzer.analysis.geographic import lending_desert_score
from hmdaanalyzer.geography_vintage import (
    DESERT_DENIAL_RATE_FLOOR, DESERT_PERCENTILE_THRESHOLD, DESERT_TRACT_FLOOR,
)

#: Located from THIS FILE, not from the installed package and not from the cwd.
#:
#: The first version of this resolved it from ``hmdaanalyzer.__file__`` and
#: skipped when it was absent. Under the sdist smoke test — pip-installed into a
#: venv, suite run from a directory containing neither import name — the package
#: lives in site-packages and the README does not, so nine assertions here and
#: eleven in test_output_columns.py silently skipped. Twenty tests reporting
#: success while asserting nothing, in a suite whose stated property is zero skip
#: markers.
#:
#: All four invocations that run this suite put README.md one level above
#: ``tests/``, which is what ``test_backlog_0_6_0.py`` already relies on.
README = Path(__file__).resolve().parent.parent / "README.md"


def _readme() -> str:
    """The README, read or failed — never skipped.

    A skip here is the vacuity this repo's pytest configuration exists to
    prevent: ``empty_parameter_set_mark = "fail_at_collect"`` turns an empty
    parametrize into a collection error for exactly this reason, and a
    conditional skip on a file that is always supposed to be there is the same
    hole with a different shape.
    """
    assert README.exists(), (
        f"README.md not found at {README}. These tests read it deliberately; if "
        f"the packaging changed so the README no longer ships beside tests/, fix "
        f"the path rather than skipping — a skip here certifies nothing."
    )
    return README.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# F2 — the exception hierarchy.
# --------------------------------------------------------------------------- #

#: Every typed failure this package exports, and the base class it actually has.
#: The point of writing it out is that the split is REAL and load-bearing: data
#: problems are ValueErrors, transport problems are not.
VALUE_ERRORS = [
    MissingColumnError, SchemaValidationError, ActivityYearMismatchError,
    GeographyVintageError, UnreachableFlagError, ReferenceGroupError,
]
RUNTIME_ERRORS = [CFPBAPIError]


@pytest.mark.parametrize("exc", VALUE_ERRORS, ids=[e.__name__ for e in VALUE_ERRORS])
def test_data_refusals_are_value_errors(exc):
    """The promise ``except ValueError`` callers rely on, for the types it
    actually covers."""
    assert issubclass(exc, ValueError), f"{exc.__name__} MRO: {exc.__mro__}"


@pytest.mark.parametrize("exc", RUNTIME_ERRORS, ids=[e.__name__ for e in RUNTIME_ERRORS])
def test_transport_failures_are_runtime_errors_and_not_value_errors(exc):
    """``CFPBAPIError`` subclasses ``RuntimeError`` deliberately — it reports
    that the CFPB API returned an HTTP error, not that the caller's frame is
    wrong. This asserts BOTH halves: that it is a RuntimeError, and that it is
    not quietly also a ValueError, because a later 'fix' making it both would
    make the old lede true again by breaking the deliberate distinction."""
    assert issubclass(exc, RuntimeError), f"{exc.__name__} MRO: {exc.__mro__}"
    assert not issubclass(exc, ValueError), (
        f"{exc.__name__} became a ValueError; the README distinguishes data "
        f"refusals from transport failures and that distinction is the reason "
        f"the exception table has a base-class column at all"
    )


def test_except_valueerror_does_not_catch_a_cfpb_api_error():
    """The reader's failure mode, executed rather than described. This is what
    happens to somebody who wrote their handler from the old lede."""
    with pytest.raises(CFPBAPIError):
        try:
            raise CFPBAPIError("403 from the CFPB API")
        except ValueError:  # pragma: no cover - must not catch
            pytest.fail("except ValueError caught CFPBAPIError")


def test_readme_does_not_claim_every_exception_subclasses_valueerror():
    """The specific false sentence, and the shape of it.

    Matched loosely on purpose: any sentence pairing a universal quantifier with
    ValueError subclassing is the claim that was wrong, however it is reworded.

    Matched against WHITESPACE-COLLAPSED text, which is not incidental. The
    offending sentence wrapped as "every type subclasses\\n`ValueError`", so the
    first version of this test — written with ``\\s`` unaccounted for — passed
    against the very README it was written to fail against. A documentation test
    that cannot see across a line break is a documentation test for one-line
    documents."""
    readme = re.sub(r"\s+", " ", _readme())
    for pattern in [
        r"every type subclasses `?ValueError`?",
        r"all of (?:them|which) subclass(?:es)? `?ValueError`?",
        r"every (?:exception|failure|error|type)[^.]{0,60}subclasses `?ValueError`?",
    ]:
        assert not re.search(pattern, readme, re.IGNORECASE), (
            f"the README makes a universal ValueError claim matching {pattern!r}; "
            f"CFPBAPIError is a RuntimeError, so no universal claim is true"
        )


def test_readme_names_the_runtime_error_exception_beside_the_claim():
    """Removing the false sentence is not enough — the true one has to be there,
    and near enough to the lede that a reader writing a handler sees it."""
    readme = _readme()
    heading = readme.index("## Errors and refusals")
    table_end = readme.index("|", heading)
    lede = readme[heading:table_end]

    assert "CFPBAPIError" in lede, (
        "the exceptions lede does not mention CFPBAPIError, so a reader still "
        "learns about the RuntimeError only from row 7 of the table"
    )
    assert "RuntimeError" in lede


@pytest.mark.parametrize(
    "exc", VALUE_ERRORS + RUNTIME_ERRORS,
    ids=[e.__name__ for e in VALUE_ERRORS + RUNTIME_ERRORS],
)
def test_every_exported_exception_has_a_row_in_the_readme_table(exc):
    """docs-check asserts the name appears SOMEWHERE in the README. This asserts
    it appears in the exception table specifically, which is where a caller
    looks."""
    readme = _readme()
    table = readme[readme.index("## Errors and refusals"):]
    table = table[:table.index("\n\n", table.index("| Exception |"))]
    assert f"`{exc.__name__}`" in table, (
        f"{exc.__name__} is exported but has no row in the exception table"
    )


# --------------------------------------------------------------------------- #
# F7 / F9 — threshold literals in docstrings.
# --------------------------------------------------------------------------- #

def _docstring_of(obj) -> str:
    return inspect.getdoc(obj) or ""


def test_lending_desert_score_docstring_has_no_bare_denial_rate_floor():
    """F7. The docstring's ``is_lending_desert`` formula display wrote
    ``denial_rate > 0.15`` while the comparison site ninety lines below used
    ``DESERT_DENIAL_RATE_FLOOR`` — and a comment at that site said the literal
    had been removed. The README's copy of the same formula already uses the
    constant name; this brings the docstring into line with both."""
    doc = _docstring_of(lending_desert_score)
    assert str(DESERT_DENIAL_RATE_FLOOR) not in doc, (
        f"the denial-rate floor {DESERT_DENIAL_RATE_FLOOR} is written as a "
        f"literal in the lending_desert_score docstring; use "
        f"DESERT_DENIAL_RATE_FLOOR"
    )
    assert "DESERT_DENIAL_RATE_FLOOR" in doc


def test_lending_desert_score_docstring_has_no_bare_percentile_threshold():
    doc = _docstring_of(lending_desert_score)
    assert not re.search(rf"< *{DESERT_PERCENTILE_THRESHOLD}\b", doc), (
        f"the percentile threshold {DESERT_PERCENTILE_THRESHOLD} is compared "
        f"against as a literal in the docstring; use "
        f"DESERT_PERCENTILE_THRESHOLD"
    )


def test_lending_desert_score_docstring_does_not_contradict_its_own_code():
    """The specific contradiction F7 names: the docstring asserted the floor was
    'a bare literal at the comparison site', which stopped being true in 0.6.0
    and was denied by a comment in the same function."""
    doc = _docstring_of(lending_desert_score)
    assert "bare literal at the comparison site" not in doc, (
        "the docstring still claims the denial-rate floor is a bare literal at "
        "the comparison site; it has been DESERT_DENIAL_RATE_FLOOR since 0.6.0"
    )


def test_unreachable_flag_error_docstring_has_no_bare_thresholds():
    """F9. ``exceptions.py`` re-typed both numbers. Drift is caught by two tests
    elsewhere, but not at this copy — so a developer who moves the threshold
    fixes the two sites those tests name and leaves this one stale."""
    doc = _docstring_of(UnreachableFlagError)
    assert not re.search(rf"< *{DESERT_PERCENTILE_THRESHOLD}\b", doc), (
        f"'app_percentile < {DESERT_PERCENTILE_THRESHOLD}' is a literal in the "
        f"UnreachableFlagError docstring; reference "
        f"DESERT_PERCENTILE_THRESHOLD instead"
    )
    assert not re.search(rf"n *<= *{DESERT_TRACT_FLOOR - 1}\b", doc), (
        f"'n <= {DESERT_TRACT_FLOOR - 1}' is a literal derived from the floor; "
        f"reference DESERT_TRACT_FLOOR instead"
    )
    assert "DESERT_PERCENTILE_THRESHOLD" in doc and "DESERT_TRACT_FLOOR" in doc, (
        "the docstring must name the constants it is describing, or a reader "
        "has no way to look up the live values"
    )


def test_the_derivation_between_the_two_constants_still_holds():
    """The relationship the docstrings now describe in words instead of digits.
    If this breaks, the prose is wrong everywhere at once and loudly."""
    assert round(100 / DESERT_TRACT_FLOOR, 1) < DESERT_PERCENTILE_THRESHOLD
    assert round(100 / (DESERT_TRACT_FLOOR - 1), 1) >= DESERT_PERCENTILE_THRESHOLD
