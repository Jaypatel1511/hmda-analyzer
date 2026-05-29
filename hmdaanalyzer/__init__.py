from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("hmda-analyzer")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from hmdaanalyzer.data.loader import (
    load_from_api, load_from_file, load_sample,
)
from hmdaanalyzer.analysis.disparity import (
    denial_rate_by_race, disparity_ratio,
    denial_rate_by_income_band, denial_reasons_by_race,
)
from hmdaanalyzer.analysis.geographic import (
    lending_by_tract, lending_by_county, lending_by_state,
    lending_desert_score, racial_composition_by_tract,
)
from hmdaanalyzer.analysis.lender import (
    lender_summary, lender_vs_market, top_lenders_by_volume,
)
from hmdaanalyzer.report.generator import (
    generate_disparity_report, summary_table,
)
__all__ = [
    "load_from_api", "load_from_file", "load_sample",
    "denial_rate_by_race", "disparity_ratio",
    "denial_rate_by_income_band", "denial_reasons_by_race",
    "lending_by_tract", "lending_by_county", "lending_by_state",
    "lending_desert_score", "racial_composition_by_tract",
    "lender_summary", "lender_vs_market", "top_lenders_by_volume",
    "generate_disparity_report", "summary_table",
]
