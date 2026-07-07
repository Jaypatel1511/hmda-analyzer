# CRA-Proxy Distribution Analytics — Methodology (hmda-analyzer) — v2

> **Status: REVISED (v2), audit-cleared.** Methodology-first artifact. v1 decisions:
> originations-only, exclude-not-impute, DataFrame transform. v1 is single-source
> HMDA, originations-only, distribution-only, **no comparator** (§15).

## 1. Purpose & scope
Descriptive distributional analytics on HMDA LAR that approximate the **distribution
dimensions** a CRA lending analysis looks at — borrower-income distribution and
geographic (tract-income) distribution of mortgage lending — for CDFI/fair-lending
practitioners without data teams.

- **Descriptive only.** Counts and shares. No inference, no statistical significance,
  no disparity claims. Explicitly **NOT** a fair-lending screener.
- **It is a PROXY** (see §8). Never a CRA rating, grade, metric, or performance evaluation.
- **No protected-class crossing.** Income and geography only.

## 2. What it computes (v1)
Given a HMDA LAR frame (from `load_from_api` or `load_range`):
- **Borrower-income distribution** — count + share of originations to Low / Moderate /
  Middle / Upper-income borrowers.
- **Geographic (tract-income) distribution** — count + share of originations in Low /
  Moderate / Middle / Upper-income tracts.
- **LMI lending share** — Low+Moderate combined, reported **separately** for borrower
  and for tract.
- **By year** when the frame carries `activity_year` (multi-year via `load_range`).

Output is a set of tidy tables (category, count, share) plus, for each, the **classified
denominator** and an explicit **excluded/unclassified count**. There is deliberately
**no single composite "score"** — a scalar invites reading it as a CRA grade.

## 3. Loan universe (v1)
- **Originations only:** `action_taken == 1`.
- **Purchased loans** (`action_taken == 6`) available behind an optional documented flag
  (`include_purchased=False` default), kept visibly separate — never blended, because
  purchased credit was already originated and HMDA-reported by the originator elsewhere.

## 4. Income classification thresholds (FFIEC/CRA regulatory)
Applied to an "MFI%" (median-family-income as a percentage of the area median):

| Level | MFI% band |
|---|---|
| Unknown (excluded) | MFI% == 0, blank, or NA |
| Low | **0 < MFI% < 50** |
| Moderate | 50 ≤ MFI% < 80 |
| Middle | 80 ≤ MFI% < 120 |
| Upper | MFI% ≥ 120 |

**LMI = Low + Moderate = 0 < MFI% < 80.** Boundary convention: lower-inclusive,
upper-exclusive per band. Verified against 12 CFR §25.12 / §228.12 / §345.12 (identical
across all three agencies). FFIEC's official "Tract Income Level" uses the same bands but
reserves code **0 = "Unknown / not available"** and defines Low as ">0% and <50%" — which
is why the Unknown row is FIRST and Low is lower-bounded at 0 (§5). Regulatory-status
note: the 1995 CRA framework is operative; the 2023 modernization rule was enjoined
(Mar 2024) and is proposed for rescission (NPR Jul 2025, not finalized). The income-band
text is identical across both frameworks; cite §25/§228/§345 neutrally and never describe
the 2023 rule as "current."

## 5. Geographic (tract-income) classification
- **Input:** LAR-native `tract_to_msa_income_percentage` (FFIEC-appended: tract MFI ÷
  MSA/MD MFI, or statewide non-MSA MFI for non-metro tracts).
- **CRIT-1 — exclude Unknown FIRST, then threshold the survivors.** The classifier tests
  the Unknown condition (`percentage == 0` OR blank OR NA) and routes those rows to
  "Unknown (excluded)" **before** any `<`/`≤` comparison. Rationale: FFIEC reserves `0`
  for "Unknown/not available"; a literal `0` is a real number that *passes* a bare `< 50`
  gate and would be fabricated into Low — inflating the LMI-tract share in the flattering
  direction. That directional, flattering fabrication is the cardinal sin this tool exists
  to prevent. (pandas `NaN < 50 → False`, so genuine NaN already falls out of all bands —
  but a literal `0` does not, which is the exact bug.)
- **Sentinel encoding (recon-verified):** in the public LAR,
  `tract_to_msa_income_percentage` is a **string column, 100% populated**, and the Unknown
  sentinel is the **literal string `"0"`** (not blank, not NA). Genuine blank/NA can still
  occur in other files and is also routed to Unknown.
- **Static-vintage caveat:** the tract percentage is based on 5-year ACS, updated every
  5 years (or on an OMB boundary change). Documented; correct per FFIEC method.

## 6. Borrower-income classification
- **Inputs:** LAR `income` (applicant gross annual income, in thousands, relied on in the
  credit decision) and LAR-native `ffiec_msa_md_median_family_income` (dollars).
- **Borrower MFI% = (income × 1000) ÷ ffiec_msa_md_median_family_income × 100**, then §4
  thresholds. `income` is thousands rounded to nearest $1k; the denominator is the annual
  FFIEC MSA/MD MFI (12 CFR §228.12; Interagency CRA Q&A §__.12(m)–1).
- **NO `1111`/"Exempt" handling for `income`.** `income` is one of the always-required
  22 data points and is **never exempt-eligible**. Because `income` is in *thousands*, a
  value of `1111` is a legitimate **$1,111,000** (a real Upper-income borrower). Dropping
  `income == 1111` would systematically delete high-income originations and spuriously
  inflate LMI borrower share — the mirror image of CRIT-1.
- **Missing area-median guard (recon-verified).** In the public LAR,
  `ffiec_msa_md_median_family_income` is a **string column** and the FFIEC-unmatched tracts
  carry the **literal `"0"`** (a strict subset of the `tract_to_msa_income_percentage=="0"`
  Unknown rows). `income / 0 == inf` passes the `≥ 120` gate and would be fabricated into
  Upper. A `0`/blank/NA area median is a **missing denominator → excluded**, never divided.
- **`income` valid states:** numeric-thousands, or **"NA"/blank** (multifamily,
  non-natural-person applicant, income-not-relied-on). Exclude on NA/blank only; never impute.
- **Combined-income upward bias (per-output caveat):** `income` is the income *relied on
  in the credit decision* — frequently combined co-applicant income — which pushes
  borrowers into higher bands and tends to **understate** the LMI borrower share.
- **Differing denominators (per-output caveat):** multifamily / non-natural-person /
  (if enabled) purchased loans have `income = NA` → excluded from the borrower denominator,
  but they carry a valid tract → included in the geographic denominator. Borrower-LMI% and
  tract-LMI% are computed on **different populations** — **do not difference the two LMI%s**.
- The MSA/MD MFI denominator updates **annually**; never cross-substitute the tract-%
  denominator for borrower classification.

## 7. Missing-data / denominator discipline (the fabrication firewall)
Every distribution reports its **classified denominator** and the **count of records
excluded** for missing/unclassifiable inputs. Missing → **excluded and surfaced**, NEVER
imputed into a band, NEVER a fabricated 0 or plausible default. The specific traps: (a) a
literal `0` (FFIEC's Unknown sentinel) *passes* a `< 50` gate — excluded by an explicit
Unknown test first; (b) genuine `NaN` already fails `<`/`≤` comparisons but must still be
counted in the excluded tally; (c) no `.fillna(<band-value>)`, no truthiness gate
(`if pct:` treats `0` as falsy — `0` is the Unknown sentinel, not merely falsy).

## 8. The PROXY firewall (prominent; enforced in output)
This is a proxy for CRA distribution analysis, not CRA analysis. Every output carries:
- **Not assessment-area-bound.** CRA distribution tests are computed *within a bank's
  designated assessment area(s)*; HMDA has no assessment-area concept, so this proxy spans
  all HMDA lending in the requested geography — a different population than any CRA exam
  evaluates. (Largest gap.)
- **Mortgage-only.** CRA lending tests also cover small-business, small-farm, and
  community-development lending, invisible to HMDA.
- **Reporter population ≠ CRA-covered institutions.**
- **Not a CRA rating / grade / performance evaluation.**

**Output language guardrail — bind the qualifier to the METRIC, not the page.** A footer
caveat is strippable. So: the **share column names carry the qualifier** (`cra_proxy_share`)
— the word "CRA" never appears in output without "proxy" adjacent, including headers;
**every table** carries the `STANDARD_CRA_PROXY_CAVEAT`; and **every output carries an
explicit "distribution only; no comparator — not interpretable as CRA performance" line.**

## 9. Firewall vs. fair-lending
No regression, no significance, no disparity inference, no protected-class stratification —
purely distributional counts/shares. Disparity inference is a fair-lending screener's
guarded territory; CRA-proxy must not acquire an inference path.

## 11. Data dependency
v1 requires **no *runtime* join** — but that is NOT "no FFIEC data."
`tract_to_msa_income_percentage` and `ffiec_msa_md_median_family_income` are **FFIEC census
fields pre-appended to the public LAR** — a census dependency baked into the input.
Structural NA is definitional (multifamily, non-natural-person, unmatched tracts) —
those classes are excluded-and-surfaced, not errors, and their existence is why the
borrower and tract denominators legitimately differ.

## 13. Limitations (in the doc AND per-output)
Not assessment-area-bound · mortgage-only · reporter-population ≠ CRA institutions · not a
CRA rating · **no comparator/benchmark — not interpretable as CRA performance** · HMDA
`income` is lender-relied-upon (often combined) income, upward-biased (understates LMI
borrower share) · **borrower and tract distributions use different denominators — do not
difference the two LMI%s** · static tract vintage vs. annual MSA MFI · excludes
non-classifiable/Unknown records (surfaced in an excluded tally, never imputed).

## 15. Comparator position
**Disclaimer-sufficient for v1; comparator deferred to v2.** The no-composite-scalar rule
removes the worst performance-reading vector; the meaningful CRA comparator is the
demographic baseline (ACS/census data) — the external dependency v1 defers to v2, bundled
in one increment. v1 is defensible without a comparator only because (1) the caveat is
metric-bound, not strippable (§8), and (2) every output carries the explicit no-comparator
line.

## 16. Regulatory-status note
The 1995 CRA framework is operative; the 2023 modernization rule was enjoined (Mar 29 2024)
and is proposed for rescission (interagency NPR, Jul 16 2025), no final rescission
confirmed. The income-band text is identical across both frameworks — cite §25/§228/§345
neutrally and never describe the 2023 rule as "current."
