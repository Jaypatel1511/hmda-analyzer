# CRA-Proxy Distribution Analytics — Methodology (hmda-analyzer) — v2 (hostile-audit findings applied)

> **Status: REVISED (v2), audit-cleared pending Jay sign-off.** Methodology-first artifact. Hostile audit verdict was **REVISE** (0 NO-GO; 2 boundary HIGH/CRIT + 1 HIGH framing + 2 MED + 1 recon-gate MED); all six required changes are folded in below and every `[VERIFY]` citation is reconciled against a primary source (§14). v1 decisions: originations-only, exclude-not-impute, DataFrame transform. **One ratified call was overturned by the audit and re-decided:** "derive-not-join" — the "HMDA-only, no external dependency" premise was false (the FFIEC fields are census-appended, and `income`/tract-% carry structural NA), so v1 is honestly stated as "no *runtime* join, but an FFIEC-census-append dependency" (§11). No rescope: v1 stays single-source HMDA, originations-only, distribution-only, **no comparator** (§15).

## 1. Purpose & scope
Descriptive distributional analytics on HMDA LAR that approximate the **distribution dimensions** a CRA lending analysis looks at — borrower-income distribution and geographic (tract-income) distribution of mortgage lending — for CDFI/fair-lending practitioners without data teams.

- **Descriptive only.** Counts and shares. No inference, no statistical significance, no disparity claims. Lives on **hmda-analyzer** (descriptive layer). Explicitly **NOT** fair-lending-screener.
- **It is a PROXY** (see §8). Never a CRA rating, grade, metric, or performance evaluation.
- **No protected-class crossing.** Income and geography only. Race/ethnicity-crossed disparity is fair-lending-screener's guarded territory; this tool must not drift toward it.

## 2. What it computes (v1)
Given a HMDA LAR frame (from `load_from_api` or `load_range`):
- **Borrower-income distribution** — count + share of originations to Low / Moderate / Middle / Upper-income borrowers.
- **Geographic (tract-income) distribution** — count + share of originations in Low / Moderate / Middle / Upper-income tracts.
- **LMI lending share** — Low+Moderate combined, reported **separately** for borrower and for tract.
- **By year** when the frame carries `activity_year` (multi-year via `load_range`).

Output is a set of tidy tables (category, count, share) plus, for each, the **classified denominator** and an explicit **excluded/unclassified count**. There is deliberately **no single composite "score"** — a scalar invites reading it as a CRA grade.

## 3. Loan universe (v1)
- **Originations only:** `action_taken == 1`.
- **Purchased loans** (`action_taken == 6`) available behind an optional documented flag (`include_purchased=False` default), kept visibly separate.
- Denials / withdrawn / incomplete / preapproval-only are out of the lending-distribution universe by definition. (This is a distribution-of-lending metric, not an approve/deny analysis — that's fair-lending's domain.)
- **Resolved (audit):** originations-only is the correct default. `action_taken == 6` is credit the institution *purchased* — already originated and HMDA-reported by the originator elsewhere — so blending it into a distribution double-counts. CRA's lending test does give some credit for purchases (so "excludes some CRA-relevant activity" is literally true), but for a *distribution* proxy, blending distorts. If purchases are ever shown, they belong in a separate, labeled cut, never blended into the borrower/tract distribution.

## 4. Income classification thresholds (FFIEC/CRA regulatory)
Applied to an "MFI%" (median-family-income as a percentage of the area median):
| Level | MFI% band |
|---|---|
| Unknown (excluded) | MFI% == 0, blank, or NA |
| Low | **0 < MFI% < 50** |
| Moderate | 50 ≤ MFI% < 80 |
| Middle | 80 ≤ MFI% < 120 |
| Upper | MFI% ≥ 120 |

**LMI = Low + Moderate = 0 < MFI% < 80.**
Boundary convention: lower-inclusive, upper-exclusive per band. **VERIFIED (audit)** against 12 CFR §25.12 / §228.12 / §345.12 — word-for-word identical across all three agencies: lower bound inclusive ("at least"), upper exclusive ("less than"), Upper = "120 percent or more." FFIEC's official "Tract Income Level" uses the *same* bands but reserves code **0 = "Unknown / not available"** (tract MFI = 0 or unavailable) and defines Low as **">0% and <50%."** This is why the Unknown row is FIRST and Low is lower-bounded at 0 — see §5/§7. Regulatory-status note: the 1995 CRA framework is operative; the 2023 modernization rule was enjoined (Mar 2024) and is proposed for rescission (NPR Jul 2025, not finalized as of this writing). The income-band text is identical across both frameworks, so cite §25/§228/§345 neutrally and never describe the 2023 rule as "current."

## 5. Geographic (tract-income) classification
- **Input:** LAR-native `tract_to_msa_income_percentage` (FFIEC-appended: tract MFI ÷ MSA/MD MFI, or statewide non-MSA MFI as the denominator for non-metro tracts).
- **CRIT-1 fix — exclude Unknown FIRST, then threshold the survivors.** The classifier MUST test the Unknown condition (`percentage == 0` OR blank OR NA) and route those rows to "Unknown (excluded)" **before** any `<`/`≤` comparison. Do NOT rely on the Low band to catch them. Rationale (audit): FFIEC reserves `0` for "Unknown/not available"; a literal `0` is a real number that *passes* a bare `< 50` gate and would be fabricated into Low — inflating the LMI-tract share in the flattering direction (making lending look more CRA-favorable than reality). That directional, flattering fabrication is the cardinal sin this tool exists to prevent. (Note: pandas `NaN < 50 → False`, so genuine NaN already falls out of all bands — but a literal `0` does not, which is the exact bug.)
- **Static-vintage caveat:** the tract percentage is based on 5-year ACS, updated every 5 years (or on an OMB boundary change) — stable within a census vintage. Document it; it's correct per FFIEC method.
- **Sentinel encoding is a hard recon item (§11):** how the *public LAR* encodes Unknown in `tract_to_msa_income_percentage` (literal `0` vs blank vs NA) is **not documented by CFPB and could not be verified from docs** — it MUST be determined against the actual file at the recon gate before the classifier is written. The authoritative fix is v2's FFIEC census join (it carries the official 0–4 code incl. the Unknown flag); the LAR does not carry that code, so v1 re-derives and therefore must get Unknown handling exactly right.
- **Small-county / special / underwater tracts** (e.g. `9999.99`, 9900-series) — confirm at recon whether they carry a usable percentage or must be routed to Unknown; do not let a special-tract code silently satisfy a band. **Out-of-range rule (ratified post-audit):** route negative, non-finite (inf/-inf), and above-ceiling percentage values to Unknown/excluded (surfaced with a distinct reason), never into a band. Default ceiling 1000 — no legitimate tract plausibly exceeds ~600–700% of area median given ACS top-coding, while FFIEC sentinel-style codes are ≥9900; recon may adjust the ceiling with documented rationale.

## 6. Borrower-income classification
- **Inputs:** LAR `income` (applicant gross annual income, in thousands, relied on in the credit decision) and LAR-native `ffiec_msa_md_median_family_income` (dollars).
- **Borrower MFI% = (income × 1000) ÷ ffiec_msa_md_median_family_income × 100**, then §4 thresholds. **VERIFIED (audit):** field, units, and denominator are correct — `income` is thousands rounded to nearest $1k; `ffiec_msa_md_median_family_income` is whole dollars, the same annual FFIEC MSA/MD MFI that CRA's "area median income" refers to (12 CFR §228.12; Interagency CRA Q&A §__.12(m)–1).
- **HIGH fix — NO `1111`/"Exempt" handling for `income`.** The earlier "Exempt (1111) → excluded" rule was based on a **wrong citation** and is actively harmful. Verified against the CFPB EGRRCPA partial-exemption interpretive rule: `income` is one of the always-required 22 data points and is **never exempt-eligible** — it is never reported as "Exempt"/`1111`. And because `income` is in *thousands*, a value of `1111` is a legitimate **$1,111,000** (a real Upper-income borrower). Dropping `income == 1111` would systematically delete high-income originations, biasing the borrower distribution downward at the top and spuriously inflating LMI borrower share — the mirror image of CRIT-1. The `1111`/"Exempt" drop discipline is correct for *other* fields (Balloon, Property Value, etc.); it does not belong on any of this tool's four fields.
- **`income` has exactly two valid states:** numeric-thousands, or **"NA"/blank** (multifamily, non-natural-person applicant, purchased-loan-not-relied-on, or income-not-relied-on). **Exclude on "NA"/blank only**, add to the excluded tally, never impute.
- **THIRD SENTINEL — `ffiec_msa_md_median_family_income == 0` (added post-build recon; ratified July 2026).** The area-median denominator carries the *same* FFIEC-unmatched sentinel as the tract %: a literal `0` (in the public LAR, the string `"0"`), on the same FFIEC-unmatched tracts. `income ÷ 0 → inf`, which passes the `≥ 120` gate and **fabricates Upper** — the denominator-side analogue of CRIT-1, and proven real in recon (rows with a `0` area median AND a real income). **Required handling:** exclude any row whose area median is `0`/blank/NA as a **missing denominator — never divide.** This is not new policy; it is §7's fabrication firewall applied to the denominator the original §6 didn't name. Route these to the excluded tally (reason: `missing_area_median`).
- **Dtype note (recon):** `_clean` numeric-coerces `income` (NA → NaN) but leaves `tract_to_msa_income_percentage` and `ffiec_msa_md_median_family_income` as **strings**. The classifier must `pd.to_numeric` the two FFIEC fields itself, and the Unknown/missing sentinel arrives as the **literal string `"0"`**, not a numeric 0 or NaN — the exclusion tests must key on that.
- **Per-output caveat (MED, combined-income bias):** `income` is the income *relied on in the credit decision* — frequently combined co-applicant income, which pushes borrowers into higher bands relative to an individual-income concept, tending to **understate** the LMI borrower share. Surface this as a one-line caveat on **every borrower-distribution output**, not just the docs.
- The MSA/MD MFI denominator updates **annually** (unlike the static tract %) — correct per FFIEC; never cross-substitute the tract-% denominator for borrower classification.
- **Per-output caveat (MED, differing denominators):** multifamily / non-natural-person / (if enabled) purchased loans have `income = NA` by definition → excluded from the borrower denominator, but they carry a valid tract → included in the geographic denominator. So borrower-LMI% and tract-LMI% are computed on **different populations** (the gap is systematic — entity/multifamily lending). State this per output and **warn against differencing the two LMI%s**.

## 7. Missing-data / denominator discipline (the fabrication firewall)
- Every distribution reports its **classified denominator** and the **count + share of records excluded** for missing/exempt/unclassifiable inputs.
- Missing → **excluded and surfaced**, NEVER imputed into an income band, NEVER a fabricated 0 or a plausible default. An explicit "unclassified (excluded)" count is honest; folding unclassified rows into a real band is the banned move.
- Mirrors the portfolio NaN-not-fabrication and exempt-drop lessons. **The specific traps here:** (a) a literal `0` (FFIEC's Unknown sentinel for tract %) *passes* a `< 50` gate and lands in Low — must be excluded by an explicit Unknown test first (§5, CRIT-1); (b) genuine `NaN` already fails `<`/`≤` comparisons (falls out safely) but must be counted in the excluded tally, not dropped silently; (c) no `.fillna(<band-value>)`, no truthiness gate (`if pct:` treats `0` as falsy — do not use it to mean "missing," since `0` is the Unknown sentinel, not merely falsy); (d) a `0` **denominator** (`ffiec_msa_md_median_family_income == 0`) makes `income ÷ 0 → inf`, which passes the `≥ 120` gate and fabricates Upper — exclude a `0`/blank/NA area median as a missing denominator BEFORE dividing (§6, third sentinel). Grep every comparison, every fill, AND every division on the classification fields — the sentinel `0` bites as a numerator (tract %), and as a denominator (area median).

## 8. The PROXY firewall (prominent; enforced in output)
This is a proxy for CRA distribution analysis, not CRA analysis. The methodology and **every output** must carry these:
- **Not assessment-area-bound.** CRA distribution tests are computed *within a bank's designated assessment area(s)*; HMDA has no assessment-area concept, so this proxy spans all HMDA lending in the requested geography — a different population than any CRA exam evaluates. (This is the largest gap.)
- **Mortgage-only.** CRA lending tests also cover small-business, small-farm, and community-development lending, invisible to HMDA.
- **Reporter population ≠ CRA-covered institutions.** Independent mortgage companies report HMDA but aren't CRA banks; coverage thresholds differ.
- **Not a CRA rating / grade / performance evaluation.**

**Output language guardrail — HIGH fix: bind the qualifier to the METRIC, not the page.** A report-footer caveat is strippable: a user copies one row — "LMI borrowers: 42%" — into a board deck and every firewall is gone; the fragment then reads exactly as a CRA performance figure, and it carries no CRA word at all (the most copy-pasteable, most performance-looking fragment). So:
- The **share column names themselves** carry the qualifier, e.g. `cra_proxy_lmi_share__not_assessment_area_bound__not_performance` (or a clearly-labeled equivalent), so no extractable cell reads as a CRA metric.
- **Every table** (not just the report footer) carries the `STANDARD_CRA_PROXY_CAVEAT` line stating it is not assessment-area-bound and not a CRA performance measure.
- Results are labeled "**CRA-proxy distribution estimate**," never "CRA metric/rating/performance"; the word "CRA" never appears in output without "proxy" adjacent — including in column headers.
- **Plus (comparator position, §15): every output carries an explicit "distribution only; no comparator — not interpretable as CRA performance" line.** Naming the absent benchmark is more protective than silently omitting it.

## 9. Firewall vs. fair-lending (descriptive/inferential separation)
No regression, no significance, no disparity inference, no protected-class stratification — purely distributional counts/shares. If a user wants disparity inference, that is fair-lending-screener (guarded, court-defensible framing). CRA-proxy must not acquire an inference path.

## 10. Relationship to cra-scraper
`cra-scraper` retrieves the **official** CRA exam ratings (the real regulatory output). CRA-proxy derives **HMDA-based distribution estimates**. Complementary: the proxy is useful where official CRA data is sparse or lagged — but it is never the exam metric, and the docs must say so.

## 11. Data dependency (HIGH-2 corrected)
- **Honest statement:** v1 requires **no *runtime* join** — but that is NOT "no FFIEC data / HMDA-only." `tract_to_msa_income_percentage` and `ffiec_msa_md_median_family_income` are **FFIEC census fields pre-appended to the public LAR** — a census dependency that is already baked into the input. Do not let the doc or marketing drift into "no external dependency."
- **Structural NA is definitional, not incidental:** `income = NA` is *expected* for multifamily loans, non-natural-person applicants (corp/partnership/trust), and most purchased loans (income optional); `tract_to_msa_income_percentage` can be blank for unmatched tracts. These loan classes are **excluded-and-surfaced** (§6/§7), not errors — and their existence means the borrower and tract denominators legitimately differ (§6).
- **Recon gate (build stage), MED — presence + population + SENTINELS:** for all three fields against the actual 99/101-col file, determine (a) presence, (b) real-world population rate, and (c) **the exact Unknown/NA encoding** — literal `0` vs blank vs NA for the tract %, and how `income = NA` renders. (c) is load-bearing for CRIT-1 and is the one item docs could not confirm.
- **v2 enhancement (bundle together):** join the official FFIEC census file for (i) the authoritative tract income-level code (0–4, incl. the Unknown flag — removes the re-derivation risk) and (ii) the demographic comparator baseline (§15). Same census dependency, one increment.

## 12. API / function shape (intended; exact signature is a build-stage call)
- **Pure descriptive transform on a passed-in DataFrame** — the frame from `load_from_api` or `load_range`. No fetch, no network, no new WAF surface.
- Shape sketch: `cra_proxy_distribution(df, *, by="borrower"|"tract"|"both", include_purchased=False, year_column="activity_year")` → tidy distribution table(s) with denominators + excluded counts + the standing caveat.
- **Multi-year:** if the frame carries `activity_year` (from `load_range`), group by year → distribution per year. (This is the 0.4.0 synergy that put multi-year first in the queue.) **Reconciliation rule (ratified post-audit):** in multi-year mode, rows with a missing/NA `activity_year` must NOT silently vanish — route them to the excluded tally (reason `unknown_year`) so classified denominators + excluded always reconcile to the universe count.

## 13. Limitations (in the doc AND per-output, metric-bound per §8)
Not assessment-area-bound · mortgage-only · reporter-population ≠ CRA institutions · not a CRA rating · **no comparator/benchmark — not interpretable as CRA performance** · HMDA `income` is lender-relied-upon (often combined) income, an imperfect and likely **upward-biased** proxy for CRA borrower income (understates LMI borrower share) · **borrower and tract distributions use different denominators — do not difference the two LMI%s** · static tract vintage vs. annual MSA MFI (never cross-substitute) · excludes non-classifiable/Unknown records (surfaced in an excluded tally, not hidden, never imputed).

## 14. Citations — reconciled against primary sources (audit)
- **VERIFIED** — income bands + inclusivity: 12 CFR §25.12 / §228.12 / §345.12 (eCFR). Low <50, Moderate [50,80), Middle [80,120), Upper ≥120; LMI <80. Identical across all three agencies.
- **VERIFIED** — borrower denominator = annual FFIEC MSA/MD median family income (not HUD limits, not household): §228.12; Interagency CRA Q&A §__.12(m)–1. Formula (`income×1000 ÷ ffiec_msa_md… ×100`) and units confirmed: CFPB FIG / LAR field docs.
- **VERIFIED on bands; DIVERGES on Unknown** — FFIEC "Tract Income Level" (Online Data Dictionary; annual census file spec): same 50/80/120 bands, but Low = ">0% and <50%," code `0` = Unknown. FFIEC publishes the 0–4 code directly (not in the LAR → v1 re-derives, hence §5's Unknown-first rule; v2 join adopts the official code).
- **WRONG (removed)** — the prior "`income` Exempt/`1111` → excluded" claim: `income` is an always-required data point, never Exempt-eligible; `1111` = a real $1.111M income (CFPB EGRRCPA partial-exemption interpretive rule; FIG). Corrected in §6.
- **VERIFIED** — `action_taken` 1=originated, 6=purchased (CFPB public LAR docs); field always present.
- **UNVERIFIABLE from docs (→ recon gate)** — the public-LAR Unknown/blank encoding of `tract_to_msa_income_percentage`. Must be checked against the actual file (§5, §11).
- **VERIFIED** — borrower-income + geographic distribution are the CRA lending-test distribution dimensions (Interagency CRA Q&A; FFIEC/FDIC exam manual).
- **Regulatory-status note (cite neutrally):** the 1995 CRA framework is operative and banks are examined under it today; the 2023 modernization rule was enjoined (Mar 29 2024) and is proposed for rescission (interagency NPR, Jul 16 2025) with no final rescission confirmed as of this writing. The income-band text is identical across both frameworks — cite §25/§228/§345 without characterizing either as "the current rule," and never describe the 2023 rule as current.

## 15. Resolved positions (audit)
- **Boundary conventions** — verified exact (§4, §14).
- **Combined-income upward bias** — real and stated per-output (§6).
- **Originations-only** — affirmed as default (§3).
- **Special/underwater tracts** — routed to Unknown or confirmed usable at recon (§5).
- **Fabrication paths** — closed by Unknown-first + no-`1111`-drop + comparison/fill audit (§5, §6, §7).
- **The comparator — DISCLAIMER-SUFFICIENT FOR v1; comparator deferred to v2. Do NOT expand v1.** Reasoning: §2's no-composite-scalar rule already removes the worst performance-reading vector (a headline grade); the meaningful CRA comparator is the demographic baseline (LMI-family share, owner-occupied-units-in-LMI-tracts share), which is ACS/census data — i.e. exactly the external dependency §11 defers to v2, so bundle it there in one increment. A peer/market comparator is often ill-defined for this tool's inputs (if the frame is market-wide HMDA, the output *is* the market distribution — there's no bank-vs-market to draw). v1 is defensible without a comparator **only if both hold** (both now in the doc): (1) the caveat is metric-bound, not strippable (§8); (2) every output carries an explicit "distribution only; no comparator — not interpretable as CRA performance" line. When the v2 demographic comparator lands, guard it (§9) so the baseline never becomes a protected-class benchmark — that's the slope into fair-lending-screener's territory.

## 16. Build-stage requirements carried forward
- **Bundle the methodology into the wheel** (the fair-lending `get_methodology_path()` pattern) so the firewall + limitations travel with the installed tool.
- **Recon gate before the classifier:** presence + population + exact Unknown/NA sentinel encoding for all three fields against the actual file (§5, §11).
- Column names carry the proxy/limitation qualifier (§8); every table carries the caveat + the no-comparator line.
