"""The report layer's inverted allowlist.

WHAT THESE TESTS COVER, AND WHAT THEY DO NOT — read this before trusting them.

They test the **allowlist mechanism**: that an exception type the report layer
was not written to render propagates out of ``generate_disparity_report`` and
``summary_table`` instead of being typeset into a markdown table cell.

They do **NOT** test the geography path end to end, and that test cannot be
written today. Propagating a real ``GeographyVintageError`` out of the report
layer requires a guarded function to be reachable from it, and none is: all five
geography imports in ``report/generator.py`` (``lending_by_state``,
``lending_by_county``, ``lending_desert_score``, ``lender_summary``,
``lender_vs_market``) are **dead** — imported, never called. That is what
"latent" means for this defect. The tests below therefore monkeypatch a
*disparity* function, which the report layer does call, and raise the geography
exception from there.

The difference matters and is stated here rather than glossed, because a test
named for an end-to-end guarantee it does not provide is the misdescribed gate
this engagement keeps finding. The genuine end-to-end test becomes writable the
moment someone wires the tract section those five imports were obviously staged
for, and it should be written *then*, in the same change.

``test_the_five_geography_imports_are_still_dead`` below is the tripwire for
that moment: it fails when someone wires one up, which is when the real test is
owed.
"""
import ast
import pathlib

import pandas as pd
import pytest

import hmdaanalyzer.report.generator as generator
from hmdaanalyzer.exceptions import (
    GeographyVintageError, MissingColumnError, ReferenceGroupError,
    UnreachableFlagError,
)
from hmdaanalyzer.report.generator import (
    RENDERABLE_ERRORS, generate_disparity_report, summary_table,
)

GENERATOR_SRC = pathlib.Path(generator.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("exc_type", [GeographyVintageError, UnreachableFlagError])
def test_a_refusal_propagates_out_of_the_report_instead_of_being_rendered(
    monkeypatch, sample_df, exc_type
):
    """The whole case for raising over warning is that a raise cannot be ignored.

    ``report/generator.py`` is where that stopped being true: it converted the
    raise into a rendered table cell, producing a report that looks complete with
    the refusal typeset into it — strictly worse than a warning, because a cell
    reading "Error: ..." reads as a rendering glitch while every surrounding
    section still carries numbers.
    """
    def boom(*a, **k):
        raise exc_type("frame spans two bases")

    monkeypatch.setattr(generator, "disparity_ratio", boom)
    with pytest.raises(exc_type):
        generate_disparity_report(sample_df)


def test_the_refusal_is_not_typeset_into_a_table_cell(monkeypatch, sample_df):
    """The negative half: assert the OLD behaviour is gone, not just that the
    new one happens. Without this, a report that both raised and rendered would
    pass the test above.

    The assertion used to sit INSIDE ``pytest.raises``, on the line after the
    call that raises — so it never executed, and the docstring claimed a
    negative check the body did not perform. The check has to happen where a
    rendered report could actually exist: in the ``except`` branch, on whatever
    the function managed to produce before it raised, and on the exception's own
    text.
    """
    def boom(*a, **k):
        raise GeographyVintageError("MARKER-frame-spans-two-bases")

    monkeypatch.setattr(generator, "denial_rate_by_race", boom)

    report = None
    try:
        report = generate_disparity_report(sample_df)
    except GeographyVintageError as exc:
        # The refusal must arrive as an exception carrying its own text...
        assert "MARKER-frame-spans-two-bases" in str(exc)
    else:
        pytest.fail(
            "generate_disparity_report returned a report instead of "
            "propagating the refusal. Rendered:\n" + str(report)[:2000]
        )
    # ...and NOT as a returned document with the refusal typeset into it.
    assert report is None, (
        "a report object survived the refusal; if it is ever returned, a cell "
        "reading 'Error: ...' reads as a rendering glitch while every "
        "surrounding section still carries numbers"
    )


def test_summary_table_no_longer_swallows_everything(monkeypatch, sample_df):
    """The fifth site, and it was the worst: ``try: disparity_ratio(df) except
    Exception: denial_rate_by_race(df)`` — no re-raise allowlist at all. It
    swallowed even the exceptions the rest of the module was careful to re-raise
    and silently substituted a different analysis."""
    def boom(*a, **k):
        raise GeographyVintageError("frame spans two bases")

    monkeypatch.setattr(generator, "disparity_ratio", boom)
    with pytest.raises(GeographyVintageError):
        summary_table(sample_df)


def test_summary_table_still_falls_back_for_the_case_the_fallback_was_written_for(
    monkeypatch, sample_df
):
    """Inverting an allowlist must not become over-propagation.

    A missing reference group is a renderable failure — the frame is fine, this
    section just has no baseline to divide by — and the fallback exists for it.
    """
    def no_reference(*a, **k):
        raise ReferenceGroupError("Reference group 'White' not found in data.")

    monkeypatch.setattr(generator, "disparity_ratio", no_reference)
    out = summary_table(sample_df)
    assert isinstance(out, pd.DataFrame) and len(out) > 0


def test_missing_column_still_propagates(monkeypatch, sample_df):
    """The one type the old allowlist did name must keep propagating."""
    def boom(*a, **k):
        raise MissingColumnError("no such column")

    monkeypatch.setattr(generator, "disparity_ratio", boom)
    with pytest.raises(MissingColumnError):
        generate_disparity_report(sample_df)


def test_a_renderable_failure_is_still_rendered(monkeypatch, sample_df):
    """The report must not become brittle: an expected, renderable failure still
    produces a report rather than an exception."""
    def boom(*a, **k):
        raise KeyError("derived_race")

    monkeypatch.setattr(generator, "denial_rate_by_race", boom)
    report = generate_disparity_report(sample_df)
    assert "Error computing denial rates" in report


def test_value_error_is_not_in_the_renderable_set():
    """``ValueError`` is the base class of every typed refusal in this package.

    Catching it anywhere in the report layer would silently restore the exact
    swallowing this inversion removes.
    """
    assert ValueError not in RENDERABLE_ERRORS
    for exc in RENDERABLE_ERRORS:
        if issubclass(exc, ValueError):
            assert exc is ReferenceGroupError, (
                f"{exc.__name__} is a ValueError subclass in RENDERABLE_ERRORS; "
                f"only the named renderable disparity failure may be."
            )
    for refusal in (GeographyVintageError, MissingColumnError, UnreachableFlagError):
        assert not issubclass(refusal, tuple(RENDERABLE_ERRORS))


def test_no_broad_exception_handler_remains_in_the_report_layer():
    """The convention, asserted. This is NOT the same as a gate on new sites —
    see the module docstring — but it does pin the five that were inverted."""
    tree = ast.parse(GENERATOR_SRC)
    broad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                broad.append((node.lineno, "bare except"))
            elif isinstance(node.type, ast.Name) and node.type.id in (
                    "Exception", "BaseException", "ValueError"):
                broad.append((node.lineno, node.type.id))
    assert not broad, f"broad exception handler(s) reintroduced at {broad}"

    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert len(handlers) == 5, (
        f"expected the five inverted swallowing sites, found {len(handlers)}"
    )
    for h in handlers:
        assert isinstance(h.type, ast.Name) and h.type.id == "RENDERABLE_ERRORS", (
            f"handler at line {h.lineno} does not use the shared allowlist"
        )


def test_the_five_geography_imports_are_still_dead():
    """A tripwire, not a guarantee.

    While these imports are unused, no geography refusal can reach the report
    layer and the end-to-end test described in this module's docstring cannot be
    written. When this test fails, someone has wired one up — and that change
    owes the real end-to-end test.
    """
    tree = ast.parse(GENERATOR_SRC)
    geography_names = {
        "lending_by_state", "lending_by_county", "lending_desert_score",
        "lender_summary", "lender_vs_market",
    }
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert geography_names <= imported, "the staged geography imports were removed"

    used = [n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]
    live = sorted(n for n in geography_names if n in used)
    assert not live, (
        f"{live} is now CALLED from report/generator.py. A guarded function is "
        f"reachable from the report layer for the first time, so the end-to-end "
        f"geography propagation test is now writable — and owed. See this "
        f"module's docstring and methodology §M3.2a item 3."
    )
