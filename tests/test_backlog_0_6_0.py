"""The 0.6.0 backlog: six independent defects, each with a test that FAILS on
0.5.0's behaviour.

Every test here is written against the defect, not against the fix. A test that
merely asserts the new code does what it does would have passed on the old code
too for four of these six — the old behaviours were all silent, and silence
asserts nothing. Where the old behaviour was "returns a plausible object with no
signal", the test asserts the SIGNAL is present and says what it must say.

No skip markers, by construction: nothing here needs network, a file, or a
platform. The suite has zero skips and this module does not introduce the first.
"""
import re

import pandas as pd
import pytest

import hmdaanalyzer as H
from hmdaanalyzer.analysis.cra_proxy import cra_proxy_distribution
from hmdaanalyzer.analysis.geographic import lending_desert_score
from hmdaanalyzer.data import schema
from hmdaanalyzer.data.loader import _clean, _validate_lar_schema
from hmdaanalyzer.exceptions import MissingColumnError
from hmdaanalyzer.geography_vintage import (
    DESERT_DENIAL_RATE_FLOOR,
    DESERT_PERCENTILE_THRESHOLD,
    DESERT_TRACT_FLOOR,
)
from hmdaanalyzer.report.generator import RENDERABLE_ERRORS


def _cra_ready(df):
    """Add the two columns ``cra_proxy_distribution`` needs.

    ``load_sample`` does not emit ``ffiec_msa_md_median_family_income`` or
    ``tract_to_msa_income_percentage``, so the CRA-proxy path cannot be
    exercised from the sample loader without them. That is itself worth knowing
    and is asserted in its own test below.
    """
    out = df.copy()
    out["ffiec_msa_md_median_family_income"] = "90000"
    out["tract_to_msa_income_percentage"] = "85"
    return out


# ── B1: include_purchased is inert on frames the package's own loaders make ──


def test_api_action_set_excludes_purchased():
    """The root cause, asserted directly rather than inferred from behaviour."""
    assert 6 not in schema.API_ACTIONS_TAKEN, (
        "action 6 (Purchased loan) is in the API query — if this is now "
        "deliberate, include_purchased's documentation and the empty-cut caveat "
        "both become wrong and must be revisited together"
    )
    assert schema.API_ACTIONS_TAKEN == (1, 2, 3, 4, 5)


def test_load_sample_produces_no_purchased_rows(sample_df):
    """The sample generator emits actions 1, 3 and 4 only."""
    assert 6 not in set(sample_df["action_taken"].dropna().unique())


def test_a_frame_wide_empty_purchased_cut_now_raises(sample_df):
    """SUPERSEDED, deliberately, and kept as the record of what replaced it.

    This test used to assert that ``include_purchased=True`` on a purchase-free
    frame RETURNED a four-zero table carrying an ``EMPTY PURCHASED CUT`` caveat.
    That was the 0.6.0 build's mitigation for a 0.5.0 defect, and it was the
    wrong instrument: the caveat sits on ``table.caveat``, a sibling of
    ``table.distribution``, so every use the output is actually put to —
    charting it, ``to_csv``, ``pd.concat`` of the distributions, reading a cell —
    carried the four zeros and dropped the caveat. A table of zeros in the same
    shape as the real distribution beside it reads as "purchased no LMI loans"
    when the fact is "purchased loans were never fetched".

    It now raises. Full argument in :class:`EmptyUniverseError` and in
    tests/test_include_purchased.py; the short version is that this is the
    README's opening commitment ("an arithmetically impossible flag raises"), not
    the "well-formed query that matches no rows" case — that rule is about an
    EMPTY result, which cannot be mistaken for a finding.
    """
    from hmdaanalyzer import EmptyUniverseError

    with pytest.raises(EmptyUniverseError) as exc:
        cra_proxy_distribution(
            _cra_ready(sample_df), by="borrower", include_purchased=True
        )
    msg = str(exc.value)
    # The message must still name the actionable cause, exactly as the caveat had
    # to. Losing the diagnosis while gaining the refusal would be a bad trade.
    assert "API_ACTIONS_TAKEN" in msg
    assert "load_from_file" in msg


def test_non_empty_purchased_cut_has_no_empty_caveat(sample_df):
    """The caveat must be conditional. If it rode every purchased table it would
    be noise, and a reader would learn to skip the line that matters."""
    df = _cra_ready(sample_df)
    df.loc[df.index[:50], "action_taken"] = 6
    result = cra_proxy_distribution(df, by="borrower", include_purchased=True)
    purchased = [t for t in result.tables if t.universe == "purchased"]
    assert purchased
    for table in purchased:
        assert table.classified_denominator > 0
        assert "EMPTY PURCHASED CUT" not in table.caveat


def test_load_sample_lacks_the_cra_proxy_columns(sample_df):
    """Recorded because it surprises: the offline loader cannot feed the offline
    CRA-proxy transform. If this ever changes, the README's CRA-proxy example
    can stop insisting on load_from_api."""
    assert "ffiec_msa_md_median_family_income" not in sample_df.columns
    assert "tract_to_msa_income_percentage" not in sample_df.columns


# ── B2: small-N suppression is real, and was silent ──────────────────────────


def test_small_n_suppression_actually_removes_groups():
    """The precondition for the rest of B2. If no group is ever suppressed the
    visibility tests below would pass vacuously."""
    df = H.load_sample(n=60, seed=42)
    entering = set(
        df[df["action_taken"].isin([1, 2, 3])]["derived_race"].unique()
    )
    leaving = set(H.denial_rate_by_race(df)["derived_race"])
    assert leaving < entering, "no group was suppressed — fixture no longer bites"


def test_suppression_is_reported_on_the_frame():
    """0.5.0 dropped the rows and said nothing. These three columns are the fix."""
    df = H.load_sample(n=60, seed=42)
    result = H.denial_rate_by_race(df)

    for col in ("suppressed_groups", "suppressed_applications",
                "suppressed_group_names"):
        assert col in result.columns, f"{col} missing"

    n = int(result["suppressed_groups"].iloc[0])
    assert n > 0
    # The names must be the groups that actually left, not a count alone: a
    # fair-lending reader needs to know WHICH protected classes are absent.
    entering = set(
        df[df["action_taken"].isin([1, 2, 3])]["derived_race"].unique()
    )
    named = set(result["suppressed_group_names"].iloc[0].split("; "))
    assert named == entering - set(result["derived_race"])
    assert len(named) == n
    assert int(result["suppressed_applications"].iloc[0]) > 0


def test_suppression_columns_present_and_zero_when_nothing_fired(sample_df):
    """The columns must not signal by their own absence — the same argument the
    vintage STATUS columns rest on."""
    result = H.denial_rate_by_race(sample_df)
    assert int(result["suppressed_groups"].iloc[0]) == 0
    assert int(result["suppressed_applications"].iloc[0]) == 0
    assert result["suppressed_group_names"].iloc[0] == ""


def test_suppression_survives_into_disparity_ratio():
    """disparity_ratio is built on denial_rate_by_race, so it inherits the
    suppression. It must inherit the record of it too."""
    df = H.load_sample(n=60, seed=42)
    result = H.disparity_ratio(df)
    assert int(result["suppressed_groups"].iloc[0]) > 0


def test_report_states_the_suppression():
    """The rendered markdown is what a human reads; the columns are invisible
    there. A protected class missing from the table with no note is exactly the
    artefact the package exists to prevent."""
    df = H.load_sample(n=60, seed=42)
    report = H.generate_disparity_report(df, title="small-N")
    assert "Small-N suppression fired" in report
    assert "NOT a finding of no disparity" in report
    assert str(schema.MIN_APPLICATIONS_FOR_RATE) in report


def test_report_omits_the_note_when_nothing_was_suppressed(sample_df):
    report = H.generate_disparity_report(sample_df)
    assert "Small-N suppression" not in report


def test_suppression_threshold_is_read_from_the_constant(sample_df):
    """The threshold must exist in exactly one place. It was a bare literal in
    denial_rate_by_race through 0.5.0, and the report's note re-derives nothing:
    it reads the columns the function attached."""
    assert schema.MIN_APPLICATIONS_FOR_RATE == 5
    kept = H.denial_rate_by_race(sample_df)
    assert (kept["applications"] >= schema.MIN_APPLICATIONS_FOR_RATE).all()


def test_tract_level_functions_do_not_suppress(sample_df):
    """Deliberate, and asserted so it cannot change silently. Extending
    suppression to tract level is a disclosure-methodology decision 0.6.0 does
    not make; if a future release makes it, this test fails and forces the
    decision to be written down."""
    tracts = H.lending_by_tract(sample_df)
    assert int(tracts["applications"].min()) < schema.MIN_APPLICATIONS_FOR_RATE


# ── B3: limit truncates, and the frame now says so ───────────────────────────


def test_truncation_column_is_registered_as_derived():
    """If it were not in DERIVED_LAR_COLUMNS the schema guard would read it as
    CFPB drift and every load_range call would raise."""
    assert schema.TRUNCATED_COLUMN in schema.DERIVED_LAR_COLUMNS
    assert schema.TRUNCATED_COLUMN not in schema.RAW_LAR_COLUMNS


def test_schema_guard_accepts_a_frame_carrying_the_truncation_column():
    ok = pd.DataFrame({c: pd.Series(dtype=object) for c in sorted(schema.RAW_LAR_COLUMNS)})
    for derived in schema.DERIVED_LAR_COLUMNS:
        ok[derived] = pd.Series(dtype=object)
    _validate_lar_schema(ok, 2023)   # must not raise


@pytest.mark.parametrize("truncated", [True, False])
def test_clean_records_truncation_on_every_row(truncated):
    raw = pd.DataFrame(
        [{"action_taken": "1", "income": "50", "activity_year": "2023"}] * 3
    )
    out = _clean(raw, truncated=truncated)
    assert out[schema.TRUNCATED_COLUMN].tolist() == [truncated] * 3


def test_truncation_column_is_written_even_when_false(sample_df):
    """Absence must never be the signal: a consumer cannot distinguish a
    complete pull from a frame made before the column existed."""
    assert schema.TRUNCATED_COLUMN in sample_df.columns
    assert not sample_df[schema.TRUNCATED_COLUMN].any()


def test_loader_docstring_says_truncation_not_sampling():
    """The defect was a documented promise, so the documentation is part of the
    fix and is asserted as such."""
    doc = H.load_from_api.__doc__
    assert "TRUNCATES" in doc
    assert "not a sample" in doc or "does not sample" in doc


# ── B4: the desert score's two rules, and the constants behind them ──────────


def test_desert_constants_are_not_literals_at_the_site():
    import inspect

    body = inspect.getsource(lending_desert_score)
    # Everything after the docstring is the executable part.
    code = body.split('"""')[2]
    assert "0.15" not in code, "denial-rate floor is a literal again"
    assert str(DESERT_PERCENTILE_THRESHOLD) not in code, \
        "percentile threshold is a literal again"
    assert "DESERT_DENIAL_RATE_FLOOR" in code
    assert "DESERT_PERCENTILE_THRESHOLD" in code


def _tract_frame(specs):
    """Build a LAR-shaped frame from ``[(tract_suffix, n_apps, n_denied), ...]``.

    ``load_sample`` cannot serve this test: its tracts are drawn at random and
    almost all carry a single application, so ``rank(pct=True)`` ties every one
    of them near the top and NO tract clears the percentile cut. Volume-only and
    the real flag are then both all-False and agree trivially — which is a test
    that cannot tell the documented rule from the implemented one. Measured on
    ``load_sample(n=2000)``: 1,909 tracts, zero below the 25th percentile.
    """
    rows = []
    for suffix, n_apps, n_denied in specs:
        for i in range(n_apps):
            rows.append({
                "action_taken": "3" if i < n_denied else "1",
                "loan_amount": "200000",
                "income": "80",
                "census_tract": f"17031{suffix:06d}",
                "county_code": "17031",
                "state_code": "17",
                "derived_race": "White",
                "activity_year": "2023",
            })
    return _clean(pd.DataFrame(rows))


def test_is_lending_desert_is_a_conjunction_not_a_desert_score_cut():
    """The README described the flag as low volume alone. It is low volume AND
    high denial rate, and on a frame where those disagree the two rules give
    different answers.

    The frame is built so the single lowest-volume tract has a ZERO denial rate:
    it clears the percentile cut and fails the flag. Volume-only would call it a
    desert; the implemented rule does not.
    """
    # 20 tracts. Tract 0 is the sparsest (1 application) and never denies.
    specs = [(0, 1, 0)] + [(i, 5 + i * 3, 3 + i) for i in range(1, 20)]
    result = lending_desert_score(_tract_frame(specs))

    expected = (
        (result["app_percentile"] < DESERT_PERCENTILE_THRESHOLD)
        & (result["denial_rate"] > DESERT_DENIAL_RATE_FLOOR)
    )
    assert (result["is_lending_desert"] == expected).all()

    volume_only = result["app_percentile"] < DESERT_PERCENTILE_THRESHOLD
    assert volume_only.any(), "no tract clears the percentile cut — fixture is inert"
    assert (volume_only != result["is_lending_desert"]).any(), (
        "volume-only and the real flag agree on this frame, so the test cannot "
        "distinguish the documented rule from the implemented one"
    )

    # And name the concrete disagreement: the sparsest tract is low-volume but
    # not a desert, because it denies nobody.
    sparsest = result.loc[result["applications"].idxmin()]
    assert sparsest["app_percentile"] < DESERT_PERCENTILE_THRESHOLD
    assert not bool(sparsest["is_lending_desert"])


def test_desert_score_is_the_documented_weighted_composite(sample_df):
    result = lending_desert_score(sample_df)
    expected = (
        (100 - result["app_percentile"]) * 0.6
        + result["denial_rate"] * 100 * 0.4
    ).round(1)
    assert (result["desert_score"] - expected).abs().max() < 1e-9


def test_desert_docstring_no_longer_asserts_the_housing_units_claim():
    """The retired claim was "relative to its expected volume based on housing
    units". The new docstring QUOTES it in order to retract it, so a bare
    substring search would fail on the correction itself. What must be true is
    that every occurrence is quoted and the retraction is present.
    """
    # Collapse the docstring's own line wrapping first: every phrase below is
    # longer than one wrapped line, so a raw substring search would report a
    # missing sentence that is present and merely broken across lines.
    doc = re.sub(r"\s+", " ", lending_desert_score.__doc__)

    claim = "relative to its expected volume based on housing units"
    occurrences = [m.start() for m in re.finditer(re.escape(claim), doc)]
    assert len(occurrences) == 1, f"expected the claim once, quoted; got {len(occurrences)}"
    # It must appear inside quotation marks — i.e. as reported speech.
    assert doc[occurrences[0] - 1] == '"', "the retired claim is being asserted, not quoted"
    # And the retraction must be explicit and checkable.
    assert "No housing-unit figure is read" in doc
    assert "tract_owner_occupied_units" in doc


def test_tract_floor_still_derives_from_the_percentile_threshold():
    """Guards the relationship the added constant must not have disturbed."""
    assert round(100 / DESERT_TRACT_FLOOR, 1) < DESERT_PERCENTILE_THRESHOLD
    assert round(100 / (DESERT_TRACT_FLOOR - 1), 1) >= DESERT_PERCENTILE_THRESHOLD


# ── B5 / F9: a non-numeric income must not destroy the whole report ──────────


def _datetime_income(df):
    out = df.copy()
    out["income"] = pd.to_datetime("2023-01-01")
    return out


def test_income_band_raises_typed_error_on_datetime_income(sample_df):
    """0.5.0: pd.cut raised a BARE ValueError ("bins must be of datetime64
    dtype") that no layer could classify."""
    with pytest.raises(MissingColumnError) as exc:
        H.denial_rate_by_income_band(_datetime_income(sample_df))
    assert "numeric" in str(exc.value)
    assert "pd.to_numeric" in str(exc.value)


def test_report_fails_up_front_not_three_sections_in(sample_df):
    """The report promises to validate before rendering. A wrong-dtype income is
    the same class of precondition failure as an absent column."""
    with pytest.raises(MissingColumnError) as exc:
        H.generate_disparity_report(_datetime_income(sample_df))
    assert "generate_disparity_report" in str(exc.value)


def test_the_allowlist_was_not_widened_to_fix_this():
    """The whole point of fixing it at the input. ValueError is
    GeographyVintageError's base class, so admitting it here would typeset a
    vintage refusal into a table cell — the swallowing 0.6.0 removed."""
    assert ValueError not in RENDERABLE_ERRORS
    assert MissingColumnError not in RENDERABLE_ERRORS
    assert H.GeographyVintageError not in RENDERABLE_ERRORS
    for err in RENDERABLE_ERRORS:
        assert not issubclass(H.GeographyVintageError, err), (
            f"{err.__name__} is a base class of GeographyVintageError — a "
            f"vintage refusal would be swallowed into a table cell"
        )


def test_numeric_income_still_works(sample_df):
    """The validation must not have made the happy path stricter."""
    assert not H.denial_rate_by_income_band(sample_df).empty
    assert H.generate_disparity_report(sample_df).startswith("# HMDA")


# ── B6: the cache that never existed ─────────────────────────────────────────


def test_dead_cache_symbols_are_gone():
    from hmdaanalyzer.data import loader

    assert not hasattr(loader, "get_cache_dir")
    assert not hasattr(schema, "CACHE_DIR")


# ── B7 / V: metadata ─────────────────────────────────────────────────────────


def test_version_is_single_sourced():
    """__version__ comes from installed metadata, so it cannot drift from
    pyproject.toml. Asserting the SHAPE, not the number, so this test does not
    need editing at every release."""
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", H.__version__), H.__version__
    assert H.__version__ != "0.0.0+unknown", "package is not installed"


def test_both_import_names_report_the_same_version():
    import hmda_analyzer

    assert hmda_analyzer.__version__ == H.__version__
    assert hmda_analyzer.__all__ == H.__all__


def test_distribution_declares_an_author():
    import importlib.metadata as md

    meta = md.metadata("hmda-analyzer")
    # PEP 621 `authors = [{name, email}]` renders into Author-email as
    # "Name <addr>"; setuptools leaves Author empty in that form.
    author = meta.get("Author-email") or meta.get("Author") or ""
    assert "Jay Patel" in author, f"no author in distribution metadata: {author!r}"


# ── The README values docs-check structurally cannot check ───────────────────
#
# docs-check asserts that every name in __all__ APPEARS in the README
# (assertion 6) and that every symbol it names IMPORTS (assertion 2). Neither
# looks at a NUMBER quoted in prose. So the README can say
# DESERT_PERCENTILE_THRESHOLD is 40, or that the floor is 3, and the gate stays
# green — which is the drift §M3.3a exists to prevent, one document over.
#
# docs-check.toml records this as an explicit non-assertion. These tests close
# it from the other side. They are here rather than in the gate because the gate
# travels byte-identical across the portfolio and this coupling is repo-specific.


def _readme_text():
    """The README, located relative to THIS FILE rather than the cwd.

    All four invocations that run this suite put README.md one level above
    tests/: the source tree, test-wheel (from the checkout root), test-sdist
    (from a directory assembled out of the tarball), and the docs-check job.
    Resolving from ``__file__`` rather than ``Path.cwd()`` is what makes that
    true in all four instead of three.
    """
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "README.md"
    assert path.is_file(), (
        f"README.md not found at {path}. This test reads it deliberately; if the "
        f"packaging changed so the README no longer ships beside tests/, fix the "
        f"packaging or move this assertion — do NOT skip it."
    )
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "phrase",
    [
        # Each is the README's own prose, quoting a live constant's value.
        "`DESERT_PERCENTILE_THRESHOLD` (25)",
        "`DESERT_DENIAL_RATE_FLOOR` (0.15)",
        "`DESERT_TRACT_FLOOR` (5)",
    ],
)
def test_readme_quotes_constants_that_still_hold(phrase):
    assert phrase in _readme_text(), (
        f"README no longer contains {phrase!r}. Either the constant moved and the "
        f"README was not updated, or the README was reworded — reconcile them."
    )


def test_readme_quoted_threshold_values_match_the_constants():
    """The other half: the phrases above must quote the CURRENT values."""
    readme = _readme_text()
    assert f"`DESERT_PERCENTILE_THRESHOLD` ({DESERT_PERCENTILE_THRESHOLD})" in readme
    assert f"`DESERT_DENIAL_RATE_FLOOR` ({DESERT_DENIAL_RATE_FLOOR})" in readme
    assert f"`DESERT_TRACT_FLOOR` ({DESERT_TRACT_FLOOR})" in readme
    assert f"fewer than **{schema.MIN_APPLICATIONS_FOR_RATE}**" in readme


def test_readme_states_the_supported_python_range():
    """The README's floor is DERIVED from ``requires-python``, not typed twice.

    0.6.0 hard-coded ``"Python **3.11 or newer**"`` here, which meant the floor
    was declared in two files and asserted against neither — change one and this
    test fails with no indication that the other is the authority. 0.6.1 reads
    ``pyproject.toml`` (present beside ``README.md`` in all four invocations, the
    same property ``_readme_text`` relies on) so the two cannot drift apart.

    Read with a regex rather than ``tomllib``: ``tomllib`` is 3.11+, and a test
    of a 3.9 floor that can only run on 3.11 asserts nothing where it matters.

    The matrix sentence stays a literal. It is a claim about the CI workflows,
    and the workflows do not ship in the sdist — deriving it would either make
    this test unrunnable from the tarball or need a skip, and a skip is how a
    gate stops being one.
    """
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject.is_file(), f"pyproject.toml not found at {pyproject}"
    m = re.search(
        r'^requires-python\s*=\s*"[><=~!]*\s*(\d+)\.(\d+)',
        pyproject.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert m, "no requires-python line found in pyproject.toml"
    floor = f"{m.group(1)}.{m.group(2)}"

    readme = _readme_text()
    assert f"Python **{floor} or newer**" in readme, (
        f"pyproject declares a floor of {floor}; the README does not say so. "
        f"These are one claim in two files — reconcile them."
    )
    assert "3.9, 3.10, 3.11, 3.12, 3.13 and 3.14" in readme


def test_readme_column_count_claim_matches_the_schema():
    """The '99 raw columns' figure appears in prose in two places."""
    readme = _readme_text()
    n = len(schema.RAW_LAR_COLUMNS)
    assert n == 99
    assert f"same {n} raw columns" in readme
    assert f"the {n} raw CFPB columns" in readme
