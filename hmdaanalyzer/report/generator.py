"""
Generate HMDA analysis reports.
"""
import pandas as pd
from hmdaanalyzer.exceptions import MissingColumnError
from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, disparity_ratio, denial_rate_by_income_band
)
from hmdaanalyzer.analysis.geographic import (
    lending_by_state, lending_by_county, lending_desert_score
)
from hmdaanalyzer.analysis.lender import lender_summary, lender_vs_market


def generate_disparity_report(
    df: pd.DataFrame,
    title: str = "HMDA Disparity Analysis",
    lei: str = None,
) -> str:
    """
    Generate a full HMDA disparity analysis report as Markdown.
    """
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception:
        pass

    return "\n".join(lines)


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return denial rates and disparity ratios as a DataFrame."""
    try:
        return disparity_ratio(df)
    except Exception:
        return denial_rate_by_race(df)
