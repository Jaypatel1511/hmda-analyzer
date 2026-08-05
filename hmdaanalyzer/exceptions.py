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
    ``app_percentile < 25``. For n <= 4 the flag is *arithmetically* incapable of
    being ``True`` whatever the data says, so returning ``is_lending_desert =
    False`` for every tract is a **fabricated negative** — the precise failure
    this module exists to prevent. Ties only raise the minimum percentile, so the
    floor holds unconditionally.

    This is neither a small-N suppression rule nor a claim that five tracts is
    statistically adequate. It is the point below which the output is
    arithmetically incapable of a positive, which is a different and much lower
    bar (methodology §M3.3a).
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


__all__ = [
    "MissingColumnError",
    "SchemaValidationError",
    "ActivityYearMismatchError",
    "GeographyVintageError",
    "UnreachableFlagError",
    "ReferenceGroupError",
]
