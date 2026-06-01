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


__all__ = ["MissingColumnError"]
