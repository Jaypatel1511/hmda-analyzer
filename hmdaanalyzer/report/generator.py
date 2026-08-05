"""
Generate HMDA analysis reports.

**On the ``except`` clauses below — the allowlist is inverted, deliberately.**

Every ``try`` in this module used to catch ``except Exception`` with a re-raise
allowlist naming ``MissingColumnError`` only (and ``summary_table`` named
nothing at all). That shape swallows every exception type added *after* it was
written, and renders the failure into a markdown table cell — a report that looks
complete with a refusal typeset into it, which is strictly worse than the warning
the methodology rejects: a cell reading "Error: ..." looks like a rendering
glitch rather than a refusal, and every surrounding section still carries
numbers.

So these blocks now name the **narrow, expected** failures they can actually
render, and let everything else propagate. A report that fails to generate is a
correct outcome; a report that renders a refusal as a table cell is not.
``GeographyVintageError`` is the exception that motivated the inversion, but it
is deliberately NOT what the blocks are keyed on — enumerating types to re-raise
is the pattern that created the problem (methodology §M3.2a).

**What is and is not enforced.** The AST site-list test in
``tests/test_geography_vintage_sites.py`` walks ``hmdaanalyzer/**/*.py``, but it
enumerates *geography-keyed aggregation sites* and this module has none, so its
expected set is silent about this file. **Nothing gates the exception
allowlist.** A sixth ``except Exception`` added here tomorrow would swallow the
refusal and no test would fail. The inversion fails safe — a new swallowing site
has to be written deliberately rather than inherited by default — but it is a
convention, not a gate, and it is not the same thing as the site-list
enforcement the aggregation sites get.
"""
import pandas as pd
from hmdaanalyzer.exceptions import (
    MissingColumnError, ReferenceGroupError, _require_columns,
)

from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, disparity_ratio, denial_rate_by_income_band
)
from hmdaanalyzer.analysis.geographic import (
    lending_by_state, lending_by_county, lending_desert_score
)
from hmdaanalyzer.analysis.lender import lender_summary, lender_vs_market

#: The failures a report section can meaningfully render into a table cell: the
#: frame is well-formed but this particular section has nothing coherent to say
#: about it. ``ValueError`` is deliberately absent — it is the base class of
#: ``MissingColumnError``, ``SchemaValidationError``, ``GeographyVintageError``
#: and ``UnreachableFlagError``, so catching it would restore exactly the
#: swallowing this inversion removes.
RENDERABLE_ERRORS = (KeyError, IndexError, ZeroDivisionError, TypeError,
                     ArithmeticError, AttributeError, ReferenceGroupError)


def generate_disparity_report(
    df: pd.DataFrame,
    title: str = "HMDA Disparity Analysis",
    lei: str = None,
) -> str:
    """
    Generate a full HMDA disparity analysis report as Markdown.

    Raises:
        MissingColumnError: if ``df`` lacks a column the report's analysis
            sections require, or if ``lei`` is given but ``df`` has no ``lei``
            column. Validated up front so a schema problem raises a clear error
            rather than being rendered as a misleading "no disparity" report.
    """
    # Schema precondition: the report's denial-rate, disparity-ratio, and
    # income-band sections require these columns. Validate the union up front and
    # raise before rendering anything, so a missing column can never be swallowed
    # into an error cell or an empty Key Findings section.
    _require_columns(
        df,
        ["action_taken", "derived_race", "is_denied", "income"],
        "generate_disparity_report",
    )

    if lei is not None:
        if "lei" not in df.columns:
            raise MissingColumnError(
                f"generate_disparity_report was given lei={lei!r} but requires "
                f"column 'lei' to scope the report; got: {list(df.columns)}"
            )
        analysis_df = df[df["lei"] == lei]
        scope = f"Lender: {lei}"
    else:
        analysis_df = df
        scope = "All Lenders"

    # Legitimate empty result: schema is fine, the lei filter (including lei="")
    # just matched no rows. Render a clean no-records report instead of indexing
    # into an empty frame (which would raise IndexError on .iloc[0] below).
    if lei is not None and analysis_df.empty:
        return "\n".join([
            "# HMDA Lending Disparity Analysis Report",
            f"## {title}",
            "",
            f"**Scope:** {scope}",
            "**Total Records:** 0",
            "",
            "---",
            "",
            f"No records found for LEI {lei!r}.",
        ])

    total = len(analysis_df)
    actionable = analysis_df[analysis_df["action_taken"].isin([1, 2, 3])]
    year = analysis_df["activity_year"].iloc[0] if "activity_year" in analysis_df.columns else "N/A"

    lines = [
        f"# HMDA Lending Disparity Analysis Report",
        f"## {title}",
        "",
        f"**Scope:** {scope}",
        f"**Year:** {year}",
        f"**Total Records:** {total:,}",
        f"**Actionable Applications:** {len(actionable):,}",
        "",
        "---",
        "",
        "## Denial Rate by Race",
        "",
        "| Race/Ethnicity | Applications | Denials | Denial Rate |",
        "|----------------|-------------|---------|-------------|",
    ]

    try:
        rates = denial_rate_by_race(analysis_df)
        for _, row in rates.iterrows():
            lines.append(
                f"| {row['derived_race']} | {row['applications']:,} | "
                f"{int(row['denials']):,} | {row['denial_rate']*100:.1f}% |"
            )
    except RENDERABLE_ERRORS as e:
        lines.append(f"| Error computing denial rates: {e} |")

    lines += [
        "",
        "---",
        "",
        "## Disparity Ratios (vs White Applicants)",
        "",
        "A disparity ratio >= 2.0 indicates HIGH disparity (CFPB threshold).",
        "A disparity ratio >= 1.5 indicates MODERATE disparity.",
        "",
        "| Race/Ethnicity | Denial Rate | Reference Rate | Disparity Ratio | Level |",
        "|----------------|-------------|----------------|-----------------|-------|",
    ]

    try:
        disp = disparity_ratio(analysis_df)
        for _, row in disp.iterrows():
            if row["derived_race"] == "White":
                continue
            ratio = f"{row['disparity_ratio']:.2f}x" if pd.notna(row.get("disparity_ratio")) else "N/A"
            level_emoji = {
                "HIGH": "🔴 HIGH",
                "MODERATE": "🟡 MODERATE",
                "LOW": "🟢 LOW",
                "FAVORABLE": "✅ FAVORABLE",
                "N/A": "—",
            }.get(row.get("disparity_level", "N/A"), "—")

            lines.append(
                f"| {row['derived_race']} | "
                f"{row['denial_rate']*100:.1f}% | "
                f"{row['reference_denial_rate']*100:.1f}% | "
                f"{ratio} | {level_emoji} |"
            )
    except RENDERABLE_ERRORS as e:
        lines.append(f"| Error: {e} |")

    lines += [
        "",
        "---",
        "",
        "## Denial Rate by Income Band",
        "",
        "| Income Band | Applications | Denial Rate |",
        "|-------------|-------------|-------------|",
    ]

    try:
        income_df = denial_rate_by_income_band(analysis_df)
        for _, row in income_df.iterrows():
            lines.append(
                f"| {row['income_band']} | {row['applications']:,} | "
                f"{row['denial_rate']*100:.1f}% |"
            )
    except RENDERABLE_ERRORS as e:
        lines.append(f"| Error: {e} |")

    lines += [
        "",
        "---",
        "",
        "## Key Findings",
        "",
    ]

    try:
        disp = disparity_ratio(analysis_df)
        high = disp[disp.get("disparity_level", pd.Series()) == "HIGH"]
        if not high.empty:
            lines.append("**High Disparity Groups:**")
            for _, row in high.iterrows():
                if row["derived_race"] != "White":
                    lines.append(
                        f"- {row['derived_race']}: "
                        f"{row['disparity_ratio']:.1f}x denial rate vs White applicants"
                    )
            lines.append("")
    except RENDERABLE_ERRORS:
        pass

    return "\n".join(lines)


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return denial rates and disparity ratios as a DataFrame."""
    try:
        return disparity_ratio(df)
    except RENDERABLE_ERRORS:
        # The fifth swallowing site, and it was the worst: it had NO re-raise
        # allowlist at all, so it swallowed everything the rest of the module was
        # careful to re-raise and silently substituted a different analysis.
        # ReferenceGroupError -- no baseline group to divide by -- is the case
        # this fallback was written for and the only one it now covers (§M3.2a).
        return denial_rate_by_race(df)
