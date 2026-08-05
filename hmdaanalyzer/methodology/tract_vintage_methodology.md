# Census-tract vintage in multi-year HMDA frames — methodology

> **Status: v2, POST-AUDIT, PRE-BUILD.** Methodology-first artifact. No code
> exists for this feature and none should be written until this document has had
> a scoped re-audit of the sections changed in this revision.
>
> **v1 was hostile-audited and the verdict was *revise, then build*.** The core
> design survives: the audit independently reproduced the geometry to the tract on
> three counties, re-derived the site inventory by AST sweep, and confirmed the
> binding, the no-crosswalk argument, the raise-over-warn argument and the
> unknown-year raise. This revision changes what gets built in three places
> (§M1.2a, §M2.1, §M2.4) and repairs evidence in several more.
>
> **What changed in v2, in one list:** the Connecticut "loud failure" claim is
> struck as false and the design gains a measured key-disjointness limb alongside
> the declarative map (§M1.2a, §M6.5); county and MSA basis maps join the tract
> one and two county guard sites are added (§M1.2, §M2.1, §M2.3, §M6.6); the
> "materially different ground" phrasing is retired and the recarve rule gains an
> `AREALAND_PART > 0` filter (§M3.1); the pandas evidence is re-run across three
> versions and two of three v1 results are replaced (§M4.1); §M1.1's "prospective"
> claim is struck as contradicting §M1.3 (§M1.1); the narrowing parameter's three
> undefined cases are decided (§M3.3a); the guard becomes one helper with a test
> that enforces the site list (§M2.4) and the report layer's swallowing is
> addressed (§M3.2a); the document moves in-package so it ships (correction 7);
> and the coverage section is rewritten around the pattern that produced its own
> holes.
>
> **This document also revises the recon design it was commissioned to justify.**
> Three of the recon's four proposals survive in altered form; one — "raise on a
> vintage-spanning frame" — is rejected and replaced (§M2, §M3). The recon's
> *detection method* is also rejected, though more narrowly than v1 stated: it is
> anti-correlated with key *reuse*, and valid for key *replacement* (§M6.3,
> §M6.4).
>
> Every empirical claim carries the command that produced it. v1's claims were run
> 2026-08-03 and are in §V; v2's were run 2026-08-04 and are in §V-2 onward. Where
> a v1 claim did not reproduce, the v1 row is struck rather than deleted.

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

**What v2 adds to 0.6.0's payload**, since this revision expands it: a county
basis map and an MSA basis map alongside the tract one; guards at
`lending_by_county` and `lender_summary`'s `unique_counties`; a measured
key-disjointness check; a single shared guard helper; an AST-based test that
enforces the site list; a fix to the report layer's exception allowlist; a
`README` sentence change; and this document's relocation into the package with a
packaging gate. None of that is implemented here — this remains a decision record,
not a specification.

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

Retrieved again 2026-08-04 and confirmed verbatim:

```
$ curl -s "https://www.consumerfinance.gov/rules-policy/regulations/1003/4/" \
    | python3 -c "import sys,re,html; t=re.sub(r'<script.*?</script>','',sys.stdin.read(),flags=re.S); \
      t=html.unescape(re.sub(r'<[^>]+>',' ',t)); t=re.sub(r'\s+',' ',t); \
      j=t.find('in effect on January 1'); print(t[j-330:j+120])"

  Official interpretation of Paragraph 4(a)(9)(ii)(C) 1. General. Census tract
  numbers are defined by the U.S. Census Bureau. A financial institution complies
  with § 1003.4(a)(9)(ii)(C) if it uses the boundaries and codes in effect on
  January 1 of the calendar year covered by the loan/application register that it
  is reporting.
```

**What this comment does and does not settle.** It is a **safe harbor** — note
the form, "complies … *if* it uses". It fixes **when** the codes are read: as of
1 January of the LAR year. It says nothing about **which delineation will be in
effect** on that date, because that is decided elsewhere, by the Census Bureau's
publication schedule and by FFIEC's adoption of it.

So the comment is a rule rather than a table, which is why it is cited, but **it
is not prospective in the sense that matters here.** Knowing the reading date for
2033 does not tell you what will be readable on it. §M1.3 develops this and is the
controlling statement; an earlier draft of this section claimed the comment
"determines the answer for 2027 and 2033 as much as for 2022", which contradicted
§M1.3 two pages later. That sentence is struck. **The comment is not the
load-bearing citation for any individual year** — the year-by-year CFPB *Summary*
publications carry that load, and §M1.3's raise exists precisely because the
comment cannot.

What the comment *does* explain is the shape of the lag: the 2020 Census was taken
in 2020, but its tract delineations were not "in effect" on 1 January 2020 or
1 January 2021. They were first in effect on 1 January 2022.

**The year-by-year fact is separately citable**, from CFPB's own annual data
publications. Both ends of the boundary, read 2026-08-03:

These, not the comment, are what an individual year's entry cites.

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

**Decision: three closed mappings from data year to a geography-key basis year —
one for the tract key, one for the county key, one for the MSA key.**

The tract map was the original design. §M2.3 and §M6.6 measure the other two keys
moving on their own schedules, and §M5.2 option 2 sends users *to* those keys as
the escape route, so shipping a guard on only the tract key would harden the exit
door and leave the corridor open. All three have the same shape:

```
TRACT_GEOID_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022..2025 -> 2020}
COUNTY_CODE_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022, 2023 -> 2020,
                              2024, 2025 -> 2023}     # see §M2.3, §M6.7
MSA_CODE_BASIS_BY_YEAR     : {2018 -> ..., ..., 2024, 2025 -> 2023}
```

The basis-year *values* differ between the three maps because the three keys are
redrawn by different authorities on different schedules — Census decennial
delineation for tracts, Census county-equivalent changes for counties, OMB
delineation bulletins for MSAs. **Do not collapse them into one map.** A single
"geography basis year" would be wrong for at least one key at every boundary
measured in §M6.

- **Values are plain `int` basis years** — not an enum, not a string, not a
  boolean.
- **The domain is closed.** Years present are answered; years absent raise
  (§M1.3), in all three maps independently.
- **Each entry carries its citation in a comment**, per §M1.3.
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

### M1.2a Key on the GEOID *scheme*, not the delineation *basis*

The maps above are indexed by data year and return a **basis year**. That is the
right thing to *declare* and the wrong thing to *compare*, and Connecticut is why.

Two years can share a delineation basis and still have non-comparable keys. CT
2023 and CT 2024 are both 2020-Census tracts — same basis — while sharing **zero**
GEOIDs, because the county prefix was renumbered underneath them (§M6.5, §M6.7).
A basis-year comparison reports "same vintage" and lets the analysis through. The
quantity that actually governs comparability is the **GEOID scheme**: the
(delineation basis, code assignment) pair that determines whether the same string
denotes the same ground.

**Scheme strictly dominates basis.** It catches everything basis catches — the
2021→2022 decennial change is a scheme change — and it also catches Connecticut,
which basis does not. There is no case where basis is right and scheme is wrong.

**But scheme is not a scalar per year.** In 2024 the tract scheme differs from
2023 *only inside Connecticut*; everywhere else the keys are unchanged. A national
`year -> scheme` map cannot express "different in CT, same in the other 49
states" without becoming a `year × state -> scheme` table — which is a crosswalk
by another name, needs a citation per cell, and would have to be re-derived every
time any state restructures.

**Decision: a hybrid. Declare the basis; measure the disjointness.**

| | what it detects | why the other cannot |
|---|---|---|
| **Declarative** year→basis maps (§M1.2) | **key REUSE** — the same string meaning different ground | Reuse is invisible to measurement *by construction*: the keys match, so no comparison of key sets can see it (§M6.4) |
| **Measured** key-disjointness check | **key REPLACEMENT** — the ground surviving under a new string | Replacement is invisible to the map: the basis year is unchanged, so the map reports "safe" (§M6.5) |

The two failure modes are complements, and each instrument is blind to exactly
the one the other catches. Shipping only the map lets Connecticut through;
shipping only the measurement lets Baltimore city through (§M6.4: Jaccard 0.985,
18% of rows on re-carved keys). Ship both.

**The measured limb, stated concretely.** For each pair of years in the frame,
compare the sets of geography keys present. If the intersection is empty — or
below a threshold that must be argued, not guessed — the keys have been replaced
and the aggregation refuses, *regardless of what the basis map says*. On CT
2023+2024 this is unambiguous:

```
$ .venv/bin/python r1_ct.py     # scratchpad, 2026-08-04
  |2023 keys|=872  |2024 keys|=872  intersection=0  jaccard=0.000
```

Zero intersection over 872 keys on each side is not a threshold judgement; it is a
disjoint partition. **Scope the check to the empty-intersection case in v1** and
leave any softer threshold to a later release with its own evidence, because
§M6.4 is a standing proof that intermediate Jaccard values do not mean what
intuition says they mean.

Two measured hazards that constrain how this check may be built, both found while
verifying §M2.3 (§M6.7):

- **Single-state pulls carry out-of-state keys.** A `states=VA` fetch for 2018
  contains 233 distinct `county_code` values; for 2019, 145. The difference is
  almost entirely out-of-state codes appearing and disappearing, not Virginia
  changing. A disjointness check run on a raw key set will read that as
  instability.
- **Sparse keys drop out of a year entirely.** Alaska's `county_code` set scores
  Jaccard 0.732 at 2018→2019 and 0.806 at 2019→2020 — years with **no boundary
  change at all** — purely because low-volume boroughs had zero rows in one year.

Both push the same way: the check must be **presence-robust**, and the
empty-intersection scope above is what makes it so. Neither hazard can produce a
zero intersection; both can produce a middling Jaccard. This is a second,
independent reason not to threshold on Jaccard.

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

**That cost is not prospective. It is already due.** The v1 draft of this document
was written against 2018–2024 and treated the unmapped-year raise as a future
event. It is not — **the 2025 data year is already served**, measured
2026-08-04:

```
$ curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" \
    "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?years=2025&states=AK&actions_taken=1,2,3,4,5"
  301 -> https://files.ffiec.cfpb.gov/data-browser/datasets/2025/filtered-queries/snapshot/50bf...csv

$ .venv/bin/python -c "…"   # full-state pulls through the scratch fetcher
  AK 2025:  19,621 rows | activity_year=['2025'] | 168 tracts | 30 counties
  CT 2025: 123,752 rows | activity_year=['2025'] | 872 tracts |  9 counties
          county prefixes: ['09110' … '09190']       (planning regions, as 2024)
  AK 2024->2025 tract jaccard = 0.977   CT 2024->2025 tract jaccard = 0.998
```

(2026 returns HTTP 400 — not yet served.)

So a map shipped with 2024 as its last entry raises on the **current** data year
on release day, for every tract-keyed operation. **The three maps must each carry
a 2025 entry at ship time.** The measurements above are consistent with 2025
continuing on the same schemes as 2024 — tract keys are near-identical and CT is
still on planning regions — but consistency is not a citation, and §M1.3's whole
rule is that an entry is a deliberate human act with a citation attached. Locating
the CFPB *Summary of 2025 Data* statement is therefore a **release blocker**, not a
nicety, and it is recorded as such in §O.

This is worth naming as a pattern, because the document walked into it: a rule
whose cost is described in the future tense should be checked against the present
before it ships. The unknown-year raise was argued entirely in terms of 2026 and
2032. Nobody asked what the API was serving that afternoon.

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
survive Connecticut — which is why §M1.2a pairs the declarative map with a
measured disjointness check rather than choosing between them.

---

## M2 — What is actually incoherent, and what is not

"The vintages differ" is not a defect. Joining across them on a key that means
different things is. Over-refusing is its own defect — a rule that fires on
analyses that were always correct trains users to reach for the override, and then
the override is load-bearing in exactly the cases it should not be.

### M2.1 Incoherent

**Any aggregation whose grouping key is a geography key, on rows spanning more
than one basis for *that* key.** The v1 draft said "includes `census_tract`" and
called that "the whole of it". It is not: §M2.3 measures the county key moving at
2021→2022 and the MSA key moving at 2023→2024, and §M5.2 option 2 actively directs
users onto both. Six sites, re-derived by AST sweep in §M6.2 rather than by
reading:

| Site | Operation | Key | Guarded by |
|---|---|---|---|
| `geographic.py:25` `lending_by_tract` | `groupby("census_tract")` | tract | tract map + disjointness |
| `geographic.py:74` `lending_desert_score` | inherits, then `rank(pct=True)` | tract | tract map + disjointness |
| `geographic.py:108` `racial_composition_by_tract` | `groupby(["census_tract","derived_race"])` | tract | tract map + disjointness |
| `lender.py:52` `lender_summary["unique_tracts"]` | `nunique()` | tract | tract map + disjointness |
| **`geographic.py:51` `lending_by_county`** | `groupby("county_code")` | **county** | **county map + disjointness** |
| **`lender.py:53` `lender_summary["unique_counties"]`** | `nunique()` | **county** | **county map + disjointness** |

`lending_desert_score` is the worst of them: its percentile rank is computed *over
the collapsed tract set*, so the reference distribution every tract is scored
against is corrupted, not only the colliding rows — sized in §M6.1.

**`derived_msa_md` gets no guard site, because it has none to guard.** The sweep
finds zero aggregations on it; it occurs exactly once in the package, in the
schema frozenset. §M2.3 and §M6.6 say what protects the user anyway.

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
attributes move on their own schedule (§"does not protect against", item 5). Do
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

**And the county key moves at the 2021→2022 tract boundary itself — in Alaska.**
The v1 draft replaced the prompt's false premise ("county FIPS is largely
stable") with a narrower claim that is also false: that county codes are safe
*at* 2021→2022 and move only for Connecticut at 2023→2024. Measured on full-state
files (§M6.7):

```
$ .venv/bin/python r2_alaska.py          # scratchpad, 2026-08-04
=== codes added / removed at 2021->2022 ===
  only in 2021: ['02261']
  only in 2022: ['02063', '02066']
  jaccard     : 0.903

=== rows at the 2021->2022 boundary ===
  2021 02261: 323 rows        (Valdez-Cordova Census Area)
  2022 02063: 158 rows        (Chugach Census Area)
  2022 02066:  40 rows        (Copper River Census Area)
```

Alaska's `02261` is retired and split into `02063` + `02066`, live in the LAR, at
**exactly** the boundary the v1 draft declared county-safe. So the honest
statement is narrower again:

> **No geography key is safe across a year boundary merely because it is coarser
> than the tract key.** The tract key moves at 2021→2022. The county key also
> moves at 2021→2022 (Alaska) and again at 2023→2024 (Connecticut). The MSA key
> moves at 2023→2024. Aggregating *up* is not an escape route; it is a different
> unguarded key. §M5.2 option 2 is rewritten accordingly.

**Scope, stated exactly, because it is easy to overclaim in both directions:**

- The **county** limb fails at **2021→2022** (Alaska, measured above) and at
  **2023→2024** (Connecticut, jaccard 0.056).
- The **MSA** limb **holds** at 2021→2022 and at 2020→2021, and fails at
  **2023→2024**. See §M6.6 — and note that this corrects the audit prompt, which
  placed the MSA failure at 2020→2021. Measured across four states, 2020→2021 has
  MSA code-set Jaccard 1.000 *and* zero material county reassignments.
- **`state_code`** is not measured to move anywhere in 2018–2025.

And the structural point, which matters more than any individual exception —
**restated, because the v1 draft got its second half wrong:**

**Key reuse is the dangerous mode. Key replacement is the *less* dangerous one —
not the safe one.** Where keys are replaced, rows fall into disjoint buckets and
the row count visibly inflates. Where keys persist, rows silently merge. That much
holds. But the v1 draft went on to treat replacement as harmless, and §M6.5 now
measures that to be false: CT 2023+2024 pooled produces 1,742 rows where 871 are
expected — visibly wrong — *and* silently corrupts the percentile of 845 of 871
tracts, flipping 25 desert verdicts, because `lending_desert_score` ranks against
a reference distribution that doubled. **Replacement is loud in the row count and
silent in every derived statistic.** That distinction drives §M3, and it is the
reason §M1.2a keeps a measured limb rather than relying on replacement being
self-announcing.

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
- **The blast radius is small enough to guard precisely.** Six functions (§M6.2).
  Guarding six call sites is cheaper and far more accurate than guarding every
  frame that might one day reach one of them.
- **The operation is where the meaning is.** Only at `groupby("census_tract")` is
  it knowable that the key is about to be treated as an identity.

**Cost, and how it is paid.** Six guards can drift apart; one load-time guard
cannot. The v1 draft deferred this to the build prompt. **That deferral is
withdrawn**, and the reason is portfolio evidence rather than taste: this
portfolio has just spent three consecutive passes reconciling five drifted copies
of one CI gate, and the sdist defect underneath those copies was independently
rediscovered five times and propagated zero times. A cost that has been paid five
times is not a hypothetical.

**Decision: one helper, called from N places. Not N copies of a check.**

The six sites differ only in which key they aggregate on and which basis map
governs it. Everything else — reading `activity_year`, looking up the basis,
running the disjointness check, formatting the message (§M3.1) — is identical.
That is one function taking the key column and its map, and six one-line calls.
A future seventh site is then a call, not a re-implementation, and cannot drift
because there is nothing to drift *from*.

**Decision: a test enumerates the sites, so adding an unguarded one fails CI.**

One helper stops the *copies* from diverging. It does nothing about a new site
that never calls the helper at all — and nothing currently fails when one is
added. There is no test, no lint rule, and no CI step that enumerates
geography-keyed operations. §M6.2's inventory is a snapshot in a document; the
document does not run.

The sweep in §M6.2 is the test. It is roughly sixty lines and it needs no
fixtures:

1. Walk `hmdaanalyzer/**/*.py` with `ast`.
2. Collect every `ast.Call` whose `func.attr` is an identity-forming verb —
   `groupby`, `nunique`, `unique`, `value_counts`, `drop_duplicates`,
   `duplicated`, `set_index`, `merge`, `join`, `pivot`, `pivot_table`,
   `crosstab`, `reindex`, `isin`, `map`.
3. Take the string constants in the call's arguments **and in the subscript it is
   called on** — `df["census_tract"].nunique()` carries its key in the latter,
   which is why the v1 draft's grep-based verb list missed `lender.py:52`.
4. Intersect with the geography column names; attribute each hit to its
   enclosing `FunctionDef`.
5. Take the transitive closure over the call graph, so `lending_desert_score`
   inherits exposure from `lending_by_tract`.
6. **Assert the resulting set equals a literal expected set in the test file.**

The assertion must be **set equality, not a subset or a count**. A count passes
when one site is added and another deleted; a subset check passes when a site is
added. Equality forces a deliberate edit to the expected set, which is the moment
the author is asked whether the new site is guarded. Failure message: name the
unexpected function, its file and line, and point at this section.

This test is what makes the §M2.4 trade-off honest. Guarding at the operation
rather than at load accepts the risk of a forgotten site; a test that enumerates
the sites converts that risk from *silent* to *loud*, which is the same move the
whole document is making about the data.

---

## M3 — Raise, or annotate?

### M3.1 Raise, at the six aggregation sites

**Decision: raise.** A new exception, subclassing `ValueError` to match the
existing `MissingColumnError` precedent in `hmdaanalyzer/exceptions.py` so that
`except ValueError` callers keep working.

**The message must carry the measurement, not just the verdict.** A message that
says "frame spans multiple tract vintages" tells a user they are blocked without
telling them whether it matters. It must name:

1. the function that refused;
2. the delineation bases present and the years mapping to each;
3. **how many GEOIDs are shared between the years, and what share of rows land on
   them** — see below, which is where the v1 draft overclaimed;
4. the concrete next actions, in order of preference (§M5.2).

Item 3 is the difference between an error a user routes around and an error a user
learns from. It is also the item most easily turned into a lie.

**The collision count is a fact. "Materially different ground" is a modelling
claim, and the v1 draft made it without earning it.**

The v1 draft described the §M6.4 figure as "the materiality number" and said the
GEOIDs it counts denote "materially different ground". The underlying test — a
2020 GEOID is RECARVED if it maps to ≥2 relationship rows, or is 1:1 with a
land-area change ≥1% — has one genuine virtue and two real defects.

*The virtue, confirmed:* **it never under-flags.** Against an independent,
stricter overlap test (RECARVED iff less than 99% of the 2020 tract's land came
from the same-numbered 2010 tract), there is not one GEOID the strict test flags
and the shipped test misses, across five counties:

```
$ .venv/bin/python r3_recarve.py         # scratchpad, 2026-08-04
county                   A-calls  >=99% same  slivers B-calls  A misses B
--------------------------------------------------------------------------
Baltimore city, MD            36          21        1      15           0
Cook County, IL              223         163        5      60           0
Fayette County, PA            36          30        0       6           0
Cuyahoga County, OH          172         100        1      72           0
Bernalillo County, NM        114          45        0      69           0
--------------------------------------------------------------------------
TOTAL                        581         359        7                   0

share of Rule-A RECARVED calls that are >=99% the same ground: 61.8%
Rule A never under-flags relative to Rule B: True
```

*Defect one: most of what it flags is not materially different ground.* Nationally:

```
$ .venv/bin/python r3_natl.py            # scratchpad, 2026-08-04
relationship rows: 126,450 | distinct 2020 GEOIDs: 85,528
rows with AREALAND_PART == 0: 3,999

Rule-A RECARVED calls (national)          : 46,204
  ... of which >=99% the SAME ground      : 19,440 (42.1%)
  ... resting on ZERO-land-area slivers   : 1,787
      (of those, >=99% same ground        : 1,358)
Rule-A calls if AREALAND_PART>0 is filtered: 44,417

distribution of 'share of 2020 land from the same-numbered 2010 tract'
among Rule-A RECARVED calls:
  [0.000, 0.500) : 22,804  (49.4%)
  [0.500, 0.900) :    404  ( 0.9%)
  [0.900, 0.990) :  3,556  ( 7.7%)
  [0.990, 0.999) :  6,911  (15.0%)
  [0.999, 1.010) : 12,529  (27.1%)
```

The distribution is bimodal: **49.4% of flagged GEOIDs kept less than half their
ground** — unambiguously different places — while **27.1% kept 99.9% or more**,
which no examiner would call a different place. The single word "materially" is
carrying both.

*Defect two: 1,787 flags rest on zero-land-area slivers.* The "≥2 parts" limb
counts relationship **rows**, and 3,999 of the national file's rows have
`AREALAND_PART == 0` — a boundary that touches without enclosing any land. Those
rows make a 1:1 tract look like a multi-part one.

Row-weighted, the two tests are far apart:

```
LAR row share on a RECARVED key — Rule A (shipped) vs Rule B (<99% same ground)
Baltimore city, MD        2021: A= 18.2% B=  8.0%   2022: A= 18.2% B=  8.2%
Cook County, IL           2021: A= 15.6% B=  1.2%   2022: A= 19.8% B=  5.5%
Fayette County, PA        2021: A= 99.9% B= 16.0%   2022: A= 99.9% B= 16.4%
Cuyahoga County, OH       2021: A= 27.4% B=  5.2%   2022: A= 36.1% B= 13.1%
Bernalillo County, NM     2021: A= 43.7% B= 13.2%   2022: A= 68.6% B= 38.2%
```

Fayette County PA is the case that should end the argument: **99.9% of its rows
sit on a "RECARVED" key**, which reads as "this county is entirely
unanalysable", and 16.0% sit on a key that changed by more than 1% of its ground.

**Decisions.**

1. **Filter `AREALAND_PART > 0` in the ≥2-parts limb.** A zero-land-area part is
   not a part. This is not a threshold choice; it is excluding rows that describe
   no ground. Nationally it removes 1,787 of 46,204 calls. The slivers are not
   kept, and the v1 rule statement in §M6.4 is amended.
2. **Drop the word "materially" from the error message.** It is unearned at the
   1% threshold and the document has no defended threshold to replace it with.
   §M5.1 rejects a crosswalk precisely because proportional allocation is "a
   modelling choice masquerading as a data-cleaning step"; calling a 1%-area
   change "materially different ground" is the same move, made by this document
   about its own number.
3. **The message states the count and names its limits**, in this shape:

   > `lending_by_tract` refused: this frame spans tract delineation bases 2010
   > (2021) and 2020 (2022).
   > 196 of 199 GEOIDs appear in both years and would be merged; they carry
   > 18.2% (2021) and 18.1% (2022) of rows.
   > Sharing a GEOID across the boundary does not by itself mean the ground
   > changed — nationally about 42% of such GEOIDs are ≥99% unchanged — but it
   > does mean the two years cannot be summed without deciding which. See §M5.2
   > for the four options.

   The count is stated because it is a fact and the user needs it. The
   interpretation is stated as a range, not a verdict, because that is what the
   measurement supports.

**Why not just adopt the stricter test as the shipped rule?** Because it is also a
modelling choice — 99% is as arbitrary as 1% — and because the *refusal* does not
depend on either. The frame is refused for spanning two bases, which is a
declarative fact from §M1.2. The overlap figure is context in the message, not the
trigger. Keeping it out of the trigger is what lets the document report it
honestly instead of having to defend it as a threshold.

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

### M3.2a The raise/report boundary — where "a raise cannot be ignored" stops being true

§M3.1's entire case for raising over warning is that a raise cannot be ignored.
`report/generator.py` is where that stops being true, and it must be decided here
rather than discovered during the build.

The module wraps its analysis calls in `try` blocks whose re-raise allowlist is
`MissingColumnError` only:

```
$ grep -n "except" hmdaanalyzer/report/generator.py
95:    except MissingColumnError:
97:    except Exception as e:          -> lines.append(f"| Error computing denial rates: {e} |")
133:   except MissingColumnError:
135:   except Exception as e:          -> lines.append(f"| Error: {e} |")
155:   except MissingColumnError:
157:   except Exception as e:          -> lines.append(f"| Error: {e} |")
180:   except MissingColumnError:
182:   except Exception:               -> pass
192:   except Exception:               -> return denial_rate_by_race(df)
```

A new exception subclassing `ValueError` is not `MissingColumnError`, so it is
caught by the `except Exception` arm and **rendered into a markdown table cell**.
The result is a report that looks complete with the refusal typeset into it —
strictly worse than the warning §M3.2 rejects, because a table cell reading
"Error: frame spans…" looks like a rendering glitch rather than a refusal, and the
surrounding sections still carry numbers.

**Two corrections to how this was described to the audit, both material:**

- **The threat is latent, not live.** `generator.py` imports
  `lending_desert_score`, `lender_summary`, `lending_by_county`,
  `lending_by_state` and `lender_vs_market`, but **calls none of them** — all five
  are dead imports, confirmed by AST (`ast.Name` load-context lookup finds zero
  references). The four guarded `try` blocks wrap only `denial_rate_by_race`,
  `disparity_ratio` (twice) and `denial_rate_by_income_band`, none of which is a
  geography-keyed site. So nothing swallows the new exception **today**. It
  becomes live the first time anyone adds the tract section those imports were
  obviously staged for.
- **There are five swallowing sites, not four, and the fifth is worse.**
  `summary_table` (line 188-193) is `try: return disparity_ratio(df) except
  Exception: return denial_rate_by_race(df)` — no `MissingColumnError` re-raise at
  all. It swallows *everything*, including the exception the rest of the module
  is careful to re-raise, and silently substitutes a different analysis.

**Decision: the allowlist is the wrong mechanism; invert it.**

Enumerating exceptions to re-raise means every new exception type is swallowed by
default, and this document is about to add one. The report layer should catch the
**narrow, expected** failures it can actually render — and let everything else
propagate. Concretely, for 0.6.0:

1. Add the new exception to the re-raise allowlist at all four sites **and** give
   `summary_table` an allowlist it currently lacks. This is the minimum and it is
   not sufficient, because it repeats the pattern that created the problem.
2. **Preferred:** replace `except Exception` with the specific exceptions each
   block can meaningfully render, so an unanticipated type propagates by default.
   A report that fails to generate is a correct outcome; a report that renders a
   refusal as a table cell is not.
3. Either way, **a test asserts that a geography-vintage refusal propagates out of
   `generate_disparity_report` and `summary_table`** rather than appearing in the
   returned string. Without it this regresses the moment someone adds the tract
   section.

This is a design question, not an implementation detail, because it decides
whether §M3.1's central claim survives contact with the one shipped caller that
would otherwise falsify it.

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

**`vintage=` sits on the aggregation functions, not on `load_range`.** The load
contract stays exactly as §M2.4 requires and the user keeps every year they asked
for; the narrowing happens at the point of aggregation, where the meaning is.

#### M3.3a The three cases the v1 draft left undefined

Measured against the shipped functions on Baltimore city 2022 (§M6.8):

```
$ .venv/bin/python r6_narrowing.py       # scratchpad, 2026-08-04
=== CASE 1: narrowing yields ZERO rows ===
  lending_by_tract            -> 0 rows, no raise
  lending_desert_score        -> 0 rows, 0 deserts, no raise
  racial_composition_by_tract -> 0 rows, no raise
  lender_summary              -> {}
  warnings emitted            : 0
```

**The empty case collides head-on with this package's own stated philosophy.**
`exceptions.py` holds that "an empty result can never silently read as 'no
disparity' in a fair-lending context", and `lender_summary`'s `{}` is *documented*
as meaning a legitimate empty result. A narrowing that selects a year not present
in the frame — `vintage=2010` on a 2022-only frame — currently produces exactly
the artefact the package says must never exist: zero deserts, no warning,
indistinguishable from a clean bill of health.

**Decision: an empty narrowing raises.** It is a caller error, not a finding.
`vintage=` names a basis the caller believes is in the frame; if it is not, the
question was malformed and the answer is not "nothing here". The message states
which bases *are* present. This is distinct from a legitimately empty input frame,
which keeps its current behaviour — the distinguishing fact is that the narrowing
removed the rows, and the function knows it did.

```
=== CASE 2: narrowing yields ONE tract (24510240100, 332 rows) ===
census_tract  applications  denial_rate  app_percentile  desert_score  is_lending_desert
 24510240100           248      0.100806           100.0           4.0              False
```

**The single-tract case is worse, and the floor is higher than it looks.**
`rank(pct=True)` over *n* rows has minimum `1/n`, so `app_percentile` has minimum
`100/n`. `is_lending_desert` requires `app_percentile < 25`. The flag is therefore
**mathematically unreachable for n ≤ 4**, not merely for n = 1:

```
=== how many tracts before a desert CAN be flagged? ===
  n_tracts= 1: min app_percentile= 100.0  (<25 reachable: False)  deserts=0
  n_tracts= 2: min app_percentile=  50.0  (<25 reachable: False)  deserts=0
  n_tracts= 3: min app_percentile=  33.3  (<25 reachable: False)  deserts=0
  n_tracts= 4: min app_percentile=  25.0  (<25 reachable: False)  deserts=0
  n_tracts= 5: min app_percentile=  20.0  (<25 reachable: True)   deserts=1
```

**Decision: the floor is five tracts, and below it `lending_desert_score`
raises.** Not one — five, derived from the threshold rather than from intuition.
A narrowed frame with four or fewer tracts cannot flag a desert *whatever the
data says*, so returning `is_lending_desert=False` is a fabricated negative, which
is the precise failure `exceptions.py` exists to prevent. The message must say the
flag is unreachable at this tract count rather than implying the tracts were
examined and cleared.

Two things this floor is not. It is **not** a small-N suppression rule — that is
out of scope and unrelated — and it is **not** a claim that five tracts is
statistically adequate. It is the point below which the output is *arithmetically
incapable* of a positive, which is a different and much lower bar. Whether the
`lending_desert_score` formula is sound at any n remains out of scope
(coverage item 14).

**The dropped years need a named channel.** The v1 draft required "the dropped
years' row count reported" without naming how. A `print` or a `warnings.warn` dies
exactly as §M3.2 argues warnings die — invisible on notebook re-run, absent from
the artefact. **Decision: the channel is the returned object**, the same standard
§M3.3 sets for the override it rejects:

- For frame-returning functions: the selected basis year as a **column value on
  every row**, plus the dropped-year row counts as an added column or a companion
  frame — never a side effect.
- For `lender_summary`, which returns a `dict` (§M4.5): explicit keys, e.g.
  `basis_year` and `dropped_rows_by_year`. A dict can carry provenance even though
  it cannot carry a column.

**Carry-forward: the document's own two findings collide with its own
requirement.** §M3.3 requires the selected basis year present on the returned
frame. §M4.1 measures `.agg()` dropping the column, and `lending_by_tract` **is**
an `.agg()`. §M4.5 notes `lender_summary` returns a dict. The v1 draft never
connected them. Measured:

```
=== M3.3 carry-forward requirement vs M4.1 finding ===
  input carried tract_geoid_vintage : True
  lending_by_tract output carries it: False   <-- .agg() dropped it
  lender_summary output type        : dict    (no column can ride on a dict)
```

So the requirement is not satisfiable by passing the column through; it must be
**re-attached after aggregation, explicitly, at each site**. That is one more
reason the guard is one helper called from N places (§M2.4): re-attachment is part
of the same helper's job, and six hand-written re-attachments would drift the same
way six hand-written checks would. This does not contradict §M4.1 — the column is
still provenance, never mechanism; the basis is still derived from
`activity_year`. It only means the provenance must be written onto the output
deliberately, because nothing carries it there by itself.

**If the audit concludes a true override is nonetheless required**, the minimum
bar is that the acknowledgement travels with the data, not with the call: the
returned object carries the cross-vintage fact as a value in a column, and any
frame derived from it carries it forward. A flag that exists only in the calling
code fails this bar. A flag that sets `DataFrame.attrs` also fails it — but **not
for the reason the v1 draft gave.** It claimed the marker "evaporates on the first
`.copy()` or `.merge()`". Measured, `.copy()` preserves `attrs`. What drops it is
`.merge()` and `.agg()` — and `.agg()` is the operation at the heart of
`lending_by_tract`, which the v1 draft did not name. Identical on pandas 1.4.4,
2.2.3 and 3.0.5 (§V-2):

```
5) attrs survives .copy()   : True
   attrs survives pd.concat: True
   attrs survives .merge()  : False
   attrs survives .agg()    : False
   attrs survives slicing   : True
```

**The conclusion stands and is in fact stronger:** `attrs` is not a reliable
carrier. It survives the three operations that do not matter here and is dropped
by the two that do — including, precisely, the aggregation this whole design is
guarding. **This document's position is that no override should ship in v1.** Ship
the narrowing, and let the audit or a real user demand more.

### M3.4 What a user with a legitimate need does

Someone who genuinely wants a 2019–2023 tract-level trend is not doing anything
illegitimate. §M5.2 is the answer to that person, and the error message must point
at it.

---

## M4 — The `tract_vintage` column as a contract

### M4.1 The column cannot be the mechanism

The recon proposed emitting the vintage as a first-class column and treating it as
the contract. **A column cannot carry a guarantee**, and the reasons are stable
across the whole supported pandas range.

**The v1 draft's evidence was wrong and is replaced.** It reported one measurement
against pandas 3.0.5 alone, and `pandas` is not pinned — `pyproject.toml` says
`pandas>=1.4.0`. Re-run on **1.4.4, 2.2.3 and 3.0.5**, results identical on all
three except where noted (§V-2):

```
$ for v in 1.4.4 2.2.3 3.0.5; do .venv-pd$v/bin/python r4_pandas.py; done

pandas 1.4.4 | numpy 1.26.4        (also 2.2.3/numpy 2.4.6 and 3.0.5/numpy 2.5.1)
==============================================================
1) concat of two disjoint Categoricals -> dtype: int64
   values: [2010, 2020]
1b) same with STRING categories        -> dtype: object     [1.4.4, 2.2.3]
1b) same with STRING categories        -> dtype: str        [3.0.5]
2) concat with a frame missing the column -> nulls: 1
   dtype BEFORE concat: int64  AFTER: float64   <-- unreported flip
3) agg() output keeps tract_geoid_vintage? False   cols=['census_tract', 'applications']
4) plain int round-trip to_csv/read_csv: int64 -> int64  values [2010]
4b) AFTER a missing-column concat, round-trip: float64 -> float64  values [2010.0, nan]
```

Corrections, in order:

- **(1) is not `str`; it is `int64`.** The v1 draft's "concat of two disjoint
  Categoricals -> dtype: str" does not reproduce on any of the three versions. A
  `str` result requires *string* categories, and even then it is `object` on 1.4.4
  and 2.2.3 and `str` only on 3.0.5. The draft measured a string-category case and
  reported it as the int case it had chosen thirty lines later in §M4.2.
- **(2) reproduces**, and carries an unreported second effect: the dtype flips
  `int64 → float64`, because NaN cannot live in an int64 column.
- **(3) reproduces** on all three versions.

**The conclusion is unchanged, and the corrected measurement supports it better.**
A `Categorical` does not survive the concat that matters — not by degrading to a
string, but by **losing its categorical dtype entirely and returning the plain
value dtype**. The closed-domain guarantee that was the entire reason to choose
`Categorical` is silently discarded by the one operation that creates a
vintage-spanning frame. Concatenating a frame that lacks the column yields silent
`NaN` *and* silently changes the dtype. And `.agg()` — the call at the heart of
`lending_by_tract` — drops the column entirely unless it is explicitly carried.

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

- Round-trips `to_csv` / `read_csv` as `int64` **provided nothing upstream has
  introduced a null**. A string does not (leading-zero and dtype-inference
  hazards); an enum does not at all.

  The v1 draft said flatly that plain `int` "survives to_csv/read_csv round-trips
  as itself". That is true in isolation and false after the §M4.1(2) concat: one
  frame missing the column flips the dtype to `float64`, and the round-trip then
  preserves `float64`, writing `2010.0`. Measured on all three pandas versions:

  ```
  4)  plain int round-trip:                 int64 -> int64    values [2010]
  4b) round-trip AFTER a missing-column concat: float64 -> float64  values [2010.0, nan]
  ```

  This does not change the decision — `float64` is still orderable, still
  comparable, and still not a string — but the honest claim is narrower: **plain
  `int` round-trips as itself unless a null has already been introduced, at which
  point it round-trips as `float`.** No dtype available here survives that concat
  as an integer, so this is a property of the operation, not a defect of the
  choice. It is one more reason the column is provenance and `activity_year` is
  the mechanism (§M4.1).
- Orderable, so "which is newer" is `<`, with no lookup.
- Identical to the mapping's values, so there is one representation, not two.

**Rejected: `Categorical`** — its categorical dtype does not survive the concat
that matters. On disjoint int categories it returns plain `int64` (verified above
on 1.4.4, 2.2.3 and 3.0.5), so the closed-domain guarantee that is the only reason
to pay for a `Categorical` is silently discarded by exactly the operation that
creates a vintage-spanning frame. Choosing `Categorical` would buy the *appearance*
of a constrained domain and none of the enforcement.
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

`lender_summary` returns a **`dict`**, not a DataFrame (`lender.py:43-54`), and
**two** of its keys are geography-keyed `nunique()` calls — `unique_tracts` on
`census_tract` (`lender.py:52`) and `unique_counties` on `county_code`
(`lender.py:53`). The v1 draft named only the first; the AST sweep in §M6.2 finds
both, and both are wrong across their respective boundaries (§M6.4, §M2.3).

**No column design reaches either.** Its guard must be the raise, and its
provenance must ride as explicit dict keys — §M3.3a specifies `basis_year` and
`dropped_rows_by_year`. This is a concrete gap in the "emit a column everywhere"
framing, and it is why §M2.4's shared helper must return the provenance rather
than write a column: one of the six call sites has nowhere to write one.

One further wrinkle the build must not trip on: `lender_summary` returns `{}` when
`total == 0` (`lender.py:40-41`), and that empty dict is documented as a
legitimate empty result. §M3.3a decides how a *narrowing*-induced empty is
distinguished from a genuine one — the two must not collapse into the same
return value.

### M4.6 Downstream and documented-shape exposure

**Recorded, not fixed, per scope.**

- **`fair-lending-screener`** consumes HMDA frames and does its own tract work. A
  new column means: any strict schema check there breaks the same way §M4.4
  describes; any snapshot test over `df.columns` breaks; and — the quieter risk —
  a consumer that has never heard of `tract_geoid_vintage` will pass it through
  into its own outputs, where it will be read as an assertion that the screener
  understands vintages. It does not. **Exposure noted; not fixed here.**
- **hmda-analyzer's own README** states (lines 99-100) that "The CFPB column schema
  is identical across **2018–2025** … so no columns are year-conditional." The
  header claim is confirmed — 99 columns, identical names, every year 2018–2025:

  ```
  $ # header line of each full-state CFPB CSV
  2018: 99 cols   2019: 99 cols   2020: 99 cols   2021: 99 cols
  2022: 99 cols   2023: 99 cols   2024: 99 cols   2025: 99 cols
  ```

  **But the sentence needs to change for two independent reasons, and the v1 draft
  only had the first.**

  *First:* it sits directly above the `load_range` documentation and will read as a
  claim that nothing about the columns varies by year — the exact misconception
  this defect lives in.

  *Second, and new:* a column's **values** can be year-conditional even when its
  **name** is not, and `derived_msa_md` is a live example. Its `'0'` sentinel is
  present in **2018 and 2019** and gone from 2020 onward:

  ```
  $ # '0' rows in derived_msa-md, full-state files
    CT 2018:  784   2019:  705   2020-2025: 0
    MI 2018: 2623   2019: 4000   2020-2025: 0
  ```

  (The audit prompt put this sentinel in 2019 only; it is in 2018 too.) A consumer
  that writes `df["derived_msa_md"] != "0"` against 2019 data and pools 2019 with
  2020 gets a filter that is meaningful for one year's rows and vacuous for the
  other's, with no schema signal at all. "No columns are year-conditional" is true
  of the header and false of the data, and the README sentence does not make that
  distinction.

  Whatever replaces it must say what it actually covers: the *header* is stable
  2018–2025; the *meaning* of `census_tract`, `county_code` and `derived_msa_md`,
  and the *domain* of `derived_msa_md`, are not.
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

**2. Aggregate to a coarser geography — NOT because it "survives the boundary",
because it does not. — CONDITIONALLY ENDORSED, and now guarded.**

The v1 draft told the user to "aggregate to a geography that survives the
boundary — county, state, or MSA". **That advice was wrong**, and it was the most
dangerous sentence in the document: it named the exit and the exit was unguarded.

Measured (§M2.3, §M6.7):

| Key | Moves at | Mode |
|---|---|---|
| `census_tract` | 2021→2022 (national); 2023→2024 (CT) | reuse; replacement |
| `county_code` | **2021→2022 (AK `02261`→`02063`+`02066`)**; 2023→2024 (CT) | replacement; replacement |
| `derived_msa_md` | **2023→2024** (both modes — see §M6.6) | reuse **and** replacement |
| `state_code` | not measured to move, 2018–2025 | — |

A user escaping the tract rule by moving up to county lands on a key that moves at
**the same boundary they were escaping**, in Alaska. Moving up to MSA is safe
across 2021→2022 and lands on an unguarded reuse at 2023→2024.

*What makes this option usable in 0.6.0:* the county key is now guarded at both
its sites (§M2.1), with its own basis map and the same disjointness check. So the
advice is no longer "this is safe" but "this is checked" — a county aggregation
that spans a county-basis boundary now refuses, exactly as a tract one does.

*Cost:* loses tract granularity, which is often exactly the point of the analysis.
*Residual exposure:* `state_code` has one aggregation site and no basis map,
because nothing was measured to move. That is an argument from absence and it is
recorded as such in the coverage list.

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
empty and there was almost nothing to test.

**Open item O-2 is now closed: the effect is sized, and it is larger on the
innocent tracts than on the guilty ones.** Three counties with substantial
non-colliding populations, 2021 alone vs pooled 2021+2022 (§V-3):

```
$ .venv/bin/python r9_spread.py          # scratchpad, 2026-08-04

Wayne County MI (26163)   2021 keys 600 | 2022 keys 584 | colliding 510 | jaccard 0.757
  NON-colliding  n=  90 | applications changed: 0
    percentile moved 90/90 (100%) | desert flips 7 (7.8%) [newly 7, de-flagged 0]
  COLLIDING      n= 510 | applications changed: 510
    percentile moved 506/510 (99%) | desert flips 22 (4.3%) [newly 2, de-flagged 20]

Cook County IL (17031)    2021 keys 1316 | 2022 keys 1327 | colliding 1283 | jaccard 0.943
  NON-colliding  n=  30 | applications changed: 0
    percentile moved 28/30 (93%) | desert flips 2 (6.7%) [newly 2, de-flagged 0]
  COLLIDING      n=1283 | applications changed: 1283
    percentile moved 1264/1283 (99%) | desert flips 54 (4.2%) [newly 28, de-flagged 26]

Cuyahoga County OH (39035) 2021 keys 443 | 2022 keys 421 | colliding 378 | jaccard 0.778
  NON-colliding  n=  65 | applications changed: 0
    percentile moved 64/65 (98%) | desert flips 3 (4.6%) [newly 3, de-flagged 0]
  COLLIDING      n= 377 | applications changed: 377
    percentile moved 373/377 (99%) | desert flips 19 (5.0%) [newly 1, de-flagged 18]
```

Read `applications changed: 0` first — it is the control. A non-colliding tract's
own counts are provably untouched; nothing merged into it. **Every movement in its
percentile and its desert verdict is pure reference-distribution contamination.**

Three findings, in decreasing order of how robust they are:

1. **The contamination is essentially total.** 93–100% of non-colliding tracts
   have a moved percentile in all three counties. The mechanism argument was
   right, and the effect is not marginal.
2. **It is directional.** Non-colliding tracts flip **only** toward being flagged
   a lending desert — 7/0, 2/0, 3/0 across the three counties, twelve newly
   flagged and zero de-flagged. Colliding tracts flip mostly the other way
   (20 of 22, 26 of 54, 18 of 19 de-flagged), because merging two years inflates
   their application counts and pushes them up the distribution. **The innocent
   tracts absorb the displacement.** This is the finding that matters: the
   corruption does not average out, and it manufactures false positives in the
   exact metric a fair-lending screen acts on.
3. **The flip *rate* is higher on non-colliding tracts in two of three counties,
   not all three.** Wayne 7.8% vs 4.3% and Cook 6.7% vs 4.2%, but Cuyahoga 4.6%
   vs 5.0%. **Do not state "innocent tracts flip at a higher rate" as a general
   result** — the sample does not support it. The directional finding (2) holds in
   all three and is the defensible one.

Exposed internal operations, therefore: `groupby("census_tract")` → `.agg()` →
`rank(pct=True)` → threshold comparison → boolean flag. Four steps downstream of
the collision, and the last one is what a user reads.

### M6.2 Inventory of geography-key operations — re-derived by AST sweep

The v1 draft built this table by reading, with a grep as a cross-check. It is
**re-derived here by an AST sweep** — the same sweep §M2.4 requires as a test —
because a table produced by reading is exactly the artefact that goes stale
silently, and because the grep verb list (`groupby|merge|set_index`) had already
missed one site.

Method: parse every `hmdaanalyzer/**/*.py`; collect every `ast.Call` whose
`func.attr` is one of fifteen identity-forming verbs; take string constants from
the call arguments **and from the subscript the call is made on**; intersect with
the geography column names; attribute to the enclosing `FunctionDef`; then take
the transitive closure over the call graph.

```
$ .venv/bin/python ast_sweep.py          # scratchpad, 2026-08-04

=== PASS 1: DIRECT identity-forming operations on a geography key ===
file:line                               function                    verb      key             basis
hmdaanalyzer/analysis/geographic.py:25  lending_by_tract            groupby   census_tract    tract
hmdaanalyzer/analysis/geographic.py:51  lending_by_county           groupby   county_code     county
hmdaanalyzer/analysis/geographic.py:108 racial_composition_by_tract groupby   census_tract    tract
hmdaanalyzer/analysis/geographic.py:130 lending_by_state            groupby   state_code      state
hmdaanalyzer/analysis/lender.py:52      lender_summary              nunique   census_tract    tract
hmdaanalyzer/analysis/lender.py:53      lender_summary              nunique   county_code     county

counts by basis: {'tract': 3, 'county': 2, 'state': 1}

=== PASS 2: after transitive closure over the call graph ===
function                       file                                bases          how
lender_summary                 hmdaanalyzer/analysis/lender.py     county,tract   direct
lending_by_county              hmdaanalyzer/analysis/geographic.py county         direct
lending_by_state               hmdaanalyzer/analysis/geographic.py state          direct
lending_by_tract               hmdaanalyzer/analysis/geographic.py tract          direct
lending_desert_score           hmdaanalyzer/analysis/geographic.py tract          inherited
racial_composition_by_tract    hmdaanalyzer/analysis/geographic.py tract          direct

TOTAL exposed functions: 6
  tract  : 4  ['lender_summary', 'lending_by_tract', 'lending_desert_score', 'racial_composition_by_tract']
  county : 2  ['lender_summary', 'lending_by_county']
  msa    : 0  []
  state  : 1  ['lending_by_state']
```

**The sweep independently reproduces the v1 draft's four tract sites** — including
`lender.py:52`, which the grep verb list missed and which the subscript rule
recovers — and adds the two county sites the v1 draft classified as "no".

**`derived_msa_md`: zero sites.** The sweep finds no aggregation on it anywhere.
Confirmed directly:

```
$ grep -rn "derived_msa" hmdaanalyzer/
hmdaanalyzer/data/schema.py:131:    "activity_year", "lei", "derived_msa_md", "state_code", "county_code",
```

One occurrence in the whole package, in `EXPECTED_LAR_COLUMNS`. **So
`derived_msa_md` gets no guard site, because there is nothing to guard** — see
§M6.6 for what protects the user who reaches it through §M5.2 anyway.

Not exposed, for the record: `lender.py:123` `groupby("lei")`, `lender.py:87` and
`disparity.py:132` `.merge(on="derived_race")`, `disparity.py` groupbys on race and
income band, and `cra_proxy.py`'s row-level classification (§M2.2). No `set_index`,
`merge` or `join` on any geography key anywhere in the package.

**Six exposed sites across two files.** This is still a small, contained blast
radius, and it remains the evidence for §M2.4's decision to guard at aggregation
rather than at load — but it is 50% larger than the v1 draft's count, and the
growth came entirely from keys the v1 draft had declared safe.

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

**Amendment to the rule stated above.** The "≥2 parts" limb must count only
relationship rows with **`AREALAND_PART > 0`**. As written it counts rows, and
3,999 rows in the national file describe a boundary that touches without
enclosing land, which makes 1,787 one-to-one tracts look multi-part. §M3.1 has the
measurement and the reasoning. The counts in the block above are the v1 figures
and are **not** re-stated here with the filter applied, because §M3.1 supersedes
this metric's role: it is context in an error message, not a trigger.

**Baltimore city: Jaccard 0.985, and 18% of rows on both sides of the boundary
land on a key shared between two different delineations.** The county that looks
safest by the recon's metric is the one whose rows are most quietly at risk.
(The v1 draft said "materially different ground" here; §M3.1 retires that phrase —
about 42% of such keys nationally are ≥99% unchanged.)

Two consequences, and they are the reason this document exists in the form it
does:

- **Measurement is invalid for detecting key REUSE and valid for detecting key
  REPLACEMENT. The two fail in opposite directions.** The v1 draft compressed this
  into "the binding must be declarative, never measured", which over-generalises a
  true finding — and a future reader would use that sentence to delete the
  disjointness check in §M1.2a as contradicting the document's own rule. State it
  precisely:

  | | reuse (same key, new ground) | replacement (new key, same ground) |
  |---|---|---|
  | **Declarative** year→basis map | **detects it** — the basis year changes | **misses it** — CT 2023/2024 share basis 2020 |
  | **Measured** key overlap | **misses it, by construction** — the keys match, so no set comparison can see it | **detects it** — the key sets are disjoint |

  Baltimore city is the reuse case: Jaccard 0.985 says "safe", the map says
  "unsafe", and the map is right. Connecticut 2023→2024 is the replacement case:
  the map says "safe", Jaccard 0.000 says "unsafe", and the measurement is right.
  **Neither instrument dominates. §M1.2a ships both**, and this section is the
  proof that the declarative one cannot be dropped — not the proof that the
  measured one must be.
- **High ID stability is the *more* dangerous case, not the safer one.** Where IDs
  churn, rows fall into disjoint buckets and the tract count visibly inflates.
  Where IDs persist, rows silently merge. Intuition runs backwards here, and any
  reviewer's instinct to "just check how much the tract list changed" must be
  headed off explicitly. **This is an argument against thresholding on Jaccard,
  not against measuring at all** — which is why §M1.2a scopes the measured limb to
  the empty-intersection case, where no threshold judgement is involved.

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

**There is no saving grace, and the v1 draft's claim that there was one is
false.** It argued that because the new keys are disjoint, the failure is
fragmentation rather than collision — "visible", with "no individual number
silently corrupted". Both halves fail against live 2023–2024 data, run through the
shipped functions (§V-1):

```
$ .venv/bin/python r1_ct.py              # scratchpad, 2026-08-04
CT 2023: 105,543 rows | CT 2024: 112,090 rows | pooled: 217,633 rows
pooled activity_year values: ['2023', '2024']

=== HALF 1: 'loud (row counts roughly double)' ===
  2023 alone    871 rows |  195 deserts
  2024 alone    871 rows |  189 deserts
  POOLED       1742 rows |  381 deserts
  warnings emitted : 0
  exceptions       : none (all three calls returned)
  vintage column   : NONE

=== HALF 2: 'no individual number is silently corrupted' ===
  2023 tracts also present pooled: 871 of 871
     applications  differ: 0
     denials       differ: 0
     app_percentile MOVED: 845/871  (rose 10, fell 835)
     desert_score   MOVED: 836/871
     is_lending_desert FLIPPED: 11  (newly flagged 11, de-flagged 0)

  2024 tracts also present pooled: 871 of 871
     applications  differ: 0
     denials       differ: 0
     app_percentile MOVED: 850/871  (rose 817, fell 33)
     desert_score   MOVED: 824/871
     is_lending_desert FLIPPED: 14  (newly flagged 0, de-flagged 14)
```

**Half 1 — "loud" is not what the row count does here.** 871 → 1,742 is a
doubling, and it is only legible to someone who already knew to expect 871. There
is no warning, no exception, and no vintage column. And the number a user actually
reads is not the row count: **the desert total goes 195 + 189 = 384 apart, 381
pooled.** The aggregate barely moves. Nothing in the output is anomalous enough to
prompt a second look, which is the operational meaning of "silent".

**Half 2 — individual numbers are silently corrupted, in bulk.** Per-tract
`applications` and `denials` are untouched, exactly as the fragmentation argument
predicts. But `app_percentile`, `desert_score` and `is_lending_desert` are derived
from the *reference distribution*, and pooling doubled it. 845 of 871 tracts get a
wrong percentile from the 2023 side and 850 of 871 from the 2024 side; **25 tracts
get a wrong desert verdict** — the boolean a fair-lending screen acts on.

**The mechanism is the one this document already proved two pages earlier, in
§M6.1.** That section establishes that `lending_desert_score` ranks over the
collapsed tract set, so every tract's score depends on a population that pooling
altered — and §M6.1 now sizes that effect on tracts which *cannot* have collided.
Connecticut is the same mechanism at its limit: **no tract collides at all**
(intersection 0 of 872), and 97% of them are still wrong. The v1 draft proved the
mechanism and then, two pages later, asserted Connecticut was exempt from it. It
is not exempt; it is the cleanest demonstration of it in the document.

**Why the corruption is asymmetric.** The two directions are not noise. 2023
tracts overwhelmingly fall (835 of 845 moves) and 2024 tracts overwhelmingly rise
(817 of 850) because 2024 carried more volume — 112,090 rows against 105,543 — so
pooling redistributes rank between the years by volume. It is not a uniform skew
that a reader might spot as a shifted distribution; it is a **volume-driven
redistribution between two disjoint halves**, which is precisely why the aggregate
desert count barely moves while 25 individual verdicts flip.

**Consequence for the design.** A year→basis map cannot see this: CT 2023 and CT
2024 are both basis 2020. The disjointness check in §M1.2a is what catches it, and
this section is that check's justification. It is a demonstrated hole, not a
theorised one, and it belongs in the coverage section as such.

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

- **`county_code`** — not stable. CT 2023→2024, and **AK 2021→2022** (§M2.3).
- **`derived_msa_md`** — not stable, **and unstable in both modes**. See below;
  the v1 draft characterised this key's instability solely as replacement and
  missed the reuse entirely.
- **`lei`** — globally unique and persistent by construction, but an institution
  that changes LEI mid-span appears as two lenders. This is *fragmentation*, not
  collision: the counts are right and the attribution is split. Different failure,
  visible, out of scope here, worth someone's attention eventually.

#### `derived_msa_md` — replacement was noted; reuse was missed

The v1 draft recorded CT `49340` → `47930` at 2023→2024, jaccard 0.714. That is
real and reproduces:

```
$ .venv/bin/python r2_counties.py        # CT derived_msa-md value counts
  2023: {'25540': 36381, '14860': 24720, '35300': 24584, '35980': 8816, '99999': 7134, '49340': 3908}
  2024: {'25540': 36341, '14860': 26337, '35300': 16562, '47930': 14757, '35980': 9357, '99999': 8736}
```

But `49340`→`47930` is the **visible** half. At the same boundary, the codes that
*persist* change which ground they cover — and code-set Jaccard is blind to that
by construction:

```
$ .venv/bin/python r2_msa6.py            # scratchpad, 2026-08-04

MI  2023->2024   code-set jaccard=0.944
  REPLACEMENT (gaining code is NEW in 2024 — visible): 4    [45900 x4]
  REUSE (gaining code EXISTED in 2023 — INVISIBLE): 2
      county 26015 -> MSA 24340 (2,771 rows)  [24340 covered 26067,26081,26117,26139 in 2023]
      county 26155 -> MSA 99999 (2,504 rows)

NC  2023->2024   code-set jaccard=0.842
  REPLACEMENT: 1   [38240]
  REUSE      : 7
      county 37019 -> MSA 48900 (11,372 rows)  [48900 covered 37129,37141 in 2023]
      counties 37049/37077/37085/37087/37103/37137 -> 99999

OH  2023->2024   code-set jaccard=0.824
  REPLACEMENT: 8   [17460 -> 17410 for Cuyahoga 39035, 42,617 rows; 41780 x2]
  REUSE      : 0

CT — MSA code coverage, 2023 vs 2024 (county codes are themselves disjoint)
  MSA 14860: 2023 ['09001']                 -> 2024 ['09120','09190']   REUSE
  MSA 25540: 2023 ['09003','09007','09013'] -> 2024 ['09110','09130']   REUSE
  MSA 35300: 2023 ['09009']                 -> 2024 ['09170']           REUSE
  MSA 35980: 2023 ['09011']                 -> 2024 ['09180']           REUSE
  MSA 99999: 2023 ['09005']                 -> 2024 ['09150','09160']   REUSE
```

**Both modes, at the same boundary.** Ohio is pure replacement — `17460` retires,
`17410` appears, and the Jaccard drop announces it. North Carolina is mostly
reuse: `48900` exists in both years and quietly acquires Franklin County
(11,372 rows). Connecticut is entirely reuse: **every surviving MSA code covers
different ground in 2024 than in 2023**, and four of the five would look perfectly
stable to any code-set comparison.

**`99999` is a permanent reuse hazard.** It is the "not in a metropolitan area"
bucket, so it is present in every year with Jaccard contribution 1.000 while its
membership changes at every delineation — six counties enter or leave it across
MI and NC alone at this one boundary. A code-set check can never flag it.

**Correction to the audit prompt: the MSA limb fails at 2023→2024, not at
2020→2021.** The prompt placed it at 2020→2021 on the theory that OMB's 2020
delineations reassign counties between existing MSAs while leaving the code set
intact. The code set is indeed intact — but nothing material moves:

```
$ .venv/bin/python r2_msa5.py CT MI NC OH        # material = >=5% of a county's rows
  CT  2020->2021  msa-code-set jaccard=1.000  MATERIAL county reassignments: 0
  MI  2020->2021  msa-code-set jaccard=1.000  MATERIAL county reassignments: 0
  NC  2020->2021  msa-code-set jaccard=1.000  MATERIAL county reassignments: 0
  OH  2020->2021  msa-code-set jaccard=1.000  MATERIAL county reassignments: 0
  ...
  MI  2023->2024  jaccard=0.944  MATERIAL: 6
  NC  2023->2024  jaccard=0.842  MATERIAL: 8
  OH  2023->2024  jaccard=0.824  MATERIAL: 8
```

The set-level differences at 2020→2021 that a looser test reports are **single
stray rows**, not reassignments:

```
$ .venv/bin/python r2_msa3.py CT MI
  --- MATERIAL (>=10% of county rows on a one-year-only code): 0 counties ---
  --- IMMATERIAL (<10% — stray rows, not a reassignment): 2 counties [CT] ---
    09001  2020 n=60,222 {'14860': 60221, '25540': 1}
           2021 n=66,401 {'14860': 66401}
    09009  2020 n=44,170 {'25540': 2, '35300': 44168}
           2021 n=52,336 {'35300': 52336}
```

One row and two rows. And the prompt's specific example — "MSA 25540 (Hartford)
covers different counties in 2020 than in 2021" — does not hold: 25540 covers
`09003`, `09007`, `09013` in **both** years, plus three stray rows in 2020. It
does cover different ground in **2024** (`09110`, `09130`), which is the finding,
one boundary later.

This is the same artefact class the audit correctly declined to file for the
2019→2020 apparent MSA contraction, and it is worth naming as a method rule: **a
key-membership change is only a delineation change if it moves a material share
of the key's rows.** A single misreported record is indistinguishable from a
boundary revision under a set-difference test, and single misreported records are
common.

**Guard decision: guidance, not a site — and here is what protects the user.**
§M6.2's sweep finds zero aggregations on `derived_msa_md`; it appears once, in
`EXPECTED_LAR_COLUMNS`. So there is no call site to guard, and adding a guard to a
function that does not exist is not possible. The exposure is **entirely through
documented guidance** — §M5.2 option 2 tells users to aggregate to an MSA, and
they would then do it with their own `groupby`, outside the library.

Three things protect that user, and it is worth being clear that they are weaker
than a raise:

1. **§M5.2 option 2 no longer says MSA aggregation survives the boundary.** It is
   rewritten to say which keys move when, with this section cited.
2. **The MSA basis map ships anyway** (§M1.2), even with no internal caller, so a
   user doing their own MSA aggregation has a documented, citable constant to
   check against rather than having to re-derive OMB's adoption schedule.
3. **The coverage list names this as an unguarded key**, so nobody reads "the
   library guards geography keys" as covering it.

If a future release adds an MSA aggregation, the §M2.4 test fails on the new
site — which is the point of asserting set equality rather than a subset.

### M6.7 County-key stability — the jurisdictions checked

```
$ .venv/bin/python r2_alaska.py          # full-state files, 2018-2024
=== ALASKA county_code universe by year ===
  2018->2019  jaccard=0.732  n= 36   <<< sparse-county noise, no boundary change
  2019->2020  jaccard=0.806  n= 29   <<< sparse-county noise, no boundary change
  2020->2021  jaccard=1.000  n= 29
  2021->2022  jaccard=0.903  n= 30   <<< REAL: 02261 -> 02063 + 02066
  2022->2023  jaccard=1.000  n= 30
  2023->2024  jaccard=1.000  n= 30

  02261: 2018=168  2019=223  2020=311  2021=323  2022=-    2023=-   2024=-
  02063: 2018=-    2019=-    2020=-    2021=-    2022=158  2023=92  2024=119
  02066: 2018=-    2019=-    2020=-    2021=-    2022=40   2023=26  2024=35
```

Note the two false positives at 2018→2019 and 2019→2020: Jaccard 0.732 and 0.806
in years with **no boundary change**, caused purely by low-volume boroughs having
zero rows in one year. This is the measurement hazard §M1.2a scopes around.

**The relationship-file companions the audit named, checked against the LAR:**

- **AK `02270` → `02158`** — `02270` appears in **no** LAR year 2018–2024;
  `02158` appears in all of them. The change predates the LAR window (2015).
- **SD `46113` → `46102`** — `46113` appears in **no** LAR year 2018–2024;
  `46102` appears in all of them. Predates the window (2015).
- **VA `51515` retired** — `51515` appears in **no** LAR year 2018–2024;
  Bedford County `51019` appears throughout. Predates the window (2013).

**So of the four companions named, only Alaska's `02261` split is live in the LAR
window.** The other three are real Census changes that happened before 2018 and
have no effect on any frame this library can build. They are recorded here so a
future reader does not re-open them.

**A measurement hazard that constrains the disjointness check.** Single-state
pulls carry out-of-state county codes, in volume:

```
$ .venv/bin/python r2_counties.py        # VA full-state files
  2018: 233 counties
  2019: 145 counties | -['04013','06037','06053', ... ,'78010','99999']  (~100 codes)
  2020: 133 counties | -['11001','12061','18019', ...]
  2021: 133 counties
```

Virginia does not have 233 counties. A `states=VA` fetch contains rows whose
`county_code` is in another state entirely, and the set of such strays changes
every year. Any disjointness check that consumes a raw key set will read this as
instability — a second, independent reason the check is scoped to the
empty-intersection case (§M1.2a).

### M6.8 The narrowing parameter's degenerate cases

Measured in §M3.3a; the commands are `r6_narrowing.py` (empty selection,
single-tract selection, the five-tract floor, and the `.agg()` carry-forward
failure). Recorded here so §V has a single index of the empirical program.

---

## What this rule does not protect against

Written honestly and at length, because every gate in this portfolio that
misdescribed its own coverage became a defect later. A reader should be able to
use this list to decide whether they still have a problem after the rule ships.

**This section was the strongest in the v1 draft and it had three known holes.**
It is rewritten against the measurements, and the holes are named as such rather
than repaired quietly: items 1, 2 and 6 below all previously understated their
exposure, each in the same direction.

**Before the list: the pattern, which is the most transferable thing here.**

Across three geography keys, the v1 draft described the **visible** failure mode
and missed the **silent** one — three for three:

| Key | Visible mode it described | Silent mode it missed |
|---|---|---|
| `census_tract` (CT) | disjoint keys, row count doubles | percentiles silently wrong for 97% of tracts, 25 verdicts flipped (§M6.5) |
| `county_code` | "does not move at 2021→2022" | Alaska `02261`→`02063`+`02066`, live in the LAR at exactly that boundary (§M2.3) |
| `derived_msa_md` | replacement, `49340`→`47930`, Jaccard 0.714 | reuse — every surviving CT code covers new ground; NC `48900` gains 11,372 rows (§M6.6) |

The tract analysis got it right, and the reason is instructive: §M6.4 went looking
for the *invisible* mode first — that is the whole content of "Jaccard is
anti-correlated with the risk". The three misses all happened where the document
stopped at the mode that announces itself.

> **Rule for the next reader: whenever a rule is written about a geography key,
> identify which failure mode is invisible for that key, and check that one
> first.** For key reuse, the invisible evidence is *behavioural* — what happens
> to derived statistics — and no comparison of key sets will ever show it. For key
> replacement, the invisible evidence is that a loud row-count change is
> accompanied by silent corruption of everything computed from a reference
> distribution. In both cases the visible signal is the distraction, not the
> finding.

1. **Connecticut, 2023→2024 — demonstrated, and NOT loud.** Every CT tract GEOID
   changes (jaccard 0.000) while the delineation basis stays 2020, so a
   year→basis rule declares it safe. **The v1 draft's stated mitigation — "the
   failure is loud (row counts roughly double) rather than silent" and "no
   individual number is silently corrupted" — is false in both halves.** Measured
   on live 2023–2024 data: no warning, no exception, no vintage column; 845 of 871
   tracts get a wrong `app_percentile` and 25 get a wrong `is_lending_desert`
   verdict, while the aggregate desert count moves only 384 → 381. Per-tract
   `applications` and `denials` are the *only* things that survive intact. §M6.5.
   **What now covers it:** the measured disjointness check (§M1.2a), which is in
   the design specifically because this case defeats the declarative map.

2. **The escape route up to county or MSA — the v1 draft named it and did not
   guard it.** §M5.2 option 2 told users to "aggregate to a geography that survives
   the boundary". No such geography exists among these keys. The county key moves
   at **2021→2022** (Alaska) and at 2023→2024 (Connecticut); the MSA key moves at
   **2023→2024**, in both modes. §M2.3, §M6.6, §M6.7.
   **What now covers it:** county basis map + disjointness check at both county
   sites (§M2.1); §M5.2 option 2 rewritten.
   **What does not:** `derived_msa_md` has no aggregation site in this package
   (§M6.2) and therefore no guard. A user who follows the rewritten §M5.2 option 2
   and does their own MSA `groupby` is protected only by the documentation and by
   the shipped MSA basis map — not by a raise. That is a weaker instrument and it
   is named as one. §M6.6.

3. **`state_code` is unguarded, on an argument from absence.** The sweep finds one
   `groupby("state_code")` site (§M6.2) and no basis map governs it, because
   nothing was measured to move state codes in 2018–2025. That is not the same as
   a demonstration that they cannot. If a state-level equivalent of the
   Connecticut restructuring occurs, this key fails exactly as county did, and
   nothing in the design would notice.

4. **Future geography changes of a kind not yet seen.** The rule encodes decennial
   re-delineation, the CT county-equivalent restructuring, and OMB's 2023
   delineation revision. Nothing in it anticipates the *next* novel kind — a
   tribal-area boundary change, a further county-equivalent restructuring in
   another state, or a Census methodology change. Both Connecticut and Alaska were
   found by testing a stated assumption rather than by anticipating a category.

5. **The FFIEC demographic appends, which move on a different schedule.**
   `tract_population`, `tract_minority_population_percent`,
   `tract_to_msa_income_percentage`, `ffiec_msa_md_median_family_income`,
   `tract_owner_occupied_units` and the rest are refreshed annually against a
   rolling 5-year ACS. Two rows sharing a delineation basis and a GEOID may still
   carry appended demographics computed on different ACS vintages. **This directly
   affects `cra_proxy_distribution` pooled across years** — which §M2.2 declares
   safe *from the key-collision defect* and which this item declares not thereby
   correct. The naming decision in §M4.3 exists to stop the column from being read
   as covering this. It does not cover it.

6. **The non-colliding spread — the third hole, now sized rather than open.** The
   v1 draft logged this as "argued from mechanism, not sized" (§O-2). It is sized,
   and it is worse than the framing "colliding rows are corrupted" implies.
   Tracts whose GEOID appears in only ONE year cannot have merged with anything —
   their `applications` are provably unchanged — and their derived statistics move
   anyway, because `lending_desert_score` ranks them against a reference
   distribution that pooling altered:

   ```
   Wayne County MI, 2021 alone vs pooled 2021+2022
     NON-colliding (n=90): percentile moved 90/90 (100%) -> 7 desert flips (7.8%), ALL newly flagged
     colliding     (n=510):                                 22 flips (4.3%), 20 of them DE-flagged
   Cook County IL
     NON-colliding (n=30): moved 28/30 -> 2 flips (6.7%), both newly flagged
   Cuyahoga County OH
     NON-colliding (n=65): moved 64/65 -> 3 flips (4.6%), all newly flagged
   ```

   **The direction is the finding: twelve newly-flagged, zero de-flagged, across
   three counties.** Innocent tracts absorb the displacement and move exclusively
   toward being called a lending desert, while colliding tracts mostly move the
   other way. The corruption does not average out; it manufactures false positives
   in the one boolean a screen acts on. §M6.1.

   *Not claimed:* that innocent tracts flip at a **higher rate** than colliding
   ones. That holds in Wayne (7.8% vs 4.3%) and Cook (6.7% vs 4.2%) and reverses
   in Cuyahoga (4.6% vs 5.0%). Three counties do not establish a rate ordering.

7. **Within-vintage incomparability generally.** "Same delineation basis" is
   necessary for tract-level comparison. It is not sufficient.

8. **Outputs that are not DataFrames.** `lender_summary` returns a `dict`; its
   `unique_tracts` and `unique_counties` values are `nunique()` calls that
   undercount across their respective boundaries and no column can ride along with
   them. Guarded only if the raise reaches them; provenance rides as explicit dict
   keys (§M3.3a). §M4.5.

9. **Frames the library did not build.** The guard derives the basis from
   `activity_year`. `load_from_file` accepts an arbitrary CSV and does not assert
   that column exists (`loader.py:258-266`), so a user-supplied file may carry no
   year at all — in which case the guard cannot fire and must say so rather than
   assume. A frame with a *fabricated* `activity_year` defeats the guard entirely.

10. **A seventh geography-keyed operation added later without its guard.** The
   §M2.4 decision to guard six call sites rather than the frame accepts this
   exposure. It is now *bounded* rather than open: the AST test in §M2.4 asserts
   set equality over the site list, so a new site fails CI. What the test cannot
   catch is a site that reaches a geography key by a route the fifteen-verb list
   does not cover — a `.loc` selection, a hand-rolled dict lookup, or a key
   assembled from string slices.

11. **The report layer, until §M3.2a is implemented.** `generate_disparity_report`
    and `summary_table` catch `except Exception` with a `MissingColumnError`-only
    re-raise allowlist, so a new `ValueError` subclass renders as a table cell
    instead of propagating. Latent today only because the geography imports in
    `report/generator.py` are unused. §M3.2a.

12. **It does not make cross-vintage analysis correct.** It makes it *not silent*.
    A user who takes the narrowing parameter still has two panels, not a trend. The
    rule removes a wrong answer; it does not supply the right one. §M5.2 is the
    nearest thing to a right answer and every option there has a cost.

13. **Truncation interacts with all of it.** `limit` silently truncates each year's
    fetch (out of scope, recorded). A truncated frame's tract set is a biased
    sample of the county's tracts, so collision counts and row shares measured on
    one are not the county's true figures. The measurements in this document
    deliberately used full state and county files to avoid this.

14. **Nothing here addresses whether the underlying analysis is sound.** A
    correctly-vintaged `lending_desert_score` is still computed by the formula at
    `geographic.py:83-91`, which is out of scope and unexamined. The five-tract
    floor in §M3.3a is a statement about when the flag is *arithmetically*
    reachable, not about when it is *statistically* meaningful.

---

## Corrections to the recon and to the commissioning prompt

Recorded because they are load-bearing, and because ten prompts in this engagement
have carried factual errors that surfaced only when a session executed them.

**Against the recon design:**

1. **"Raise on a vintage-spanning frame" — rejected.** It refuses analyses that
   were always correct (group-by-lender on a multi-year frame). Replaced by:
   annotate at load, raise at aggregation. §M2.4.
2. **"Emit `tract_vintage` as the contract" — revised.** A column cannot carry a
   guarantee: `.agg()` drops it, and concat with a frame lacking it yields silent
   NaN *and* an `int64→float64` dtype flip. A `Categorical` loses its categorical
   dtype entirely under that concat. The column is provenance; the guard derives
   from `activity_year`. §M4.1.
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

7. **`docs/rate-spread/` is not in this repo — and `docs/` was the wrong home.
   RESOLVED: the document moved.** It is in `fair-lending-screener`; this repo's
   methodology precedent is `hmdaanalyzer/methodology/cra_proxy_methodology.md`,
   *inside the package*. `MANIFEST.in` includes no `docs/` path. Confirmed by
   building both artifacts from a clean clone (a build in a working tree with a
   stale `*.egg-info/` reuses `SOURCES.txt` and hides this — see `MANIFEST.in`):

   ```
   $ git clone -q --branch docs/tract-vintage-methodology ~/hmda-analyzer clean && cd clean
   $ python -m build --outdir ../dist
   $ tar tzf ../dist/hmda_analyzer-0.5.0.tar.gz | grep -E "docs/|\.md$"
     hmda_analyzer-0.5.0/CHANGELOG.md
     hmda_analyzer-0.5.0/CONTRIBUTING.md
     hmda_analyzer-0.5.0/README.md
     hmda_analyzer-0.5.0/hmdaanalyzer/methodology/cra_proxy_methodology.md
   $ unzip -l ../dist/hmda_analyzer-0.5.0-py3-none-any.whl | grep -E "docs/|\.md"
     22313  hmdaanalyzer/methodology/cra_proxy_methodology.md
   $ # occurrences of "tract-vintage"/"tract_vintage" in either artifact:
     sdist: 0    wheel: 0
   ```

   **This document is therefore moved to
   `hmdaanalyzer/methodology/tract_vintage_methodology.md`.** It needs no new
   machinery: `[tool.setuptools.package-data]` already globs
   `"hmdaanalyzer.methodology" = ["*.md"]`, and `get_methodology_path(filename)`
   already exists and already takes a filename argument
   (`cra_proxy.py:54`). One in-package location, not two — deliberately **not**
   `fair-lending-screener`'s pattern of keeping both `docs/methodology.md` and an
   in-package copy, because two copies of a methodology is a drift hazard and this
   portfolio has just spent three passes on exactly that failure.

   **The gate it needs.** `test-sdist`'s required-files loop checks
   `tests/conftest.py`, `tests/__init__.py`, `README.md` and `pyproject.toml` —
   no methodology file. What actually protects the existing doc is
   `test_get_methodology_path_returns_bundled_file` (`tests/test_cra_proxy.py:254`),
   which runs against the installed artifact in both `test-wheel` and `test-sdist`
   — **but it calls `get_methodology_path()` with the default argument**, so a
   second bundled doc is entirely ungated. Specify a parallel test:
   `get_methodology_path("tract_vintage_methodology.md")` is a file, reads as
   UTF-8, and contains a marker phrase from this document's binding section. Same
   shape, explicit filename, so both bundled docs are covered by the same
   mechanism.
8. **The FFIEC FIG does not state the tract vintage.** Proposed as the citation;
   read; it says only "Enter the 11-digit census tract number." The authority is
   Reg C Comment 4(a)(9)(ii)(C)-1 plus CFPB's annual data summaries. §M1.1.
9. **"County FIPS is largely stable across vintages" is false.** Connecticut,
   2023→2024, jaccard 0.056. The prompt invited a blanket declaration that
   cross-vintage county aggregation is defensible; the correct statement is
   narrower and is given in §M2.3.
10. **The prompt's verb list for the inventory — groupby/merge/set_index — misses a
    site.** `lender.py:52` is a `nunique()`. §M6.2, now re-derived by AST sweep:
    six exposed sites across two files, four on the tract key and two on the county
    key.
11. **`EXPECTED_LAR_COLUMNS` uses strict two-way set equality**, so adding any
    column to `_clean`'s output makes **every `load_range` call raise
    `SchemaValidationError`**. Not mentioned in the design; it is a total failure
    on the first call, not an edge case. §M4.4.
12. **`lender_summary` returns a `dict`.** "Emit the column on every frame that
    carries `census_tract`" does not reach it. §M4.5.

**And the thing the commissioning prompt did not know existed:** the Connecticut
2023→2024 tract-key discontinuity (§M6.5). It is a second, independent break in
tract-key comparability, at a different year than the one this document was
commissioned about, invisible to the binding being designed, and it was found only
by testing the prompt's own stated assumption about county stability rather than
accepting it.

**Against this document's own v1 draft** (the hostile audit's findings, verified
independently in this pass unless noted):

13. **The Connecticut "loud failure" claim was false in both halves.** §M6.5 and
    coverage item 1 asserted "the failure is loud (row counts roughly double)" and
    "no individual number is silently corrupted". Measured: no warning, no
    exception, no vintage column; 845/871 and 850/871 tracts get wrong
    percentiles; 25 get wrong desert verdicts; the aggregate desert count moves
    384 → 381. **The draft proved this exact mechanism in §M6.1 and then asserted
    Connecticut was exempt from it two pages later.** §M6.5.
14. **"The binding must be declarative, never measured" over-generalises.**
    Measurement is invalid for detecting key *reuse* and valid for detecting key
    *replacement*; they fail in opposite directions. The corrected statement and
    the hybrid design are in §M1.2a and §M6.4.
15. **Two of the three "verified" pandas outputs did not reproduce**, and one was
    run on a different input type than the design it justified. Disjoint
    `Categorical` concat gives `int64`, not `str`. Re-run on 1.4.4 / 2.2.3 / 3.0.5
    — `pandas` is unpinned at `>=1.4.0` — with identical results. The `attrs`
    claim named `.copy()` (which preserves) instead of `.agg()` (which drops, and
    which is the operation that matters). Conclusions survive; evidence replaced.
    §M4.1, §M4.2, §M3.3.
16. **The county key moves at 2021→2022 too.** Correction #9 above replaced the
    prompt's false premise with a narrower claim that is also false. Alaska
    `02261` → `02063` + `02066`, live in the LAR at exactly the tract boundary.
    §M2.3, §M6.7.
17. **`derived_msa_md` instability was characterised solely as replacement.** The
    reuse mode — same code, new ground — was missed entirely, and it is the larger
    and more dangerous half. §M6.6.
18. **"Materially different ground" was a modelling choice presented as a
    measurement.** 42.1% of the flagged GEOIDs nationally share ≥99% of their
    ground with the same-numbered 2010 tract, and 1,787 flags rest on zero-land-area
    slivers. The word is retired and the `AREALAND_PART > 0` filter is added.
    §M3.1, §M6.4.
19. **The narrowing parameter had three undefined cases** — empty selection,
    single-tract selection, and the carry-forward requirement that §M4.1's own
    finding makes unsatisfiable. §M3.3a.
20. **Nothing enforced the site list**, and one shipped caller would have defeated
    the raise entirely. §M2.4, §M3.2a.

**Against the hostile audit's own report** — three corrections, because an audit
is a claim like any other:

21. **The MSA limb fails at 2023→2024, not 2020→2021.** The audit placed it at
    2020→2021 with counts "MI 6 of 83, CT 2 of 8, NC 2 of 100, OH 5 of 88". Those
    counts are **single stray rows** — Fairfield County CT has 60,221 rows in
    `14860` and *one* in `25540` — not reassignments. Measured with a materiality
    threshold, 2020→2021 has zero material reassignments in all four states, and
    2023→2024 has 6 / 8 / 8. The audit's specific example, "MSA 25540 (Hartford)
    covers different counties in 2020 than in 2021", does not hold; 25540 covers
    the same three counties in both years. §M6.6.
    *This is the same artefact class the audit correctly refused to file for the
    2019→2020 apparent contraction — applied inconsistently one boundary over.*
22. **The desert-flag floor is five tracts, not one.** The audit noted that
    `rank(pct=True)` on one row is always 1.0. The threshold is
    `app_percentile < 25` and the minimum percentile is `100/n`, so the flag is
    unreachable for **n ≤ 4**. §M3.3a.
23. **`report/generator.py`'s swallowing is latent, not live, and there are five
    sites, not four.** The five geography imports are dead — never called — so
    nothing swallows the new exception today. And `summary_table` has a fifth
    `except Exception` with **no** `MissingColumnError` re-raise at all, which the
    audit did not name and which is the worst of the five. §M3.2a.

Reproduced from the audit without correction: the CT row counts and desert
figures (105,543 / 112,090; 871/195, 871/189, 1742/381; 25 flipped verdicts), the
Alaska split and its row counts, the Wayne and Cook non-colliding spread, all
three pandas behaviours, the "never under-flags" result, and the packaging
finding. Not reproduced exactly: the audit's "68.7%" ≥99%-same-ground share
(measured 61.8% on five counties, 42.1% nationally) and its "872" sliver count
(measured 1,787 nationally) — both are scope differences rather than errors, and
both point the same way as the audit's conclusion.

**And the thing THIS prompt did not know existed: the 2025 data year is already
served.** §M1.3 argues the unmapped-year raise entirely in the future tense —
"when 2026 data lands", "in 2032" — and treats the resulting breakage as a cost to
be accepted later. The CFPB API returns a complete 2025 snapshot today: 19,621
Alaska rows, 123,752 Connecticut rows, `activity_year='2025'`. A map shipped with
2024 as its last entry raises on the current data year on release day. The maps
must carry 2025 entries, with citations, before 0.6.0 ships. It was found by
asking what the API was actually serving rather than by reading the document's
year range — the same move that found Connecticut and Alaska. §M1.3, §O.

---

## O — Open items

**Release blockers for 0.6.0:**

1. **The 2025 entry in all three basis maps needs its citation.** 2025 is already
   served (§M1.3). The measurements are consistent with 2025 continuing on the
   2020 tract scheme and the 2023 county/MSA schemes, but §M1.3's own rule is that
   an entry is a citation, not an inference. The CFPB *Summary of 2025 Data on
   Mortgage Lending* statement was **not located in this session** — the two URLs
   tried (`consumerfinance.gov/data-research/hmda/` and the
   `data-point-2024-…` report slug) returned HTTP 200 with no delineation
   sentence and HTTP 404 respectively. A human should find it, or find the FFIEC
   equivalent, before the maps ship.
2. **The county and MSA basis maps' full year→basis assignments are not yet
   established year by year.** §M2.3 and §M6.6 establish *where the boundaries
   are* (county: 2021→2022 and 2023→2024; MSA: 2023→2024) from LAR measurement.
   Turning those into complete maps with a citation per entry — OMB bulletin
   numbers and their FFIEC adoption years — is required before the maps are
   anything more than the measurements restated.

**Still open, not blocking:**

3. **FFIEC's operational adoption notice was not read** (HTTP 403 from
   `ffiec.gov` and `geomap.ffiec.gov` to every automated request, both sessions).
   The binding does not depend on it, but a human with a browser should confirm
   it and either add it to §M1.1 or record that it says nothing new.
4. **Whether any override should exist at all.** §M3.3 says no for v1 and states
   the minimum bar if a reviewer disagrees.
5. **The disjointness check's threshold beyond the empty-intersection case.**
   §M1.2a scopes v1 to zero intersection deliberately. Whether a partial-overlap
   threshold can be defended — given §M6.4's proof that intermediate Jaccard means
   the opposite of what intuition says — is a real question with no answer here.
6. **The 2019→2020 apparent MSA contraction remains unexplained and is
   deliberately not filed.** Large apparent drops appear in every state
   (CT code-set jaccard 0.545 at that boundary, OH 0.357). They trace to the `'0'`
   sentinel present in 2018–2019 and to out-of-state metropolitan-division codes
   appearing in single-state pulls. That is enough to decline to call it a
   delineation change and not enough to say what it is. **Reopening it needs a data
   question answered first — what the `'0'` sentinel meant and why it stopped —
   not a methodology paragraph.**

**Closed by this revision:**

- ~~The reference-distribution contamination is argued from mechanism, not
  sized.~~ Sized on three counties; see §M6.1 and coverage item 6. The effect is
  near-total on percentiles and directional on verdicts.
- ~~Whether this document belongs in `docs/` or in `hmdaanalyzer/methodology/`.~~
  Moved, with the packaging evidence in correction 7.
- ~~Drift between four independent guards.~~ One helper called from N places, plus
  an AST test asserting set equality over the site list. §M2.4.

---

## V — Verification log

**v1 program (2026-08-03).** All commands run from a clean checkout of `main` at
`bace2f2`, Python 3.14, pandas 3.0.5, in a scratch virtualenv outside the repo. No
repository code was modified.

Rows 13 and 14 are **superseded** — see the v2 program below. Row 13's stated
result did not reproduce; row 14's method missed two sites.

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
| 13 | ~~pandas column-durability behaviours~~ **SUPERSEDED by V-2** | pandas 3.0.5 | ~~Categorical→str on disjoint concat~~ — did not reproduce; see V-2 |
| 14 | ~~Source inventory~~ **SUPERSEDED by V-2** | `grep -rn -E "groupby\|\.merge\|set_index\|nunique\|census_tract"` | ~~Four exposed tract-key sites~~ — missed both county sites |

**v2 program (2026-08-04).** All commands run from the
`docs/tract-vintage-methodology` branch at `84b7633`, in scratch virtualenvs
outside the repo. **No repository code was modified and no `.py` file was
touched.** Scratch scripts live in the session scratchpad, not in the repo, per
scope. Data is full-state and full-county CFPB Data Browser CSVs — no `limit`
truncation anywhere, per coverage item 13.

| # | What | Command | Established |
|---|---|---|---|
| V-1 | CT 2023+2024 pooled, through the shipped functions | `r1_ct.py` | 105,543 / 112,090 rows; 871/871/1742 rows; 195/189/381 deserts; 0 warnings, 0 exceptions, no vintage column; percentile moved 845/871 and 850/871; **25 desert verdicts flipped**; applications/denials unchanged; key intersection 0 of 872 |
| V-2 | pandas durability, **three versions** | `r4_pandas.py` on 1.4.4 / 2.2.3 / 3.0.5 | disjoint Categorical concat → **`int64`** (not `str`); missing-column concat → 1 null **+ `int64`→`float64`**; `.agg()` drops the column; `attrs` survives `.copy()`/`concat`/slicing, dropped by `.merge()`/`.agg()`; identical across all three |
| V-3 | Non-colliding reference-distribution spread | `r9_spread.py` | Wayne MI 90/90 moved, 7 flips all newly flagged; Cook IL 28/30, 2 flips both newly flagged; Cuyahoga OH 64/65, 3 flips all newly flagged; **12 newly flagged, 0 de-flagged** |
| V-4 | AK `county_code` 2018–2024, full state | `r2_alaska.py` | `02261` (323 rows, 2021) → `02063` (158) + `02066` (40) at **2021→2022**; jaccard 0.903; two false-positive jaccard dips at 2018→2019 and 2019→2020 from sparse-borough absence |
| V-5 | MSA county-coverage, CT/MI/NC/OH 2019–2024 | `r2_msa5.py`, `r2_msa6.py`, `r2_msa3.py`, `r2_msa4.py` | **2020→2021: code-set jaccard 1.000 and ZERO material reassignments in all four states**; 2023→2024: 6/8/8 material reassignments, split into replacement (OH `17460`→`17410`) and **reuse** (NC `48900` +11,372 rows; CT all five codes) |
| V-6 | County companions vs the LAR | `r2_counties.py` | `02270`, `46113`, `51515` appear in **no** LAR year 2018–2024 — all pre-window; VA single-state pulls carry ~100 out-of-state county codes |
| V-7 | Recarved rule vs a stricter overlap test | `r3_recarve.py`, `r3_natl.py` | Rule A **never under-flags** (0 misses, 5 counties); nationally 46,204 calls, **42.1% ≥99% same ground**, **1,787 on zero-area slivers**; row-weighted A vs B: Fayette PA 99.9%/16.0%, Cook 15.6%/1.2%, Baltimore 18.2%/8.0% |
| V-8 | Narrowing degenerate cases | `r6_narrowing.py` | empty → 0 rows / `{}` / no raise / no warning; single tract → `app_percentile` 100.0; **flag unreachable for n ≤ 4**; `.agg()` drops a carried `tract_geoid_vintage` |
| V-9 | Geography-key site inventory | `ast_sweep.py` | **6 sites**: 4 tract, 2 county, **0 MSA**, 1 state; `derived_msa_md` occurs once in the package, in `EXPECTED_LAR_COLUMNS` |
| V-10 | Packaging | `git clone` + `python -m build` from a clean tree | Neither sdist nor wheel contains the tract-vintage document (0 occurrences); `cra_proxy_methodology.md` ships in both |
| V-11 | 2025 data year | CFPB Data Browser API | **2025 is served**: AK 19,621 rows, CT 123,752 rows, `activity_year='2025'`; 2026 returns HTTP 400; tract jaccard 2024→2025 = 0.977 (AK) / 0.998 (CT) |
| V-12 | CFPB header stability + `'0'` sentinel | header line of each full-state CSV | 99 columns every year **2018–2025**; `derived_msa-md` `'0'` present 2018–2019, absent 2020–2025 |
| V-13 | Reg C commentary, re-fetched | `consumerfinance.gov/rules-policy/regulations/1003/4/` | Comment 4(a)(9)(ii)(C)-1 confirmed **verbatim**, independently of v1 |

**Next step: scoped re-audit of the changed sections and the new county/MSA
material. No code until then.**
