"""
Constants, field mappings, and dataclasses for HMDA LAR data analysis.
Based on 2024 HMDA Filing Instruction Guide (FIG) and CFPB Data Browser API.
"""

# ── CFPB HMDA Data Browser API ────────────────────────────────────────────────
HMDA_API_BASE = "https://ffiec.cfpb.gov/v2/data-browser-api/view"
HMDA_AGG_BASE = "https://ffiec.cfpb.gov/v2/data-browser-api/view/aggregations"

# ── Action Taken Codes ────────────────────────────────────────────────────────
ACTION_TAKEN = {
    1: "Loan originated",
    2: "Application approved but not accepted",
    3: "Application denied",
    4: "Application withdrawn by applicant",
    5: "File closed for incompleteness",
    6: "Purchased loan",
    7: "Preapproval request denied",
    8: "Preapproval request approved but not accepted",
}

APPROVED_ACTIONS = {1, 2, 8}
DENIED_ACTIONS   = {3, 7}
WITHDRAWN_ACTIONS = {4, 5}

# ── Race Codes ────────────────────────────────────────────────────────────────
RACE_CODES = {
    1: "American Indian or Alaska Native",
    2: "Asian",
    3: "Black or African American",
    4: "Native Hawaiian or Other Pacific Islander",
    5: "White",
    6: "Not applicable",
    7: "Information not provided",
}

# ── Ethnicity Codes ───────────────────────────────────────────────────────────
ETHNICITY_CODES = {
    1: "Hispanic or Latino",
    2: "Not Hispanic or Latino",
    3: "Information not provided",
    4: "Not applicable",
}

# ── Sex Codes ─────────────────────────────────────────────────────────────────
SEX_CODES = {
    1: "Male",
    2: "Female",
    3: "Information not provided",
    4: "Not applicable",
    6: "Both male and female",
}

# ── Loan Type Codes ───────────────────────────────────────────────────────────
LOAN_TYPE = {
    1: "Conventional",
    2: "FHA",
    3: "VA",
    4: "RHS/FSA",
}

# ── Loan Purpose Codes ────────────────────────────────────────────────────────
LOAN_PURPOSE = {
    1: "Home purchase",
    2: "Home improvement",
    31: "Refinancing",
    32: "Cash-out refinancing",
    4: "Other purpose",
    5: "Not applicable",
}

# ── Denial Reason Codes ───────────────────────────────────────────────────────
DENIAL_REASONS = {
    1: "Debt-to-income ratio",
    2: "Employment history",
    3: "Credit history",
    4: "Collateral",
    5: "Insufficient cash (downpayment, closing costs)",
    6: "Unverifiable information",
    7: "Credit application incomplete",
    8: "Mortgage insurance denied",
    9: "Other",
    10: "Not applicable",
}

# ── Key LAR Fields We Use ─────────────────────────────────────────────────────
LAR_FIELDS = [
    "action_taken",
    "loan_type",
    "loan_purpose",
    "loan_amount",
    "income",
    "applicant_race_1",
    "applicant_ethnicity_1",
    "applicant_sex",
    "derived_race",
    "derived_ethnicity",
    "derived_sex",
    "census_tract",
    "county_code",
    "state_code",
    "denial_reason_1",
    "denial_reason_2",
    "interest_rate",
    "rate_spread",
    "hoepa_status",
    "lien_status",
    "lei",
    "activity_year",
]

# ── Multi-year loading (load_range) ───────────────────────────────────────────
# Earliest year the CFPB Data Browser API serves. Verified empirically from a
# residential probe: a 2017 request returns HTTP 400 ("must provide years in the
# range of 2018-…"). The API's 400 text names an upper bound of 2023, but that
# text is stale — 2024 and 2025 single-year requests return correct-year data.
# We therefore do NOT hard-code a served upper bound; the year ceiling is the
# current calendar year, and any not-yet-served year fails loud at the API.
EARLIEST_HMDA_YEAR = 2018

# The RAW CFPB column set — what the Data Browser actually serves, and the only
# thing the schema guard is for. Empirically verified IDENTICAL across 2018–2025
# (same 99 columns, same names, every year).
#
# This set is deliberately SEPARATE from the columns ``_clean`` derives. The
# guard's documented job is to detect *CFPB* schema drift; validating our own
# derived names against it makes a drift detector that is increasingly about us,
# and — the reason this split exists — it is a total failure on the first call,
# not an edge case. ``_validate_lar_schema`` uses strict two-way set equality, so
# adding ANY derived column to ``_clean``'s output made EVERY ``load_range`` call
# raise ``SchemaValidationError: unexpected=[...]`` on the first year it fetched.
# Verified by executing it before the split. Methodology §M4.4, option 3.
RAW_LAR_COLUMNS = frozenset({
    # provenance + geography
    "activity_year", "lei", "derived_msa_md", "state_code", "county_code",
    "census_tract", "conforming_loan_limit",
    # derived roll-ups
    "derived_loan_product_type", "derived_dwelling_category", "derived_ethnicity",
    "derived_race", "derived_sex",
    # action / loan
    "action_taken", "purchaser_type", "preapproval", "loan_type", "loan_purpose",
    "lien_status", "reverse_mortgage", "open_end_line_of_credit",
    "business_or_commercial_purpose", "loan_amount", "loan_to_value_ratio",
    "interest_rate", "rate_spread", "hoepa_status", "total_loan_costs",
    "total_points_and_fees", "origination_charges", "discount_points",
    "lender_credits", "loan_term", "prepayment_penalty_term", "intro_rate_period",
    "negative_amortization", "interest_only_payment", "balloon_payment",
    "other_nonamortizing_features", "property_value", "construction_method",
    "occupancy_type", "manufactured_home_secured_property_type",
    "manufactured_home_land_property_interest", "total_units",
    "multifamily_affordable_units", "income", "debt_to_income_ratio",
    # applicant / co-applicant demographics
    "applicant_credit_score_type", "co_applicant_credit_score_type",
    "applicant_ethnicity_1", "applicant_ethnicity_2", "applicant_ethnicity_3",
    "applicant_ethnicity_4", "applicant_ethnicity_5",
    "co_applicant_ethnicity_1", "co_applicant_ethnicity_2",
    "co_applicant_ethnicity_3", "co_applicant_ethnicity_4",
    "co_applicant_ethnicity_5", "applicant_ethnicity_observed",
    "co_applicant_ethnicity_observed",
    "applicant_race_1", "applicant_race_2", "applicant_race_3", "applicant_race_4",
    "applicant_race_5", "co_applicant_race_1", "co_applicant_race_2",
    "co_applicant_race_3", "co_applicant_race_4", "co_applicant_race_5",
    "applicant_race_observed", "co_applicant_race_observed",
    "applicant_sex", "co_applicant_sex", "applicant_sex_observed",
    "co_applicant_sex_observed", "applicant_age", "co_applicant_age",
    "applicant_age_above_62", "co_applicant_age_above_62",
    "submission_of_application", "initially_payable_to_institution",
    # AUS / denial reasons
    "aus_1", "aus_2", "aus_3", "aus_4", "aus_5",
    "denial_reason_1", "denial_reason_2", "denial_reason_3", "denial_reason_4",
    # tract context
    "tract_population", "tract_minority_population_percent",
    "ffiec_msa_md_median_family_income", "tract_to_msa_income_percentage",
    "tract_owner_occupied_units", "tract_one_to_four_family_homes",
    "tract_median_age_of_housing_units",
})

# Columns ``_clean`` DERIVES and adds. Not CFPB's, so not the guard's business.
# ``_validate_lar_schema`` subtracts this set before comparing, which is what
# makes adding a future derived column a non-event instead of a release-breaking
# one.
DERIVED_LAR_COLUMNS = frozenset({
    # booleans derived from action_taken
    "is_approved", "is_denied",
    # census-tract GEOID delineation basis, derived from activity_year via
    # hmdaanalyzer.geography_vintage.TRACT_GEOID_BASIS_BY_YEAR. PROVENANCE ONLY —
    # every guard derives the basis from ``activity_year``, never from this
    # column, because ``.agg()`` drops it, ``pd.concat`` with a frame lacking it
    # yields silent NaN and flips int64→float64, and the function most in need
    # of the guard (``lending_by_tract``) is an ``.agg()``. Methodology §M4.1.
    "tract_geoid_vintage",
})

# Backwards-compatible union: the full set a cleaned ``load_from_api`` frame
# carries. Kept as a public name because callers and tests import it. The guard
# no longer compares against this directly — see ``_validate_lar_schema``.
EXPECTED_LAR_COLUMNS = RAW_LAR_COLUMNS | DERIVED_LAR_COLUMNS

# ── Cache Directory ───────────────────────────────────────────────────────────
import os
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".hmdaanalyzer", "cache")

# ── Disparity Thresholds ──────────────────────────────────────────────────────
DISPARITY_THRESHOLDS = {
    "high":     2.0,   # Denial rate ratio >= 2.0x = high disparity
    "moderate": 1.5,   # Denial rate ratio >= 1.5x = moderate disparity
    "low":      1.0,   # Below 1.0x = no disparity
}

# ── Reference Group for Disparity ────────────────────────────────────────────
REFERENCE_RACE = "White"
