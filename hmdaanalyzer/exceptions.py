"""
Typed exceptions for hmdaanalyzer.

These let callers distinguish *schema problems* (the input DataFrame is missing a
column an analysis requires) from *legitimate empty results* (a well-formed query
that simply matched no rows). The latter still return an empty DataFrame/dict; the
former now raise, so an empty result can never silently read as "no disparity" in a
fair-lending context.
"""


class MissingColumnError(ValueError):
    """
    Raised when an analysis function is given a DataFrame that lacks a column it
    requires (a schema precondition failure).

    Subclasses :class:`ValueError` deliberately, so existing ``except ValueError``
    callers — and the historical ``lending_by_tract`` / ``lending_by_county``
    contract that raised a bare ``ValueError`` — keep working unchanged.
    """


class SchemaValidationError(ValueError):
    """
    Raised by :func:`hmdaanalyzer.load_range` when a fetched year's frame does not
    match the canonical CFPB LAR column set
    (:data:`hmdaanalyzer.data.schema.EXPECTED_LAR_COLUMNS`).

    This is the load-bearing regression guard against a silent CFPB schema change:
    a year with a *missing* or *unexpected* column raises here (naming the year and
    the offending columns) rather than being silently concatenated with NaN-filled
    or dropped fields. Subclasses :class:`ValueError` for the same back-compat
    reason as :class:`MissingColumnError`.
    """


class ActivityYearMismatchError(ValueError):
    """
    Raised by :func:`hmdaanalyzer.load_range` when the native ``activity_year`` in a
    fetched year's rows does not match the year that was requested — i.e. the API
    returned the wrong year's data. Names both the requested and the returned
    year(s). Subclasses :class:`ValueError`.
    """


class GeographyVintageError(ValueError):
    """
    Raised by a geography-keyed aggregation when the frame it was given pools
    data years whose geography keys do not mean the same thing.

    An 11-digit census-tract GEOID is only meaningful relative to a tract
    *delineation*, and the delineation changed between the 2021 and 2022 data
    years. The key did not change with it: ``24510130400`` exists in both years
    and denotes a different piece of ground in each. The county code moves too —
    at 2021→2022 in Alaska and again at 2023→2024 in Connecticut, where every
    tract GEOID changes with the county prefix while the tract delineation basis
    stays 2020.

    **Why this raises rather than warns.** Warnings are invisible where this
    library lives: Python's default filter shows a given warning once per
    location, so a notebook re-run — the normal way of working — is silent the
    second time. The output is indistinguishable from a correct one: same
    columns, same dtypes, a plausible row count. And the artefact outlives the
    session — the number goes into a spreadsheet, a memo, or a regulatory file,
    and carries no warning with it. A warning is the right instrument when the
    user can still see the problem in the output; here the entire defect is that
    they cannot (methodology §M3.2).

    Subclasses :class:`ValueError` for the same back-compat reason as
    :class:`MissingColumnError`, so existing ``except ValueError`` callers keep
    working. Note that this is exactly why ``report/generator.py``'s re-raise
    allowlists had to be inverted: an allowlist that names what to re-raise
    swallows every exception type added after it was written (§M3.2a).
    """


class ReferenceGroupError(ValueError):
    """
    Raised by :func:`hmdaanalyzer.disparity_ratio` when the reference group it
    was asked to compare against is not present in the data (after the
    five-application minimum in :func:`hmdaanalyzer.denial_rate_by_race`).

    This is a *renderable* failure and the only one the report layer's
    ``except`` blocks are permitted to swallow from a disparity call: the frame
    is well-formed, the question is answerable in principle, and this particular
    section simply has no baseline to divide by. It has a name so it can be
    named — the report layer catches what it can render and lets everything
    else propagate, which it cannot do while the case is an anonymous
    ``ValueError`` indistinguishable from a refusal (methodology §M3.2a).

    Previously a bare ``ValueError``; subclassing it keeps every existing
    ``except ValueError`` caller working.
    """


class UnreachableFlagError(ValueError):
    """
    Raised by :func:`hmdaanalyzer.lending_desert_score` when the frame has too
    few tracts for ``is_lending_desert`` to be reachable at all.

    ``rank(pct=True)`` over *n* rows has a minimum of ``1/n``, so
    ``app_percentile`` has a minimum of ``100/n``, and the flag requires
    ``app_percentile < DESERT_PERCENTILE_THRESHOLD``. Below
    ``DESERT_TRACT_FLOOR`` tracts the flag is *arithmetically* incapable of being
    ``True`` whatever the data says, so returning ``is_lending_desert = False``
    for every tract is a **fabricated negative** — the precise failure this
    module exists to prevent. Ties only raise the minimum percentile, so the
    floor holds unconditionally.

    Both constants live in :mod:`hmdaanalyzer.geography_vintage`, and
    ``DESERT_TRACT_FLOOR`` is *derived* from
    ``DESERT_PERCENTILE_THRESHOLD`` at import rather than written down beside
    it, so the two cannot drift apart. They are named here rather than quoted
    because a value re-typed into a docstring is a fourth copy that no
    threshold-drift test was reading: the two tests that fail when the threshold
    moves both point at executable code, and this text would have been left
    stale by anyone who fixed exactly what those tests named.

    This is neither a small-N suppression rule nor a claim that the floor is
    statistically adequate. It is the point below which the output is
    arithmetically incapable of a positive, which is a different and much lower
    bar (methodology §M3.3a).
    """


class EmptyUniverseError(ValueError):
    """
    Raised when a caller asks for a universe cut the frame cannot supply at all.

    The shipped case is
    ``cra_proxy_distribution(df, include_purchased=True)`` on a frame containing
    no ``action_taken == 6`` row. That flag adds purchased loans as a separate,
    labelled cut — and no loader in this package can produce a purchased loan:
    ``load_from_api`` and ``load_range`` query the CFPB Data Browser with
    ``actions_taken=1,2,3,4,5`` and ``load_sample`` generates only 1, 3 and 4.

    **Why this is a refusal and not an empty result.** Through the 0.6.0 build
    the call returned a fully populated four-row table — Low/Moderate/Middle/
    Upper, every count ``0``, every share ``0.0`` — over a denominator of zero,
    in the identical shape as the real distribution printed beside it. A reader
    sees "this lender purchased no LMI loans"; the fact is "purchased loans were
    never fetched". The mitigation was a caveat on ``table.caveat``, a *sibling*
    of ``table.distribution``, so charting, exporting or concatenating the
    distribution carried the zeros and dropped the caveat.

    That is the third clause of the design commitment in the README's opening
    section — "an arithmetically impossible flag raises" — and the identical
    argument :class:`UnreachableFlagError` makes for ``is_lending_desert``:
    a result that is incapable of being anything but empty is a fabricated
    negative, not a finding.

    **This is not the "well-formed query that matches no rows" case.** That rule
    is real and this package honours it — ``lender_summary(df, lei=...)`` with an
    unknown LEI returns an empty dict rather than raising. The difference is the
    shape of the output, not the emptiness: an empty result cannot be mistaken
    for a finding, and a populated table of zeros is built to be.

    Subclasses ``ValueError`` like every other refusal about the caller's data.
    """


def _require_columns(df, required, fn_name):
    """
    Raise :class:`MissingColumnError` if ``df`` is missing any of ``required``.

    Names *all* missing columns and the calling function, so the message is the
    same diagnosable form the analysis functions already emit. ``required`` order
    is preserved in the reported list. Returns ``None``; call it for its side
    effect before touching the columns.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise MissingColumnError(
            f"{fn_name} requires column(s) {missing}; "
            f"got: {list(df.columns)}"
        )


def _object_column_holds_numbers(series) -> bool:
    """Whether an ``object``-dtype column holds nothing but numbers.

    ``pandas.api.types.is_numeric_dtype`` answers a question about the *dtype*,
    and a column of ``decimal.Decimal`` — the natural dtype for a monetary
    column arriving out of SQL ``NUMERIC`` through most DB-API drivers — is
    ``object``. So is a column of ``fractions.Fraction``. Both are columns of
    finite numbers that ``pd.cut`` bins correctly, and both were accepted
    through v0.5.0; deciding on the dtype alone refused them.

    ``numbers.Real`` covers ``Fraction`` and the numpy scalars. ``Decimal`` is
    named separately because it is deliberately NOT registered as
    ``numbers.Real``, so an ABC check on ``Real`` alone still refuses it. That
    pair is the same gate cdfi-fund-tracker 0.2.0 arrived at for the same
    defect, and ``bool`` is excluded here for the same reason it is excluded
    there: ``bool`` is both ``numbers.Real`` and ``numbers.Integral``, so
    without the clause a boolean column reads as a column of 1s and 0s.

    **A null anywhere in an object column returns ``False``, and that asymmetry
    with ``float64`` is deliberate and measured.** A ``float64`` ``income``
    column containing ``NaN`` is ordinary — HMDA NA-income rows produce exactly
    that — and ``pd.cut`` bins it correctly, so it is accepted and always has
    been. An ``object`` column is different in fact, not merely in dtype::

        pd.cut(Series([Decimal('50'), Decimal('NaN')], dtype=object))
            -> decimal.InvalidOperation
        pd.cut(Series([Decimal('50'), None],           dtype=object))
            -> TypeError
        pd.cut(Series([Decimal('50'), float('nan')],   dtype=object))
            -> decimal.InvalidOperation

    Neither ``decimal.InvalidOperation`` nor ``TypeError`` is a ``ValueError``,
    so both escape every handler this package documents, and they surface from
    inside the report's rendering — the partial-output failure the gate exists
    to prevent. Admitting the column would move the crash rather than remove it.

    So this is NOT a case of the object column being held to a stricter standard
    than the ``float64`` column it stands in for. It is the same standard —
    *can the downstream bin it* — applied to a column pandas genuinely cannot
    bin. v0.5.0, which had no gate at all, did not "accept" a ``Decimal`` column
    containing nulls either; it raised ``InvalidOperation`` from inside
    ``pd.cut``. Refusing it here is that same failure, typed and named up front,
    and the message says how to fix it.

    A column with no non-null values returns ``False`` for the same reason.
    Zero values is zero evidence that the column holds numbers, and guessing is
    the failure mode this package refuses everywhere else.

    Cost: this walks the column. It runs only on the ``object`` branch, which no
    loader in this package produces — every frame from ``load_from_api``,
    ``load_range``, ``load_from_file`` and ``load_sample`` is already coerced
    with ``pd.to_numeric`` and takes the dtype fast path.
    """
    import numbers
    from decimal import Decimal

    import pandas as pd

    seen = False
    for value in series.to_numpy():
        if value is None:
            return False
        try:
            if bool(pd.isna(value)):
                return False
        except (TypeError, ValueError):
            pass  # not a scalar pandas can answer for; fall through to the type check
        if isinstance(value, bool) or not isinstance(value, (numbers.Real, Decimal)):
            return False
        seen = True
    return seen


def _require_numeric(df, column, fn_name):
    """
    Raise :class:`MissingColumnError` if ``df[column]`` is present but not numeric.

    A column that exists with the wrong dtype is a schema precondition failure of
    exactly the same kind as a column that is absent, and it is reported as the
    same type so callers need one ``except``.

    This exists as a shared helper rather than as a check written twice because
    both places that need it — ``denial_rate_by_income_band`` and
    ``generate_disparity_report``'s up-front precondition — must agree about what
    "numeric" means. Two hand-written dtype tests are two things that can drift,
    and the report's contract is that it validates BEFORE rendering: if the two
    disagreed, the report would pass its own precondition and then die halfway
    through a section, which is the partial-output failure it promises not to
    produce.

    Three branches, and each one is load-bearing:

    * ``bool`` and ``complex`` are refused FIRST, ahead of the numeric-dtype
      check, because ``is_numeric_dtype`` returns ``True`` for both. Through the
      0.6.0 build a boolean ``income`` column passed this gate and was binned as
      a column of 1s and 0s — a fabricated income distribution, produced
      silently. A complex column reached ``pd.cut`` the same way.
    * A genuine numeric dtype passes.
    * An ``object`` column is inspected by :func:`_object_column_holds_numbers`,
      which is what readmits ``Decimal`` and ``Fraction``.

    Everything else — ``datetime64``, ``timedelta64``, strings, categoricals —
    stays refused. ``datetime64`` and numeric strings are the two defects this
    gate was built for (they used to reach ``pd.cut`` and die as a bare
    ``ValueError`` and a ``TypeError`` respectively, mid-render), so the
    widening is deliberately narrow enough not to readmit them.

    Absent columns are NOT reported here — call :func:`_require_columns` first.
    """
    from pandas.api.types import (
        is_bool_dtype, is_complex_dtype, is_numeric_dtype, is_object_dtype,
    )

    if column not in df.columns:
        return

    series = df[column]
    if is_bool_dtype(series) or is_complex_dtype(series):
        acceptable = False
    elif is_numeric_dtype(series):
        acceptable = True
    elif is_object_dtype(series):
        acceptable = _object_column_holds_numbers(series)
    else:
        acceptable = False

    if not acceptable:
        detail = (
            f"  An 'object' column IS accepted when it is null-free and every "
            f"value is a number: decimal.Decimal and fractions.Fraction both "
            f"qualify, and Decimal is what a SQL NUMERIC column usually arrives "
            f"as. This one does not qualify.\n"
            f"  If the values are Decimals and the column simply contains NULLs, "
            f"that is the common case and the coercion below is the fix — pandas "
            f"cannot bin an object column containing nulls at all "
            f"(pd.cut raises decimal.InvalidOperation or TypeError, neither of "
            f"which is a ValueError), so it is refused here rather than left to "
            f"fail mid-analysis.\n"
            if is_object_dtype(series) else ""
        )
        raise MissingColumnError(
            f"{fn_name} requires a numeric {column!r} column; got dtype "
            f"{series.dtype!r}.\n"
            + detail +
            f"  Frames from load_from_api(), load_range(), load_from_file() and "
            f"load_sample() are already coerced with pd.to_numeric; a frame built "
            f"by hand may not be. Fix with: "
            f"df[{column!r}] = pd.to_numeric(df[{column!r}], errors='coerce')"
        )


__all__ = [
    "MissingColumnError",
    "SchemaValidationError",
    "ActivityYearMismatchError",
    "GeographyVintageError",
    "UnreachableFlagError",
    "ReferenceGroupError",
    "EmptyUniverseError",
]
