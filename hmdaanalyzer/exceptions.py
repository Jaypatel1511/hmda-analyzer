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


__all__ = ["MissingColumnError"]
