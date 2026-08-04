# Census-tract vintage in multi-year HMDA frames — methodology

> **Status: v1, PRE-AUDIT.** Methodology-first artifact. No code exists for this
> feature and none should be written until this document has been hostile-audited
> in a fresh session and revised. The verdict of that audit may be *do not ship*;
> that is an acceptable outcome.
>
> **This document revises the recon design it was commissioned to justify.** Three
> of the recon's four proposals survive in altered form; one — "raise on a
> vintage-spanning frame" — is rejected and replaced (§M2, §M3). The recon's
> *detection method* is also rejected: it is anti-correlated with the risk it was
> used to measure (§M6.3). Every change is argued below with the measurement that
> forced it.
>
> Written 2026-08-03. Every empirical claim in this document was produced by a
> command run on that date; the commands and their output are in §M6 and §V.

---

## 0. What this document is, and what it is not

It is a decision record for one defect: **HMDA LAR census-tract keys do not mean
the same thing in every data year**, and `hmda-analyzer` currently gives a user no
signal when that matters.

It is **not** a specification. No API signatures, no exception hierarchies beyond
the one naming decision in §M3, no version numbers, no tests. Those belong to the
build prompt that follows the audit.

Out of scope and deliberately not decided here, recorded so a reader does not
think they were missed: `include_purchased` unreachability; small-N suppression;
the `limit`-is-truncation caveat; the `lending_desert_score` formula itself; the
README's "86 tests" claim (`pytest` collects 114); and any change to
`fair-lending-screener`. Already settled elsewhere and not re-litigated here:
0.6.0 declares `requires-python = ">=3.11"`; the CI workflow's `name:` becomes
`CI` with the filename `test.yml` unchanged; `docs-check` adoption rides this
release.

---

## 1. The defect

HMDA LAR reports property location as an 11-digit census-tract GEOID. That GEOID
is only meaningful relative to a census-tract *delineation* — a set of polygon
boundaries — and the delineation changed between the 2021 and 2022 data years.

The failure is not that the delineation changed. It is that **the key did not
change with it**. A GEOID such as `24510130400` exists in both the 2021 and the
2022 LAR and denotes a different piece of ground in each. Concatenate the two
years and `groupby("census_tract")` silently sums two different places into one
row.

Reproduced through the shipped public API on Baltimore city, MD (FIPS 24510):

```
load_range(2021, 2022, county="24510", limit=200_000)

  frame: 57,131 rows, 101 cols
  activity_year present: True | values: ['2021', '2022']
  tract_vintage column present: False

  per-year distinct tract keys:
    2021    198
    2022    197
    sum of per-year keys : 395
    pooled distinct keys : 199
    COLLIDING GEOIDs     : 196

  --- lending_by_tract on the vintage-spanning frame ---
  rows returned      : 199
  exception raised   : no
  warning emitted    : no
  vintage column     : False
```

Every row in that frame is real, correctly loaded, and correctly labelled by its
own `activity_year`. `load_range`'s contract holds exactly as written. The output
of `lending_by_tract` is nonetheless a lending picture of 199 places that do not
all exist, and nothing in the object, the console, or the column set says so.

**That invisibility is the whole defect.** A user gets a plausible, wrong,
tract-level result and has no signal. In a fair-lending context the output looks
like every other output.

---

## M1 — The binding, and its source of authority

### M1.1 The authority is a rule, not a table

The recon established the 2018–2021 / 2022+ split by measuring published data.
Measurement cannot establish what is true of a data year that does not exist yet,
so a citation was required.

**The prompt commissioning this document proposed the FFIEC Filing Instructions
Guide as that citation. The FIG does not carry it.** Read 2026-08-03 at
`https://ffiec.cfpb.gov/documentation/fig/2022/overview`, the 2022 FIG's entire
instruction for this data point is:

> "Enter the 11-digit census tract number as defined by the U.S. Census Bureau.
> Do not use decimals."

No vintage, no Census year, no geocoder reference. A methodology that cited the
FIG here would be citing a document that does not say the thing.

**The authority is Regulation C's official commentary.** Read 2026-08-03 at
`https://www.consumerfinance.gov/rules-policy/regulations/1003/4/` (the CFPB's own
hosted current text of 12 CFR Part 1003, Supplement I), **Comment
4(a)(9)(ii)(C)-1**:

> "Census tract numbers are defined by the U.S. Census Bureau. A financial
> institution complies with § 1003.4(a)(9)(ii)(C) if it uses the boundaries and
> codes **in effect on January 1 of the calendar year covered by the
> loan/application register** that it is reporting."

This is the load-bearing citation, and it is the right kind: a **rule**, not a
table. It is prospective — it determines the answer for 2027 and 2033 as much as
for 2022 — and it explains *why* there is a lag between a decennial census and the
data year that first reflects it. The 2020 Census was taken in 2020, but its tract
delineations were not "in effect" on 1 January 2020 or 1 January 2021. They were
first in effect on 1 January 2022.

**The year-by-year fact is separately citable**, from CFPB's own annual data
publications. Both ends of the boundary, read 2026-08-03:

| Source | Published | Statement (verbatim) |
|---|---|---|
| CFPB, *Summary of 2021 Data on Mortgage Lending* | 2022-06-16 | "The 2021 HMDA data use the census tract delineations, population, and housing characteristic data from the 2011–2015 American Community Survey (ACS)." |
| CFPB, *Summary of 2022 Data on Mortgage Lending* | 2023-06-29 | "The 2022 HMDA data use the census tract delineations, population, and housing characteristic data from the 2020 Census." |

Note what the 2021 sentence actually says. CFPB attributes the *delineations* to
the 2011–2015 ACS. The ACS does not delineate tracts; it uses the 2010 decennial
delineations. The sentence conflates the geometry basis with the demographic
vintage — and that conflation is a live hazard for this design, addressed in §M4.3.

**Honest statement of citation status.** The rule (Comment 4(a)(9)(ii)(C)-1) and
the two annual CFPB summaries were retrieved and read on 2026-08-03. FFIEC's own
operational pages — `ffiec.gov/data/census/*` and the geocoder's
`CensusUpdates.html` — returned **HTTP 403** to every automated request from this
session, including a browser-style User-Agent. This is the same Akamai edge block
that `hmdaanalyzer/_http.py` already documents for the CFPB API. **The FFIEC
geocoder adoption notice was therefore not read, and is not cited.** It is listed
as an open item in §O. The chain above does not depend on it: the rule plus the
CFPB summaries plus the measurements in §M6 establish the binding without it.

### M1.2 The shape of the constant

The recon proposed one constant on nmtc-mapper's `TractVintage` frozen-dataclass
pattern. That pattern was read (`nmtcmapper/data/schema.py:25-62`). **It does not
port, and it should not be copied.**

nmtc-mapper's `TractVintage` binds *one* vintage across *three* facts that must
agree — `basis_year`, `geocoder_vintage`, `table_geoid_header` — and its
`__post_init__` refuses to construct when they disagree. That cross-field check is
the entire value of the class. hmda-analyzer has no geocoder and no table header.
There is nothing to cross-check. Copying the class would produce a frozen
dataclass with one field and a `__post_init__` that checks nothing — the form of a
safety mechanism without the mechanism.

What ports is the *principle*: one object, in one place, that a future edit cannot
desync. What is needed here is a **mapping**, not a singleton.

**Decision: a closed mapping from data year to tract-delineation basis year.**

- **Values are plain `int` basis years** — `2010`, `2020` — not an enum, not a
  string, not a boolean.
- **The domain is closed.** Years present are answered; years absent raise.
- **The name is deliberately different from nmtc-mapper's.** `TRACT_VINTAGE` there
  means "the one binding in force"; here it would mean "a year-indexed lookup".
  Same name, different shape, in one portfolio is how a future edit copies the
  wrong semantics across repos. Use a name that says what it is —
  `TRACT_GEOID_VINTAGE_BY_YEAR` or equivalent — and say in a comment why it does
  *not* reuse the nmtc-mapper name.

**Rejected alternative — a threshold constant** (`FIRST_2020_VINTAGE_YEAR = 2022`,
with `2010` implied below it). It is shorter and it is what the two-value data
invites. It loses because it cannot express a third value. When the 2030 Census
delineations arrive, a threshold must become a mapping, and every call site that
read the threshold must change — a breaking change forced by the constant's shape
rather than by the world. The mapping absorbs a third vintage as an append. **The
threshold form is the one shape that guarantees a breaking change at the next
boundary, which is precisely the boundary this whole exercise exists to survive.**

**Rejected alternative — an enum of vintages.** Type-safe and self-documenting,
but it does not survive a CSV round-trip, it does not compare with `<`, and it
adds an import to every consumer. The basis year is already a meaningful,
orderable integer. Use it.

### M1.3 The unknown year — the load-bearing case

When 2026 data lands and the mapping has no entry for 2026, what happens?

**Decision: raise. Never infer, in either direction.**

The tempting behaviour is "assume the newest vintage we know about." It is wrong,
and it is wrong in the specific way this document exists to eliminate: it is
**silently** wrong, and it is wrong *exactly at a boundary*. Every year from 2022
to 2031 that guess is right, which trains everyone to trust it; in 2032 it is
wrong and produces no signal, because a guess that has been right for a decade
does not announce the year it stops being right. That is this defect, reintroduced
by the fix for this defect.

The symmetric temptation — "assume the oldest vintage" — fails identically, just
sooner.

A reader may object that the rule in §M1.1 is deterministic, so the forward answer
is computable: 2030 Census, delineations published, first January 1 they are in
effect, done. **It is not computable in advance, and the 2020 cycle proves it.**
The 2020 Census delineations became effective for the 2022 data year — a two-year
lag driven by publication timing that was itself disrupted by a pandemic. The lag
is contingent on Census publication schedules and on FFIEC's adoption of them. A
constant that encodes a *predicted* lag is a prediction wearing the costume of a
citation. This portfolio has shipped that mistake.

So: an unmapped year raises, and the message says what a human must do — read the
CFPB *Summary of {year} Data on Mortgage Lending*, confirm the delineation basis,
add the entry, cite it in the comment. Adding a year to this mapping is a
deliberate human act with a citation attached, every time. That is the point.

**Cost, stated plainly.** This means `hmda-analyzer` breaks on the first day a new
HMDA year is served, for any tract-keyed operation, until someone edits a
constant. That is a real cost and it will annoy someone. It is the correct cost:
the alternative is being confidently wrong at a boundary in a fair-lending tool.

### M1.4 Does the design survive a third vintage?

Yes, with one caveat that §M2 and §"What this rule does not protect against" make
load-bearing.

The mapping absorbs 2032 (or whenever) as a new entry with a new basis year. No
call site changes. Comparisons of the form "do all rows in this frame share a
basis year" work unchanged for two, three, or seven vintages.

**The caveat: the binding is not purely a function of data year.** Connecticut
breaks it, and the break is measured, not hypothesised (§M6.5). A year→vintage
mapping is correct for the *delineation basis* and still insufficient for *key
comparability*. The design survives a third vintage; it does not, on its own,
survive Connecticut. §M3 and the coverage section say what to do about that.

---

## M2 — What is actually incoherent, and what is not

"The vintages differ" is not a defect. Joining across them on a key that means
different things is. Over-refusing is its own defect — a rule that fires on
analyses that were always correct trains users to reach for the override, and then
the override is load-bearing in exactly the cases it should not be.

### M2.1 Incoherent

**Any aggregation whose grouping key includes `census_tract`, on rows spanning
more than one delineation basis.** That is the whole of it. Concretely, in this
package (full inventory in §M6.2):

- `lending_by_tract` — `groupby("census_tract")`
- `lending_desert_score` — via `lending_by_tract`, and worse: its percentile rank
  is computed *over the collapsed tract set*, so the reference distribution every
  tract is scored against is corrupted, not only the colliding rows
- `racial_composition_by_tract` — `groupby(["census_tract", "derived_race"])`
- `lender_summary`'s `unique_tracts` — `nunique()` on `census_tract`

### M2.2 Safe, and explicitly declared safe

**Per-year analysis that never pools across years.** Confirmed. Each year's rows
carry that year's delineation; within a year the key is internally consistent.

**Any aggregation whose key does not include `census_tract`** — by lender, by
year, by race, by income band, by action taken. A frame that *spans* the boundary
but is only ever grouped by `lei` is correct and must not be refused. This is the
case that makes a load-time raise wrong.

**Row-level classification that reads FFIEC tract *attributes* without joining on
the tract *key*.** `cra_proxy_distribution` is the live example: it classifies each
row from that row's own `tract_to_msa_income_percentage` and
`ffiec_msa_md_median_family_income`, both pre-appended per row by year. No tract
key is joined. Pooling years does not collide anything. **This is safe from *this*
defect** — and it is not thereby correct across years, because those appended
attributes move on their own schedule (§"does not protect against", item 4). Do
not let this paragraph be quoted as "cra_proxy is fine across years."

### M2.3 County, state and MSA — the prompt's premise is false

The commissioning prompt asserts that "county FIPS is largely stable across
vintages," and invites this document to declare cross-vintage county/state/MSA
aggregation defensible for that reason.

**Measured, it is not stable.** Connecticut replaced its eight legacy counties
with nine planning regions for federal statistical use, and the LAR adopted the
change (§M6.5):

```
CONNECTICUT -- county_code by year
  2020-2023:   09001 09003 09005 09007 09009 09011 09013 09015   (8 legacy counties)
  2024:        09110 09120 09130 09140 09150 09160 09170 09180 09190   (9 planning regions)
        jaccard vs prior year = 0.056   <<< KEY UNIVERSE CHANGED
```

`derived_msa_md` moves too, at the same boundary — CT's `49340` is replaced by
`47930` in 2024 (jaccard 0.714). CFPB's own 2022 summary already warns of this in
general terms: comparisons "are limited due to the changes in **MSA and census
tract boundaries**."

So the honest statement is more useful than the prompt's:

> **County, state and MSA aggregation across the 2021→2022 tract boundary is
> defensible, because that boundary does not move county, state or MSA codes.**
> Those keys have their own, *different*, boundaries — for Connecticut, at
> 2023→2024 — and cross-year aggregation on them is not universally safe.

And a structural point that matters more than the exception:

**The county failure is loud; the tract failure is silent.** CT's county codes
change to a *disjoint* set (jaccard 0.056), so a `groupby("county_code")` across
2023–2024 returns roughly seventeen rows where nine are expected. That is visible.
The 2021→2022 tract failure *reuses* keys, so the row count looks right and the
numbers are wrong. **Key reuse is the dangerous mode. Key replacement is the safe
one.** That distinction drives §M3.

### M2.4 Where the check belongs

**Decision: annotate at load, raise at aggregation. Not at load.**

The recon proposed raising on a vintage-spanning *frame*. Rejected.

- **A vintage-spanning frame is not itself wrong.** `load_range(2021, 2023,
  state="OH")` grouped by `lei` is a correct analysis today. Raising at load
  breaks it. This portfolio has already shipped one false refusal — oz-tracker's
  `calculate_benefits()` refusing a fully-specified investment — and a
  load-time raise here is the same mistake with the same shape: refusing the
  input because *some* downstream use of it would be wrong.
- **`load_range`'s contract is honest and should stay honest.** It says it returns
  every requested year's rows, correctly labelled. It does. Making it refuse to
  return data it correctly loaded would make the docstring false.
- **The blast radius is small enough to guard precisely.** Four functions (§M6.2).
  Guarding four call sites is cheaper and far more accurate than guarding every
  frame that might one day reach one of them.
- **The operation is where the meaning is.** Only at `groupby("census_tract")` is
  it knowable that the key is about to be treated as an identity.

**Cost, stated plainly.** Four guards can drift apart; one load-time guard cannot.
If a fifth tract-keyed operation is added later and its author forgets the guard,
the defect returns silently for that operation. Mitigation is a matter for the
build prompt, not this document, but the exposure is real and belongs in the
audit's sights. The load-time alternative buys uniformity at the price of refusing
correct work, and refusing correct work is the more expensive failure in a tool
whose users will reach for an override the first time it happens.

---

## M3 — Raise, or annotate?

### M3.1 Raise, at the four aggregation sites

**Decision: raise.** A new exception, subclassing `ValueError` to match the
existing `MissingColumnError` precedent in `hmdaanalyzer/exceptions.py` so that
`except ValueError` callers keep working.

**The message must carry the measurement, not just the verdict.** A message that
says "frame spans multiple tract vintages" tells a user they are blocked without
telling them whether it matters. It must name:

1. the function that refused;
2. the delineation bases present and the years mapping to each;
3. **how many GEOIDs actually collide** and **what share of rows land on them** —
   this is the materiality number, it varies from 18% to 45% across the counties
   measured in §M6.4, and a user deciding what to do next needs it;
4. the concrete next actions, in order of preference (§M5.2).

Item 3 is the difference between an error a user routes around and an error a user
learns from.

### M3.2 Warn instead — argued, and why it loses

The case for warning is real: it is non-breaking, it preserves every existing
call, and it puts the decision with the analyst.

It loses on three counts.

- **Warnings are invisible where this library lives.** `hmda-analyzer` is used in
  notebooks; the repo ships `examples/hmda_disparity_demo.ipynb`. Python's default
  filter shows a given warning **once per location**, so in a notebook re-run — the
  normal way of working — the second execution is silent. Output pinned above a
  scrolled cell is output nobody reads.
- **The output is indistinguishable.** A warned-about `lending_by_tract` result is
  a DataFrame with the same columns, the same dtypes, and a plausible row count.
  Once it is assigned to a variable, the warning is gone and the wrongness is not.
- **The artefact outlives the session.** A warning is a property of the run; the
  number goes into a spreadsheet, a memo, or a regulatory file. In a fair-lending
  context the number is the thing that persists, and it carries no warning with it.

A warning is the right instrument when the user can still see the problem in the
output. Here the entire defect is that they cannot.

### M3.3 The override — replaced, not provided

An escape hatch that lets a user produce a cross-vintage tract-level aggregation
is a loaded gun: the output looks like every other output, and the only trace of
the acknowledgement is in the calling code, which does not travel with the number.

**Decision: there is no boolean override. There is a narrowing parameter instead.**

Rather than `allow_cross_vintage=True` — which says "merge them anyway and I
accept the consequences" — the caller names the basis they want:
`vintage=2020`. This **selects a coherent subset** of the frame before
aggregating. It cannot produce a wrong number, because it never merges two
delineations. It answers the real underlying request ("give me a tract analysis
from this frame") without granting the dangerous capability ("give me one that
pools incompatible keys").

This is the central design move of the document: **the escape hatch a user reaches
for is almost always a narrowing request wearing an override's clothes.** Give them
the narrowing and the override becomes unnecessary.

The narrowed result must say so in its own output — the selected basis year
present as a value on the returned frame, and the dropped years' row count
reported — so a copied table still shows which years it covers.

**If the audit concludes a true override is nonetheless required**, the minimum
bar is that the acknowledgement travels with the data, not with the call: the
returned object carries the cross-vintage fact as a value in a column, and any
frame derived from it carries it forward. A flag that exists only in the calling
code fails this bar. A flag that sets an attribute on the DataFrame also fails it —
pandas drops non-standard attributes through most operations, so the marker
evaporates on the first `.copy()` or `.merge()`. **This document's position is
that no override should ship in v1.** Ship the narrowing, and let the audit or a
real user demand more.

### M3.4 What a user with a legitimate need does

Someone who genuinely wants a 2019–2023 tract-level trend is not doing anything
illegitimate. §M5.2 is the answer to that person, and the error message must point
at it.

---

## M4 — The `tract_vintage` column as a contract

### M4.1 The column cannot be the mechanism

The recon proposed emitting the vintage as a first-class column and treating it as
the contract. **Measured against pandas 3.0.5, a column cannot carry a guarantee.**
Three behaviours, verified 2026-08-03 (§V):

```
1) concat of two disjoint Categoricals -> dtype: str
2) concat with a frame missing the column -> nulls: 1 (silent NaN, no error)
4) agg() output keeps tract_vintage? False
```

Read those in order. A `Categorical` dtype — the obvious choice for a small closed
set of values — **silently degrades to `str`** when two frames with disjoint
categories are concatenated, which is exactly the operation that creates a
vintage-spanning frame. Concatenating a frame that lacks the column yields silent
`NaN`, not an error. And `.agg()` — the call at the heart of `lending_by_tract` —
**drops the column entirely** unless it is explicitly carried.

That last one is decisive: **the function most in need of the guard is the
function that discards it.**

**Decision: the column is provenance, not mechanism.**

The guard derives the delineation basis from **`activity_year`**, which
`load_range` already asserts is present and correct for every row
(`_assert_activity_year`, `loader.py:148-162`), and which no aggregation can drop
without the guard noticing its absence. The column exists so that a human, and a
downstream consumer, can *see* the vintage. It is never trusted as the source of
truth.

This costs nothing and closes the whole class of "user dropped the column" and
"concat mangled the dtype" failures at once.

### M4.2 Values and dtype

**Decision: plain `int` basis year — `2010`, `2020`.**

- Survives `to_csv` / `read_csv` round-trips as itself. A string does not
  (leading-zero and dtype-inference hazards); an enum does not at all.
- Orderable, so "which is newer" is `<`, with no lookup.
- Identical to the mapping's values, so there is one representation, not two.

**Rejected: `Categorical`** — degrades to `str` under exactly the concat that
matters (verified above), and the degradation is silent.
**Rejected: string labels** (`"2010 Census"`) — invites `.str` operations,
does not compare, and the label drifts from the constant.
**Rejected: enum** — best type safety of the four, but does not survive
serialization, and this value's whole job is to travel with the data.

### M4.3 Naming — and a misdescription trap

**Decision: name the column `tract_geoid_vintage`, not `tract_vintage`.**

The LAR carries two tract-related things that change on **different schedules**:

| | changes on | 2021 → 2022 | 2023 → 2024 |
|---|---|---|---|
| tract *delineation* (the GEOID's meaning) | decennial | **changes** | stable (except CT) |
| FFIEC demographic appends (`tract_population`, `tract_to_msa_income_percentage`, `ffiec_msa_md_median_family_income`, …) | 5-year ACS refresh, applied annually | changes | changes |

CFPB's own 2021 summary conflates them ("delineations … from the 2011–2015 ACS",
§M1.1). A column called `tract_vintage` will be read by a consumer that has never
seen this document as covering both. It covers only the first.

Every gate in this portfolio that misdescribed its own coverage became a defect
later. `tract_geoid_vintage` names the thing it governs — the key — and buys
nothing else. The cost is a longer name that diverges from nmtc-mapper's
`TRACT_VINTAGE`; §M1.2 already argues that divergence is correct, because the two
things genuinely are not the same thing.

### M4.4 The schema guard collides with this, today

`load_range` validates every fetched year against `EXPECTED_LAR_COLUMNS` using
**strict set equality in both directions** (`loader.py:136-145`):

```python
missing    = EXPECTED_LAR_COLUMNS - actual
unexpected = actual - EXPECTED_LAR_COLUMNS
if missing or unexpected:
    raise SchemaValidationError(...)
```

`_validate_lar_schema` runs on the frame **after** `_clean`. So if the vintage
column is added in `_clean` or `load_from_api`, **every `load_range` call raises
`SchemaValidationError: unexpected=['tract_geoid_vintage']`** on the first year it
fetches. The recon design does not mention this. It is not a subtlety; it is a
total failure on the first call.

Three ways out, and the choice matters:

1. **Add the name to `EXPECTED_LAR_COLUMNS`.** One line. But that frozenset's
   documented job is to detect *CFPB* schema drift, and it already blurs this by
   including `is_approved`/`is_denied`. Adding more of our own derived names makes
   a drift detector that is increasingly about us.
2. **Add the column after validation, inside `load_range` only.** Keeps the guard
   pure, but then single-year `load_from_api` frames lack the column while
   `load_range` frames have it — two shapes from one library, and the single-year
   path is the one most users start with.
3. **Split the frozenset** into the raw CFPB column set (what the guard is
   actually for) and a derived set added by `_clean`, validating `actual - derived`
   against the raw set. **Endorsed.** It makes the guard mean what its comment
   already claims it means, and it makes adding any future derived column a
   non-event.

### M4.5 Outputs that cannot carry a column

`lender_summary` returns a **`dict`**, not a DataFrame (`lender.py:43-54`), and one
of its keys is `unique_tracts` — a `nunique()` on `census_tract` that is wrong
across the boundary (§M6.4). **No column design reaches it.** Its guard must be the
raise, or the metric must be per-vintage inside the dict. This is a concrete gap
in the "emit a column everywhere" framing and the build prompt must handle it
explicitly rather than inheriting the assumption that every output is a frame.

### M4.6 Downstream and documented-shape exposure

**Recorded, not fixed, per scope.**

- **`fair-lending-screener`** consumes HMDA frames and does its own tract work. A
  new column means: any strict schema check there breaks the same way §M4.4
  describes; any snapshot test over `df.columns` breaks; and — the quieter risk —
  a consumer that has never heard of `tract_geoid_vintage` will pass it through
  into its own outputs, where it will be read as an assertion that the screener
  understands vintages. It does not. **Exposure noted; not fixed here.**
- **hmda-analyzer's own README** states (line 99-100) that "The CFPB column schema
  is identical across **2018–2025** … so no columns are year-conditional." That
  remains literally true of the *CFPB* schema, but sits directly above the
  `load_range` documentation and will read as a claim that nothing about the
  columns varies by year — which is the exact misconception this defect lives in.
  The README needs a change with this release.
- **Tests** assert column membership with `in` and `issubset` rather than
  equality (`tests/test_disparity.py:63,90`), so an added column does not break
  them. `tests/test_load_range.py:30` pins the exact 99-column live CFPB header;
  that is a raw-header fixture and is unaffected by a derived column, provided
  §M4.4 option 3 is taken.

---

## M5 — No crosswalk

### M5.1 The argument

**Decision: do not bundle a crosswalk. Do not offer one as an option.**

"The data is unavailable" is not the reason and would be false. Census publishes
2020↔2010 tract relationship files; **this document used them** (§M6.4) — they
downloaded in seconds and are authoritative.

The reason is what a crosswalk would have to do to a count.

A relationship file tells you that 2020 tract `35001000601` overlaps three 2010
tracts. It does not tell you which of the 2019 loans in those 2010 tracts were
inside the piece that became `35001000601`, because **HMDA does not carry
sub-tract location.** The filer reports a tract, not a point. Any conversion must
therefore allocate *proportionally* — by land area, or by population, or by
housing units — and proportional allocation of a count produces **fractional
loans**.

That is the defect class this entire engagement has been closing, in its purest
form: an operation that silently converts a **count** into an **estimate** while
changing nothing about the column name, the dtype, the row count, or the shape of
the output. `applications = 47` and `applications = 47.3` look like the same kind
of number. In a fair-lending screening context they are not, and the second one
cannot be defended in a conversation with an examiner.

There is a second, quieter reason. Allocation weights are demographic, and the
demographics that would weight a fair-lending allocation are the same
demographics the analysis is about. Allocating loan counts by tract population
across a boundary bakes a population assumption into a disparity measurement.
Even done carefully, it is a modelling choice masquerading as a data-cleaning
step.

**A library that ships a screening tool should not silently model.** If a user
needs an estimate, they should have to make the estimate themselves, knowingly.

### M5.2 The honest answer to "I need a 2019–2023 tract-level trend"

That is a legitimate need and the tool should not pretend otherwise. Four options,
their costs, and which the library endorses.

**1. Two panels, split at the boundary. — ENDORSED.**
Run 2019–2021 on 2010 delineations and 2022–2023 on 2020 delineations; present
them as two series with an explicit, labelled break. *Cost:* no single continuous
line, so no "growth since 2019" number for any individual tract. *Why endorsed:*
it is the only option that involves no estimation and no non-random subsetting.
The break is real; showing it is honest reporting, not a limitation.

**2. Aggregate to a geography that survives the boundary.**
County, state, or MSA — subject to §M2.3, and check Connecticut before assuming.
*Cost:* loses tract granularity, which is often exactly the point of the analysis.

**3. Restrict to tracts verified geometrically identical across the boundary.**
The Census relationship file identifies them exactly. Measured (§M6.4):

| County | GEOIDs in both vintages | geometrically identical | usable share |
|---|---|---|---|
| Baltimore city, MD | 198 | 156 | 79% |
| Cuyahoga County, OH | 382 | 228 | 60% |
| Bernalillo County, NM | 126 | 46 | 37% |

*Cost, and it is a serious one:* **the surviving subset is not random.** Tracts
that were not re-carved are disproportionately the built-out, stable-population
ones; tracts that *were* re-carved are disproportionately the fast-growing and
fast-changing ones. A trend computed on stable tracts only is a trend with growth
areas systematically removed — which is a bias pointed directly at what
fair-lending analysis is usually looking for. Anyone taking this option must state
it. The library can *identify* the stable subset without endorsing the analysis.

**4. Build the crosswalk yourself, outside the library, and own the estimate.**
Entirely legitimate; the relationship files are public. *Cost:* the output is an
estimate and must be labelled as one for the rest of its life. The library will
not do this step for you, and §M5.1 is why.

---

## M6 — Empirical answers

Every command below was run 2026-08-03. Scripts live in the session scratchpad,
not in the repo, per scope. Output is pasted unedited.

### M6.1 Does `lending_desert_score` group on `census_tract`?

**Yes — indirectly, and it is worse than a plain groupby.**

`geographic.py:74` calls `lending_by_tract(df)`, which groups on `census_tract`
at `geographic.py:25`. It then does something the direct call does not
(`geographic.py:77-91`): it computes `rank(pct=True)` over the **collapsed** tract
set and derives both `desert_score` and the boolean `is_lending_desert` from that
percentile.

**So the corruption is not confined to colliding rows.** The percentile is a
*reference distribution*: every tract's score depends on the population of tracts
it is ranked against, and that population has been altered.

```
--- lending_desert_score (M6.1: does it group on census_tract?) ---
rows returned      : 199
same row count as lending_by_tract: True
deserts flagged    : 47
columns            : ['census_tract', 'applications', 'denials', 'originations',
                      'avg_loan_amount', 'median_income', 'denial_rate',
                      'origination_rate', 'app_percentile', 'desert_score',
                      'is_lending_desert']

per-year runs      : 2021 -> 198 rows, 197 rows for 2022
sum of per-year rows 395 vs pooled 199  -> 196 tracts silently merged
non-colliding 2021 tracts whose desert verdict flips when pooled: 0
```

**That last line is not evidence of safety and must not be read as such.** In
Baltimore city, 196 of ~198 GEOIDs collide, so the non-colliding set is nearly
empty and there was almost nothing to test. The reference-distribution argument
stands on the mechanism, not on this measurement; a county with a large
non-colliding population would be needed to size the effect, and that measurement
was not made. **Recorded as an open item (§O).**

Exposed internal operations, therefore: `groupby("census_tract")` → `.agg()` →
`rank(pct=True)` → threshold comparison → boolean flag. Four steps downstream of
the collision, and the last one is what a user reads.

### M6.2 Inventory of tract-key operations

Full sweep of `hmdaanalyzer/`. **Note that the prompt's verb list —
groupby/merge/set_index — misses one of the four.**

| File:line | Operation | Key | Exposed? |
|---|---|---|---|
| `analysis/geographic.py:25` | `groupby("census_tract").agg(...)` | tract | **YES** |
| `analysis/geographic.py:74` | `lending_by_tract(df)` then `rank(pct=True)` | tract | **YES** (+ reference distribution) |
| `analysis/geographic.py:108` | `groupby(["census_tract","derived_race"])` | tract | **YES** |
| `analysis/lender.py:52` | `actionable["census_tract"].nunique()` | tract | **YES** — not a groupby/merge/set_index |
| `analysis/geographic.py:51` | `groupby("county_code")` | county | no (see §M2.3 for CT) |
| `analysis/geographic.py:130` | `groupby("state_code")` | state | no |
| `analysis/lender.py:123` | `groupby("lei")` | lender | no |
| `analysis/lender.py:87` | `.merge(..., on="derived_race")` | race | no |
| `analysis/disparity.py:30,100,127,131` | `groupby` on race / income band | — | no |
| `analysis/disparity.py:132` | `.merge(..., on="derived_race")` | race | no |
| `analysis/cra_proxy.py` | row-level classification, no tract-key join | — | no (§M2.2) |

**Four exposed sites**, all in two files. No `set_index` on a tract key anywhere.
No merge on a tract key anywhere. This small, contained blast radius is the
evidence for §M2.4's decision to guard at aggregation rather than at load.

### M6.3 Independent confirmation of the 2021→2022 flip

Four counties the recon did not use, full county files (no `limit` truncation, so
the tract-ID set is complete rather than a stream-truncated sample):

```
Baltimore city, MD (24510)      Bexar County, TX (48029)
  2018->2019   0.990              2018->2019   0.992
  2019->2020   0.995              2019->2020   0.992
  2020->2021   1.000              2020->2021   0.992
  2021->2022   0.985              2021->2022   0.899   <<< COLLAPSE
  2022->2023   0.985              2022->2023   0.989
  2023->2024   0.990              2023->2024   0.995

Cuyahoga County, OH (39035)     Bernalillo County, NM (35001)
  2018->2019   0.993              2018->2019   0.987
  2019->2020   0.989              2019->2020   1.000
  2020->2021   0.993              2020->2021   1.000
  2021->2022   0.778   <<<        2021->2022   0.635   <<< COLLAPSE
  2022->2023   0.995              2022->2023   1.000
  2023->2024   0.993              2023->2024   0.994
```

Plus Massachusetts statewide, 2021→2022 jaccard **0.747** (1457 → 1589 tracts).

**The boundary reproduces, and no other transition behaves like it.** In three of
the four counties, 2021→2022 is the single lowest transition by a wide margin
(0.635–0.899 against a 0.987–1.000 background). Every non-boundary transition in
every county measured sits at 0.985 or above. The one exception in either
direction is Connecticut's 2023→2024, which is a different phenomenon (§M6.5).

**But the recon's numbers do not generalise, and its detection method is wrong.**

The recon reported "0.997 everywhere except 2021→2022, where it collapses to
0.530," described as verified national. Measured across four fresh counties the
2021→2022 value ranges **0.635 to 0.985**. In Baltimore city it is **0.985 —
indistinguishable from that county's own ordinary year-over-year transitions**
(0.985–1.000). A detector thresholded on tract-ID Jaccard would have returned
"no boundary here" for Baltimore.

It would have been badly wrong, which §M6.4 establishes.

### M6.4 Jaccard is anti-correlated with the risk — the decisive result

Jaccard measures ID **churn**. The defect is ID **reuse**. They pull in opposite
directions, and the limiting case makes it obvious: a county whose tracts were
completely re-carved but which kept every GEOID would score Jaccard **1.000** and
be **100% corrupted**.

Verified against the U.S. Census Bureau 2020↔2010 tract relationship files
(`www2.census.gov/geo/docs/maps-data/data/rel2020/tract/`, published 2022-01-25,
downloaded 2026-08-03). A GEOID is counted as denoting different ground
("RECARVED") only if it maps to two or more 2010 tracts, or is 1:1 with a land-area
change of 1% or more — sub-1% boundary refinements are conservatively *excluded*:

```
Baltimore city, MD (24510)          Bernalillo County, NM (35001)
  GEOIDs in both vintages : 198       GEOIDs in both vintages : 126
     IDENTICAL polygon    : 156          IDENTICAL polygon    :  46
     MINOR (<1% area)     :   7          MINOR (<1% area)     :  16
     RECARVED             :  35          RECARVED             :  64
  LAR rows on a RECARVED key:          LAR rows on a RECARVED key:
     2021: 6,134/33,679 =  18.2%          2021: 21,470/49,095 = 43.7%
     2022: 4,234/23,452 =  18.1%          2022: 12,654/28,050 = 45.1%
  Jaccard(2021,2022)      : 0.985      Jaccard(2021,2022)      : 0.635

Cuyahoga County, OH (39035)
  GEOIDs in both vintages : 382 | IDENTICAL 228 | MINOR 28 | RECARVED 126
  LAR rows on a RECARVED key: 2021 20,666/75,366 = 27.4% | 2022 14,952/53,119 = 28.1%
  Jaccard(2021,2022)      : 0.778
```

**Baltimore city: Jaccard 0.985, and 18% of rows on both sides of the boundary
land on a key that denotes materially different ground.** The county that looks
safest by the recon's metric is silently wrong for roughly one row in five.

Two consequences, and they are the reason this document exists in the form it
does:

- **The binding must be declarative, never measured.** A rule derived from
  year→vintage is right in Baltimore city. A rule derived from observed ID overlap
  is wrong there, and wrong in the direction of false reassurance.
- **High ID stability is the *more* dangerous case, not the safer one.** Where IDs
  churn, rows fall into disjoint buckets and the tract count visibly inflates.
  Where IDs persist, rows silently merge. Intuition runs backwards here, and any
  reviewer's instinct to "just check how much the tract list changed" must be
  headed off explicitly.

### M6.5 Connecticut — a second discontinuity the proposed binding does not describe

Connecticut's `county_code` universe changes completely at 2023→2024 (§M2.3), and
because the county code is the first five digits of the tract GEOID, **every
Connecticut tract key changes with it**:

```
CONNECTICUT -- census_tract GEOID universe by year
  2018:  825 tracts   prefixes 09001..09015
  2021:  824 tracts   prefixes 09001..09015     jaccard vs 2020 = 0.996
  2022:  872 tracts   prefixes 09001..09015     jaccard vs 2021 = 0.822  <<< the tract boundary
  2023:  872 tracts   prefixes 09001..09015     jaccard vs 2022 = 1.000
  2024:  872 tracts   prefixes 09110..09190     jaccard vs 2023 = 0.000  <<< EVERY KEY CHANGED
```

And it is a **pure renumbering**, not a re-carving:

```
2023 CT tracts: 872   2024 CT tracts: 872
distinct 6-digit tract SUFFIXES: 2023=872  2024=872
suffix multiset identical 2023 vs 2024: True
suffixes only in 2023: []   suffixes only in 2024: []
full-GEOID overlap: 0
```

Same 872 polygons, same 872 within-county tract numbers, new county prefix.

**This is the finding that constrains the whole design.** The delineation basis for
CT 2023 and CT 2024 is the *same* — both are 2020 Census tracts — so a correct
year→vintage mapping reports "same vintage" and a check built on it **lets a CT
2023–2024 tract trend through**. The binding is not wrong; it is answering a
different question than the one that matters.

The saving grace is the §M2.3 structure: because the new keys are *disjoint*
(jaccard 0.000), the failure is fragmentation, not collision. A CT 2023–2024
`lending_by_tract` returns 1,744 rows where 872 are expected, every 2023 tract
appears to cease lending, and 872 new tracts appear from nowhere. That is wrong
and disruptive, but it is **visible**, and no individual number is silently
corrupted.

It is nonetheless a hole, it is demonstrated rather than theorised, and it belongs
in the coverage section below rather than being quietly absorbed.

### M6.6 Does `load_range` have any other cross-year join?

**No.** `load_range` (`loader.py:165-255`) fetches each year independently and
combines with a single `pd.concat(frames, ignore_index=True)` at line 253. That is
a vertical stack on position, not a join on any key. There is no `merge`, no
`join`, no `set_index`, and no cross-year lookup anywhere in the function.

The cross-year assumptions it *does* make are all in the schema guard, and they
are correct: `_validate_lar_schema` asserts each year's column set matches, and
`_assert_activity_year` asserts each year's rows are actually that year's.

Every other cross-year key assumption in the package is downstream, at the
aggregation sites in §M6.2. Beyond the tract key, three deserve naming:

- **`county_code`** — not stable (CT, 2023→2024).
- **`derived_msa_md`** — not stable (CT `49340` → `47930`, 2023→2024, jaccard
  0.714); CFPB's 2022 summary warns of MSA boundary changes generally.
- **`lei`** — globally unique and persistent by construction, but an institution
  that changes LEI mid-span appears as two lenders. This is *fragmentation*, not
  collision: the counts are right and the attribution is split. Different failure,
  visible, out of scope here, worth someone's attention eventually.

---

## What this rule does not protect against

Written honestly and at length, because every gate in this portfolio that
misdescribed its own coverage became a defect later. A reader should be able to
use this list to decide whether they still have a problem after the rule ships.

1. **Connecticut, 2023→2024 — demonstrated, not hypothetical.** Every CT tract
   GEOID changes (jaccard 0.000) while the delineation basis stays 2020. A
   year→vintage rule declares this safe. It is not comparable. Mitigating factor:
   the failure is loud (row counts roughly double) rather than silent. §M6.5.

2. **County and MSA code changes generally.** The rule governs the tract key and
   says nothing about `county_code` or `derived_msa_md`, both measured unstable at
   2023→2024 in Connecticut. A user who moves *up* from tract to county to escape
   the tract rule can land in an unguarded version of the same problem. §M2.3.

3. **Future geography changes of a kind not yet seen.** The rule encodes decennial
   re-delineation. Nothing in it anticipates another CT-style county-equivalent
   restructuring, an OMB delineation revision, or a tribal-area boundary change.
   The Connecticut case was not anticipated by the recon either.

4. **The FFIEC demographic appends, which move on a different schedule.**
   `tract_population`, `tract_minority_population_percent`,
   `tract_to_msa_income_percentage`, `ffiec_msa_md_median_family_income`,
   `tract_owner_occupied_units` and the rest are refreshed annually against a
   rolling 5-year ACS. Two rows sharing a delineation basis and a GEOID may still
   carry appended demographics computed on different ACS vintages. **This directly
   affects `cra_proxy_distribution` pooled across years** — which §M2.2 declares
   safe *from the key-collision defect* and which this item declares not thereby
   correct. The naming decision in §M4.3 exists to stop the column from being read
   as covering this. It does not cover it.

5. **Within-vintage incomparability generally.** "Same delineation basis" is
   necessary for tract-level comparison. It is not sufficient.

6. **Outputs that are not DataFrames.** `lender_summary` returns a `dict`; its
   `unique_tracts` value is a `nunique()` that undercounts across the boundary and
   no column can ride along with it. Guarded only if the raise reaches it. §M4.5.

7. **Frames the library did not build.** The guard derives the basis from
   `activity_year`. `load_from_file` accepts an arbitrary CSV and does not assert
   that column exists (`loader.py:258-266`), so a user-supplied file may carry no
   year at all — in which case the guard cannot fire and must say so rather than
   assume. A frame with a *fabricated* `activity_year` defeats the guard entirely.

8. **A fifth tract-keyed operation added later without its guard.** The §M2.4
   decision to guard four call sites rather than the frame accepts this exposure
   deliberately. It is the known cost of not over-refusing.

9. **It does not make cross-vintage analysis correct.** It makes it *not silent*.
   A user who takes the narrowing parameter still has two panels, not a trend. The
   rule removes a wrong answer; it does not supply the right one. §M5.2 is the
   nearest thing to a right answer and every option there has a cost.

10. **Truncation interacts with all of it.** `limit` silently truncates each year's
    fetch (out of scope, recorded). A truncated frame's tract set is a biased
    sample of the county's tracts, so collision counts and row shares measured on
    one are not the county's true figures. The measurements in this document
    deliberately used full county files to avoid this.

11. **Nothing here addresses whether the underlying analysis is sound.** A
    correctly-vintaged `lending_desert_score` is still computed by the formula at
    `geographic.py:83-91`, which is out of scope and unexamined.

---

## Corrections to the recon and to the commissioning prompt

Recorded because they are load-bearing, and because ten prompts in this engagement
have carried factual errors that surfaced only when a session executed them.

**Against the recon design:**

1. **"Raise on a vintage-spanning frame" — rejected.** It refuses analyses that
   were always correct (group-by-lender on a multi-year frame). Replaced by:
   annotate at load, raise at aggregation. §M2.4.
2. **"Emit `tract_vintage` as the contract" — revised.** A column cannot carry a
   guarantee: `.agg()` drops it, concat with a frame lacking it yields silent NaN,
   and a `Categorical` degrades to `str` under exactly the concat that matters.
   The column is provenance; the guard derives from `activity_year`. §M4.1.
3. **The `TractVintage` frozen-dataclass pattern — does not port.** Its entire
   value is a cross-field consistency check between a geocoder vintage and a table
   header, neither of which exists here. A mapping is needed, not a singleton, and
   it should not reuse the name. §M1.2.
4. **The recon's detection method is anti-correlated with the risk.** Tract-ID
   Jaccard measures churn; the defect is reuse. Baltimore city scores 0.985 —
   normal-looking — with 18% of rows on re-carved keys. §M6.4.
5. **"0.997 everywhere except 2021→2022, where it collapses to 0.530", described
   as verified national — does not generalise.** Measured range across four fresh
   counties: 0.635 to 0.985. The boundary is national; the magnitude is not.
6. **"Do not bundle a crosswalk" — upheld, with a different argument.** Not
   because the data is unavailable (it is not; this document used it), but because
   HMDA carries no sub-tract location, so any conversion allocates proportionally
   and produces fractional loan counts. §M5.1.

**Against the commissioning prompt:**

7. **`docs/rate-spread/` is not in this repo.** It is in `fair-lending-screener`.
   `hmda-analyzer` has **no `docs/` directory at all**; its methodology precedent
   is `hmdaanalyzer/methodology/cra_proxy_methodology.md` — *inside the package*.
   **Consequence:** `MANIFEST.in` includes no `docs/` path, so this document at
   `docs/tract-vintage/methodology.md` **will not ship in the sdist or the
   wheel**, whereas the CRA-proxy methodology does. The prompt's instruction was
   followed; whether that is the right home is a question for the audit.
8. **The FFIEC FIG does not state the tract vintage.** Proposed as the citation;
   read; it says only "Enter the 11-digit census tract number." The authority is
   Reg C Comment 4(a)(9)(ii)(C)-1 plus CFPB's annual data summaries. §M1.1.
9. **"County FIPS is largely stable across vintages" is false.** Connecticut,
   2023→2024, jaccard 0.056. The prompt invited a blanket declaration that
   cross-vintage county aggregation is defensible; the correct statement is
   narrower and is given in §M2.3.
10. **The prompt's verb list for the inventory — groupby/merge/set_index — misses a
    site.** `lender.py:52` is a `nunique()`. Four exposed sites, not three. §M6.2.
11. **`EXPECTED_LAR_COLUMNS` uses strict two-way set equality**, so adding any
    column to `_clean`'s output makes **every `load_range` call raise
    `SchemaValidationError`**. Not mentioned in the design; it is a total failure
    on the first call, not an edge case. §M4.4.
12. **`lender_summary` returns a `dict`.** "Emit the column on every frame that
    carries `census_tract`" does not reach it. §M4.5.

**And the thing the prompt did not know existed:** the Connecticut 2023→2024
tract-key discontinuity (§M6.5). It is a second, independent break in tract-key
comparability, at a different year than the one this document was commissioned
about, invisible to the binding being designed, and it was found only by testing
the prompt's own stated assumption about county stability rather than accepting it.

---

## O — Open items for the audit

1. **FFIEC's operational adoption notice was not read** (HTTP 403 from
   `ffiec.gov` and `geomap.ffiec.gov` to every automated request this session).
   The binding does not depend on it, but a human with a browser should confirm
   it and either add it to §M1.1 or record that it says nothing new.
2. **The reference-distribution contamination in `lending_desert_score` is argued
   from mechanism, not sized.** The Baltimore measurement could not size it
   (§M6.1). A county with a large non-colliding tract population would settle how
   far the corruption spreads beyond colliding rows.
3. **Whether this document belongs in `docs/` or in `hmdaanalyzer/methodology/`**
   — the repo's own precedent and the packaging consequence both point the other
   way from the instruction that was followed (§ correction 7).
4. **Whether any override should exist at all.** §M3.3 says no for v1 and states
   the minimum bar if the audit disagrees.
5. **Drift between four independent guards** is the accepted cost of §M2.4. Worth
   an adversarial look at whether it can be made structurally hard to forget the
   fifth one without moving the check back to load time.

---

## V — Verification log

All commands run 2026-08-03 from a clean checkout of `main` at `bace2f2`, Python
3.14, pandas 3.0.5, in a scratch virtualenv outside the repo. No repository code
was modified.

| # | What | Source / command | Established |
|---|---|---|---|
| 1 | Reg C commentary | `consumerfinance.gov/rules-policy/regulations/1003/4/` — Comment 4(a)(9)(ii)(C)-1 | The rule: boundaries in effect Jan 1 of the LAR year |
| 2 | 2022 FIG | `ffiec.cfpb.gov/documentation/fig/2022/overview` | The FIG does **not** state the vintage |
| 3 | CFPB 2021 summary (pub. 2022-06-16) | consumerfinance.gov | 2021 = 2011–2015 ACS delineations |
| 4 | CFPB 2022 summary (pub. 2023-06-29) | consumerfinance.gov | 2022 = 2020 Census delineations; MSA + tract boundary changes limit comparison |
| 5 | Tract-ID Jaccard, 4 counties × 2018–2024, full files | CFPB Data Browser CSV | Boundary at 2021→2022 only; magnitude 0.635–0.985 |
| 6 | Census 2020↔2010 tract relationship files (pub. 2022-01-25) | `www2.census.gov/geo/docs/maps-data/data/rel2020/tract/` | Re-carved GEOID counts; 18.1–45.1% of LAR rows affected |
| 7 | Shipped-API reproduction | `load_range(2021,2022,county="24510",limit=200_000)` + `lending_by_tract` + `lending_desert_score` + `lender_summary` | 196 colliding GEOIDs; no raise, no warning, no vintage column |
| 8 | CT `county_code` 2018–2024 | CFPB Data Browser CSV | Complete change at 2023→2024, jaccard 0.056 |
| 9 | CT `census_tract` 2018–2024 | CFPB Data Browser CSV | Jaccard 0.000 at 2023→2024; 0.822 at 2021→2022 |
| 10 | CT tract-suffix multiset 2023 vs 2024 | CFPB Data Browser CSV | Pure renumbering: identical 872 suffixes, zero GEOID overlap |
| 11 | CT `derived_msa_md` 2021–2024 | CFPB Data Browser CSV | `49340` → `47930` at 2023→2024, jaccard 0.714 |
| 12 | MA `census_tract` 2021–2024 | CFPB Data Browser CSV | 2021→2022 jaccard 0.747 — fifth jurisdiction confirming |
| 13 | pandas column-durability behaviours | pandas 3.0.5 | Categorical→str on disjoint concat; silent NaN on missing column; `.agg()` drops the column |
| 14 | Source inventory | `grep -rn -E "groupby|\.merge|set_index|nunique|census_tract" hmdaanalyzer/` | Four exposed tract-key sites |

**Next step: hostile audit in a fresh session. No code until then.**
