# hmda-analyzer 📊

**HMDA mortgage lending disparity analyzer.**

Compute denial rate disparities by race, identify lending deserts, benchmark lenders
against peers, and generate fair lending analysis reports — using CFPB HMDA LAR data.
Free public API, no authentication required.

---

## Why hmda-analyzer?

HMDA data covers 10+ million mortgage applications per year with borrower demographics,
denial rates, loan amounts, and census tract locations. It is the most powerful public
dataset for analyzing mortgage lending disparities — but it requires significant
engineering to use. hmda-analyzer makes it accessible in Python.

---

## Installation

    pip install hmda-analyzer

Both of these import styles work after installation:

    from hmdaanalyzer import denial_rate_by_race   # canonical form
    from hmda_analyzer import denial_rate_by_race   # pip-name convention alias

---

## Quickstart

    from hmdaanalyzer import (
        load_sample, denial_rate_by_race, disparity_ratio,
        lending_by_tract, lending_desert_score, lender_summary,
        generate_disparity_report,
    )

    # Load sample data (no API required)
    df = load_sample(n=5000)

    # Or load from CFPB API — streams and stops at limit rows
    # df = load_from_api(year=2023, state="IL", limit=10_000)

    # Denial rates by race
    rates = denial_rate_by_race(df)
    print(rates)

    # Disparity ratios vs White applicants
    disparities = disparity_ratio(df)
    print(disparities)

    # Geographic analysis — lending activity by census tract
    tracts = lending_by_tract(df)
    print(tracts.head())

    # Lending desert identification — tracts with abnormally low application volume
    deserts = lending_desert_score(df)
    print(deserts.head())

    # Lender analysis
    summary = lender_summary(df, lei="LEI000001")

    # Full disparity report
    report = generate_disparity_report(df, title="Illinois Mortgage Market 2023")
    print(report)

---

## Analyses Supported

- Denial rate by race and ethnicity
- Disparity ratios vs reference group (default: White applicants)
- Denial rate by income band
- Denial reasons by race
- Lending activity by census tract, county, and state
- Lending desert identification (low application volume tracts)
- Lender vs market comparison
- Top lenders by origination volume

---

## Error Handling

If you pass a DataFrame that is missing a column an analysis requires, the function
raises **`MissingColumnError`** (importable from `hmdaanalyzer` or `hmda_analyzer`)
instead of silently returning an empty result. In a fair-lending context a silent
empty result can read as "no disparity," so a schema problem fails loudly:

    from hmdaanalyzer import MissingColumnError, lending_by_state

    try:
        lending_by_state(df)            # df has 'state' but not 'state_code'
    except MissingColumnError as e:
        print(e)                        # names the function and the missing column

`MissingColumnError` subclasses `ValueError`, so existing `except ValueError`
handlers keep working. This applies to the analysis functions and to filtering
arguments: passing `lei=...` or `state=...` when that column is absent raises rather
than silently computing whole-market results. A **well-formed query that simply
matches no rows is not an error** — e.g. `lender_summary(df, lei=...)` with a valid
schema but an unknown LEI still returns an empty `{}`, and
`generate_disparity_report(df, lei=...)` returns a clean no-records report.

> **Breaking change in 0.3.0:** functions that previously returned an empty result on
> a missing column now raise `MissingColumnError`. See the CHANGELOG for the full list.

---

## Disparity Ratio Thresholds

Based on CFPB fair lending examination standards:

- >= 2.0x — HIGH disparity (triggers regulatory scrutiny)
- >= 1.5x — MODERATE disparity
- < 1.5x — LOW disparity
- < 1.0x — FAVORABLE (group has lower denial rate than reference)

---

## Data Sources

CFPB HMDA Data Browser API — free, no API key required.
2024 data covers 4,908 institutions and millions of loan applications.

    https://ffiec.cfpb.gov/data-browser/

### Cloud environments (Colab/hosted notebooks)

From cloud/datacenter environments such as Google Colab, an API request can hit an
HTTP 403 "Access Denied" from the CFPB edge (Akamai) even when the query is valid —
it's an access/network block, not a problem with your year/state/county values.
`hmda-analyzer` sends an identifying User-Agent and `Accept`/`Accept-Language`
headers that clear this in the cases we reproduced, and a 403 now raises a typed
`CFPBAPIError` explaining the situation. If you still hit a block, run locally or
download the CSV directly from the HMDA Data Browser and load it with
`load_from_file(...)`.

---

## Running Tests

    PYTHONPATH=. pytest tests/ -v

70 tests across all modules.

---

## Who This Is For

- Fair lending analysts and compliance teams at banks and CDFIs
- Community reinvestment researchers studying mortgage disparities
- Journalists covering housing discrimination and redlining
- Regulators and examiners analyzing lender performance
- Academics studying racial wealth gaps and homeownership barriers

---

## License

MIT 2026 Jaypatel1511
