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

    # Or load multiple years at once (inclusive range) with provenance
    # from hmdaanalyzer import load_range
    # df = load_range(2021, 2023, state="IL", county="17031", limit=10_000)
    # df["activity_year"] tags each row's year; filters apply to every year

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

## Multi-Year Loading (`load_range`)

`load_range(start_year, end_year, ...)` fetches HMDA LAR for **every year in the
inclusive range** and returns one concatenated DataFrame with an `activity_year`
provenance column:

    from hmdaanalyzer import load_range

    df = load_range(2021, 2023, state="IL", county="17031", limit=10_000)
    df["activity_year"].value_counts()   # rows tagged by year

- **Filters apply to every year.** `state`, `lei`, `county`, and `limit` are
  forwarded identically to each per-year fetch; `limit` is **per year**.
- **Fail-loud, no partial.** If any year's fetch fails, `load_range` raises
  immediately with the failing year named (a `CFPBAPIError` keeps its HTTP status)
  and returns **no** partial frame — it never silently skips a year.
- **Schema guard.** Each year's columns are validated against a canonical set;
  a missing or unexpected column raises `SchemaValidationError` naming the year,
  rather than silently NaN-filling or dropping fields.
- **Provenance checked.** The native `activity_year` is asserted to match the
  requested year; a wrong-year payload raises `ActivityYearMismatchError`.
- **Empty years are fine.** A valid year matching zero rows is not an error; its
  empty frame just contributes no rows.

The CFPB column schema is identical across **2018–2025** (2018 is the earliest year
the API serves), so no columns are year-conditional.

> ⚠️ **Scale.** Multi-year national pulls are enormous — the same filters apply to
> every year, so a range with no `state`/`county` filter multiplies a full national
> LAR file by the number of years. Always filter multi-year loads. `load_range`
> streams each year to `limit`; it does not silently cap or block large pulls.

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
- **CRA-proxy distribution** — borrower-income & tract-income distribution of
  originations (`cra_proxy_distribution`; see below)

---

## CRA-Proxy Distribution (`cra_proxy_distribution`)

Descriptive borrower-income and geographic (tract-income) distribution of mortgage
**originations**, approximating the *distribution dimensions* a CRA lending analysis
looks at. It is a **pure transform** on a frame you already loaded — no fetch, no network.

    from hmdaanalyzer import cra_proxy_distribution, load_from_api

    df = load_from_api(year=2023, state="RI")
    result = cra_proxy_distribution(df, by="both")   # "borrower" | "tract" | "both"

    for t in result.tables:
        print(t.dimension, t.year, "denominator:", t.classified_denominator,
              "excluded:", t.excluded)
        print(t.distribution)          # category, count, cra_proxy_share

Each table is tidy — `category` (Low / Moderate / Middle / Upper), `count`, and
`cra_proxy_share` — plus the **classified denominator** and an explicit
**excluded/unclassified count**. Bands follow 12 CFR §25/§228/§345 (Low `0 < MFI% < 50`,
Moderate `[50, 80)`, Middle `[80, 120)`, Upper `≥ 120`; LMI = Low + Moderate).
A frame spanning ≥2 `activity_year`s produces **per-year** tables, each using that
year's own annual area median. Purchased loans (`action_taken == 6`) are excluded by
default; `include_purchased=True` adds them as a separate, labeled cut — never blended.

### ⚠️ This is a PROXY — read before using the numbers

`cra_proxy_distribution` is **not** a CRA rating, grade, metric, or performance evaluation.
Every returned table carries `STANDARD_CRA_PROXY_CAVEAT` and an explicit no-comparator
line, and the share column is named `cra_proxy_share` so no copied cell reads as a CRA
metric. The limits, prominently:

- **Not assessment-area-bound.** CRA distribution tests are computed within a bank's
  designated assessment area(s); HMDA has no assessment-area concept, so this spans all
  HMDA lending in the requested geography — a different population than any CRA exam
  evaluates. (The largest gap.)
- **Mortgage-only**; the reporter population ≠ CRA-covered institutions.
- **No comparator/benchmark in v1** — a distribution alone is **not interpretable as CRA
  performance**. The demographic (ACS/census) baseline is deferred to v2.
- **Borrower and tract denominators differ.** NA-income multifamily / non-natural-person
  loans are excluded from the borrower denominator but carry a valid tract (so they count
  in the geographic denominator). **Do not difference the two LMI%s.**
- HMDA `income` is the (often combined) income relied on in the credit decision — an
  upward-biased proxy that tends to **understate** the LMI borrower share.

The full methodology — including the fabrication firewall — ships inside the wheel:

    from hmdaanalyzer import get_methodology_path
    print(get_methodology_path().read_text())

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

86 tests across all modules (offline/mocked; no live API calls).

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
