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

**The design commitment, stated once.** In a fair lending context an empty or
silently-narrowed result reads as "no disparity." This library therefore refuses
rather than guesses: a schema problem raises, a frame that pools incompatible
census geographies raises, an arithmetically impossible flag raises, and every
narrowing it *does* perform — small-N suppression, `limit` truncation, `vintage=`
selection — is written into the returned object where it outlives the session.
If you are looking for the list of things that can stop your call, it is
[Errors and refusals](#errors-and-refusals).

---

## Requirements

Python **3.9 or newer**. Tested on 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14 — against
the source tree, against the built wheel, and against the built sdist. Every
version in that list is an entry in all three CI matrices; none is asserted by
description alone.

0.6.0 raised the floor to 3.11, which nothing in the package needed. 0.6.1 puts
it back where 0.5.0 had it, so the two silent defects 0.6.0 fixed are reachable
by ordinary `pip install --upgrade` on 3.9 and 3.10.

---

## Installation

    # docs-check: skip installs from PyPI; the gate already runs against the built wheel
    pip install hmda-analyzer

Both import styles work after installation, and they are the same module object:

    # docs-check: run dual-import
    from hmdaanalyzer import denial_rate_by_race           # canonical form
    from hmda_analyzer import denial_rate_by_race as alias  # pip-name convention
    print(denial_rate_by_race is alias)

---

## Quickstart

    # docs-check: skip prints DataFrame reprs, whose formatting is pandas-version-dependent
    from hmdaanalyzer import (
        load_sample, denial_rate_by_race, disparity_ratio,
        lending_by_tract, lending_desert_score, lender_summary,
        generate_disparity_report,
    )

    # Load sample data (no API required)
    df = load_sample(n=5000)

    # Or load from CFPB API — streams and TRUNCATES at limit rows (see below)
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

    # Lending desert scoring — low volume AND high denial rate (both required)
    deserts = lending_desert_score(df)
    print(deserts.head())

    # Lender analysis
    summary = lender_summary(df, lei="LEI000001")

    # Full disparity report
    report = generate_disparity_report(df, title="Illinois Mortgage Market 2023")
    print(report)

---

## The census-geography vintage rule

**This is the change most likely to break an upgrade from 0.5.0.** Calls that
previously returned a number now raise.

A census tract GEOID is only meaningful relative to a tract *delineation*, and
the delineation changes. `24510130400` exists in both the 2021 and the 2022 LAR
and denotes a **different piece of ground** in each. Concatenate two such years,
`groupby("census_tract")`, and you silently sum two different places into one
row — a plausible, wrong, tract-level result with nothing in the output, the
dtypes, or the column set to signal it.

So the geography-keyed aggregations now check, and refuse.

### What raises, and when

Three declarative maps record, per HMDA data year, which basis each key uses.
They are lookups with citations attached — nothing is inferred from the data:

    # docs-check: run vintage-basis
    from hmdaanalyzer import basis_year
    for year in (2021, 2022, 2023, 2024):
        print(year, basis_year("census_tract", year), basis_year("county_code", year))

`None` is the **UNKNOWN** state: no human has yet added a cited entry for that
year. It is an assertion of ignorance, never a guess.

`TRACT_GEOID_BASIS_BY_YEAR`, `COUNTY_CODE_BASIS_BY_YEAR` and
`MSA_CODE_BASIS_BY_YEAR` are importable if you want to read the maps directly.
`MSA_CODE_BASIS_BY_YEAR` has no internal caller — the package performs no
aggregation on `derived_msa_md` — and ships so that a user doing their own MSA
`groupby` has a citable constant instead of re-deriving OMB's schedule. It is a
weaker instrument than a raise, and is named as one.

`GeographyVintageError` is raised when:

| Condition | Example |
|---|---|
| The frame spans two bases for the key | tract frame pooling 2021 (basis 2010) with 2022 (basis 2020) |
| The frame spans two bases for a key the guard **consults** | **county** frame pooling 2023 (basis 2020) with 2024 (basis 2023) |
| An **UNKNOWN** year is pooled with any other year | tract frame pooling 2023 with 2024 or 2025 |
| `vintage=` selects no rows at all | `vintage=2020` on a 2018–2021 frame |

A note on rows 2 and 3, because they used to carry the same example and only one
of them was right. The tract guard *does* consult the county map — the county
code is the tract GEOID's first five digits, so a county-scheme change is
necessarily a tract-key change — but **as shipped that consult has no live
case.** Since the uncited 2024 tract entry was removed, 2024 is UNMAPPED for
tracts, and the UNKNOWN rule is evaluated before the basis comparison. So a
tract frame pooling 2023 with 2024 is refused by row 3, never by row 2. No
shipped year-pair has agreeing tract bases and disagreeing county bases.

The consult stays, and is exercised by a test that restores the 2024 tract entry
for its duration. It re-arms the moment somebody adds a cited 2024 tract entry —
which is exactly when Connecticut would otherwise become invisible to the tract
map.

A single UNKNOWN year **alone** is fine and is not refused — a 2025-only
analysis is exactly as coherent as a 2023-only one.

    # docs-check: run vintage-refusal
    import pandas as pd
    from hmdaanalyzer import lending_by_county, GeographyVintageError

    df = pd.DataFrame({
        "activity_year": ["2023", "2023", "2024", "2024"],
        "county_code":   ["09001", "09003", "09110", "09120"],
        "action_taken":  [1, 3, 1, 3],
        "is_approved":   [True, False, True, False],
        "is_denied":     [False, True, False, True],
        "loan_amount":   [200000.0, 210000.0, 220000.0, 230000.0],
    })
    try:
        lending_by_county(df)
    except GeographyVintageError as e:
        print(type(e).__name__)
        print(str(e).splitlines()[0])

### The two ways through a 2023→2024 refusal

The 2023→2024 county boundary is **Connecticut replacing its eight legacy
counties (`09001`…`09015`) with nine planning regions (`09110`…`09190`)** for
federal statistical use (87 FR 34235, 2022-06-06). Census lists it as the sole
county-equivalent change of the 2020s. Every Connecticut tract GEOID changes
with the county prefix even though the tract *delineation* basis stays 2020.

The refusal is nationwide and its cause is one state. That is deliberate — the
library will not decide on your behalf that your rows are unaffected — but it
means the refusal may be costing you an analysis that would have been correct.

**Filtering the frame is not one of the ways through.** The guard's verdict is
computed from the **years** a frame spans, never from the rows it contains: it
compares the frame's year set against the basis maps and never reads
`state_code` or `county_code` at all. So dropping every Connecticut row leaves
2023 and 2024 both present, and the identical refusal fires on the filtered
frame. That is the same sentence as the paragraph above — the library will not
decide on your behalf that your rows are unaffected — restated as a mechanism,
and it is deliberate: a verdict that depended on which rows you kept could be
disarmed by subsetting.

Two exact ways through. Both change the **years**, not the rows:

**a. Split at the boundary and present two panels.** The endorsed path for *any*
vintage break. Keeps Connecticut in, involves no estimation and no non-random
subsetting. Label the break explicitly.

    # docs-check: skip illustrative fragment on a frame the reader supplies
    panel_2023 = lending_by_county(df[df["activity_year"] == "2023"])
    panel_2024 = lending_by_county(df[df["activity_year"] == "2024"])

**b. Narrow to one basis with `vintage=`.** Selects the rows whose data year uses
that basis and aggregates only those. Note the argument is the **basis** year,
not the data year — at this boundary the 2023 rows use county basis 2020 and the
2024 rows use county basis 2023.

    # docs-check: skip illustrative fragment on a frame the reader supplies
    lending_by_county(df, vintage=2020)   # the 2023 rows
    lending_by_county(df, vintage=2023)   # the 2024 rows

Three things that are **not** ways through: filtering out Connecticut (above),
aggregating up to county or MSA (those keys move too, at overlapping
boundaries), and building a crosswalk inside the library (HMDA carries no
sub-tract location, so any conversion allocates proportionally and produces
fractional loan counts — if you want that estimate, build it yourself and own
it).

Note that the measured county-scheme change is Connecticut-only, but two other
states' `county_code` **sets** differ between 2023 and 2024: SD `46017` and TX
`48269` — the sparsest county in each state — carry rows every year 2018–2023,
zero in 2024, and rows again in 2025. Those codes never left the county
universe; nobody applied for a mortgage there that year. A set comparison reads
that as a boundary change. It is not one.

### The `vintage=` narrowing parameter

`lending_by_tract`, `lending_by_county`, `lending_desert_score`,
`racial_composition_by_tract` and `lender_summary` all accept `vintage=`.

    # docs-check: skip illustrative fragment on a frame the reader supplies
    lending_by_tract(df, vintage=2020)   # keep only years whose tract basis is 2020

It selects the rows whose data year maps to that basis and aggregates only
those. It is a **narrowing, not an override**: it can never produce a wrong
number because it never merges two delineations, and the guard still runs
afterwards — a narrowing that leaves an incoherent frame still refuses.

Three things to know:

- **It can narrow a frame to nothing, and that raises.** `vintage=2020` on a
  frame containing only 2018–2021 selects zero rows. That is a malformed
  question, not a finding: the answer is not "nothing here." `GeographyVintageError`
  names the bases and years the frame actually contains.
- **Dropped rows are recorded, always.** Every guarded output carries a
  `vintage_dropped_rows` column — `0` when nothing was dropped — and
  `lender_summary`, which returns a dict and cannot carry a column, carries a
  `dropped_rows_by_year` key, `{}` when nothing was dropped. Both are
  **unconditional**, for the same reason the `*_status` columns are: a field that
  appears only in the unhappy cases signals by its own absence, which a caller
  holding one frame cannot read. Note what it does *not* distinguish — "no
  `vintage=` requested" and "`vintage=` dropped nothing" are both `0`, because in
  both cases zero rows were dropped and the column names exactly one fact.
- **It does not exempt you from the five-tract floor** below.

### The five-tract floor on `lending_desert_score`

`is_lending_desert` requires `app_percentile < DESERT_PERCENTILE_THRESHOLD` (25).
`rank(pct=True)` over *n* rows has a minimum of `100/n`, so for n ≤ 4 the flag is
**arithmetically incapable** of being `True` whatever the data says. Returning
`is_lending_desert=False` for every tract there would be a fabricated negative.

So `lending_desert_score` raises `UnreachableFlagError` below
`DESERT_TRACT_FLOOR` tracts. The floor is **derived from the threshold at
import**, not written down separately, so the two cannot drift apart; at the
shipped threshold of 25 it is 5. Narrowing with `vintage=` can drop you under
the floor, which is one more reason the guard runs after the narrowing.

This is neither a small-N suppression rule nor a claim that five tracts is
statistically adequate. It is only the point below which a positive is
impossible. Use `lending_by_tract` for the underlying counts.

### Provenance columns

Every guarded aggregation stamps what governed it. `.agg()` drops columns, so
these are written back deliberately — and the *status* column is always present,
including when a basis **is** cited, because a column that appeared only in the
unhappy cases would signal by its own absence.

| Column | Meaning |
|---|---|
| `tract_geoid_vintage` | Tract delineation basis year (e.g. `2020`). **Omitted**, not `NaN`, when no basis can be asserted — a null would flip the column to `float64` and a guess is the defect this exists to prevent. |
| `tract_geoid_vintage_status` | `CITED`, `UNKNOWN`, or `NO_YEAR_COLUMN`. Always present. |
| `county_code_vintage` | County FIPS basis year. Present on **tract** outputs too: the tract guard consults the county map, so the output owes provenance for everything that governed it, not only for its own key. |
| `county_code_vintage_status` | As above, for the county key. Always present. |
| `vintage_dropped_rows` | How many rows `vintage=` dropped. **Always present**, `0` when none were. |

`tract_geoid_vintage` is deliberately **not** called `tract_vintage`. The LAR
carries two tract-related things on different schedules — the tract
*delineation* (decennial) and the FFIEC *demographic appends*
(`tract_population`, `tract_to_msa_income_percentage`, …, refreshed annually
against a rolling 5-year ACS). This column covers only the first.

`lender_summary` returns a dict and carries the same facts as keys:
`census_tract_basis_year`, `census_tract_basis_status`,
`county_code_basis_year`, `county_code_basis_status`, and `dropped_rows_by_year`.

The status values are importable as `BASIS_STATUS_CITED`,
`BASIS_STATUS_UNKNOWN` and `BASIS_STATUS_NO_YEAR_COLUMN` from
`hmdaanalyzer.geography_vintage`.

    # docs-check: run provenance-columns
    import pandas as pd
    from hmdaanalyzer import lending_by_tract

    df = pd.DataFrame({
        "activity_year": ["2023", "2023"],
        "census_tract":  ["09001010100", "09001010200"],
        "action_taken":  [1, 3],
        "is_approved":   [True, False],
        "is_denied":     [False, True],
        "loan_amount":   [200000.0, 210000.0],
        "income":        [80.0, 90.0],
    })
    out = lending_by_tract(df)
    for col in ("tract_geoid_vintage", "tract_geoid_vintage_status",
                "county_code_vintage", "county_code_vintage_status",
                "vintage_dropped_rows"):
        print(col, "=", out[col].iloc[0])
    # vintage_dropped_rows is present with no vintage= argument at all — it
    # reports 0, rather than signalling "nothing dropped" by being absent.

The full decision record — every rejected alternative and the measurement behind
it — ships inside the wheel:

    # docs-check: skip prints a multi-thousand-line methodology document
    from hmdaanalyzer import get_methodology_path
    print(get_methodology_path("tract_vintage_methodology.md").read_text())

**`lending_by_state` is deliberately unguarded.** `state_code` gets no basis map
because nothing was measured to move a state code in 2018–2025. That is an
argument from absence, not a demonstration that they cannot move.

---

## Multi-Year Loading (`load_range`)

`load_range(start_year, end_year, ...)` fetches HMDA LAR for **every year in the
inclusive range** and returns one concatenated DataFrame with an `activity_year`
provenance column:

    # docs-check: skip requires live CFPB API access
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
- **A multi-year frame will be refused by the geography guards** unless every
  year in it shares a basis. That is the point of `load_range` and the vintage
  rule meeting: loading the range is allowed, and *pooling incompatible years
  into one tract-level number* is not.

### What is and is not stable across years

The CFPB column **header** is identical across **2018–2025** (2018 is the
earliest year the API serves): the same 99 raw columns, same names, every year.
That is asserted by the test suite, not assumed.

**The header being stable does not make the values stable, and the previous
wording of this section ("no columns are year-conditional") was false.** A
column's values can be year-conditional while its name is not, and
`derived_msa_md` is a live example: its `'0'` sentinel is present in **2018 and
2019** and gone from 2020 onward (measured on full-state files — CT 784 rows in
2018 and 705 in 2019; MI 2,623 and 4,000; zero for both states 2020–2025). A
consumer who writes `df["derived_msa_md"] != "0"` against 2019 data and pools
2019 with 2020 gets a filter that is meaningful for one year's rows and vacuous
for the other's, with no schema signal at all.

So, precisely: the *header* is stable 2018–2025; the *meaning* of
`census_tract`, `county_code` and `derived_msa_md`, and the *domain* of
`derived_msa_md`, are not.

> ⚠️ **Scale.** Multi-year national pulls are enormous — the same filters apply to
> every year, so a range with no `state`/`county` filter multiplies a full national
> LAR file by the number of years. Always filter multi-year loads. `load_range`
> streams each year to `limit`; it does not silently cap or block large pulls.

---

## `limit` truncates. It does not sample.

`load_from_api` streams the CFPB file and stops at `limit` rows. The rows you get
back are the **first `limit` rows in the server's file order** — which is not
random with respect to lender, geography, race, or outcome. A denial rate
computed on a truncated pull describes an arbitrary slice of the state while
having exactly the shape of a statistic about the state.

Every returned row therefore carries a **`limit_truncated`** column:

| Value | Meaning |
|---|---|
| `True` | The stream was cut short. You have a slice, not a population. |
| `False` | The whole file fit under `limit`. |

The column is written **even when `False`**, so a complete pull is
distinguishable from a frame produced before the column existed. Absence is
never the signal.

Check it before quoting any number, and raise `limit` (or narrow with `county=`)
until it reads `False` if you need the population. Under `load_range` the flag is
**per year** — a range can be complete in one year and truncated in another —
so check `df.groupby("activity_year")["limit_truncated"].any()` rather than the
frame as a whole. Comparing a truncated year against a complete one is comparing
a slice to a population.

`load_from_file` and `load_sample` are complete by construction and always report
`False`.

---

## Small-N suppression

`denial_rate_by_race` drops any `derived_race` group with fewer than **5**
actionable applications (`MIN_APPLICATIONS_FOR_RATE`), because a rate over four
or fewer decisions can only take the values 0 / 25 / 50 / 75 / 100 % and a
disparity ratio built on one asserts a precision it does not have.

**That rule is not new. Until 0.6.0 it was silent** — the groups simply were not
in the output, and a protected class absent from a disparity table is
indistinguishable from a protected class with no disparity. Three columns now
record it on every returned row:

| Column | Meaning |
|---|---|
| `suppressed_groups` | How many race/ethnicity groups were removed |
| `suppressed_applications` | How many applications those groups held |
| `suppressed_group_names` | Which groups, `"; "`-joined (`""` when none) |

They propagate into `disparity_ratio`, and `generate_disparity_report` renders an
explicit note under the denial-rate table when suppression fired. In
`lender_vs_market` the columns are prefixed `lender_` and `market_`, because the
two sides are suppressed independently and a row is usually absent because *that
lender* had too few applications.

**Not applied at tract level.** `lending_by_tract`, `lending_desert_score` and
`racial_composition_by_tract` report every tract they are given, including
single-application ones. Choosing a tract-level suppression rule is a disclosure
methodology decision — it changes denominators, and HMDA public data is already
disclosure-controlled upstream by the CFPB — and 0.6.0 deliberately does not make
it. If you are publishing tract-level counts, apply your own rule and say what it
is.

Residual gap, stated rather than hidden: if *every* group falls below the
threshold the returned frame has no rows to carry the columns. `disparity_ratio`
raises `ReferenceGroupError` on that input; `denial_rate_by_race` still returns
empty.

---

## Analyses Supported

| Function | Returns |
|---|---|
| `denial_rate_by_race` | Denial rate per `derived_race`, plus suppression columns |
| `disparity_ratio` | Ratio vs a reference group (default White), with a severity level |
| `denial_rate_by_income_band` | Denial rate by income band (`<$50k` … `$200k+`) |
| `denial_reasons_by_race` | Denial reason breakdown per race, with shares |
| `lending_by_tract` | Applications, denials, originations and rates per census tract |
| `lending_by_county` | The same, keyed by county FIPS |
| `lending_by_state` | The same, keyed by state FIPS (unguarded — see above) |
| `lending_desert_score` | Tract scoring and the `is_lending_desert` flag |
| `racial_composition_by_tract` | Applications and denial rate per (tract, race) |
| `lender_summary` | One lender's volumes, rates and geographic reach, as a dict |
| `lender_vs_market` | A lender's denial rates against the market, by race |
| `top_lenders_by_volume` | Lenders ranked by origination count |
| `cra_proxy_distribution` | Borrower- and tract-income distribution of originations |
| `generate_disparity_report` | The whole analysis as a Markdown report |
| `summary_table` | `disparity_ratio`, falling back to `denial_rate_by_race` |

`summary_table` is the one fallback in the package: if no reference group is
present to divide by (`ReferenceGroupError`) it returns plain denial rates
instead. It swallows nothing else.

### Output columns

Not checked by the docs gate — an output-columns table is a documented blind
spot in it — but no longer unchecked. `tests/test_output_columns.py` asserts
every row below against what the function actually returns.

| Function | Columns |
|---|---|
| `denial_rate_by_race` | `derived_race`, `applications`, `denials`, `denial_rate`, `suppressed_groups`, `suppressed_applications`, `suppressed_group_names` |
| `disparity_ratio` | the above, plus `reference_group`, `reference_denial_rate`, `disparity_ratio`, `disparity_level` |
| `denial_rate_by_income_band` | `income_band`, `applications`, `denials`, `denial_rate` |
| `denial_reasons_by_race` | `derived_race`, `denial_reason_label`, `count`, `total`, `pct` |
| `lending_by_tract` | `census_tract`, `applications`, `denials`, `originations`, `avg_loan_amount`, `median_income`, `denial_rate`, `origination_rate`, `tract_geoid_vintage`, `tract_geoid_vintage_status`, `county_code_vintage`, `county_code_vintage_status`, `vintage_dropped_rows` |
| `lending_by_county` | `county_code`, `applications`, `denials`, `originations`, `total_loan_volume`, `avg_loan_amount`, `denial_rate`, `state_code`, `county_code_vintage`, `county_code_vintage_status`, `vintage_dropped_rows` |
| `lending_by_state` | `state_code`, `applications`, `denials`, `originations`, `total_volume`, `denial_rate` (no vintage columns — unguarded) |
| `lending_desert_score` | everything `lending_by_tract` returns, plus `app_percentile`, `desert_score`, `is_lending_desert` |
| `racial_composition_by_tract` | `census_tract`, `derived_race`, `applications`, `denial_rate`, `tract_geoid_vintage`, `tract_geoid_vintage_status`, `county_code_vintage`, `county_code_vintage_status`, `vintage_dropped_rows` |
| `lender_vs_market` | `derived_race`, `lender_applications`, `lender_denials`, `lender_denial_rate`, `lender_suppressed_groups`, `lender_suppressed_applications`, `lender_suppressed_group_names`, `market_denial_rate`, `market_suppressed_groups`, `market_suppressed_applications`, `market_suppressed_group_names`, `vs_market`, `vs_market_pct` |
| `top_lenders_by_volume` | `lei`, `originations`, `total_volume`, `avg_loan` |
| loader output | the 99 raw CFPB columns plus `is_approved`, `is_denied`, `tract_geoid_vintage`, `limit_truncated` |

`vintage_dropped_rows` is on **every** guarded output, carrying `0` when
`vintage=` dropped nothing or was never passed. With the four basis/status
columns that makes five provenance fields, and all five are unconditional.

This table used to say it was maintained by hand and unchecked. It is now
asserted: `tests/test_output_columns.py` compares every row against the columns
the function actually returns, so a drift between this table and the code fails
the suite. That closes what `docs-check.toml` names as its own largest blind
spot — the gate cannot see this table, so something else had to.

---

## Lending deserts — what the score actually is

`lending_desert_score` produces **two things, and they do not use the same rule.**

`desert_score` is a weighted composite on a 0–100 scale:

    # docs-check: skip a formula display, not executable code
    desert_score = (100 - app_percentile) * 0.6 + denial_rate * 100 * 0.4

60 % low-volume, 40 % high-denial. The weights are a **presentation choice for
ranking**, not a calibrated instrument: nothing was fitted, and no threshold on
`desert_score` means anything.

`is_lending_desert` is a boolean and is **not** a cut on `desert_score`:

    # docs-check: skip a formula display, not executable code
    is_lending_desert = ((app_percentile < DESERT_PERCENTILE_THRESHOLD)
                         & (denial_rate > DESERT_DENIAL_RATE_FLOOR))

Both conditions must hold. A tract can therefore carry a very high `desert_score`
and still be `False` — a high score driven mostly by denial rate, with volume
above the percentile cut, is the common case. **Sorting by `desert_score` and
reading the top rows as "the deserts" is wrong.**

Two further caveats the previous README did not give:

- **There is no denominator.** Earlier documentation described a tract as scored
  "relative to its expected volume based on housing units." No housing-unit
  figure is read anywhere in this package — `tract_owner_occupied_units` and
  `tract_one_to_four_family_homes` arrive in the LAR and are never used. The
  score is not normalised for tract size.
- **`app_percentile` is relative to the frame you passed**, not to a national
  distribution. The same tract scores differently depending on what else is in
  the frame. That is also why the vintage guard matters here more than anywhere
  else: pooling two vintages changes the reference distribution every tract is
  scored against, not merely the rows that collide.

The thresholds are importable as `DESERT_PERCENTILE_THRESHOLD` (25) and
`DESERT_DENIAL_RATE_FLOOR` (0.15) from `hmdaanalyzer.geography_vintage`. The
0.15 floor is unvalidated: it is not a CFPB threshold and is unrelated to the
disparity thresholds below.

---

## CRA-Proxy Distribution (`cra_proxy_distribution`)

Descriptive borrower-income and geographic (tract-income) distribution of mortgage
**originations**, approximating the *distribution dimensions* a CRA lending analysis
looks at. It is a **pure transform** on a frame you already loaded — no fetch, no network.

    # docs-check: skip requires live CFPB API access
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
year's own annual area median. Every table carries `STANDARD_CRA_PROXY_CAVEAT`.

### `include_purchased` raises on frames this package loads

Purchased loans (`action_taken == 6`) are excluded by default;
`include_purchased=True` adds them as a separate, labeled cut — never blended.

**But none of this package's loaders can produce a purchased loan.**
`load_from_api` and `load_range` query the CFPB Data Browser with
`actions_taken=1,2,3,4,5` (`API_ACTIONS_TAKEN` in `hmdaanalyzer.data.schema`),
and `load_sample` generates only actions 1, 3 and 4. So on any frame they
produced, `include_purchased=True` has nothing to select.

**It now raises `EmptyUniverseError`** rather than returning a table. Through
0.5.0 and the 0.6.0 build it returned four category rows with every count `0` and
every share `0.0`, over a zero denominator, in the identical shape as the real
distribution printed beside it — which reads as "purchased no LMI loans" when the
truth is "purchased loans were never fetched." The 0.6.0 build attached an
`EMPTY PURCHASED CUT` caveat to `table.caveat`; that is a *sibling* of
`table.distribution`, so charting, exporting or concatenating the distribution
kept the zeros and dropped the caveat. This is the opening commitment of this
README — *an arithmetically impossible flag raises* — and it is the same argument
`UnreachableFlagError` makes for `is_lending_desert`.

It is **not** the "well-formed query that matches no rows" case below. That rule
is about an *empty* result, which cannot be mistaken for a finding. A populated
table of zeros is built to be.

The flag is fully functional on a frame that *does* contain purchased loans,
which today means one supplied through `load_from_file`. One purchased row is
enough; this is not a small-N rule. Within such a frame, a *year* with no
purchases still returns a caveated zero table rather than raising — there the
sibling years are direct evidence that the universe is real, so the zero is a
fact about the year rather than about the fetch.

The default action set is deliberately not widened, and the reason previously
given here was wrong. It read that widening "would change the denominator of
every denial-rate, disparity and tract analysis in the package." Measured, it
changed **one of ten** — and only because `racial_composition_by_tract` was
missing its `action_taken` filter, which 0.6.0 fixes. The other nine already
filter `action_taken.isin([1, 2, 3])`, so an action-6 row is invisible to them
however it arrives; with the fix in, the answer is **zero of ten**. The decision
stands on the argument that actually holds: a purchased loan is an origination
somebody else made and later bought, so it is not an application to this
institution and does not belong in an application-keyed fetch — and widening
would silently double the row count and API cost of every default load to serve
one optional flag.

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

Note that `load_sample` does **not** emit
`ffiec_msa_md_median_family_income` or `tract_to_msa_income_percentage`, so the
offline sample loader cannot feed this transform.

The full methodology — including the fabrication firewall — ships inside the wheel
via `get_methodology_path`; see the vintage section above for the call.

---

## Errors and refusals

Every failure this library can raise is typed, and every type is importable from
`hmdaanalyzer` or `hmda_analyzer`. They split by **what went wrong**, and the
split decides what catches them:

- **The seven refusals about your data** — `MissingColumnError`,
  `SchemaValidationError`, `ActivityYearMismatchError`, `GeographyVintageError`,
  `UnreachableFlagError`, `ReferenceGroupError`, `EmptyUniverseError` — all
  subclass `ValueError`, so an existing `except ValueError` keeps catching them
  unchanged.
- **`CFPBAPIError` subclasses `RuntimeError`, not `ValueError`.** It reports that
  the CFPB API returned an HTTP error — a transport failure, not a problem with
  your frame — and `except ValueError` **will not catch it**. A CFPB 403 escapes
  a handler written for the first bullet alone.

So there is no single base class that catches everything. Catch the specific
types you handle, or `except (ValueError, RuntimeError)` if you want both.

| Exception | Raised when | What to do |
|---|---|---|
| `MissingColumnError` | A required column is absent — or present with a dtype the analysis cannot use, e.g. a non-numeric `income`. Also raised when a filter argument (`lei=`, `state=`) names a column the frame lacks. | Fix the frame. The message names the function and the column. |
| `SchemaValidationError` | A fetched year's columns deviate from the canonical CFPB set. Names the year and the offending columns. | The CFPB schema may have changed. Do not trust the load until `RAW_LAR_COLUMNS` is updated with the drift documented. |
| `ActivityYearMismatchError` | The API returned rows whose `activity_year` is not the year requested. | Retry; if it persists the API is serving the wrong year's data. |
| `GeographyVintageError` | The frame pools data years whose geography keys do not mean the same thing, or `vintage=` selected no rows. | Split at the boundary into two panels, or narrow with `vintage=`. Filtering rows out does **not** clear it — the verdict is on the years the frame spans. See the vintage section. |
| `UnreachableFlagError` | `lending_desert_score` was given fewer than `DESERT_TRACT_FLOOR` (5) tracts, where `is_lending_desert` cannot be `True` whatever the data says. | Use `lending_by_tract` for the counts, or widen the frame. |
| `ReferenceGroupError` | `disparity_ratio` was asked to compare against a reference group not present in the data (after small-N suppression). | Pass a `reference=` that exists, or widen the frame. |
| `EmptyUniverseError` | `cra_proxy_distribution(..., include_purchased=True)` was given a frame with no `action_taken == 6` rows, so the purchased cut has a zero denominator and nothing to distribute. | Supply a frame containing purchased loans via `load_from_file`, or drop the flag. No loader in this package can produce one. |
| `CFPBAPIError` | The CFPB API returned an HTTP error. Carries `status_code`, `response_body` and `url`. A `RuntimeError`, not a `ValueError`. | See the cloud-environment note below for the 403 case. |

    # docs-check: skip illustrative fragment on a frame the reader supplies
    from hmdaanalyzer import MissingColumnError, lending_by_state

    try:
        lending_by_state(df)            # df has 'state' but not 'state_code'
    except MissingColumnError as e:
        print(e)                        # names the function and the missing column

**A well-formed query that simply matches no rows is not an error.**
`lender_summary(df, lei=...)` with a valid schema but an unknown LEI still
returns an empty `{}`, and `generate_disparity_report(df, lei=...)` returns a
clean no-records report. The distinction the library draws is between *"you asked
a question I cannot answer"* (raise) and *"the answer is zero"* (return).

**Why these raise rather than warn.** Python's default filter shows a given
warning once per location, so a notebook re-run — the normal way of working — is
silent the second time. The output would be indistinguishable from a correct one:
same columns, same dtypes, a plausible row count. And the artefact outlives the
session — the number goes into a spreadsheet, a memo, or a regulatory filing, and
carries no warning with it.

**Report sections do not swallow refusals.** `generate_disparity_report` catches
only the narrow failures a section can meaningfully render into a table cell
(`KeyError`, `TypeError`, `ReferenceGroupError`, and similar). `ValueError` is
deliberately *not* in that set — it is the base class of `MissingColumnError`,
`SchemaValidationError`, `GeographyVintageError` and `UnreachableFlagError`, so
catching it would typeset a refusal into a markdown cell, where it reads as a
rendering glitch while every surrounding section still carries numbers. A report
that fails to generate is a correct outcome.

> **Breaking change in 0.3.0:** functions that previously returned an empty result on
> a missing column now raise `MissingColumnError`.
>
> **Breaking change in 0.6.0:** geography-keyed aggregations on a
> vintage-spanning frame now raise `GeographyVintageError`, and
> `lending_desert_score` raises `UnreachableFlagError` below five tracts. See the
> CHANGELOG for the full list of calls affected.

---

## Disparity Ratio Thresholds

Based on CFPB fair lending examination standards:

- >= 2.0x — HIGH disparity (triggers regulatory scrutiny)
- >= 1.5x — MODERATE disparity
- < 1.5x — LOW disparity
- < 1.0x — FAVORABLE (group has lower denial rate than reference)

---

## Data Sources

CFPB HMDA Data Browser API — free, no API key required:
<https://ffiec.cfpb.gov/data-browser/>. 2024 data covers 4,908 institutions and
millions of loan applications.

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

    # docs-check: skip would recursively invoke the suite this gate runs inside
    pytest tests/ -v -m "not live"

396 tests across all modules (offline/mocked; no live API calls). The suite
contains **zero skip markers** — a test that skips is a test that certifies
nothing, and `empty_parameter_set_mark = "fail_at_collect"` turns an empty
parametrize into a collection error rather than a silent skip.

The README itself is gated: `tools/docs_check.py` executes every block marked
`run`, diffs its stdout against a committed file, resolves every symbol the
README names, checks this test count against collection, and asserts that every
name in `__all__` appears somewhere in this document. It runs against the built
wheel from a directory containing no package source, on every PR and again before
publish.

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
