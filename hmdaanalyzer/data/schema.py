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
