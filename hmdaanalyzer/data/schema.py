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

#: The ``actions_taken`` filter ``load_from_api`` sends to the CFPB Data Browser.
#:
#: **6 ("Purchased loan") IS DELIBERATELY ABSENT, AND THAT HAS A CONSEQUENCE THE
#: API DOES NOT ANNOUNCE.** A frame fetched by :func:`load_from_api` or
#: :func:`load_range` cannot contain a single ``action_taken == 6`` row, because
#: the server was never asked for one. ``cra_proxy_distribution``'s
#: ``include_purchased=True`` selects exactly those rows, so on any frame this
#: package's own loaders produced it selects nothing and yields a
#: ``universe="purchased"`` table with a zero denominator, four zero counts and
#: an EMPTY ``excluded`` tally — a distribution that reads as "this lender
#: purchased no LMI loans" when the truth is "purchased loans were never
#: fetched". That is a fabricated empty, and it is why this set is a named
#: constant the loader docstring and the README both point at rather than a
#: string literal buried in a query dict.
#:
#: The set is NOT widened to include 6 here, and the reason shipped through the
#: 0.6.0 build was an overstatement worth correcting rather than repeating. It
#: read: folding purchased loans into the default fetch "would change the
#: denominator of every existing denial-rate, disparity and tract analysis in the
#: package". Measured, it changes **one of ten** — and only because
#: ``racial_composition_by_tract`` was missing its ``action_taken`` filter, which
#: 0.6.0 fixed. The other nine already filter ``action_taken.isin([1, 2, 3])``,
#: so an action-6 row is invisible to them however it arrives. With that fix in,
#: the answer is **zero of ten**.
#:
#: The decision not to widen is unchanged, on the argument that actually holds:
#: a purchased loan is an origination somebody else made and later bought. It is
#: not an application to this institution, so it does not belong in an
#: application-keyed fetch at all — regardless of how many downstream
#: denominators would notice. Widening would also silently double the row count
#: and the API cost of every default load to serve one optional flag.
#:
#: A caller who wants them supplies the frame themselves — see
#: :func:`load_from_file` — and ``include_purchased`` then does exactly what it
#: says. On a frame that cannot supply them it now raises
#: (:class:`~hmdaanalyzer.EmptyUniverseError`) rather than returning a
#: zero-denominator table.
API_ACTIONS_TAKEN = (1, 2, 3, 4, 5)

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
#: Provenance column recording whether ``limit`` cut the fetch short.
#:
#: ``load_from_api`` streams the CFPB file and stops at ``limit`` rows. That is
#: TRUNCATION IN SERVER FILE ORDER, not a sample: the rows kept are the first
#: ``limit`` the server happened to emit, which is not random with respect to
#: lender, geography, race or outcome. A denial rate computed on a truncated
#: pull is a statistic about an arbitrary slice, presented with exactly the
#: shape of a statistic about the state.
#:
#: A print is not a channel — it dies with the session while the number goes on
#: into a spreadsheet — and a ``warnings.warn`` is shown once per location, so a
#: notebook re-run is silent. The channel is therefore the returned frame, for
#: the same reason ``tract_geoid_vintage`` is (§M3.2, §M4.1).
TRUNCATED_COLUMN = "limit_truncated"

DERIVED_LAR_COLUMNS = frozenset({
    # booleans derived from action_taken
    "is_approved", "is_denied",
    # whether ``limit`` stopped the stream before the server's file ended.
    # Derived here, so ``_validate_lar_schema`` subtracts it and a truncated
    # fetch does not read as CFPB schema drift.
    "limit_truncated",
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

# ── Cache Directory: REMOVED in 0.6.0 ─────────────────────────────────────────
# ``CACHE_DIR`` and ``loader.get_cache_dir()`` are gone. Nothing in the package
# or the suite ever called them, and nothing ever wrote a byte to that path:
# every loader fetches or reads straight through. A name that promises a cache
# which does not exist is worse than no name — a reader plans around it, and a
# maintainer preserves it across refactors on the assumption something depends
# on it. If caching is added later it arrives with the code that uses it.

# ── Disparity Thresholds ──────────────────────────────────────────────────────
DISPARITY_THRESHOLDS = {
    "high":     2.0,   # Denial rate ratio >= 2.0x = high disparity
    "moderate": 1.5,   # Denial rate ratio >= 1.5x = moderate disparity
    "low":      1.0,   # Below 1.0x = no disparity
}

# ── Reference Group for Disparity ────────────────────────────────────────────
REFERENCE_RACE = "White"

# ── Small-N suppression ───────────────────────────────────────────────────────
#: Minimum actionable applications a ``derived_race`` group needs before
#: ``denial_rate_by_race`` will report a rate for it.
#:
#: **This rule is not new in 0.6.0. It has been in force since the function was
#: written, as the bare literal ``result[result["applications"] >= 5]``, and it
#: was SILENT.** Measured on ``load_sample(n=60)``: eight race groups enter,
#: three come out, and five protected classes — including "Asian" at 4
#: applications — vanish from the returned frame with no column, no attribute
#: and no message recording that they existed. The suppression propagates
#: untouched into ``disparity_ratio``, ``lender_vs_market``, ``summary_table``
#: and every report section built on them.
#:
#: In a fair-lending context that is the precise artefact ``exceptions.py``
#: exists to prevent: a group absent from a disparity table is indistinguishable
#: from a group with no disparity, and the absence reaches the memo, the
#: spreadsheet and the regulatory file with no way to recover what was removed.
#:
#: WHY THE NUMBER IS UNCHANGED. A denial rate over fewer than five applications
#: is dominated by a single decision — at n=4 the only possible rates are 0, 25,
#: 50, 75 and 100% — so a ratio built on it carries a precision it does not
#: have. Five is also the shipped behaviour of every released version, and
#: moving it would silently change every number this package has ever produced.
#: 0.6.0 therefore changes the VISIBILITY of the rule, not the rule. The
#: threshold is named here so the report layer, the README and the tests read
#: one number instead of four copies of a literal — the same drift this
#: package's DESERT_PERCENTILE_THRESHOLD exists to prevent.
#:
#: WHAT THIS IS NOT. It is not a disclosure-avoidance or re-identification
#: control, and it is not applied at tract level: ``lending_by_tract``,
#: ``lending_desert_score`` and ``racial_composition_by_tract`` report every
#: tract they are given, including single-application ones. Choosing a
#: tract-level suppression rule is a methodology decision about disclosure that
#: this release deliberately does not make — see the README.
MIN_APPLICATIONS_FOR_RATE = 5
