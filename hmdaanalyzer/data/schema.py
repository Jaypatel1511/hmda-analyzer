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

# Canonical column set that ``load_from_api`` returns (after ``_clean``) for a
# valid 2018+ query. Empirically verified IDENTICAL across 2018–2025 (same 99 raw
# API columns each year), plus the two derived booleans ``_clean`` adds
# (``is_approved``/``is_denied``). ``load_range`` validates every fetched year's
# frame against this set and RAISES on any missing or unexpected column — the
# load-bearing regression guard against a silent CFPB schema change. If the CFPB
# schema legitimately drifts in a future year, this frozenset (not silent NaNs)
# is the single place that must be updated, with the drift documented.
EXPECTED_LAR_COLUMNS = frozenset({
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
    # derived booleans added by _clean()
    "is_approved", "is_denied",
})

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
