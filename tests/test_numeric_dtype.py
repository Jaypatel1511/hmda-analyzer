"""
Numeric-dtype acceptance for ``_require_numeric``, the shared gate in front of
``denial_rate_by_income_band`` and ``generate_disparity_report``.

**Why this file exists.** 0.6.0 introduced the gate to close two real defects: a
``datetime64`` ``income`` column reached ``pd.cut`` and died with a bare
``ValueError``, and a numeric-string column died with a ``TypeError``. Both are
now ``MissingColumnError``, which is the improvement it was built to be.

But the gate was written as ``pandas.api.types.is_numeric_dtype``, and a column
of ``decimal.Decimal`` is ``object`` dtype. So a ``Decimal`` ``income`` column —
which v0.5.0 **accepted**, and on which it produced output byte-identical to the
``float64`` equivalent — became a refusal. That is a new refusal of something
that was correct before, against a CHANGELOG that promises the opposite, and
``Decimal`` is the natural dtype for a monetary column arriving out of SQL
``NUMERIC`` via most DB-API drivers.

**This is the third instance of this defect in this portfolio.** cdfi-fund-tracker
0.2.0 fixed the same shape in a scalar validator: an ``isinstance(value, (int,
float))`` gate that refused ``numpy.int64``, ``numpy.float32``, ``Decimal`` and
``Fraction`` — every one of them a finite number — with the message "must be a
number". Its two load-bearing facts are reused here as the test table:

* ``Decimal`` is **not** registered as ``numbers.Real``, so an ABC check on
  ``Real`` alone still refuses it. It has to be named.
* ``bool`` is both ``numbers.Real`` and ``numbers.Integral``, so it must be
  excluded explicitly or a boolean column passes as numeric.

**What must NOT change.** ``datetime64`` and ``str`` stay refused. Widening far
enough to readmit them would reopen the defect the gate was built for, so both
have a test here on the same footing as the acceptances.

**Nulls, and why object and float64 are treated differently.** The obvious
principle — "an object column must not be judged more harshly than the float64
column it stands in for" — was the design this file started from, and measuring
it refuted it. ``pd.cut`` bins a ``float64`` column containing ``NaN`` without
complaint. On an ``object`` column it cannot bin *any* null::

    pd.cut(Series([Decimal('50'), Decimal('NaN')], dtype=object))
        -> decimal.InvalidOperation
    pd.cut(Series([Decimal('50'), None],           dtype=object))
        -> TypeError
    pd.cut(Series([Decimal('50'), float('nan')],   dtype=object))
        -> decimal.InvalidOperation

Neither exception is a ``ValueError``, so both escape every handler the README
documents, and they surface from inside the report's rendering — the exact
partial-output failure the gate exists to prevent. So the standard is the same
one in both cases (*can the downstream bin it*); it is the column that differs.
v0.5.0 had no gate and did not accept a null-carrying Decimal column either — it
raised ``InvalidOperation`` out of ``pd.cut``. Refusing it here is that same
failure, typed and named up front, with a coercion in the message that is
executed below to confirm it works.
"""
import math
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from hmdaanalyzer import MissingColumnError
from hmdaanalyzer.analysis.disparity import denial_rate_by_income_band
from hmdaanalyzer.report.generator import generate_disparity_report


def _frame(income):
    """A minimal frame that ``denial_rate_by_income_band`` can bin, with
    ``income`` supplied as given so the caller controls the dtype."""
    n = len(income)
    return pd.DataFrame({
        "activity_year": ["2023"] * n,
        "derived_race": ["White"] * n,
        "action_taken": [1, 3, 1, 3, 1][:n],
        "is_denied": [False, True, False, True, False][:n],
        "is_approved": [True, False, True, False, True][:n],
        "income": income,
    })


_FLOATS = [50.0, 60.0, 70.0, 80.0, 90.0]


# --------------------------------------------------------------------------- #
# ACCEPTED — every one of these is a column of finite numbers.
#
# The `object`-dtype legs are the point of the file: `is_numeric_dtype` says
# False for all of them, and each was accepted by v0.5.0.
# --------------------------------------------------------------------------- #

ACCEPTED = [
    ("float64", _FLOATS),
    ("int64", [50, 60, 70, 80, 90]),
    ("Decimal_object", [Decimal(str(x)) for x in _FLOATS]),
    ("Fraction_object", [Fraction(int(x), 1) for x in _FLOATS]),
    ("numpy_int64_object", [np.int64(int(x)) for x in _FLOATS]),
    ("numpy_float32_object", [np.float32(x) for x in _FLOATS]),
    ("mixed_int_float_Decimal", [50, 60.0, Decimal("70"), 80.0, 90]),
]


@pytest.mark.parametrize("label,income", ACCEPTED, ids=[a[0] for a in ACCEPTED])
def test_numeric_column_is_accepted(label, income):
    """A column of finite numbers must not be refused for its dtype."""
    out = denial_rate_by_income_band(_frame(income))
    assert not out.empty, f"{label} produced an empty band table"


def test_decimal_column_gives_the_same_answer_as_float64():
    """The load-bearing claim: v0.5.0 accepted Decimal and its output was
    byte-identical to the float64 equivalent. If widening the gate changed any
    number, the widening would be a behaviour change rather than the removal of
    a false refusal. It is the removal of a false refusal."""
    as_float = denial_rate_by_income_band(_frame(_FLOATS))
    as_decimal = denial_rate_by_income_band(
        _frame([Decimal(str(x)) for x in _FLOATS])
    )
    pd.testing.assert_frame_equal(as_float, as_decimal)


def test_decimal_column_is_accepted_by_the_report_precondition():
    """The gate has two callers and they must agree about what numeric means.
    ``generate_disparity_report`` validates up front precisely so it cannot die
    halfway through rendering; if only one caller widened, the report would pass
    its own precondition and then fail inside a section."""
    df = _frame([Decimal(str(x)) for x in _FLOATS])
    report = generate_disparity_report(df)
    assert isinstance(report, str) and report.strip()


# --------------------------------------------------------------------------- #
# REJECTED — the defects the gate was built for. These must stay refused.
# --------------------------------------------------------------------------- #

REJECTED = [
    ("datetime64", list(pd.to_datetime(["2020-01-01"] * 5))),
    ("numeric_strings", ["50", "60", "70", "80", "90"]),
    ("plain_strings", ["a", "b", "c", "d", "e"]),
    ("bool", [True, False, True, False, True]),
    ("None_only", [None] * 5),
    ("complex", [complex(x, 1) for x in _FLOATS]),
    ("mixed_number_and_string", [50, 60.0, "70", 80.0, 90]),
]


@pytest.mark.parametrize("label,income", REJECTED, ids=[r[0] for r in REJECTED])
def test_non_numeric_column_is_refused(label, income):
    """Refused as ``MissingColumnError`` — a column present with an unusable
    dtype is a schema precondition failure of the same kind as an absent one,
    and callers need one ``except``."""
    with pytest.raises(MissingColumnError, match="income"):
        denial_rate_by_income_band(_frame(income))


def test_bool_column_is_refused_and_this_is_not_incidental():
    """``bool`` is both ``numbers.Real`` and ``numbers.Integral``. An ABC check
    without an explicit bool clause admits it, and a boolean income column would
    then be binned as $1 and $0. cdfi-fund-tracker 0.2.0 carries the same clause
    for the same reason — there, ``Award(award_amount=True)`` would have
    constructed as a $1.00 award."""
    assert isinstance(True, __import__("numbers").Real)
    with pytest.raises(MissingColumnError, match="income"):
        denial_rate_by_income_band(_frame([True, False, True, False, True]))


def test_datetime64_stays_refused_because_it_is_why_the_gate_exists():
    """Before 0.6.0 this reached ``pd.cut`` and raised a bare ``ValueError``
    mid-render. Widening for ``Decimal`` must not readmit it."""
    df = _frame(list(pd.to_datetime(["2020-01-01"] * 5)))
    assert str(df["income"].dtype).startswith("datetime64")
    with pytest.raises(MissingColumnError, match="income"):
        denial_rate_by_income_band(df)


# --------------------------------------------------------------------------- #
# Non-finite values: a dtype gate does not adjudicate them.
# --------------------------------------------------------------------------- #

def test_float64_carrying_nan_is_still_accepted():
    """The baseline the object rules are measured against, pinned so a later
    tightening cannot take it out silently. HMDA NA-income rows produce exactly
    this column and ``pd.cut`` bins it correctly."""
    out = denial_rate_by_income_band(_frame([50.0, float("nan"), 70.0, 80.0, 90.0]))
    assert not out.empty


def test_all_nan_float_column_is_still_accepted():
    """The degenerate case of the above. ``is_numeric_dtype`` says True for an
    all-NaN float64 column and always has; widening must not have changed it."""
    out = denial_rate_by_income_band(_frame([float("nan")] * 5))
    assert out is not None


NULL_CARRYING_OBJECT_COLUMNS = [
    ("Decimal_with_None", [Decimal("50"), None, Decimal("70"),
                           Decimal("80"), Decimal("90")]),
    ("Decimal_with_Decimal_NaN", [Decimal("50"), Decimal("NaN"), Decimal("70"),
                                  Decimal("80"), Decimal("90")]),
    ("Decimal_with_float_nan", [Decimal("50"), float("nan"), Decimal("70"),
                                Decimal("80"), Decimal("90")]),
]


@pytest.mark.parametrize("label,income", NULL_CARRYING_OBJECT_COLUMNS,
                         ids=[c[0] for c in NULL_CARRYING_OBJECT_COLUMNS])
def test_object_column_carrying_a_null_is_refused_not_crashed(label, income):
    """Refused as ``MissingColumnError``, up front.

    This is the one place the object rules are stricter than the ``float64``
    rules, and the reason is measured rather than stylistic: ``pd.cut`` cannot
    bin an object column containing a null, and it fails with
    ``decimal.InvalidOperation`` or ``TypeError`` — neither a ``ValueError``, so
    neither catchable by anything the README tells a caller to write, and both
    raised from inside the report's rendering. The gate converts a crash it
    cannot prevent into a refusal it can name."""
    with pytest.raises(MissingColumnError, match="income"):
        denial_rate_by_income_band(_frame(income))


@pytest.mark.parametrize("label,income", NULL_CARRYING_OBJECT_COLUMNS,
                         ids=[c[0] for c in NULL_CARRYING_OBJECT_COLUMNS])
def test_the_coercion_the_message_recommends_actually_works(label, income):
    """A remedy is only a remedy if it is executed.

    This release removed a documented remedy from three shipped surfaces because
    it did not work on its own path (F1 — "exclude Connecticut and re-run"). The
    lesson generalises: the refusal above names ``pd.to_numeric(..., errors=
    'coerce')`` as the fix, so the fix is run here on the very frame that was
    just refused, and the result must be accepted."""
    df = _frame(income)
    with pytest.raises(MissingColumnError):
        denial_rate_by_income_band(df)

    df = df.copy()
    df["income"] = pd.to_numeric(df["income"], errors="coerce")
    out = denial_rate_by_income_band(df)
    assert not out.empty, "the coercion the message recommends did not fix it"


def test_object_column_carrying_infinity_but_no_null_is_accepted():
    """``Decimal('Infinity')`` is not a null and ``pd.cut`` bins it — it lands in
    the open-ended top band exactly as ``float('inf')`` does in a ``float64``
    column. It is accepted for that reason and not by oversight: the rule is
    null-freeness, not finiteness."""
    assert not math.isfinite(float("inf"))
    out = denial_rate_by_income_band(_frame(
        [Decimal("50"), Decimal("Infinity"), Decimal("70"),
         Decimal("80"), Decimal("90")]
    ))
    assert not out.empty


# --------------------------------------------------------------------------- #
# An empty column has no values to inspect, so the dtype is all there is.
# --------------------------------------------------------------------------- #

def test_empty_object_column_is_refused_rather_than_guessed():
    """Zero values means zero evidence that the column holds numbers. Refusing
    is the same choice the vintage guard makes for an unmapped year: an
    assertion of ignorance, not a guess. It is also unreachable in practice —
    an empty frame has no rows to band either way."""
    df = pd.DataFrame({
        "activity_year": [], "derived_race": [], "action_taken": [],
        "is_denied": [], "is_approved": [],
        "income": pd.Series([], dtype=object),
    })
    with pytest.raises(MissingColumnError, match="income"):
        denial_rate_by_income_band(df)
