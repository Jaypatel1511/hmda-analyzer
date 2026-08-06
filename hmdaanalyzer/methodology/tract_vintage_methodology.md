# Census-tract vintage in multi-year HMDA frames — methodology

> **Status: v5, POST-BUILD, POST-HOSTILE-AUDIT.** The code exists. v4's
> "PRE-BUILD" banner is superseded: build 1 shipped on branch
> `feat/0.6.0-tract-vintage-rule`, was hostile-audited, and returned
> **fix-then-ship**. This revision records the fixes. The audit's verdict on the
> payload — "15/15 silent wrong answers become 15/15 refusals, 7/7 legitimate
> frames stay silent, nothing in the diff makes a number wrong" — stands
> unchanged; the design was not in question.
>
> **What changed in v5, in one list.** Three gates could not fail in the ways
> their names promised and one guard had a live bypass, so each is now
> falsifiable-by-injection rather than merely present:
>
> 1. **The desert floor is derived, not written down twice** (§M3.3a). The
>    `app_percentile < 25` threshold existed as a literal in four places with
>    nothing tying them together; moving it left `DESERT_TRACT_FLOOR` wrong and
>    the entire suite green, fabricating negatives for every frame of 5–10 tracts.
>    It is now one exported constant with the floor derived from it at import.
> 2. **A null `activity_year` no longer bypasses the guard** — and neither does a
>    `float64` year column, which is the sharper half the review did not have:
>    one blank cell flips the dtype, `int("2021.0")` raises, every year collapsed
>    to UNMAPPED, and a **decennial-spanning frame passed the guard silently**
>    (§M1.3, coverage item 20).
> 3. **The uncited 2024 tract entry is removed** (§O item 10). Its premise was
>    wrong at the granularity HMDA keys on, and §O item 1 now measures that
>    premise failing empirically on Alaska.
> 4. **The nationwide 2023→2024 refusal prices itself** (coverage item 19), the
>    refusal message names constants that exist (§M1.3), a tract output stamps
>    **both** maps that govern it (§M4.3), and UNKNOWN is distinguishable from
>    NO_YEAR_COLUMN instead of both being an absent column (§M3.3a).
> 5. **§O item 1, the last release blocker, is CLOSED** — both county change
>    records located, read and cited. The negative result that came with it is
>    load-bearing and is recorded there.
> 6. **§M6.5's harm sentence mixed denominators** and understated the measured
>    harm by roughly half. Restated with one denominator: 1,695 of 1,742
>    tract-years, not 845 of 871.
>
> **What changed in v4 — one decision, and it is a removal.** §O item 8 asked
> whether the measured per-county disjointness limb should ship at all. **It does
> not.** Its own scorecard answered the question: zero unique findings, a 5:0
> false-positive record, and a row floor the document itself called "a threshold,
> not a derivation". The three declarative maps carry the rule. The residual gap
> the limb claimed to cover is now stated as an **open, undefended gap** rather
> than as covered (§M1.2b, coverage item 15). v4 also corrects the state count
> behind every per-county measurement — five, not six — and confirms the two
> figures carried forward from v3 (the sliver counts and the pandas 1.4.4 `attrs`
> divergence). Full re-verification with the limb removed is in §V4.
>
> **v1 was hostile-audited; v2 was re-audited on the sections v1's audit changed.**
> The core design has now survived three independent passes: the declarative
> year→basis binding, the six-site inventory (three separate AST sweeps agree), the
> no-crosswalk argument, raise-over-warn, the unknown-year raise as a principle, the
> Jaccard anti-correlation result, the Connecticut `lending_desert_score` numbers,
> the packaging finding and the five-tract desert floor are all settled and are not
> reopened here.
>
> **What changed in v3, in one list:** the `NA` sentinel is documented as a valid
> reported value present in every state-year measured, four key-set figures
> contaminated by its silent removal are corrected, and every key-set measurement in
> the document now states its sentinel handling (§M1.2a, §M2.3, §M6.5, §M6.7); the
> measured limb is **redesigned from frame scope to county scope** — *and then
> removed outright in v4* — and the
> declarative limb is extended to consult the county basis map, which is what
> actually catches Connecticut (§M1.2a); §M1.3 gains an **`UNKNOWN` third map state**
> that resolves a live contradiction with §M2.2 and unblocks the 2025 release
> (§M1.3, §M2.2); the MSA map's boundary moves to **2022 on a citation** rather than
> 2024 on a measurement, and the stray-row mechanism is corrected to intra-record
> geography disagreement (§M2.3, §M6.6); the `attrs` evidence is replaced with a
> full four-configuration matrix showing `.merge()` and `pd.concat` obey **one**
> rule (§M3.3); and four mechanical defects are repaired, including two stale `O-2`
> references that had the document declaring an open release blocker closed (§M6.1,
> coverage item 6, §M3.1, §M3.2a).
>
> **This document also revises the recon design it was commissioned to justify.**
> Three of the recon's four proposals survive in altered form; one — "raise on a
> vintage-spanning frame" — is rejected and replaced (§M2, §M3). The recon's
> *detection method* is also rejected, though more narrowly than v1 stated: it is
> anti-correlated with key *reuse*, and valid for key *replacement* (§M6.3,
> §M6.4).
>
> Every empirical claim carries the command that produced it. v1's claims were run
> 2026-08-03 and are in §V; v2's 2026-08-04 in §V-2; v3's 2026-08-04 in §V-3. Where
> an earlier claim did not reproduce, the earlier row is struck rather than deleted.
>
> **Standing measurement rule, adopted in v3 and applying to every figure in this
> document:** any statement about a set of geography keys must say whether the `NA`
> sentinel was included, and must have been run both ways. §M1.2a explains why.

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
0.6.0 declares `requires-python = ">=3.11"` (0.6.1 lowered it back to `>=3.9`,
which is what this package actually supports — the line above records what 0.6.0
decided, not the current floor); the CI workflow's `name:` becomes
`CI` with the filename `test.yml` unchanged; `docs-check` adoption rides this
release.

**What 0.6.0's payload is, as of v4:** a county basis map and an MSA basis map
alongside the tract one, each with an `UNKNOWN` state for unmapped years; guards at
`lending_by_county` and `lender_summary`'s `unique_counties`; the tract guard
consulting the **county** map as well as the tract map; a single shared guard
helper; an AST-based test that enforces the site list; a fix to the report layer's
exception allowlist; a `README` sentence change; and this document's relocation into
the package with a packaging gate. None of that is implemented here — this remains a
decision record, not a specification.

**The payload is now entirely declarative.** Every guard reads `activity_year`,
looks up one or two cited maps, and raises or does not. Nothing in it compares key
sets, and nothing in it carries a tuned constant.

**What v3 removed from that payload:** the frame-level disjointness check (replaced
by the per-county one, §M1.2b) and the 2025-citation release blocker (dissolved by
`UNKNOWN`, §M1.3).

**What v4 removed from that payload:** ~~a **per-county** key-disjointness check
with a stated row floor~~ — the measured limb, entire. Zero unique findings across
every measured year-pair, five false positives, and a hand-tuned floor (§M1.2b,
§V4). The gap it claimed to cover is now stated as an open gap (coverage item 15)
rather than as covered by an instrument that has never covered it.

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

~~**The sketch that stood here is STRUCK.** It read:~~

```
~~TRACT_GEOID_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022..2025 -> 2020}~~
~~COUNTY_CODE_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022, 2023 -> 2020,~~
~~                              2024, 2025 -> 2023}~~
~~MSA_CODE_BASIS_BY_YEAR     : {2018..2021 -> 2010, 2022, 2023 -> 2020,~~
~~                              2024, 2025 -> 2023}~~
```

**Why it is struck.** The sketch maps **2025 in all three maps**. That contradicts
§0, §M1.3, §M2.2 and §O item 2, every one of which holds that 2025 is UNKNOWN in
all three maps because no citation for its basis exists — and 2025 is *the*
load-bearing case for the UNKNOWN state, present tense, already served by the API.
It also maps 2024 in the tract map, which §O item 10 removes. A future reader
implementing from this sketch would add two uncited entries and believe they were
following the document. This is the same shape as the `-lt 14` defect: a stale
example left standing next to the rule it contradicts, where the example is the
thing that gets copied.

**The maps as they actually ship** — and the module, not this sketch, is the
record:

```
TRACT_GEOID_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022, 2023 -> 2020}
                             # 2024, 2025 ABSENT = UNKNOWN (§M1.3, §O item 10)
COUNTY_CODE_BASIS_BY_YEAR  : {2018..2021 -> 2010, 2022, 2023 -> 2020,
                              2024 -> 2023}          # see §M2.3, §M6.7
                             # 2025 ABSENT = UNKNOWN
MSA_CODE_BASIS_BY_YEAR     : {2018..2021 -> 2010, 2022, 2023 -> 2020,
                              2024 -> 2023}          # see §M2.3 — the 2022
                             # 2025 ABSENT = UNKNOWN  # boundary is a CITATION,
                                                      # not a measurement
```

No year may be added to this block without being added to the module with a
citation in the same change. If the two ever disagree, the module is right and
this document is stale — which is the failure mode that produced the strike above.

The MSA map's 2022 boundary comes from CFPB's *Summary of 2023 Data* ("OMB
definitions released in 2020 that became effective for HMDA purposes in 2022") and
its 2024 boundary from OMB Bulletin 23-01. **Neither is visible in the LAR**, which
is exactly why §M2.3 sets them from citations. A fourth map state, `UNKNOWN`,
applies to any year absent from any of the three (§M1.3).

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

> ~~**Decision: a hybrid. Declare the basis; measure the disjointness.**~~
> **WITHDRAWN in v4.** The measured limb is removed from the payload. It produced
> **zero** unique findings across every year-pair in the measured sample, and its
> row floor was a hand-tuned constant. The reasoning is in §M1.2b; the evidence is
> §V4-1 through §V4-3. **Decision: declare the basis, on three maps. Do not
> measure.**

The two-instrument analysis below is retained because it is §M6.4's result and
because it is what makes the *declarative* case, but its conclusion has changed:

| | what it detects | why the other cannot |
|---|---|---|
| **Declarative** year→basis maps (§M1.2) | **key REUSE** — the same string meaning different ground | Reuse is invisible to measurement *by construction*: the keys match, so no comparison of key sets can see it (§M6.4) |
| **Measured** key-disjointness check | **key REPLACEMENT** — the ground surviving under a new string | Replacement is invisible to the map *when no map covers the key that moved* |

The two failure modes are complements, and each instrument is blind to exactly the
one the other catches. Shipping only the measurement lets Baltimore city through
(§M6.4: Jaccard 0.985, 18% of rows on re-carved keys). ~~Ship both.~~

**What the right-hand column understates, and why the table alone does not settle
the question.** "Replacement is invisible to the map *when no map covers the key
that moved*" is true, and the clause it turns on is doing all the work. Three maps
now cover tract, county and MSA, and the tract guard consults the county map — so
the uncovered region is not "key replacement" at all. It is **key replacement
inside a single county at a year where none of the three maps changes.** That is a
much smaller target than the row implies, and §M1.2b measures how often the
measured limb hit it: never.

**Two corrections to how the v2 draft justified this split**, both from §M1.2b, and
both of which — followed to their end in v4 — are what removed the measured limb
rather than narrowing it:

- **Connecticut is not the measured limb's case.** The v2 draft said "shipping only
  the map lets Connecticut through", and that is false once the tract guard consults
  the **county** map — which it must, because the county code is the tract GEOID's
  prefix. Measured, CT 2023→2024 produces **zero** disjoint-within counties, so the
  measured limb contributes nothing there. Connecticut is a declarative catch.
- **The measured limb's real job is narrower**: a key replacement inside a single
  county at a year where *no* basis map changes. That case is not observed anywhere
  in the measured sample (coverage item 15). ~~It ships as a residual net, not as the
  answer to Connecticut.~~ **v4: it does not ship.** A residual net that has never
  caught anything, and that needs a tuned constant to avoid catching the wrong
  thing, is not a net — it is an untested code path with a user-visible raise on the
  end of it. The gap it claimed to cover is now stated as a gap (coverage item 15).

#### The `NA` sentinel, and why it matters more than a filter

Before the measured limb can be specified at all, one fact about the data has to be
established, because it silently invalidated the v2 draft's showcase for this very
check.

**`census_tract` and `county_code` carry the literal string `NA` as a valid
reported value.** The 2025 FIG documents the field as `06037264000 (or) NA`. It is
not rare and it is not confined to a few years — it is present in **every
state-year measured**, ~~40 of 40~~ **39 of 39** across six states and 2018–2025
(**v4 count correction**: the sentinel cache holds 39 state-year files — AK and CT
2018–2025, MI and NC 2018–2024, OH 2019–2024, VA 2018–2020 — plus the Census
relationship file, which is not a state-year. The claim "present in every one" is
unaffected; only the denominator was):

```
$ .venv/bin/python s1_sentinel.py    # scratchpad, 2026-08-04
   file        rows     tracts  NA_tract  counties  NA_county
   CT_2023  105,543        873     1,001         9        892
   CT_2024  112,090        873     1,173        10      1,101
   AK_2021   42,991        165        66        30         56
   VA_2018  351,200      1,990     3,521       234      3,064
   ... (all 40 state-years carry NA in both columns)
```

**`pandas.read_csv` coerces it to `NaN`, and the shipped loader does not disable
that.** `loader.py:84` is `pd.read_csv(..., dtype=str, low_memory=False)`;
`dtype=str` does *not* turn off NA detection, and `"NA"` is in pandas' default
`na_values` list. So the string that leaves the CFPB is not the value that reaches
an aggregation function. Measured live through the shipped public API:

```
$ .venv/bin/python s4_ct_real.py     # scratchpad, 2026-08-04
load_range(2023, 2024, state="CT", limit=500_000)  -> 217,633 rows

=== census_tract ===
  dtype=str   NaN rows: 2023=1,001  2024=1,173
  literal string 'NA' present anywhere: 0        <-- already coerced
  set(unique())          -> |A|=873 |B|=873 INTERSECTION=1 -> empty-intersection check FIRES: False
  set(dropna().unique()) -> |A|=872 |B|=872 INTERSECTION=0 -> FIRES: True
  the shared member(s): ['nan']
  nunique() 2023=872 2024=872      (nunique drops NaN)
  groupby rows 2023=872 2024=872   (groupby drops NaN)
```

**Because `NA` is present in every year, the key sets of any two LAR years are
never disjoint.** The v2 draft's showcase for this check — "intersection=0 … not a
threshold judgement; it is a disjoint partition" — holds only under an unstated
`dropna`. Written the obvious way, the check does not fire on the one case the
document introduced it for.

**The document already contained its own refutation and nobody read it that way.**
§M2.3 reports the CT county Jaccard as 0.056. With 9 codes in 2023 and 10 in 2024,
0.056 is exactly 1/18 — which is arithmetic proof that the intersection is *not*
empty. §M2.3 was quoting the sentinel-*included* figure while §M1.2a two pages
earlier quoted the sentinel-*excluded* one, and the two numbers were describing the
same comparison.

**Two consequences for the build, and the second is the one that bites:**

1. **The filter is `.dropna()`, not a string comparison.** By the time a frame
   reaches an aggregation site the sentinel is already `NaN`. A guard written as
   `df[df.census_tract != "NA"]` is a **no-op** — it matches nothing, because
   nothing equals `"NA"` any more — and would silently reintroduce exactly this
   defect while looking like the fix for it.
2. **The current non-firing is reliable, but it rests on an object-identity
   coincidence.** `nan != nan`, so a set intersection can only find it by identity.
   pandas happens to reuse the `np.nan` singleton, so the intersection is reliably
   `{nan}` — measured identical on 2.2.3 and 3.0.5, across separate `read_csv`
   calls and across `pd.concat`, which is what `load_range` does. If that ever
   stopped being true the same line of code would flip from a silent false negative
   to a spurious false positive. Do not depend on it in either direction; filter
   explicitly.

**Corrections to four figures elsewhere in this document,** each of which was the
sentinel-excluded number presented without saying so. Both readings are now given
wherever the figure appears:

| Where | Was | Sentinel **included** | Sentinel **excluded** |
|---|---|---|---|
| §M1.2a showcase — CT tract keys | 872 / 872, inter 0 | **873 / 873, inter 1** | 872 / 872, inter 0 |
| §M6.7 — VA distinct `county_code`, 2018 | 233 | **234** | 233 |
| §M6.7 — VA distinct `county_code`, 2019 | 145 | **146** | 145 |
| §M6.7 — AK county Jaccard, 2018→2019 | 0.732 | **0.738** | 0.732 |
| §M6.7 — AK county Jaccard, 2019→2020 | 0.806 | **0.811** | 0.806 |
| §M6.7 — AK county Jaccard, 2021→2022 | 0.903 | **0.906** | 0.903 |

The last row was **not** on the list of contaminated figures handed to this
revision. It is the same contamination in the same table, on the one Alaska
transition that is a real boundary rather than sparse-borough noise — found only by
re-running the whole table both ways instead of the two rows that were named.

**The transferable rule, because this is the fourth instance of one shape.**

> **When a number comes back clean, ask what the tool dropped to make it clean.**

An intersection of exactly zero, a Jaccard of exactly 0.000, a set of exactly 872 —
these read as decisive. Each was decisive only because `read_csv` and `groupby`
had already removed the rows that would have made it messy, silently and by
default. The tool did not lie; it was never asked.

This is the same move that found the other three: Connecticut was found by testing
the prompt's stated assumption about county stability, Alaska by testing the v1
draft's replacement claim about 2021→2022, the 2025 data year by asking what the
API was serving that afternoon rather than what the document's year range said, and
the sentinel by asking what `set(unique())` had quietly discarded. **In every case
the finding was behind a premise that looked settled and had never been executed.**

#### ~~The measured limb — scope, and why the frame is the wrong one~~ (struck in v4)

> **Struck because the limb it scopes does not ship** (§M1.2b). The argument below
> is correct as far as it goes — frame scope really is wrong, and Alaska really does
> prove it — but it is an argument about *how* to build an instrument that v4
> removes. It is kept, not deleted, because the Alaska **measurement** in it is
> cited elsewhere (§M2.3, §M6.7, §V3-5) as evidence about the LAR, and because the
> next reader who proposes a frame-level check should find the refutation already
> written. Read the measurement; ignore the specification it recommends.

The v2 draft scoped this check to the whole frame: compare the two years' full key
sets, refuse on an empty intersection. **That scope is wrong independently of the
sentinel**, and Alaska proves it live in the LAR.

```
$ .venv/bin/python s5_percounty.py   # scratchpad, 2026-08-04; keys sentinel-filtered
=== Alaska 2021->2022 ===
  DISJOINT-WITHIN (both sides non-empty, intersection 0): 1
      02105: |A|=1 |B|=1 inter=0
  VANISHING (present in 2021, absent in 2022): 1   ['02261']
  APPEARING (absent in 2021, present in 2022): 2   ['02063', '02066']
  HELD (non-zero intersection): 27
  STATEWIDE frame-level: |A|=164 |B|=172 inter=144 jaccard=0.750
  -> frame-level empty-intersection check FIRES: False
  -> per-county check FIRES: True (on 1 county)
```

`02261` is retired into `02063` + `02066` and `02105` re-schemes, while 27 counties
hold. **A frame-level disjointness check is silent on all of it.** Connecticut is
the degenerate case where the whole state moves at once; *partial* is the general
shape, and the general shape is what a national frame will actually contain.

~~The full specification is in §M1.2b.~~ **v4: note what this block also shows.**
Every event it describes — `02261` retiring into `02063`+`02066`, `02105`
re-scheming — happens at **2021→2022**, the decennial boundary, where both the
tract map and the county map change. The declarative limbs refuse that frame
before any measurement runs. This block was written to choose between two
measured scopes and it never asked whether either was needed.

### M1.2b The check, specified end to end

**One limb, declarative.** v3 specified two and this pass removes the second. The
declarative limb does more work than the v2 draft gave it — enough, as it turns
out, that the measured limb had nothing left to do.

#### Limb 1 — declarative, extended: a tract guard consults *both* maps

**Decision: a tract-keyed guard raises if the frame's years disagree on the tract
basis *or* on the county basis.**

The county code is the first five digits of the tract GEOID. A county-scheme change
is therefore *necessarily* a tract-key change — it cannot be otherwise, because the
prefix is part of the key. So the county basis map already knows everything needed
to refuse Connecticut, and the v2 draft's only mistake was not wiring it into the
tract guard.

This matters more than it sounds, because of what the measurement actually shows:

```
$ .venv/bin/python s5_percounty.py   # CT 2023->2024, keys sentinel-filtered
  DISJOINT-WITHIN (both sides non-empty, intersection 0): 0
  VANISHING  (present 2023, absent 2024): 8   ['09001' ... '09015']
  APPEARING  (absent 2023, present 2024): 9   ['09110' ... '09190']
  HELD: 0
  -> per-county disjointness check FIRES: False (on 0 counties)
```

**Connecticut produces zero disjoint-within counties.** Every old county vanishes
and every new one appears; not one county exists on both sides of the boundary, so
there is nothing for a per-county *intersection* test to compare. The revision brief
for this pass assumed CT would land as "disjoint-within or vanishing" and suggested
the vanishing case "may already be owned by the county basis map." It is owned by
that map — but only if the **tract** guard is specified to consult it, and §M2.1's
table said, at the time this was written, that `lending_by_tract` is guarded by
"tract map + disjointness". (**v4:** §M2.1 now reads "tract map + county map" for
all four tract sites, with the disjointness clause struck.)

**So a naive reading of the redesign — replace the frame-level check with a
per-county one — silently un-guards Connecticut for every tract-keyed operation.**
The tract map says 2023 and 2024 are both basis 2020, and the per-county check finds
nothing to compare. That was the single most important consequence of the v3 pass,
and in v4 it is the whole of the check: **the per-county limb is not merely
insufficient for Connecticut, it is unnecessary everywhere else too.**

Extending Limb 1 also makes the vanishing-county case a *declarative* question
rather than a measured one, which is what keeps it from firing on frames that are
merely unusual. A hand-concatenated frame of Virginia-2022 counties and Ohio-2023
counties has every county vanishing and every county appearing — and must not
raise, because 2022 and 2023 share both bases and the analysis is coherent. Limb 1
distinguishes the two cases on a citation instead of on a shape.

**That last sentence is the whole v4 argument in miniature.** A citation is
auditable, cannot be fitted to a sample, and says the same thing on data nobody has
measured. A shape needs a constant, and the constant needs a sample, and the sample
was the one that motivated the search. Where a citation is available, it wins; where
it is not, §M1.2b's coverage item says so rather than substituting a shape.

> **Build-2 status of the county consult: correct, retained, and with NO LIVE
> CASE.** Removing the uncited 2024 tract entry (§O item 10) made 2024 UNMAPPED for
> tracts, so a CT 2023+2024 tract frame is now refused by the **UNKNOWN rule**
> before the basis comparison is reached — `CONSULTED_MAPS` is iterated for the
> unmapped-year check first. There is no longer any shipped year-pair with
> agreeing tract bases and disagreeing county bases, so nothing exercises this
> limb on the shipped maps.
>
> **This is stated rather than glossed, because "the mechanism that catches
> Connecticut" is a claim this document makes repeatedly and it is no longer the
> operative one.** Every such passage now names the UNKNOWN rule as what fires and
> the county consult as what *would*.
>
> The limb is retained and must not be deleted. It is the only thing that catches
> a county re-scheme at a year whose tract basis is cited and unchanged — the
> configuration build 1 actually shipped, and the configuration that returns the
> instant a human reads the FFIEC vintage and adds a cited 2024 tract entry. The
> test that covers it restores that entry for its duration
> (`test_the_county_consult_still_catches_connecticut_if_2024_is_ever_cited`) and
> says on its face that it is conditional, rather than presenting itself as
> coverage of a shipped path. The Connecticut test that *does* cover the shipped
> path now asserts the UNKNOWN mechanism, and asserts that the basis comparison is
> **not** reached — a test named for a guarantee it does not provide is the
> misdescribed gate this engagement keeps closing.

#### ~~Limb 2 — measured: per-county disjointness~~ — **REMOVED from the 0.6.0 payload**

**Decision: the measured limb does not ship. §O item 8 asked whether it should
ship at all; the answer is no.** The specification below is struck, not deleted,
because the *reasoning* that produced it is sound and a future reader who proposes
this check again should find both the design and the reason it was dropped in one
place.

**Its own scorecard, from the v3 verification, is the argument:**

- Across **16 same-basis year-pairs** in the measured sample it fired **5 times —
  all five false positives**, every one an out-of-state stray county carrying one
  to four rows (§V3-6, §V3-7).
- Every true positive it produced coincided with a basis change **the declarative
  limbs already refuse** (§V3-7, and §V4-2 below extends this to every year-pair,
  not only adjacent ones).
- **Net unique findings: zero.**
- Its ≥10-row floor is, in this document's own words, "stated as a threshold, not a
  derivation" — a constant chosen to separate 4-row false positives from 41-row
  true ones, **on the same sample that produced both**. That is fitting, not
  deriving, and the document said so without drawing the conclusion.

**Why "possible but unobserved" is not enough here.** The limb was justified as a
residual net for a within-county re-scheme at a non-boundary year. Such a thing
could happen. But the case for shipping rests entirely on its not having been
seen, while the costs are all concrete and present: a hand-tuned constant, a 5:0
false-positive record, an untested code path, and a gate whose stated coverage
exceeds anything it has ever caught. **This portfolio has closed that exact shape
five times** — a check whose stated purpose outruns its demonstrated reach — and
this document names that pattern in its own coverage section. Shipping it here
would be the sixth.

The honest alternative is not a weaker check. It is to **say the gap is open**
(coverage item 15) and let the three declarative maps carry the rule.

> **Struck specification follows.** ~~**Decision: scope the check per county, not
> per frame.** Fully specified:~~

1. **Keys are sentinel-filtered before comparison, on both columns.** The filter is
   `.dropna()` on `census_tract` and on `county_code` — *not* a comparison against
   the string `"NA"`, which is a no-op on a loaded frame (§M1.2a). Rows where either
   key is null are excluded from the comparison entirely; they are not a county and
   they are not a tract.
2. **Counties are grouped by `county_code`, not by the tract GEOID's prefix.** The
   two disagree in real data — 3 rows in CT 2020, 7 in VA 2020 (§M6.6) — and
   `county_code` is the column the county guard already uses. One key, one grouping.
3. **Both sides must be non-empty.** A county filter that returns nothing gives
   `|A|=0, |B|=0, intersection=0`, and a naive `len(A & B) == 0` fires. That would
   collide head-on with §M3.3a, which deliberately preserves current behaviour for a
   legitimately empty frame. Empty is not disjoint; it is absent.
4. **Both sides must be at or above a stated row floor.** This one is a threshold
   and is declared as such below.
5. **A county present in one year and absent in the other does not reach this
   limb.** It is a vanishing key, not a disjointness case, and Limb 1 owns it.

**Firing behaviour, measured on every case:**

```
$ .venv/bin/python s9_spec.py        # scratchpad, 2026-08-04; FLOOR=10
--- MUST FIRE ---
OK Connecticut 2023+2024      declarative: True   measured hits: 0        -> RAISES
OK Alaska 2021+2022           declarative: True   measured hits: 1 [02105] -> RAISES
OK Virginia 2021+2022         declarative: True   measured hits: 5        -> RAISES
--- MUST NOT FIRE ---
OK single-year frame (CT 2024 alone)                                       -> silent
OK CT 2022+2023 (same tract basis, same county basis)                      -> silent
OK VA 2019+2020 (sparse strays come and go, no boundary)                   -> silent
OK VA 2020+2021 (no change at all)                                         -> silent
OK hand-concat: VA 2022 counties + OH 2023 counties                        -> silent
OK VA 2018+2019 (out-of-state stray churn, no boundary)                    -> silent
OK AK 2018+2019 (out-of-state stray churn, no boundary)                    -> silent
```

**The row floor, and why the document has to accept a threshold here.** Run with no
floor, the same matrix fails on two cases:

```
$ FLOOR=0 .venv/bin/python s9_spec.py
!! VA 2018+2019   measured hits: 4  [('11001',3,2), ('24033',4,2), ('25017',1,1), ('48113',1,1)]
!! AK 2018+2019   measured hits: 1  [('05005',1,1)]
```

Every one of those is an **out-of-state stray county** in a single-state pull — DC,
Maryland, Massachusetts and Texas counties inside a Virginia fetch; an Arkansas
county inside an Alaska fetch — carrying one to four rows. With so few rows the
observed tract set is a *sample* of the county, not a description of it, and two
samples of a large county naturally miss each other.

This **falsifies a specific claim in the v2 draft**, which held that scoping to the
empty-intersection case made the check presence-robust: "Neither hazard can produce
a zero intersection." Measured, both can, and five counties in ~~six~~ **five**
states do. (**v4 correction:** the per-county measurements in this document were
run over a five-state joint cache — AK, CT, MI, OH, VA. See the v4 finding at the
end of the corrections section; the number of counties is unaffected.)

The separation is nonetheless wide and clean:

```
$ .venv/bin/python s8_strays.py
  FALSE POSITIVES (no boundary): 1-4 rows per county-year   [max 4]
  TRUE POSITIVES  (real recarve): 41-1,032 rows per county-year   [min 41]
```

Any floor in 5..41 gives the same verdicts on this sample. **Ten is stated, and it
is a threshold, not a derivation.** §M6.4's warning is about thresholding on
*Jaccard*, where intuition runs backwards; this is a floor on *presence*, which is a
different quantity and fails in the ordinary direction — too few rows means too
little information. It is recorded as an open item, and the residual exposure is a
real re-carving in a county with under ten loans in a year, which this check will
not see.

**The smallest meaningful county is one tract, and it must not be excluded.** A
one-tract county has an intersection of 0 or 1 and no middle, which invites a rule
excluding it. That rule would be wrong here: `02105` is Alaska's **only**
disjoint-within county, so excluding n=1 would drop the measured limb's entire
Alaska firing. It is also a verified true positive rather than a sparse-data
artefact — `02105000300` holds for four consecutive years and `02105000400` for the
next four, flipping exactly at the decennial boundary, while the other ten
one-tract Alaska boroughs keep their tract ID across it:

```
$ .venv/bin/python s6_ak_detail.py
  02105: 2018=000300 2019=000300 2020=000300 2021=000300
         2022=000400 2023=000400 2024=000400 2025=000400
  all other AK 1-tract counties at 2021->2022: SAME tract id
```

At n=1 the limb is maximally sensitive and maximally fragile: it cannot distinguish
a renumbering from a single misreported record. The row floor is the only thing
standing between those two, and eight years of stability is evidence available to
this document that a runtime check comparing two years will never have.

> **End of struck specification.** Note what the last paragraph concedes: the only
> thing separating the limb's single Alaska true positive from a misreported record
> is the tuned constant. That is the argument for removal, written by the
> specification itself.

#### v4 verification — the declarative limb alone, on every case

The removal is only safe if nothing reopens. Every case in §V3-6's matrix was
re-run with the measured limb deleted from the decision — `fires = declarative`,
full stop. All keys are **sentinel-excluded**: the cache preserves the literal
string `NA` as the CSV carries it, and both `county_code` and `census_tract` are
dropped where it appears, which is the offline equivalent of `.dropna()` (§M1.2a).

```
$ python3 t1_limb2_removed.py        # scratchpad, 2026-08-05
########## LIMB 2 REMOVED — declarative limbs only ##########
--- MUST FIRE ---
OK Connecticut 2023+2024   tract bases=[2020]        county bases=[2020, 2023]
                           DECLARATIVE raise: True   via: county map
                           (limb 2 would have hit: 0)              -> RAISES
OK Alaska 2021+2022        tract bases=[2010, 2020]  county bases=[2010, 2020]
                           DECLARATIVE raise: True   via: tract map + county map
                           (limb 2 would have hit: 1 [02105 41/21])-> RAISES
OK Virginia 2021+2022      tract bases=[2010, 2020]  county bases=[2010, 2020]
                           DECLARATIVE raise: True   via: tract map + county map
                           (limb 2 would have hit: 5)              -> RAISES
--- MUST NOT FIRE ---
OK single-year frame (CT 2024 alone)                               -> silent
OK CT 2022+2023 (same tract basis, same county basis)              -> silent
OK VA 2019+2020 (sparse strays come and go, no boundary)           -> silent
OK VA 2020+2021 (no change at all)                                 -> silent
OK hand-concat: VA 2022 counties + OH 2023 counties                -> silent
OK VA 2018+2019 (out-of-state stray churn, no boundary)            -> silent
OK AK 2018+2019 (out-of-state stray churn, no boundary)            -> silent
########## 10/10 cases correct with limb 2 removed ##########
```

**Alaska is the case that could have reopened this, and it does not.** `02105` was
the measured limb's only Alaska firing, so if the declarative refusal did not cover
it, the removal would cost a demonstrated catch. It covers it, and the reason is
structural rather than lucky: `02105`'s re-scheme happens *at* the decennial
boundary, which is exactly what the tract map declares.

```
$ python3 t2_alaska_and_sweep.py     # scratchpad, 2026-08-05
(a) ALASKA 02105 — every year-pair 2018..2025, sentinel-excluded
  tract ids: 2018-2021 = 02105000300 ; 2022-2025 = 02105000400
  disjoint-within in 16 of 28 pairs — every one of them crosses 2021|2022
  each of those 16 pairs: DECLARATIVE raise = True (tract map + county map)
  AK pairs where 02105 is disjoint-within but declaratively silent: NONE
```

**And the general result, which is stronger than the adjacent-pair scorecard.**
§V3-7 checked adjacent year-pairs. v4 checked **every** pair, adjacent or not, in
every cached state:

```
(b) EXHAUSTIVE SWEEP — every measured hit vs. the declarative verdict
  states = AK, CT, MI, OH, VA        FLOOR = 10
  measured hits, all pairs                                     : 76
    ... on pairs the declarative limbs already refuse          : 76
    ... on declaratively-SILENT pairs (limb 2's unique catch)  : 0
```

Seventy-six firings, zero of them unique. There is no frame in the measured sample
for which removing the measured limb changes a verdict.

#### What the check cannot see — including one gap that is now undefended

Stated plainly, because a check whose stated purpose exceeds its reach is the defect
this engagement has closed five times, and because v4 has just declined to close it
a sixth time by shipping one.

1. **A key replacement inside a single county, at a year where none of the three
   basis maps changes. This is an open, undefended gap.** No map covers it, and as
   of v4 nothing measures it either. A frame containing such a re-scheme would be
   accepted, aggregated, and returned with no raise, no warning and no signal —
   exactly the invisibility §1 calls the whole defect.
   **What is known about it.** It has never been observed: across every year-pair
   in five states over 2018–2025, every within-county key replacement found sat on
   a year-pair where a basis map changes (§V4-2). The three maps are cited (§M1.1,
   §M2.3), so a re-scheme large enough to matter would normally *be* a basis change
   and would be covered.
   **What is not known.** Whether such a case can occur at all. The evidence is
   absence over five states and eight years, which is a narrow sample of a national
   dataset, and absence is not impossibility. **This gap is not defended by
   anything.** It was previously claimed to be covered by the measured limb; that
   limb never caught an instance of it, needed a tuned constant to avoid catching
   the wrong thing, and has been removed. **An honest hole is preferred to a gate
   that has never caught anything** — but it is a hole, it is stated as one, and a
   reader deciding whether they still have a problem after this rule ships should
   count it against the rule.
   *If evidence of an actual instance appears, this is the item to reopen*, and the
   struck specification above is the starting point — with the row floor re-derived
   from that instance rather than fitted to the sample that motivated it.
2. **Key *reuse*, anywhere** — the same GEOID covering different ground. No
   comparison of key sets can see it, by construction; that is §M6.4's whole
   result, and it is the declarative limb's job. Baltimore city 2021→2022 is the
   worked case: Jaccard 0.985 and 18% of rows on re-carved keys.
3. **Counties that are wholly absent from a year.** Nothing can be said about a
   county with no rows; a frame is not a census.
4. **Frames with a fabricated or missing `activity_year`.** The limb keys off it
   (§M4.1, coverage item 9).

Items previously listed here that **no longer apply**, because they described the
measured limb's limits rather than the rule's: ~~a county below the row floor~~
(there is no floor), ~~a re-carving that preserves at least one tract ID~~ (nothing
compares tract IDs any more). Both are now absorbed into item 1 — the gap is
wider than either was, and stating it once and honestly is the point.

### M1.3 The unknown year — the load-bearing case

When 2026 data lands and the mapping has no entry for 2026, what happens?

**Decision: never infer, in either direction — and distinguish two questions the v2
draft conflated.**

> - **Which basis does year Y use?** — needs a citation. Cannot be measured.
> - **Do the years in this frame share a scheme?** — needs only to know whether they
>   are the *same*, which all six guards are the only consumers of.

The v2 draft answered both with one raise, and that was wrong for the second one.

**Decision: the maps carry a third state, `UNKNOWN`.** A year with no entry is
`UNKNOWN`. The rule is:

> **An unmapped year alone in a frame is allowed. An unmapped year pooled with any
> other year raises.**

This asserts nothing whatever about the unmapped year's basis — which is the point,
because measurement cannot establish a basis (§M6.4) and this document will not let
an inference wear a citation's clothes. It also keeps every safety property: two
years cannot be pooled unless both are mapped and agree, so no vintage-spanning
aggregation ever proceeds on a guess.

**It resolves a live contradiction.** The v2 draft's §M1.3 raised on an unmapped
year for *every* tract-keyed operation, single-year ones included, while §M2.2
declared per-year analysis safe because "within a year the key is internally
consistent." Both could not be true. `UNKNOWN` makes §M2.2's declaration hold: a
2026-only frame grouped by tract is exactly as coherent as a 2023-only frame, and
refusing it asserts a problem that does not exist.

It is also the over-refusal §M2.4 rejects a load-time raise for, and the same shape
as the false refusal this portfolio has already shipped once in oz-tracker's
`calculate_benefits()`. A rule that refuses a correct single-year analysis because
a *different* analysis would be wrong is the mistake this document was written to
avoid making.

**What `UNKNOWN` does *not* soften: the ban on inferring a basis.** The relaxation
above is entirely about *scope* — which frames refuse — and changes nothing about
what the map is allowed to contain. An unmapped year stays unmapped until a human
adds it with a citation. The argument for that is unchanged from the v2 draft and
is restated here because `UNKNOWN` makes it easier, not harder, to be lazy about:

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

So: an unmapped year **pooled with another year** raises, and the message says what
a human must do — read the CFPB *Summary of {year} Data on Mortgage Lending*,
confirm the delineation basis, add the entry, cite it in the comment. Adding a year
to this mapping is a deliberate human act with a citation attached, every time. That
is the point.

**Cost, stated plainly, and it is much smaller than the v2 draft's.** Under
`UNKNOWN`, `hmda-analyzer` does not break on the first day a new HMDA year is
served. Single-year analysis on the new year works. What breaks is *pooling* the new
year with an older one, which is precisely the operation nobody can justify until
someone has read the citation. That is the correct cost, and unlike the v2 draft's
version it is one a user cannot route around by reaching for an override, because
there is nothing to override — the narrowing parameter (§M3.3) gives them the
single-year answer directly.

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

Reproduced independently through the package's own endpoint, 2026-08-04:

```
$ for Y in 2024 2025 2026; do curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" \
    "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?years=$Y&states=AK&actions_taken=1,2,3,4,5"; done
  2024: 301 -> .../datasets/2024/filtered-queries/one-year/50bf....csv
  2025: 301 -> .../datasets/2025/filtered-queries/snapshot/50bf....csv
  2026: 400 ->
```

**Under the v2 draft's rule this was a release blocker. Under `UNKNOWN` it is
not.** A map whose last entry is 2024 leaves 2025 `UNKNOWN`, and a 2025-only
tract analysis — the overwhelmingly common thing to do with the current data year —
proceeds normally. Only pooling 2025 with an earlier year refuses, and refusing
*that* is correct until someone has read a citation.

**The citation this document's own rule demands does not exist yet, and may not be
coming.** The CFPB *Summary* series stops at 2023:

```
$ for Y in 2021 2022 2023 2024 2025; do printf "  summary-of-$Y-...: "; \
    curl -s -o /dev/null -w "%{http_code}\n" \
    "https://www.consumerfinance.gov/data-research/hmda/summary-of-$Y-data-on-mortgage-lending/"; done
  summary-of-2021-...: 200
  summary-of-2022-...: 200
  summary-of-2023-...: 200   (published 2024-07-11)
  summary-of-2024-...: 404
  summary-of-2025-...: 404
```

There is no 2024 summary either, which means this may be a **discontinued
publication rather than a pending one** — the document's designated citation source
for per-year basis facts may simply have stopped. The 2025 FIG does not state the
vintage. FFIEC's `cen2025` release notes return HTTP 403 to every automated request
(the Akamai edge block `_http.py` already documents). **Do not substitute inference
for the citation.** The measurements are consistent with 2025 continuing on the 2020
tract scheme and the 2023 county/MSA schemes, and consistency is not a citation;
§M1.3's entire rule is that measurement cannot establish a basis. 2025 stays
`UNKNOWN` until a human finds a source, and §O records the search for one as an open
item rather than a blocker.

**The data-maturity ladder, which the document had not recorded and which changes
what its own commands return.** The API serves three different dataset classes:

```
$ for Y in 2018..2025; do ... done      # redirect target, scratchpad 2026-08-04
  2018: three-year   2019: three-year   2020: three-year   2021: three-year
  2022: three-year   2023: one-year     2024: one-year     2025: snapshot
```

A **snapshot** is pre-resubmission. 2025 counts *will* be revised as filers amend,
and 2023 and 2024 will move from one-year to three-year files. **Every row count in
this document that touches 2023, 2024 or 2025 will therefore return different
output next year**, including the CT 105,543 / 112,090 figures that §M6.5's entire
Connecticut argument is built on. The *finding* is robust — a disjoint key universe
does not become joint on resubmission — but a reader re-running these commands in
2027 and getting different numbers has not found an error.

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
breaks it, and the break is measured, not hypothesised (§M6.5). A *tract*
year→vintage mapping is correct for the delineation basis and still insufficient
for key comparability. The design survives a third vintage; the **tract map alone**
does not survive Connecticut — which is why the tract guard consults the county map
as well ~~, and why §M1.2a pairs the declarative limbs with a measured one rather
than choosing between them~~ (§M1.2b). **v4 strikes the second clause**: §M1.2a no
longer pairs anything with a measured limb. What survives a third vintage is three
declarative maps, each absorbing a new entry, and a tract guard that reads two of
them.

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
| `geographic.py:25` `lending_by_tract` | `groupby("census_tract")` | tract | **tract map + county map** ~~+ per-county disjointness~~ |
| `geographic.py:74` `lending_desert_score` | inherits, then `rank(pct=True)` | tract | **tract map + county map** ~~+ per-county disjointness~~ |
| `geographic.py:108` `racial_composition_by_tract` | `groupby(["census_tract","derived_race"])` | tract | **tract map + county map** ~~+ per-county disjointness~~ |
| `lender.py:52` `lender_summary["unique_tracts"]` | `nunique()` | tract | **tract map + county map** ~~+ per-county disjointness~~ |
| **`geographic.py:51` `lending_by_county`** | `groupby("county_code")` | **county** | **county map** |
| **`lender.py:53` `lender_summary["unique_counties"]`** | `nunique()` | **county** | **county map** |

**The disjointness clause is struck in v4** — the measured limb does not ship
(§M1.2b). Every guard in this table is now declarative, and every one of them
rests on a citation rather than on a shape. **This is the table v3 warned about:**
it read "tract map + disjointness" while the tract guard was not specified to
consult the county map, which would have left Connecticut unguarded. Both halves
of that are now fixed, and in opposite directions — the county map was added, the
disjointness was removed.

**Why the tract sites consult the county map.** The county code is the first five
digits of the tract GEOID, so a county-scheme change is necessarily a tract-key
change. Connecticut 2023→2024 is the case: the tract map says both years are basis
2020, and a per-county disjointness comparison finds **zero** counties present on
both sides to compare. Without the county map in the tract guard, that frame is
completely unguarded for `lending_by_tract`. §M1.2b has the measurement.

`lending_desert_score` is the worst of them: its percentile rank is computed *over
the collapsed tract set*, so the reference distribution every tract is scored
against is corrupted, not only the colliding rows — sized in §M6.1.

**`derived_msa_md` gets no guard site, because it has none to guard.** The sweep
finds zero aggregations on it; it occurs exactly once in the package, in the
schema frozenset. §M2.3 and §M6.6 say what protects the user anyway.

### M2.2 Safe, and explicitly declared safe

**Per-year analysis that never pools across years.** Confirmed. Each year's rows
carry that year's delineation; within a year the key is internally consistent.

**This now holds for an *unmapped* year too, which it did not in the v2 draft.**
§M1.3's `UNKNOWN` state exists so that this paragraph is true without exception: a
2026-only or 2025-only tract analysis is as coherent as a 2023-only one, and the
guard does not refuse it. The v2 draft's §M1.3 raised on any unmapped year for every
tract-keyed operation, single-year included, which contradicted this section
directly. That contradiction is resolved in §M1.3's favour on the question of
authority and in this section's favour on the question of scope.

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
        jaccard vs prior year = 0.056 WITH the 'NA' sentinel  (= 1/18 exactly)
                              = 0.000 without it              <<< KEY UNIVERSE CHANGED
```

**That `0.056` was the tell, and it sat in this document unread for two passes.**
With 9 codes on one side and 10 on the other, a Jaccard of 0.056 is exactly 1/18 —
one shared member — which is arithmetic proof that the intersection is *not* empty.
§M1.2a two pages earlier reported the same comparison as "intersection=0". Both
numbers were correct; they were computed with different, unstated sentinel handling.
§M1.2a has the mechanism and the standing rule that came out of it.

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
  **2023→2024** (Connecticut, jaccard 0.056 with the sentinel included, 0.000
  without — §M1.2a).
- The **MSA** limb has a **basis boundary at 2022 and a second at 2024.** The v2
  draft said it "holds at 2021→2022", which is true as a *measurement* and false as
  a statement about the basis. See below.
- **`state_code`** is not measured to move anywhere in 2018–2025.

**The MSA basis boundary at 2022 — measurement said one thing, the citation says
another, and the citation wins.**

The v2 draft set the MSA map's boundaries from measurement: zero material
reassignments across four states at 2021→2022, code-set Jaccard 1.000/1.000/0.938/
0.857 with both sub-1.000 values traced to single stray rows. Every one of those
figures still reproduces. **They do not mean what the draft took them to mean.**

CFPB, *Summary of 2023 Data on Mortgage Lending*, published 2024-07-11, retrieved
and confirmed verbatim 2026-08-04:

> "the data reflect metropolitan statistical area (MSA) definitions released by the
> Office of Management and Budget in 2020 that became effective **for HMDA purposes
> in 2022**."

So the MSA basis changes at **2022**, on a citation, and the map must say so. The
measurement did not contradict it: **a basis can change without moving any code**,
which is this document's central thesis (§M6.4) applied to MSAs instead of tracts.
OMB's 2020 delineations happened to leave the four measured states' code sets and
county memberships essentially untouched — so the instrument that this document
*proves* cannot see a basis change duly failed to see one. The v2 draft set a
boundary using the one tool it had already established was the wrong tool for the
job.

That is §M6.4's own lesson, applied to tracts and not to MSAs, and it is the third
time in this engagement that a limb was scoped from measurement because the
measurement was the thing available.

**Corroborating citation for the 2024 entry**, verified independently 2026-08-04:
**OMB Bulletin No. 23-01**, *Revised Delineations of Metropolitan Statistical Areas,
Micropolitan Statistical Areas, and Combined Statistical Areas*, issued
**2023-07-21**, which updates and supersedes OMB Bulletin No. 20-01 (2020-03-06) and
is the first delineation to use 2020 Decennial Census data. Applying §M1.1's rule —
boundaries and codes in effect on 1 January of the LAR year — a bulletin issued
2023-07-21 is in effect on 2024-01-01, so its first LAR year is **2024**. That is
the cited rule applied to an *already-published* bulletin, not a prediction of a
future publication, which is the distinction §M1.3 turns on. FFIEC's own adoption
notice was not read (HTTP 403, §O item 3), so this entry rests on Reg C plus the
bulletin, corroborated by CT's planning regions appearing in the 2024 LAR.

So `MSA_CODE_BASIS_BY_YEAR` has boundaries at **2022** (OMB 2020 delineations, per
the CFPB 2023 summary) and at **2024** (OMB Bulletin 23-01) — not the single 2024
boundary the v2 draft measured its way to.

And the structural point, which matters more than any individual exception —
**restated, because the v1 draft got its second half wrong:**

**Key reuse is the dangerous mode. Key replacement is the *less* dangerous one —
not the safe one.** Where keys are replaced, rows fall into disjoint buckets and
the row count visibly inflates. Where keys persist, rows silently merge. That much
holds. But the v1 draft went on to treat replacement as harmless, and §M6.5 now
measures that to be false: CT 2023+2024 pooled produces 1,742 rows where 871 are
expected — visibly wrong — *and* silently corrupts the percentile of **1,695 of
those 1,742 tract-years**, flipping **25** desert verdicts, because
`lending_desert_score` ranks against a reference distribution that doubled.
**Replacement is loud in the row count and silent in every derived statistic.**
That distinction drives §M3.

> **Denominator correction (0.6.0 build 2 review).** This sentence previously read
> "845 of 871 tracts, flipping 25 desert verdicts". That mixes denominators: 845 of
> 871 is the **2023 half** against the **2023 half's** tract count, while 25 is the
> flip count across **both** halves. Recomputed on the same measurement, with one
> denominator throughout: **1,695 of 1,742 tract-years** carry a wrong
> `app_percentile` and **25** carry a wrong `is_lending_desert` verdict. Per half:
> 845/871 (2023) and 850/871 (2024); 11 flips and 14 flips. The aggregate figures
> 384 → 381 and 25 were and remain exact. The old phrasing **understated** the
> harm by roughly half — an accuracy defect rather than a safety one, and one
> that appeared in a shipped harm claim in a fair-lending tool.

~~and it is the reason §M1.2a keeps a measured limb rather than relying on
replacement being self-announcing.~~ **Struck in v4** — this clause was newly false
the moment the measured limb was removed. The point it was making survives without
it: replacement is not self-announcing, which is why it needs an instrument at all.
The instrument is now the **county** basis map consulted by the tract guard, which
is declarative and covers the replacement cases this document has actually measured
(§M1.2b, §V4-2).

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
~~running the disjointness check,~~ formatting the message (§M3.1) — is identical.
(**v4:** the disjointness step is struck; there is no measured limb. The helper is
correspondingly smaller — it reads a year, looks up one or two maps, and formats.
That is the whole of it, and a helper with no measurement in it is a great deal
easier to keep from drifting.)
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
  ... resting on ZERO-land-area slivers   : 1,787     <<< DOES NOT REPRODUCE
      (of those, >=99% same ground        : 1,358)    <<< derived from it
Rule-A calls if AREALAND_PART>0 is filtered: 44,417   <<< DOES NOT REPRODUCE

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

*Defect two: ~~1,787~~ **1,289** flags rest on zero-land-area slivers.* The "≥2
parts" limb counts relationship **rows**, and 3,999 of the national file's rows have
`AREALAND_PART == 0` — a boundary that touches without enclosing any land. Those
rows make a 1:1 tract look like a multi-part one. **The two figures in the block
above (`1,787`, and the `44,417` derived from it) do not reproduce**; measured, the
filter drops **1,289**, leaving **44,915**. The corrected measurement, and why the
subtraction was the wrong way to compute it, are in decision 1 below.

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
   no ground.

   *Corrected counts.* The v2 revision reported this as removing "1,787 of 46,204
   calls", leaving 44,417. Re-running the rule with the filter applied — rather
   than subtracting a separately-counted sliver population from the unfiltered
   total — gives a different answer:

   ```
   $ .venv/bin/python s14_sliver.py         # scratchpad, 2026-08-04
     unfiltered : 46,204          [reproduces the v2 figure exactly]
     filtered   : 44,915          [v2 stated 44,417]
       lost by the filter (U-F): 1,289      [v2 implied 1,787]
       gained by the filter    :     0
     2020 GEOIDs with >=2 rows but exactly ONE live part: 1,733
     recarved GEOIDs having >=1 zero-land-area row      : 3,045
   ```

   1,733 GEOIDs are made to *look* multi-part by zero-area rows, but 444 of those
   are independently RECARVED by the 1%-land-change limb and survive the filter, so
   only **1,289** actually drop out. Neither 1,787 nor 44,417 reproduces under any
   variant tried. Immaterial to every conclusion — §M3.1 makes this metric context
   in a message rather than a trigger — but it is a number in the document and it
   was wrong.

2. **Declare the zero-land-area tracts, rather than letting two sections treat
   them opposite ways.** The ≥99%-same-ground count divides land kept by
   `AREALAND_TRACT_20`. For **63** of the RECARVED 2020 tracts that denominator is
   zero, so the share is `0/0` — and taking it as `1.0` counts a tract with no land
   as *unchanged ground*, in the same code block where decision 1 above has just
   ruled that a zero-land-area part "is not a part". Same edge case, opposite
   treatment, undeclared.

   ```
   $ .venv/bin/python s13_pin.py            # scratchpad, 2026-08-04
     Rule-A RECARVED (national)              : 46,204
       ...whose 2020 tract has ZERO land area:     63
       >=99% same ground, EXCLUDING them     : 19,377  (41.9%)
       >=99% same ground, INCLUDING them as 1.0: 19,440  (42.1%)
   ```

   **Decision: exclude them, for consistency with decision 1 — the figure is 41.9%
   / 19,377.** A tract with no land has no ground to have kept. The difference is
   0.2 points and changes nothing, **which is exactly why it should be stated
   rather than smoothed**: an edge case that does not matter is the cheapest
   possible place to be explicit about a convention, and the 42.1% figure appears
   in a user-facing error message (decision 3 below), where "about 42%" remains
   the honest rounding either way.
3. **Drop the word "materially" from the error message.** It is unearned at the
   1% threshold and the document has no defended threshold to replace it with.
   §M5.1 rejects a crosswalk precisely because proportional allocation is "a
   modelling choice masquerading as a data-cleaning step"; calling a 1%-area
   change "materially different ground" is the same move, made by this document
   about its own number.
4. **The message states the count and names its limits**, in this shape:

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
3. **A test asserts the allowlist mechanism — and it cannot assert the geography
   path, because that path does not exist yet.**

   The v2 revision specified "a test asserts that a geography-vintage refusal
   propagates out of `generate_disparity_report` and `summary_table`". **That test
   cannot be written as specified.** Propagating a geography-vintage refusal
   requires a guarded function to be reachable from the report layer, and none is:
   all five geography imports in `report/generator.py` are dead (§M3.2a's first
   correction — that is what "latent" means). The four guarded `try` blocks wrap
   `denial_rate_by_race`, `disparity_ratio` twice and `denial_rate_by_income_band`,
   none of which is a geography-keyed site.

   What can be written today is a test that monkeypatches one of those disparity
   functions to raise the new exception and asserts it propagates rather than
   landing in a table cell. **That tests the allowlist mechanism, not the geography
   path**, and the difference must be stated in the test's own docstring — a test
   named for an end-to-end guarantee it does not provide is precisely the
   misdescribed gate this document keeps finding.

   The genuine end-to-end test becomes writable the moment someone wires the tract
   section those five imports were staged for, and it should be written *then*, in
   the same change.

**What is and is not enforced, stated plainly.** §M2.4's AST sweep walks
`hmdaanalyzer/**/*.py`, which includes `report/`, but it enumerates *geography-keyed
aggregation sites* — and `report/` has none, so the sweep's expected set is silent
about it. **Nothing enforces the exception allowlist.** A sixth `except Exception`
added to `report/generator.py` tomorrow would swallow the new exception and no test
would fail. Inverting the allowlist (option 2) is still right because it fails safe
— a new swallowing site would have to be written deliberately rather than inherited
by default — but the inversion is a convention, not a gate, and it is not the same
thing as the site-list enforcement §M2.4 buys for the aggregation sites.

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

**Revision (build 2): "no basis" was signalled by an ABSENT column, and an absence
is not a signal.** The draft above specifies what to write when a basis exists and
is silent on what to write when none does. The implementation resolved that by
omitting the column — for the right local reason, since writing `NaN` flips the
column to `float64` (§M4.2) and writing a guess is the defect the module exists to
prevent. But it produced **two distinct epistemic situations with one signal**:

```
UNKNOWN year (2025-only frame)     -> no tract_geoid_vintage column
No activity_year column at all     -> no tract_geoid_vintage column
                                      identical columns, identical shape,
                                      in BOTH the frame and the dict channel
```

"There is a year and nobody has cited its basis" and "there is no year to derive a
basis from" are different facts with different remedies — the first is answered by
a human reading a citation, the second by the caller supplying a year column — and
the artefact could not tell them apart. An absence also reaches the artefact
*unreadably*: a reader who finds no column cannot distinguish it from a column that
was never going to be written.

**Decision: emit an explicit STRING status column, always, one per consulted map.**
`tract_geoid_vintage_status` and `county_code_vintage_status`, taking
`CITED` / `UNKNOWN` / `NO_YEAR_COLUMN`; the dict channel carries the same fact as
`<key>_basis_status`. Three consequences, each deliberate:

- **A string, not a nullable numeric.** No `NaN`-dtype problem, survives
  `pd.concat` and a CSV round-trip unchanged, and asserts no basis.
- **Always present, including `CITED`.** A status column that appeared only in the
  unhappy cases would re-create this exact defect one level up, with *its* absence
  as the signal.
- **The basis column is still omitted rather than `NaN`-filled** when no basis
  exists. The status is what makes that omission *readable* instead of merely
  observable; it does not replace it.

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
code fails this bar. A flag that sets `DataFrame.attrs` also fails it — but **neither of the two
previous drafts got the reason right.**

The v1 draft claimed the marker "evaporates on the first `.copy()` or `.merge()`";
`.copy()` in fact preserves it. The v2 revision corrected that and **repeated the
fault it was correcting**: it reported `attrs` survival as a per-operation property,
listing `pd.concat` under "survives" alongside `.copy()` and slicing. Each operation
was measured in exactly one configuration and the result generalised to the
operation.

Measured in all four configurations, on **1.4.4, 2.2.3 and 3.0.5** — and they are
**not** identical, which is the finding:

```
$ .venv-pd{1.4.4,2.2.3,3.0.5}/bin/python s10_attrs.py    # scratchpad, 2026-08-04

                                          1.4.4   2.2.3   3.0.5
--- .merge() ---
  left HAS attrs, right HAS same attrs    False   True    True     <<< DIVERGES
  left HAS attrs, right has NONE          False   False   False
  left has NONE,  right HAS attrs         False   False   False
  left HAS attrs, right HAS DIFFERENT     False   False   False
--- pd.concat ---
  left HAS attrs, right HAS same attrs    True    True    True
  left HAS attrs, right has NONE          False   False   False
  left has NONE,  right HAS attrs         False   False   False
  left HAS attrs, right HAS DIFFERENT     False   False   False
--- the realistic vintage-spanning case (all three versions) ---
  concat, mismatched attrs: {}          concat, matching attrs: {'basis': 2010}
--- single-operand operations (all three versions) ---
  .copy(): {'basis': 2010}   slicing: {'basis': 2010}   .agg(): {}
```

**On 2.2.3 and 3.0.5, `.merge()` and `pd.concat` follow one rule, not two:**

> `attrs` survives a multi-operand operation **iff every operand carries identical
> `attrs`.**

That restatement matters because **`pd.concat` is the operation that creates the
vintage-spanning frame**, and the v2 draft listed it flatly under "survives". In the
only case that arises in practice — two years carrying two different basis values —
the operands are *not* identical, so `attrs` is dropped there too. The v2 draft had
measured the matching-attrs case and reported it as a property of `concat`.

**On 1.4.4 the rule does not hold: `.merge()` never propagates `attrs` at all**, even
with identical operands. So across the range `pyproject.toml` actually supports
(`pandas>=1.4.0`), this behaviour is not merely fragile — it is **not consistent
between versions**, and a library that depended on it would behave differently for
two users who both satisfy its declared dependency.

**The conclusion is unchanged and is now as strong as it can get:** `attrs` is not a
reliable carrier. It survives only single-operand operations that were never the
risk; it is dropped by `.agg()`; it is dropped by every multi-operand operation whose
operands actually differ — which is all of them, in the situation this design exists
for — and on the floor of the supported range it is dropped by `.merge()`
unconditionally. **This document's position is that no override should ship in v1.**
Ship the narrowing, and let a real user demand more.

*Scope note.* The v2 draft's "identical on pandas 1.4.4, 2.2.3 and 3.0.5" is
**withdrawn for `attrs`** and **upheld for the durability block in §M4.1** — items
1, 2, 3, 4 and 4b were re-run on 1.4.4 in this pass and do reproduce identically.
1.4.4 publishes no wheel for the Python 3.14 interpreter these measurements
otherwise use, so it was tested under Python 3.10 with `numpy==1.26.4` pinned
(1.4.4's wheels are ABI-incompatible with numpy 2.x). That is a different
interpreter, and it is stated because the version matrix is the whole point of the
measurement.

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

**Revision (build 2): a tract aggregation is governed by TWO maps and stamped
one.** The naming rule above is right and was applied too narrowly. `lending_by_tract`
consults `TRACT_GEOID_BASIS_BY_YEAR` *and* `COUNTY_CODE_BASIS_BY_YEAR` (§M1.2b,
§M2.1) — a county-scheme change is necessarily a tract-key change — and wrote only
`tract_geoid_vintage`. That is a column that **under-describes what governed the
output**, which is the same misdescription trap this section is about, in the other
direction: not a name claiming too much, but a stamp claiming too little.

The consequence is concrete and it lands on the escape route this document
*endorses*. §M5.2 option 1 sends a user across the Connecticut boundary to two
panels. Both panels carried `tract_geoid_vintage = 2020` — truthfully, since the
tract basis genuinely agrees — so a `pd.concat` of the two halves the guard had
just refused came out **labelled coherent by its own provenance**. Nothing stops a
user from doing that concat, and nothing in the result said not to.

**Decision: every consulted map gets a column pair on the output** — its basis
year where one can be asserted, and its status always (§M3.3a). A tract
aggregation therefore carries `tract_geoid_vintage` and `county_code_vintage`; a
county aggregation carries `county_code_vintage` only, since the county key
consults one map. The column names come from a single `VINTAGE_COLUMN_BY_KEY`
lookup, so the same fact has one name wherever it is written — a tract output's
county stamp and a county output's county stamp are the same column, which is the
point.

> **Naming note.** The build-2 review specified this column as
> `county_code_basis_year`, matching the **dict** channel's key. It ships as
> `county_code_vintage`, matching the **column** channel's existing name for the
> identical fact on `lending_by_county`'s output. Taking the review's name would
> have given one fact two column names depending on which function produced it —
> the trap this section exists to close. The dict channel keeps
> `county_code_basis_year`, unchanged. The requirement the review was after — the
> two panels' provenance must disagree — is met either way, and is asserted by
> `test_reconcatenating_the_two_endorsed_panels_yields_disagreeing_provenance`.

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

| Key | Basis changes at | Observed to move at | Mode |
|---|---|---|---|
| `census_tract` | 2022 | 2021→2022 (national); 2023→2024 (CT) | reuse; replacement |
| `county_code` | 2022, 2024 | 2021→2022 (AK `02261`→`02063`+`02066`); 2023→2024 (CT) | replacement; replacement |
| `derived_msa_md` | **2022** (cited), 2024 | 2023→2024 (both modes — §M6.6) | reuse **and** replacement |
| `state_code` | — (no map) | not measured to move, 2018–2025 | — |

The MSA row's two columns disagree deliberately: **the basis changed in 2022 and
nothing observable moved**, which is §M2.3's correction and this document's thesis
in miniature — a basis can change without moving a single code.

A user escaping the tract rule by moving up to county lands on a key that moves at
**the same boundary they were escaping**, in Alaska. Moving up to MSA is safe
across 2021→2022 and lands on an unguarded reuse at 2023→2024.

*What makes this option usable in 0.6.0:* the county key is now guarded at both
its sites (§M2.1) by its own basis map. So the advice is no longer "this is safe"
but "this is checked" — a county aggregation that spans a county-basis boundary now
refuses, exactly as a tract one does.

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

**The v1 draft's open item — "the reference-distribution contamination is argued
from mechanism, not sized" — is now closed: the effect is sized, and it lands
harder on the innocent tracts than on the guilty ones.** (That item was numbered
`O-2` in the v1 open-items list. The reference is spelled out rather than numbered
because §O has since been renumbered, and `O-2` now denotes an **open** item; see
the note below.) Three counties with substantial non-colliding populations, 2021
alone vs pooled 2021+2022 (§V-3):

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
enclosing land, which makes ~~1,787~~ **1,289** one-to-one tracts look
multi-part (v3 correction; the v2 figure did not reproduce). §M3.1 has the
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
  precisely: (**v4 note, and it is not a small one — v4 *did* delete that check,
  and on entirely different grounds.** Not because measurement is invalid in
  principle, which this table refutes, but because the measured limb never caught
  anything the three declarative maps did not. The distinction matters: this row
  is still the reason the *declarative* limbs cannot be dropped.)

  | | reuse (same key, new ground) | replacement (new key, same ground) |
  |---|---|---|
  | **Declarative** year→basis map | **detects it** — the basis year changes | **misses it** — CT 2023/2024 share basis 2020 |
  | **Measured** key overlap | **misses it, by construction** — the keys match, so no set comparison can see it | **detects it** — the key sets are disjoint |

  Baltimore city is the reuse case: Jaccard 0.985 says "safe", the map says
  "unsafe", and the map is right. Connecticut 2023→2024 is the replacement case:
  the **tract** map says "safe" and a key-set comparison says "unsafe".
  ~~**Neither instrument dominates. §M1.2a ships both**~~ — and this section is the
  proof that the declarative one cannot be dropped, **not** the proof that the
  measured one must be shipped. **v4 reads that last clause literally and acts on
  it.** Neither instrument dominates *in principle*; in the measured sample the
  declarative one dominates *in fact*, because the third map (county) covers the
  replacement cases the tract map misses. §M1.2a now ships the maps alone, and
  §M1.2b records the gap that leaves.

  **One correction v3 makes to this row.** "The measurement is right" about
  Connecticut was read by the v2 draft as "the measured limb catches Connecticut",
  and that does not follow. A *statewide* key-set comparison catches it; the
  *per-county* limb §M1.2b actually specifies does not, because no CT county exists
  on both sides of the boundary to compare (zero disjoint-within counties). What
  catches Connecticut is the **county basis map**, which is declarative. The
  replacement column above is right that the tract map alone is blind to it; it is
  wrong that measurement is the only remaining instrument.
- **High ID stability is the *more* dangerous case, not the safer one.** Where IDs
  churn, rows fall into disjoint buckets and the tract count visibly inflates.
  Where IDs persist, rows silently merge. Intuition runs backwards here, and any
  reviewer's instinct to "just check how much the tract list changed" must be
  headed off explicitly. **This is an argument against thresholding on Jaccard,
  not against measuring at all** ~~— which is why §M1.2a scopes the measured limb to
  the empty-intersection case, where no threshold judgement is involved.~~
  **v4 amends the trailing clause twice over.** The empty-intersection scope did
  *not* escape a threshold judgement — it needed a row floor, because out-of-state
  strays produce empty intersections too (§M1.2b, correction 27). And measurement
  is no longer shipped at all. The argument in this bullet stands unchanged; it
  simply no longer has a shipped instrument to justify.

### M6.5 Connecticut — a second discontinuity the proposed binding does not describe

Connecticut's `county_code` universe changes completely at 2023→2024 (§M2.3), and
because the county code is the first five digits of the tract GEOID, **every
Connecticut tract key changes with it**:

```
CONNECTICUT -- census_tract GEOID universe by year
  (these are IN-STATE counts: prefix 09*, which also excludes the 'NA' sentinel)
  2018:  825 tracts   prefixes 09001..09015
  2021:  824 tracts   prefixes 09001..09015     jaccard vs 2020 = 0.996
  2022:  872 tracts   prefixes 09001..09015     jaccard vs 2021 = 0.822  <<< the tract boundary
  2023:  872 tracts   prefixes 09001..09015     jaccard vs 2022 = 1.000
  2024:  872 tracts   prefixes 09110..09190     jaccard vs 2023 = 0.000  <<< EVERY KEY CHANGED
```

**Sentinel and stray handling for this table, per the standing rule (§M1.2a).** The
counts above are in-state only. The three readings differ, and the difference is not
uniform across years, so the filter has to be named rather than assumed:

```
$ .venv/bin/python s1_sentinel.py
  CT 2018: raw=835  ex-NA=834  in-state(09*)=825     <-- 9 out-of-state tracts
  CT 2021: raw=825  ex-NA=824  in-state(09*)=824
  CT 2022: raw=874  ex-NA=873  in-state(09*)=872     <-- 1 out-of-state (72141957100, PR)
  CT 2023: raw=873  ex-NA=872  in-state(09*)=872
  CT 2024: raw=873  ex-NA=872  in-state(09*)=872
  CT 2025: raw=873  ex-NA=872  in-state(09*)=872
```

A reader tempted to "correct" 872 to 873 throughout should not: that is right for
2023–2025 and wrong for 2018 and 2022, because those years also carry out-of-state
strays. The **through-the-loader** figures — which are what §M1.2a's showcase and
any shipped check actually see — are 873/873 with the sentinel and 872/872 without.

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
from the *reference distribution*, and pooling doubled it. **1,695 of 1,742
tract-years get a wrong `app_percentile`** — 845 of 871 from the 2023 side and 850
of 871 from the 2024 side — and **25 get a wrong desert verdict**, 11 from the 2023
side and 14 from the 2024 side. That boolean is the one a fair-lending screen acts
on.

State the total with the total's denominator. Every summary of this measurement
elsewhere in the document and in `geographic.py` used to pair the 2023 half's
numerator (845) with the 2023 half's denominator (871) and then the flip count for
both halves (25), which reads as a smaller harm than the one measured.

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

**Consequence for the design.** The *tract* year→basis map cannot see this: CT 2023
and CT 2024 are both basis 2020. The v2 draft concluded that the disjointness check
was therefore what catches it. **That conclusion does not survive §M1.2b.** The
per-county limb finds zero counties present on both sides — every county vanishes
and a different one appears — so it never runs a comparison at all. What catches
Connecticut is the **county** basis map (2020 → 2023), consulted by the tract guard
because the county code is the first five digits of the tract GEOID (§M1.2b,
§M2.1). It remains a demonstrated hole rather than a theorised one, and it belongs
in the coverage section as such — but the instrument that closes it is declarative,
and this section is the justification for extending the declarative limb rather
than for the measured one. **v4 confirms the refusal survives the measured limb's
removal verbatim**: CT 2023+2024 raises via the county map, and the measured limb
contributed nothing to it in v3 either (§V4-1).

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

**What produces those three rows — the v2 draft named the wrong mechanism.** It
attributed them to out-of-state county codes in single-state pulls. That phenomenon
is real, but it is a **2018–2019 artefact and is resolved by 2020**: Virginia's
distinct `county_code` count runs 234 → 146 → 134 across 2018–2020 (sentinel
included), and the out-of-state codes behind it go 100 → 13 → 1. By 2020 there is
essentially nothing left of it, so it cannot explain three rows in CT 2020.

**The actual cause is intra-record geography disagreement**: a row whose
`census_tract` names a different county than its own `county_code`. CFPB derives
`derived_msa-md` from the *tract*, so the MSA follows the tract's real county rather
than the county the filer reported. Measured on the raw CSV, sentinel rows excluded
from both columns:

```
$ .venv/bin/python s5_percounty.py       # scratchpad, 2026-08-04
  CT 2020: 3 disagreeing (county_code, census_tract) pairs, 3 rows of 211,349
      county_code=09001  census_tract=09003473100 (prefix 09003)  rows=1
      county_code=09009  census_tract=09003520501 (prefix 09003)  rows=1
      county_code=09009  census_tract=09007541401 (prefix 09007)  rows=1
  CT 2023: 0     CT 2024: 0     AK 2021: 0
  VA 2020: 5 pairs, 7 rows of 719,179
```

Three rows, and they reconcile **exactly** with the stray counts above. `09003` and
`09007` are both 25540 counties, so all three rows are assigned MSA 25540: one under
reported county `09001` and two under `09009` — which is precisely the
`{'25540': 1}` and `{'25540': 2}` observed. Three rows in 211,349.

This matters beyond the anecdote for two reasons. **First**, §M1.2b's per-county
limb groups by `county_code`, and this is the measured size of the disagreement it
tolerates by doing so — small, but not zero, and it is why that choice is stated
rather than assumed. **Second**, the v2 draft used the wrong mechanism to constrain
the check: out-of-state strays and intra-record disagreement have different
magnitudes, different year profiles, and different fixes, and a check scoped against
the wrong one is scoped against nothing.

It remains the same artefact class the audit correctly declined to file for the
2019→2020 apparent MSA contraction, and the method rule stands: **a key-membership
change is only a delineation change if it moves a material share of the key's
rows.** A single misreported record is indistinguishable from a boundary revision
under a set-difference test, and single misreported records are common.

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

**Re-run both ways, per the standing rule (§M1.2a).** The v2 draft's figures in this
table were the sentinel-*excluded* ones, presented without saying so:

```
$ .venv/bin/python s1_sentinel.py        # full-state files, 2018-2025
=== ALASKA county_code universe by year ===
                    WITH 'NA'        WITHOUT 'NA'
  2018->2019   |A|=36 |B|=37 j=0.738  |A|=35 |B|=36 j=0.732  <<< sparse-borough noise
  2019->2020   |A|=37 |B|=30 j=0.811  |A|=36 |B|=29 j=0.806  <<< sparse-borough noise
  2020->2021   |A|=30 |B|=30 j=1.000  |A|=29 |B|=29 j=1.000
  2021->2022   |A|=30 |B|=31 j=0.906  |A|=29 |B|=30 j=0.903  <<< REAL: 02261 -> 02063+02066
  2022->2023   |A|=31 |B|=31 j=1.000  |A|=30 |B|=30 j=1.000
  2023->2024   |A|=31 |B|=31 j=1.000  |A|=30 |B|=30 j=1.000
  2024->2025   |A|=31 |B|=31 j=1.000  |A|=30 |B|=30 j=1.000

  02261: 2018=168  2019=223  2020=311  2021=323  2022=-    2023=-   2024=-
  02063: 2018=-    2019=-    2020=-    2021=-    2022=158  2023=92  2024=119
  02066: 2018=-    2019=-    2020=-    2021=-    2022=40   2023=26  2024=35
```

The sentinel inflates every Jaccard in this table by adding one member to both
sides. Note that the **2021→2022 row was corrected too** — 0.903 → 0.906 — and it
was *not* among the figures flagged for correction in this revision's brief. It was
found by re-running the whole table both ways rather than only the rows that were
named, which is the standing rule doing its job on its first outing.

Note the two false positives at 2018→2019 and 2019→2020: Jaccard 0.738/0.732 and
0.811/0.806 in years with **no boundary change**, caused purely by low-volume
boroughs having zero rows in one year. This is one of the two measurement hazards
§M1.2b scopes around — and §M1.2b now measures that the *other* one, out-of-state
strays, can produce a zero intersection, which the v2 draft asserted it could not.

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

**A measurement hazard that constrained the disjointness check — and, in the end,
helped sink it.** Single-state pulls carry out-of-state county codes, in volume:

```
$ .venv/bin/python s1_sentinel.py        # VA full-state files, both ways
                WITH 'NA'   WITHOUT 'NA'
  2018:            234          233
  2019:            146          145      | -['04013','06037', ... ,'78010','99999']  (~100 codes)
  2020:            134          133      | -['11001','12061','18019', ...]
  2021:            134          133
```

Virginia does not have 233 counties, still less 234. A `states=VA` fetch contains
rows whose `county_code` is in another state entirely, and the set of such strays
changes every year.

**Two corrections the v2 draft needs here.** First, the counts above were the
sentinel-excluded ones stated as if they were the raw ones (§M1.2a). Second, and
more consequential: **this phenomenon is a 2018–2019 artefact and is essentially
resolved by 2020** — the out-of-state code count runs 100 → 13 → 1 across
2018→2019→2020. The v2 draft used it to explain stray rows in **CT 2020**, where by
then there was almost nothing left of it to explain anything; §M6.6 corrects that
attribution to intra-record geography disagreement.

Where the phenomenon *was* load-bearing is §M1.2b, and there it is worse than the v2
draft allowed. The draft held that scoping the check to an empty intersection made
it presence-robust — "neither hazard can produce a zero intersection". Measured,
out-of-state strays **can and do**: five stray counties across VA and AK produce a
zero intersection at 2018→2019 with no boundary change anywhere. That is why
§M1.2b's per-county limb carried a row floor and why the floor was declared as a
threshold rather than presented as a derivation — **and, in v4, it is a substantial
part of why that limb does not ship at all.** The strays are the entire measured
false-positive record: five firings, five strays, zero real findings. A check whose
only observed output is an artefact of how the CFPB serves single-state pulls is
not measuring the thing it was built to measure.

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
   on live 2023–2024 data: no warning, no exception, no vintage column; **1,695 of
   1,742 tract-years** get a wrong `app_percentile` and **25** get a wrong
   `is_lending_desert` verdict (per half: 845/871 and 850/871; 11 and 14 flips),
   while the aggregate desert count moves only 384 → 381. Per-tract
   `applications` and `denials` are the *only* things that survive intact. §M6.5.
   **What now covers it:** **not** the measured check, which was the v2 draft's
   answer and is wrong. CT produces *zero* disjoint-within counties — every county
   vanishes and a different one appears, so there is nothing for an intersection
   test to compare. What covers it is the **county basis map, consulted by the
   tract guard** (§M1.2b, §M2.1): county basis 2020 ≠ 2023, so the frame refuses
   declaratively, on a citation. Had the redesign simply replaced the frame-level
   check with a per-county one, this case would have become unguarded. **v4:** the
   per-county check is gone entirely and this refusal is unchanged — it never
   depended on it (§V4-1).

2. **The escape route up to county or MSA — the v1 draft named it and did not
   guard it.** §M5.2 option 2 told users to "aggregate to a geography that survives
   the boundary". No such geography exists among these keys. The county key moves
   at **2021→2022** (Alaska) and at 2023→2024 (Connecticut); the MSA key moves at
   **2023→2024**, in both modes. §M2.3, §M6.6, §M6.7.
   **What now covers it:** the county basis map at both county sites (§M2.1);
   §M5.2 option 2 rewritten. The county sites are guarded by the map alone. ~~Note
   the county sites are guarded by the map alone — the per-county disjointness limb
   is a *tract*-key instrument and has nothing to say about a county-key
   aggregation.~~ **v4:** that qualification is moot — every site is guarded by the
   maps alone now.
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
   v1 draft logged this as "argued from mechanism, not sized" in its own open-items
   list. It is sized, and it is worse than the framing "colliding rows are
   corrupted" implies.
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

15. **A within-county key re-scheme at a year the maps call same-basis would pass
    unseen. This is an open, undefended gap, and v4 opened it deliberately.**
    If a county's tract GEOIDs are re-numbered at a data year where none of the
    three basis maps changes, nothing in this design notices. The frame is
    accepted, `groupby("census_tract")` runs, and the user gets a plausible wrong
    answer with no raise, no warning and no vintage signal — which is precisely
    the invisibility §1 identifies as the whole defect.
    **What used to be here.** Through v3 this item said the measured per-county
    limb covered this case. **v4 removed that limb**, so the item is no longer a
    caveat about an instrument's reach; it is a hole in the rule. The reasons are
    in §M1.2b and they are not that the case is unimportant — they are that the
    limb never caught an instance of it (zero unique findings across every
    year-pair measured), fired five times and was wrong all five, and needed a
    row floor fitted to the same sample that produced both classes.
    **The evidence bounding the gap, stated as what it is.** Across every
    year-pair in **five** states (AK, CT, MI, OH, VA) over 2018–2025, every
    within-county key replacement observed sat on a year-pair where a basis map
    changes (§V4-2: 76 measured hits, 76 declaratively refused, 0 unique). Five
    states is a narrow slice of a national dataset, and eight years is a short
    window. **This is an argument from absence** — exactly like coverage item 3's
    for `state_code`, and now standing in the same place: a key that is not
    guarded because nothing has been measured to move it.
    **Why an undefended gap is nonetheless preferred to the limb.** A gate that
    has never caught anything, that carries a constant tuned on its own test
    sample, and whose stated coverage exceeds its demonstrated reach is the exact
    defect shape this engagement has closed five times. Shipping one to cover a
    hypothetical is how the sixth gets written. The gap is real, it is stated
    here, and a reader deciding whether they still have a problem after this rule
    ships should count it against the rule rather than discovering it later.
    **Reopen this if an instance is observed** — not before, and with the floor
    re-derived from the instance rather than from the sample that motivated the
    search. §M1.2b has the struck specification to start from.

16. ~~**Counties below the row floor are not compared at all.**~~ **Struck in v4 —
    there is no row floor, because there is no measured limb.** This item
    described a limitation of an instrument that no longer ships; its substance is
    absorbed into item 15, which is wider. Recorded rather than deleted because a
    reader who remembers "there was a floor" should find out here that it went
    away with the thing it qualified, and not conclude that the floor was raised
    or lowered. §M1.2b, §O.

17. **The `NA` sentinel is a valid reported geography, and every key-set number in
    this document depends on how it was handled.** `census_tract` and `county_code`
    carry the literal string `NA` in every state-year measured; `read_csv` coerces
    it to `NaN`, and `groupby`/`nunique` drop it. Four figures in the v2 draft were
    silently the sentinel-excluded ones. This is not fixed by the guard — it is a
    property of the data and of pandas, and it will contaminate the *next*
    measurement anyone makes unless they follow the standing rule in §M1.2a.
    Rows with a null geography key are excluded from every comparison and are
    therefore **also excluded from every aggregation** — a lending-desert analysis
    of Connecticut 2024 silently omits 1,173 rows, and nothing in the output says
    so. That exposure is out of scope here and is real.

18. **The data-maturity ladder.** 2018–2022 are served as three-year files,
    2023–2024 as one-year files, and 2025 as a **pre-resubmission snapshot**
    (§M1.3). 2025 counts will be revised and 2023–2024 will move to three-year
    files, so every row count in this document that touches those years will
    return different output on a later re-run. The findings are robust to this;
    the numbers are not. A reader who re-runs these commands and gets different
    counts has not found an error.

19. **The 2023→2024 boundary refuses NATIONWIDE for a single-state cause. This is
    deliberate, and it is a real cost.** This item exists because the refusal is
    right and its price was previously unstated, and an unpriced cost is one a
    user discovers by being blocked.

    **The measurement.** Every 2023+2024 tract-level and county-level analysis, in
    every state, refuses — on account of a county change confined to Connecticut.
    Alaska is the clean illustration: the ground is identical on both sides and
    the library refuses anyway.

    ```
    AK 2023 counties=30   AK 2024 counties=30   shared=30   -> UNCHANGED
    AK 2023 tracts=170    AK 2024 tracts=170    shared=168  -> the SAME ground

    lending_by_county: REFUSES -> "...spans more than one county_code basis"
        30 of 30 county_code keys appear in every year present and would be
        merged; they carry 99.8% / 99.9% of rows
    ```

    The message printed that evidence **against itself** and refused anyway,
    leaving a user in Alaska to work out from a shared-key count whether their
    analysis had ever been at risk.

    **Scope, measured across all 51 jurisdictions and 20.7M LAR rows.** Exactly
    **one** state's `county_code` **scheme** changes between 2023 and 2024:
    Connecticut, 8 codes → 9, sharing zero members. Independently corroborated:
    Connecticut is the **sole 2020s entry** on Census's *Substantial Changes to
    Counties and County Equivalent Entities* list (87 FR 34235; §O item 1).

    **A trap in that measurement, recorded because it nearly shipped as a false
    claim.** Three states' county **sets** differ across the boundary, not one.
    SD `46017` (Buffalo County) and TX `48269` (King County) — the sparsest county
    in each state — carry a handful of rows every year 2018–2023, **zero in 2024**,
    and rows again in 2025 (5 and 1). The codes never left the county universe;
    nobody applied for a mortgage there in 2024. This is §M6.7's measured hazard
    exactly — a set comparison reads a low-volume jurisdiction's empty year as a
    boundary change — and it is why the shipped message says **scheme** and not
    **set**. "No other state's `county_code` set changes between 2023 and 2024"
    would have been a shipped claim a user could falsify in one query.

    **Why the refusal stands.** A national key scheme did change. Deciding on a
    user's behalf that their rows are unaffected is the silent inference this
    library exists not to make, and the check that would license it — "does this
    frame contain Connecticut?" — is a measured, per-frame test of exactly the
    kind §M1.2b removed for producing five false positives and zero findings.

    **What was done instead.** The refusal message now prices itself: it names the
    boundary as Connecticut-confined, carries the citation, and gives two exact
    paths — split at the boundary into two panels (§M5.2 option 1, the endorsed
    path, which keeps Connecticut in), or narrow with `vintage=`. Asserted by
    `test_the_nationwide_county_refusal_prices_itself`, and the scope note is
    keyed to its own boundary so a decennial-boundary refusal cannot claim
    Connecticut's measurement.

    **CORRECTION (0.6.0, pre-release).** Through the 0.6.0 build the first of
    those two paths read "exclude Connecticut and re-run
    (`df[df['state_code'] != 'CT']`)", and it does not work. It was written into
    this document, into the shipped `GeographyVintageError` message, into the
    README and into the CHANGELOG's upgrade table without once being executed.

    It cannot work, and the reason is two paragraphs above this one. The basis
    comparison iterates the frame's YEAR SET against the basis maps and never
    inspects `state_code` or `county_code`, so no row filter changes the verdict.
    Measured on a CT+IL 2023+2024 frame: after excluding every Connecticut row,
    `lending_by_county` still refuses (spans more than one `county_code` basis)
    and `lending_by_tract` still refuses (pools 2024, for which no cited
    `census_tract` basis exists).

    The remedy was incompatible with the design from the start. **Coverage item
    19 rejected state-scoping precisely because a verdict that depends on which
    rows a frame contains lets a user disarm the guard by subsetting** — and the
    "why the refusal stands" paragraph above says so in as many words. So the fix
    is to delete the remedy, not to make the guard honour it; making the guard
    honour it would implement the exact design coverage item 19 refused.

    Replaced by the two paths that were executed and do work on both call paths:
    split-at-the-boundary, and `vintage=` narrowing. The refusal message now also
    states positively that filtering the frame is not a way through, so the next
    reader does not re-derive the same wrong idea from first principles.

    **How it survived to the release candidate.** README:174 was inside a
    `# docs-check: skip` block — the gate extracts symbols from skipped blocks
    and never executes them, which is a limitation `docs-check.toml` documents.
    It is recorded there now as a demonstrated gap rather than a theoretical one.

    **What state-scoping the county map would have cost, since it is the obvious
    alternative and it is not free.** It would mean `COUNTY_CODE_BASIS_BY_YEAR`
    becoming `{year: {state: basis}}`, and with it: a guard that must read
    `state_code` (a column no guarded aggregation currently requires, and which
    §M6.7 measures as carrying out-of-state strays in single-state pulls); a
    per-state default for the 49 states with no entry, which is an argument from
    absence promoted to a lookup value; and a rule whose verdict depends on which
    rows a frame happens to contain rather than on which years it spans — so the
    same two years would refuse or not depending on filtering, and a user could
    turn the guard off by subsetting. The declarative rule's whole property is
    that its verdict is a function of the years alone. That is worth more than the
    over-refusal it costs, and the over-refusal is now visible and actionable
    rather than merely suffered.

20. **A fabricated *plausible* `activity_year` still defeats the guard — and two
    ways of having NO usable year no longer do.** The guard derives every basis
    from `activity_year` and has nothing else to check it against, so a frame
    carrying `2023` on rows that are really 2024 is undetectable here. That much
    was already stated (item 9) and is unchanged.

    **What was NOT stated, and shipped in build 1, is that `_years_in` did not
    see the column it was reading.** Two live bypasses, both closed in build 2,
    both recorded because the second is worse than the first and was not in the
    review that found the first:

    - **Null years were dropped before parsing.** `_years_in` called `.dropna()`
      first, so `NaN`-year rows were invisible to the guard and were pooled in
      silently — while a non-numeric *string* in the same cell correctly became
      UNMAPPED and blocked pooling. Two spellings of "this row has no usable
      year", opposite safety outcomes.

    - **A `float64` year column discarded every REAL year.** This is the one that
      matters. A single blank `activity_year` cell is enough to make `read_csv`
      hand back `float64`; every year then reads `2021.0`; `int("2021.0")` raises;
      **every** year collapsed to `None`; the `None`s deduped to a single unmapped
      year; and the guard let a **2021+2022 decennial-spanning frame** through as
      a coherent single-year analysis. A silent wrong answer of exactly the class
      this module exists to prevent, reached by one empty cell — and note that
      fixing the null case *alone* would not have closed it, because it was the
      real years being discarded, not the null.

      The same `astype(str)` comparison broke `vintage=` narrowing on such a
      frame: `'2021.0'` was offered where `'2021'` was wanted, nothing matched,
      and a perfectly answerable narrowing raised the message reserved for a
      malformed question.

    Both are closed by one parser (`_parse_year`) that every year comparison in
    the module now goes through, with the dtype matrix asserted
    (`float64`/`Int64`/`object`/`int64`/`string` must all yield the same verdict).
    **The general lesson is the one worth carrying:** a guard that reads a column
    is only as good as its parse of that column, and the parse is a place a gate
    can be vacuous without any test noticing — all 176 tests passed with both
    bypasses live.

---

## Corrections to the recon and to the commissioning prompt

Recorded because they are load-bearing, and because ~~ten~~ **twenty** prompts in
this engagement have carried factual errors that surfaced only when a session
executed them. **Every session told to hunt for what its own prompt did not know
has found one** — Connecticut, Alaska, the 2025 data year, the `NA` sentinel, the
per-county limb never firing on Connecticut at all, and now the state count behind
every per-county measurement in this document.

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
    ground with the same-numbered 2010 tract, and ~~1,787~~ **1,289** flags rest on
    zero-land-area slivers (v3 correction 33 — the v2 figure did not reproduce).
    The word is retired and the `AREALAND_PART > 0` filter is added.
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
(measured ~~1,787~~ **1,289** nationally — see correction 33) — both are scope
differences rather than errors, and both point the same way as the audit's
conclusion.

**And the thing THAT prompt did not know existed: the 2025 data year is already
served.** §M1.3 argued the unmapped-year raise entirely in the future tense —
"when 2026 data lands", "in 2032" — and treated the resulting breakage as a cost to
be accepted later. The CFPB API returns a complete 2025 snapshot today: 19,621
Alaska rows, 123,752 Connecticut rows, `activity_year='2025'`. It was found by
asking what the API was actually serving rather than by reading the document's
year range — the same move that found Connecticut and Alaska. §M1.3, §O.

**Against the v2 revision** (this pass's findings):

24. **The `NA` sentinel invalidated §M1.2a's showcase for its own check.**
    `census_tract` and `county_code` carry the literal string `NA` in every
    state-year measured, ~~40 of 40~~ **39 of 39** (v4 count correction, denominator
    only); `read_csv` coerces it to `NaN` and `groupby`
    drops it. Through the shipped loader, CT 2023 vs 2024 has key-set intersection
    **1**, not 0, so the empty-intersection check the section was introducing does
    **not** fire on the one case it was introduced for. Four figures corrected, a
    fifth (AK 2021→2022, 0.903 → 0.906) found by re-running the whole table rather
    than the named rows. §M1.2a.
25. **The document contained its own refutation for two passes.** §M2.3's CT county
    Jaccard of 0.056 is exactly 1/18 over 9 and 10 codes — arithmetic proof of a
    non-empty intersection — sitting two pages from §M1.2a's "intersection=0".
    Neither number was wrong; the sentinel handling was unstated and different.
26. **Frame-level disjointness was the wrong scope, independently of the
    sentinel.** Alaska 2021→2022 has one disjoint-within county, one vanishing and
    two appearing while 27 hold; statewide intersection is 144, so a frame-level
    check is silent. §M1.2b.
27. **"Neither hazard can produce a zero intersection" is false.** §M1.2a claimed
    the empty-intersection scope made the check presence-robust against
    out-of-state strays and sparse keys. Measured, five stray counties across VA
    and AK produce a zero intersection at 2018→2019 with no boundary change. The
    per-county limb needed a row floor, and the floor was a threshold — **which v4
    followed to its conclusion: the limb does not ship.** §M1.2b.
28. **The MSA map's boundaries were set by measurement.** §M2.3 said the MSA limb
    "holds at 2021→2022", true as a measurement and false as a basis claim. CFPB's
    *Summary of 2023 Data* states the OMB 2020 definitions "became effective for
    HMDA purposes in 2022". The one instrument this document proves cannot see a
    basis change was used to locate one. §M2.3.
29. **The stray-row mechanism was misattributed.** §M1.2a blamed out-of-state codes
    in single-state pulls for stray MSA rows in CT 2020; that phenomenon is a
    2018–2019 artefact (VA out-of-state codes 100 → 13 → 1). The actual cause is
    intra-record geography disagreement — 3 CT 2020 rows whose `census_tract` names
    a different county than their `county_code`, which reconcile exactly with the
    observed strays. §M6.6.
30. **The `attrs` fix repeated the fault it was correcting.** §M3.3 listed
    `pd.concat` under "survives" on a single measurement of the matching-attrs
    case. `.merge()` and `concat` obey one rule on 2.2.3+ — survive iff all operands
    carry identical attrs — and `concat` is the operation that creates the
    vintage-spanning frame, where the operands differ by construction. §M3.3.
31. **§M1.3 and §M2.2 contradicted each other.** §M1.3 raised on an unmapped year
    for every tract-keyed operation including single-year ones; §M2.2 declared
    per-year analysis safe. Resolved by the `UNKNOWN` third state. §M1.3.
32. **Two stale `O-2` references had the document declaring an open release blocker
    closed.** v1's `O-2` was the unsized contamination; v2's `O-2` is the county/MSA
    map assignments. §M6.1 and coverage item 6 both pointed at the number.
33. **The zero-land-area edge case was decided two ways in one code block**, and
    `1,787` / `44,417` do not reproduce (measured 1,289 / 44,915). §M3.1.
34. **§M3.2a specified a test that cannot be written.** An end-to-end propagation
    test needs a guarded function reachable from the report layer; all five
    geography imports there are dead. §M3.2a.

**And the thing THIS prompt did not know existed: the per-county check does not
fire on Connecticut at all.** The brief for this revision stated that "every CT
county prefix changes, so every county is either disjoint-within or vanishing", and
asked which. Measured, it is *entirely* vanishing — **zero** disjoint-within
counties — so the per-county disjointness limb contributes nothing to the case it
was redesigned around. The brief also suggested the vanishing case "may already be
owned by the county basis map"; it is, but only once the **tract** guard is
specified to consult that map, which §M2.1 did not say. A redesign that swapped
frame scope for county scope without that change would have left Connecticut
2023→2024 unguarded for every tract-keyed operation — a regression introduced by
the fix for a different hole. §M1.2b.

**Against the v3 revision** (this pass's findings):

35. **The measured limb's scorecard was its verdict, and v3 read it as
    discomfort.** §O item 8 laid out zero unique findings, five false positives and
    a fitted constant, then concluded "this document ships it and records the
    discomfort rather than resolving it". Every fact needed for the decision was
    already on the page. What was missing was the willingness to let a scorecard
    that bad be dispositive. **v4 removes the limb.** §M1.2b, §O item 8.
36. **"Any floor in 5..41 gives the same verdicts on this sample" was offered as
    reassurance and is the opposite.** A constant whose defensible range is
    established by the same sample that produced both classes it separates is
    fitted, not derived. The document said "a threshold, not a derivation" and
    then treated the wide separation as if it repaired that. It does not: a wide
    separation on n=5 false positives and n=6 true ones is a small-sample
    observation, not a bound. §M1.2b, §O item 7.
37. **The document's own transferable rule was not applied to its own gate.**
    §"What this rule does not protect against" opens by stating that "every gate in
    this portfolio that misdescribed its own coverage became a defect later", and
    §M1.2b's coverage list opened by conceding the limb "has not caught anything
    the declarative limbs miss". Those two sentences, three pages apart, are a
    finding. Neither v3 pass joined them.
38. **The count of contaminated state-years was the file count, not the
    state-year count.** "40 of 40" included `rel2020.txt`, the Census relationship
    file, which is not a state-year. The correct figure is **39 of 39**. The
    sentinel claim — present in every state-year measured — is unaffected. §M1.2a.

**And the thing THIS prompt did not know existed: every per-county measurement in
this document was run over FIVE states, not six.** The document says "sixteen
adjacent year-pairs in six states" in four places, and the commissioning prompt for
this pass repeated it. Measured, the joint `(county_code, census_tract)` cache that
every per-county figure derives from holds **AK, CT, MI, OH, VA** — 29 state-year
files. **North Carolina is in the sentinel cache and not in the joint cache**, so
NC contributed to the six-state sentinel sweep and to nothing else.

**The arithmetic proves it independently of the file listing, which is how it was
confirmed rather than assumed.** NC is cached for 2018–2024, which contributes four
same-basis adjacent year-pairs (2018→2019, 2019→2020, 2020→2021, 2022→2023). Had NC
been in the sample, the scorecard would read **twenty** same-basis pairs, not
sixteen. The figure the document reports — 16 — is consistent only with five
states. This is the same move that caught the CT county Jaccard of 0.056 being
exactly 1/18 (correction 25): **a stated count and a stated denominator that cannot
both be true.**

**What it changes, and what it does not.** It does not change the decision — the
limb's net unique findings are zero over five states exactly as they were over the
claimed six, and v4's exhaustive sweep re-confirms it across every year-pair (§V4-2).
What it changes is the *strength of the absence argument* now carried by coverage
item 15. The undefended gap rests on five states over eight years, not six, and
coverage item 15 says five. **A gap justified by "never observed" is only as good
as the sample**, and the sample was one state and four year-pairs smaller than the
document claimed.

---

## O — Open items

**Release blockers for 0.6.0:**

1. ~~**The county map's full year→basis assignments still need a citation per
   entry.**~~ **CLOSED in build 2.** Both change records were located and read, and
   both are now cited per entry in `COUNTY_CODE_BASIS_BY_YEAR`:

   - **Alaska.** U.S. Census Bureau, *Substantial Changes to Counties and County
     Equivalent Entities: 1970-Present*, 2010s list, retrieved 2026-08-05:
     "Valdez-Cordova Census Area, Alaska (02-261): Split to form Chugach Census
     Area (02-063) and Copper River Census Area (02-066) **effective January 02,
     2019**."
   - **Connecticut.** Census Bureau, *Change to County-Equivalents in the State of
     Connecticut*, **87 FR 34235** (2022-06-06), FR Doc. **2022-12063**: "**By
     2024**, all Census Bureau operations and publications, both internal and
     external, will use the nine new county-equivalent boundaries, names, and
     codes, except for 2020 Decennial Census data publications and other datasets
     referencing the eight legacy counties as published before June 1, 2022." It is
     the **sole 2020s entry** on Census's *Substantial Changes* list.

   **The citations close the item. They also produce a negative result that is
   worth more than the closure, and it must not be lost:**

   > **Reg C plus a published change does NOT determine the LAR's key scheme.**
   > Alaska's split is effective **2019-01-02**. REG_C_COMMENT — "the boundaries
   > and codes in effect on January 1 of the calendar year covered by the
   > register" — therefore predicts it appears in the **2020** LAR. Measured
   > across full-state AK pulls, 2018–2025:
   >
   > ```
   >   LAR year   02261    02063    02066
   >    2018        168        0        0
   >    2019        223        0        0
   >    2020        311        0        0
   >    2021        323        0        0      <- Reg C predicts the split by now
   >    2022          0      158       40      <- the LAR actually adopts it here
   >    2023          0       92       26
   >    2024          0      119       35
   >    2025          0      131       48
   > ```
   >
   > **The LAR adopted it two years after the cited rule alone would put it.**
   > What the LAR follows is the **FFIEC census file's vintage**, which lags the
   > Census effective date by an amount neither the rule nor the change notice
   > predicts.

   So the *boundary locations* in the county map remain LAR measurement even now
   that the changes are cited, and the entries say so rather than letting the
   citation appear to cover the adoption year too. This is also the empirical
   ground for §O item 10: it is the same reasoning the removed 2024 tract entry
   rested on, falsified in the one case this package can check.

**Downgraded from a release blocker by this revision:**

2. **The 2025 entry's citation.** Under the v2 draft's rule, a map ending at 2024
   raised on the current data year on release day, making this a blocker. §M1.3's
   `UNKNOWN` state removes that: 2025 is simply unmapped, single-year 2025 analysis
   works, and only pooling 2025 with another year refuses. **The citation is still
   wanted and still absent** — and the search is now less promising than it looked,
   because the CFPB *Summary* series stops at 2023 with no 2024 edition, so this may
   be a discontinued publication rather than a pending one (§M1.3). A human should
   look for an FFIEC equivalent. It no longer blocks the release.

**Still open, not blocking:**

3. **FFIEC's operational adoption notice was not read** (HTTP 403 from
   `ffiec.gov` and `geomap.ffiec.gov` to every automated request, both sessions).
   The binding does not depend on it, but a human with a browser should confirm
   it and either add it to §M1.1 or record that it says nothing new.
4. **Whether any override should exist at all.** §M3.3 says no for v1 and states
   the minimum bar if a reviewer disagrees.
5. ~~**The disjointness check's threshold beyond the empty-intersection case.**~~
   **Closed in v4 by removal, not by an answer.** There is no disjointness check,
   so there is no threshold to extend. The underlying question — whether *any*
   partial-overlap threshold on key sets can be defended given §M6.4's proof that
   intermediate Jaccard means the opposite of what intuition says — is still
   unanswered, and is now a question about a hypothetical future instrument rather
   than about a shipped one. If item 8's gap is ever reopened, this is the first
   thing that has to be settled.
6. **The 2019→2020 apparent MSA contraction remains unexplained and is
   deliberately not filed.** Large apparent drops appear in every state
   (CT code-set jaccard 0.545 at that boundary, OH 0.357). They trace to the `'0'`
   sentinel present in 2018–2019 and to out-of-state metropolitan-division codes
   appearing in single-state pulls. That is enough to decline to call it a
   delineation change and not enough to say what it is. **Reopening it needs a data
   question answered first — what the `'0'` sentinel meant and why it stopped —
   not a methodology paragraph.**
7. ~~**The per-county row floor is a threshold and wants a better argument.**~~
   **Closed in v4 by removal.** The floor never got a better argument, and that is
   most of why the limb it belonged to is gone. Recorded verbatim for the next
   reader, because the shape is the lesson: *"any floor in 5..41 gives the same
   verdicts on this sample"* is a description of a constant fitted to its own test
   set. The sample was **five** states, not the six this item previously claimed
   (see the v4 finding in the corrections section).

8. **Whether the measured limb should ship in 0.6.0 at all. — ANSWERED IN v4: no.**
   ~~This document ships it and records the discomfort rather than resolving it.~~
   It produced zero findings the declarative limbs do not already produce, and five
   false positives before the floor was added (§M1.2b, coverage item 15). The case
   for shipping it was that key *replacement* within a county at a non-boundary
   year is a real possibility that no map covers; the case against was that a check
   with no demonstrated catch is a maintenance surface and a source of user-visible
   refusals.
   **The case against wins, and the reason the v3 draft could not see it is worth
   naming.** v3 weighed a concrete cost against a hypothetical benefit and called
   the result "discomfort". That is not a tie. An argument from absence supporting
   a *gap* (coverage items 3 and 15) is honest; the same argument supporting a
   *gate* is not, because the gate has costs that the gap does not — a tuned
   constant, an untested path, and a user-visible refusal that has so far only ever
   been wrong. **Recording discomfort is not a decision.** v4 makes the decision:
   the limb does not ship, and the gap is stated (coverage item 15).

9. **Rows with a null geography key are silently dropped from every aggregation.**
   Connecticut 2024 has 1,173 such rows in `census_tract` and 1,101 in
   `county_code`; `groupby` and `nunique` drop them by default and no output says
   so. This is a live, shipped, unrelated defect that the sentinel investigation
   surfaced (coverage item 17). It is out of scope for this document and should be
   filed separately.

10. **The 2024 tract entry was REMOVED, and what a future one must be founded on.**
   Build 1 shipped `TRACT_GEOID_BASIS_BY_YEAR[2024] = 2020`. Build 2 deletes it.
   2024 is now UNKNOWN in the tract map, and §M1.3's rule applies uniformly to
   2024 and 2025.

   **Why it went.** The entry was uncited — the CFPB *Summary of ... Data* series
   stops at 2023 — and rested instead on REG_C_COMMENT plus "the Census Bureau
   published no new tract delineation between the 2020 Census delineations and
   2024-01-01, so the boundaries in effect on January 1 of 2024 are the 2020
   ones." **That premise is wrong at the granularity HMDA actually keys on.** It
   argues continuity of the 2020 decennial *delineation*, which is true and is not
   the question. HMDA tract codes follow the **FFIEC census file**, which adopts a
   Census **geography vintage per year** — the 2024 file uses 2023 geographies. A
   year can keep the 2020 delineation and still change file vintage, and the tract
   GEOID is what the file carries.

   **And the entry's reasoning is falsified empirically, not only in principle.**
   §O item 1 measures the Alaska county split adopted by the LAR **two years after**
   the "in effect on January 1" rule would place it. "The change was published
   before January 1, therefore the LAR uses it" is the exact inference the 2024
   tract entry made, and it is measurably wrong in the one case this package can
   check.

   **The FFIEC question is OPEN and is what a future entry must be founded on.**
   `ffiec.gov` returns HTTP 403 to every automated request (§O item 3), so the
   FFIEC Census FAQ could not be read directly this session. Secondary sourcing is
   not a citation and **must not become a map entry**. A human with a browser
   should read the FFIEC census-file documentation for 2024, record which Census
   geography vintage that file adopts, and add the entry with that as its
   citation — not with a decennial-delineation argument, and not with a Reg C
   argument.

   **Removal costs nothing, measured.** Over every distinct year-pair in 2018–2025
   (28 pairs), the map with the entry and the map without it accept **the same
   seven pairs**, at both guarded keys — the removal changes no refusal decision
   anywhere. It is asserted as a test
   (`test_removing_the_2024_tract_entry_changed_no_refusal_decision`), so it fails
   if it stops being true. In the **narrowing** path removal is a net **accept**:
   `vintage=2020` on a 2022+2023+2024 frame used to select all three years and then
   refuse on the county map, and now selects the two coherent years and answers.

   **What removal costs that is not a refusal decision, stated because it is
   real.** The tract guard's county-consult limb (§M1.2b, §M2.1) now has **no live
   case**: with 2024 unmapped, no shipped year-pair has agreeing tract bases and
   disagreeing county bases, so Connecticut 2023+2024 is caught by the UNKNOWN rule
   instead — `CONSULTED_MAPS` is iterated for the unmapped-year check before the
   basis comparison is reached. The limb is not dead code and must not be deleted:
   it is the only thing that catches a county re-scheme at a year whose tract basis
   is cited and unchanged, which is precisely what happens the moment someone adds
   the 2024 entry back with a real citation. It is exercised by a test that restores
   the entry for its duration
   (`test_the_county_consult_still_catches_connecticut_if_2024_is_ever_cited`), and
   that test is honest about being conditional rather than presenting itself as
   coverage of a shipped path.

   **What removal gains besides correctness.** UNKNOWN stops being machinery with
   nothing to do. Before build 2 it had exactly one instance (2025); it now has two
   in the tract map, and the inconsistency the audit found — 2024 cited-by-argument
   while 2025 was UNKNOWN on the same evidence — disappears.

**Closed by this revision:**

- ~~The reference-distribution contamination is argued from mechanism, not
  sized.~~ Sized on three counties; see §M6.1 and coverage item 6. The effect is
  near-total on percentiles and directional on verdicts.
- ~~Whether this document belongs in `docs/` or in `hmdaanalyzer/methodology/`.~~
  Moved, with the packaging evidence in correction 7.
- ~~Drift between four independent guards.~~ One helper called from N places, plus
  an AST test asserting set equality over the site list. §M2.4.
- ~~The unmapped-year raise makes 0.6.0 unshippable against a served 2025.~~
  Resolved by the `UNKNOWN` third state, which also removed a contradiction between
  §M1.3 and §M2.2. §M1.3.
- ~~The MSA basis map's boundaries rest on measurement.~~ Both boundaries now carry
  citations: 2022 from CFPB's *Summary of 2023 Data*, 2024 from OMB Bulletin 23-01.
  §M2.3.
- ~~The disjointness check is scoped to the whole frame.~~ Rescoped per county,
  with the declarative limb extended to the county map — which is what actually
  covers Connecticut. §M1.2b.

**Closed by v4:**

- ~~Whether the measured limb should ship (item 8).~~ It does not. Zero unique
  findings, 5:0 false positives, a fitted constant. §M1.2b.
- ~~The per-county row floor's argument (item 7)~~ and ~~the disjointness
  threshold beyond empty intersection (item 5).~~ Both dissolved with the limb.
  Neither was answered; both stopped being questions this release has to answer.
- **Opened by v4, in exchange:** the within-county re-scheme at a same-basis year
  is now an undefended gap rather than a claimed coverage. It is *not* listed as
  an open item here, because there is no work pending on it and nothing to
  decide — it is a stated limitation of the shipped rule (coverage item 15). It
  becomes an open item again only if an instance is observed.

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
| V-7 | Recarved rule vs a stricter overlap test | `r3_recarve.py`, `r3_natl.py` | Rule A **never under-flags** (0 misses, 5 counties); nationally 46,204 calls, **42.1% ≥99% same ground**, ~~**1,787 on zero-area slivers**~~ **SUPERSEDED by V3-15 — measured 1,289**; row-weighted A vs B: Fayette PA 99.9%/16.0%, Cook 15.6%/1.2%, Baltimore 18.2%/8.0% |
| V-8 | Narrowing degenerate cases | `r6_narrowing.py` | empty → 0 rows / `{}` / no raise / no warning; single tract → `app_percentile` 100.0; **flag unreachable for n ≤ 4**; `.agg()` drops a carried `tract_geoid_vintage` |
| V-9 | Geography-key site inventory | `ast_sweep.py` | **6 sites**: 4 tract, 2 county, **0 MSA**, 1 state; `derived_msa_md` occurs once in the package, in `EXPECTED_LAR_COLUMNS` |
| V-10 | Packaging | `git clone` + `python -m build` from a clean tree | Neither sdist nor wheel contains the tract-vintage document (0 occurrences); `cra_proxy_methodology.md` ships in both |
| V-11 | 2025 data year | CFPB Data Browser API | **2025 is served**: AK 19,621 rows, CT 123,752 rows, `activity_year='2025'`; 2026 returns HTTP 400; tract jaccard 2024→2025 = 0.977 (AK) / 0.998 (CT) |
| V-12 | CFPB header stability + `'0'` sentinel | header line of each full-state CSV | 99 columns every year **2018–2025**; `derived_msa-md` `'0'` present 2018–2019, absent 2020–2025 |
| V-13 | Reg C commentary, re-fetched | `consumerfinance.gov/rules-policy/regulations/1003/4/` | Comment 4(a)(9)(ii)(C)-1 confirmed **verbatim**, independently of v1 |

| V-2 | ~~pandas durability, three versions~~ **`attrs` row SUPERSEDED by V3-8** | `r4_pandas.py` | The durability items (1, 2, 3, 4, 4b) reproduce on 1.4.4 / 2.2.3 / 3.0.5 and stand. The `attrs` row's "identical across three versions" is **withdrawn** — `.merge()` diverges on 1.4.4. See V3-8 |

**v3 program (2026-08-04).** All commands run from the
`docs/tract-vintage-methodology` branch at `f2de703`, in scratch virtualenvs
outside the repo. **No repository code was modified and no `.py` file was
touched.** Scratch scripts live in the session scratchpad, not in the repo, per
scope. Data is full-state CFPB Data Browser CSVs — no `limit` truncation anywhere,
per coverage item 13. **Every key-set measurement below was run both with and
without the `NA` sentinel**, per §M1.2a.

| # | What | Command | Established |
|---|---|---|---|
| V3-1 | The `NA` sentinel, raw CSV | `s1_sentinel.py` (reads via `csv.reader`, so `NA` survives) | Literal `NA` present in `census_tract` **and** `county_code` in ~~40 of 40~~ **39 of 39** state-years (v4 recount), **6 states** — AK, CT, MI, NC, OH, VA — 2018–2025. CT 2023 = 1,001 tract rows, CT 2024 = 1,173 |
| V3-2 | The sentinel through the **shipped** loader | `s4_ct_real.py` → `load_range(2023,2024,state="CT")` | `read_csv(dtype=str)` coerces `NA`→`NaN`; **literal `'NA'` present: 0**. `set(unique())` → 873/873, **intersection 1**, check does **not** fire; `set(dropna().unique())` → 872/872, intersection 0, fires. `nunique`/`groupby` both drop it |
| V3-3 | Is the non-firing reliable or accidental? | `s3_nanid.py` on 2.2.3 + 3.0.5 | pandas reuses the `np.nan` singleton across separate `read_csv` calls and across `pd.concat`, so the intersection is reliably `{nan}`. Control: `{float('nan')} & {float('nan')}` = `set()` |
| V3-4 | The four (five) contaminated figures | `s1_sentinel.py` | CT tract 873/872; VA counties 2018 234/233, 2019 146/145; AK county jaccard 0.738/0.732, 0.811/0.806, **and 0.906/0.903 at 2021→2022, not previously flagged** |
| V3-5 | Per-county disjointness — firing | `s5_percounty.py`, `s6_ak_detail.py` | **AK 2021→2022: 1 disjoint-within (`02105`), 1 vanishing (`02261`), 2 appearing, 27 held**; statewide intersection 144, so frame-level is silent. **CT 2023→2024: ZERO disjoint-within**, 8 vanishing, 9 appearing. `02105000300` holds 2018–2021 and `02105000400` 2022–2025 — a true positive, not sparsity |
| V3-6 | Per-county disjointness — non-firing | `s9_spec.py` at `FLOOR=0` and `FLOOR=10` | All 10 cases correct at FLOOR=10. At FLOOR=0, two false positives: VA and AK 2018→2019, **5 out-of-state stray counties**, 1–4 rows each. True positives carry 41–1,032 rows |
| V3-7 | Does the measured limb earn its place? | `s7_earnsplace.py` | Across **16 same-basis adjacent year-pairs** in ~~6~~ **5 states** (v4 recount — AK, CT, MI, OH, VA; NC is in the sentinel cache but not the joint cache), it fired 5 times — **all false positives**. Across basis-changing pairs it fired on 6 counties, **all already refused declaratively**. Net unique findings: **zero**. *Re-run in v4 and reproduces exactly* |
| V3-8 | `attrs`, four configurations × three versions | `s10_attrs.py` on 1.4.4 / 2.2.3 / 3.0.5 | `.merge()` and `concat` survive **iff all operands carry identical attrs** — on 2.2.3 and 3.0.5. **1.4.4 diverges: `.merge()` never propagates**, even with identical operands. Realistic case (differing basis values) drops attrs on all three. 1.4.4 tested under Python 3.10 with `numpy==1.26.4` |
| V3-9 | §M4.1 durability block on 1.4.4 | `s15_dur.py` | Items 1, 2, 3, 4, 4b reproduce identically on 1.4.4 — the v2 three-version claim stands for these |
| V3-10 | 2025 / 2026 and the maturity ladder | `curl` on the package's own endpoint | 2025 → 301 `snapshot`; 2026 → **400**. Ladder: 2018–2022 `three-year`, 2023–2024 `one-year`, 2025 `snapshot` |
| V3-11 | The CFPB *Summary* series | `curl` per year slug | 2021/2022/2023 → 200; **2024 → 404, 2025 → 404**. The series stops at 2023 (published 2024-07-11) |
| V3-12 | MSA basis citation | CFPB *Summary of 2023 Data*, fetched 2026-08-04 | Verbatim: "the data reflect metropolitan statistical area (MSA) definitions released by the Office of Management and Budget in 2020 that **became effective for HMDA purposes in 2022**." Also: "The 2023 HMDA data use the census tract delineations … from the 2020 Census" — a **new** tract-map citation the document lacked |
| V3-13 | OMB Bulletin 23-01 | independent confirmation, 2026-08-04 | Issued **2023-07-21**; updates and supersedes Bulletin 20-01 (2020-03-06); first delineation using 2020 Decennial Census data. Under §M1.1's rule its first LAR year is 2024 |
| V3-14 | Intra-record geography disagreement | `s5_percounty.py` | **CT 2020: 3 rows** whose `census_tract` names a different county than `county_code` — reconciling exactly with §M6.6's `{'25540': 1}` and `{'25540': 2}` strays. VA 2020: 7 rows. CT 2023/2024, AK 2021: 0 |
| V3-15 | Zero-land-area tracts and the sliver count | `s11_zeroland.py`, `s13_pin.py`, `s14_sliver.py` | **63** RECARVED 2020 tracts have zero land area; ≥99%-same-ground is **19,377 (41.9%)** excluding them, 19,440 (42.1%) including. Rule-A unfiltered **46,204 reproduces exactly**; filtered is **44,915**, not the stated 44,417, and the filter drops **1,289**, not 1,787 |

**Not reproduced from the v2 revision:** the `1,787` sliver count and the derived
`44,417` filtered total (measured 1,289 and 44,915); and the `attrs`
"identical on 1.4.4 / 2.2.3 / 3.0.5" claim, which fails on `.merge()` at 1.4.4.
Both are immaterial to the conclusions they support and both are corrected in place.

**v4 program (2026-08-05).** All commands run from the
`docs/tract-vintage-methodology` branch at `63625f1`, against the cached
`(county_code, census_tract)` counters and the Census relationship file from the v3
scratchpad. **No repository code was modified and no `.py` file was touched.** The
caches preserve the literal string `NA` exactly as the CFPB CSV carries it, so the
sentinel filter is applied explicitly at read time — dropping rows where either
`county_code` or `census_tract` is `NA`, the offline equivalent of `.dropna()`
(§M1.2a). **Every key-set figure below is sentinel-excluded, and says so.**

| # | What | Command | Established |
|---|---|---|---|
| V4-1 | The full case matrix, **limb 2 removed** | `t1_limb2_removed.py` (`fires = declarative` only) | **10 of 10 cases correct.** CT 2023+2024 raises via the **county map** (tract bases [2020], county bases [2020, 2023]); AK 2021+2022 and VA 2021+2022 raise via **tract map + county map**. All seven non-firing cases stay silent — single-year CT 2024, CT 2022+2023, VA 2019+2020, VA 2020+2021, the hand-concatenated VA-2022/OH-2023 frame, VA 2018+2019, AK 2018+2019. Removing the limb changes **no** verdict |
| V4-2 | Exhaustive sweep — does limb 2 catch anything the maps do not? | `t2_alaska_and_sweep.py` part (b) | Every year-pair (not only adjacent) in every cached state, FLOOR=10: **76 measured hits, 76 on pairs the declarative limbs already refuse, 0 on declaratively-silent pairs.** Limb 2's unique contribution over the whole sample is **zero** |
| V4-3 | **Alaska `02105` — the case that could have reopened the decision** | `t2_alaska_and_sweep.py` part (a) | `02105000300` for 2018–2021, `02105000400` for 2022–2025. Disjoint-within in **16 of 28** year-pairs, and **every one of those 16 crosses the 2021\|2022 decennial boundary**, where both maps change. **AK pairs where `02105` is disjoint-within but declaratively silent: NONE.** The declarative refusal covers it — structurally, not coincidentally |
| V4-4 | The state count behind every per-county figure | file listing of the joint cache + pair arithmetic | The joint cache holds **5 states** — AK, CT, MI, OH, VA — 29 state-year files. **NC is absent.** NC 2018–2024 would add 4 same-basis adjacent pairs, giving 20 rather than the 16 the document reports: the reported figure is consistent **only** with five states |
| V4-5 | The sentinel cache's denominator | file listing of the sentinel cache | **39** state-year JSONs across 6 states (AK/CT 2018–2025, MI/NC 2018–2024, OH 2019–2024, VA 2018–2020), plus `rel2020.txt`. "40 of 40" counted the relationship file |
| V4-6 | The sliver figures, re-confirmed | `s14_sliver.py` on `rel2020.txt` | Unfiltered **46,204** (reproduces exactly); filtered **44,915**; lost by the filter **1,289**; gained **0**. `1,787` and `44,417` reproduce under no variant. Consistent with V3-15 |
| V4-7 | `attrs` on pandas 1.4.4, re-confirmed | `s10_attrs.py` on the pinned 1.4.4 venv | `.merge()` propagates `attrs` in **none** of the four configurations, including identical operands; `concat` propagates only with identical operands. Matches V3-8 exactly. **The "one rule" holds on 2.2.3+ only, across a declared floor of `pandas>=1.4.0`** — which strengthens, not weakens, the no-`attrs`-carrier conclusion (§M3.3) |

**What v4 did not re-run, and why.** The declarative maps, the six-site inventory,
the no-crosswalk argument, raise-over-warn, the CT desert numbers, the packaging
finding and the five-tract floor are settled across three independent sessions and
were not touched. Nothing in this pass bears on them.

**Next step: a short fresh-session confirmation that the removal is complete and
internally consistent, then the build prompt. Not a fifth audit. No code until
then.**
