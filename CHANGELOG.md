# CHANGELOG

## [0.6.1] - 2026-08-05

Metadata and CI only. **No behaviour changed.** Every function returns and
raises exactly what 0.6.0 returned and raised; the diff is one `requires-python`
line, the documents that repeated it, and three CI matrices.

### Fixed

- **`requires-python` lowered from `>=3.11` back to `>=3.9`.** 0.6.0 raised the
  floor, and nothing in the package needed it. There is no `match` statement, no
  `tomllib` import, no `typing.Self`, no `ExceptionGroup` or `except*`, and zero
  uses of `date.fromisoformat` — which was the stated portfolio-wide reason for a
  3.11 floor. The one module using PEP 604 `int | None` syntax,
  `geography_vintage.py`, carries `from __future__ import annotations`, so those
  annotations are strings and never evaluated. The floor was set by convention,
  not by a requirement.

  The cost was not theoretical. 0.6.0 closed two silent defects in a fair-lending
  tool — a tract-vintage collapse that pooled GEOIDs denoting different polygons,
  and a small-N suppression that dropped protected classes with no signal — and
  then put them behind a floor that excluded the users most likely to hit them.
  A 3.9 or 3.10 user running `pip install --upgrade hmda-analyzer` did not get
  0.6.0; pip skipped it on `requires-python` and left them on 0.5.0. Over the 180
  days to 2026-08-05, PyPI recorded 85 downloads on 3.9 and 110 on 3.10 against
  112 on 3.11 — the stranded interpreters outnumbered the lowest supported one.

  0.6.1 restores exactly 0.5.0's support contract, so the fix is reachable by
  ordinary upgrade. A floor bump may still happen; it should happen as its own
  decision, argued on its own merits, once users are on a release that is not
  silently wrong.

- **Every other statement of the floor updated with it**, because a support claim
  declared in six places drifts: `README.md`, `CONTRIBUTING.md` (two places),
  `docs-check.toml`'s note on output stability, the in-package methodology
  document, and the test that asserts the README's wording. That test now
  *derives* the floor from `pyproject.toml` instead of hard-coding it, so the two
  files cannot disagree silently. It reads the value with a regex rather than
  `tomllib`, because `tomllib` is 3.11+ and a test of a 3.9 floor that cannot run
  on 3.9 asserts nothing where it matters.

### Changed — CI

- **All three matrices now run 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14**: `test.yml`'s
  `test` job, and `release.yml`'s `test-wheel` and `test-sdist`. A declared floor
  that no job exercises is the same defect this release exists to correct, one
  layer down — 0.6.0 declared 3.11 and tested 3.11, which is why nobody noticed
  the declaration was arbitrary.
- **`test.yml`'s `test` job sets `fail-fast: false`.** It was the only matrixed
  job in either workflow without it, so one red interpreter cancelled the rest
  and the run reported a single failure — hiding whether a break is version
  specific or universal. Exactly the information a six-entry matrix exists to
  produce.

### Not done, deliberately

- **No release is yanked, and the reason is worth stating.** With the floor
  restored, every 0.5.0 user reaches 0.6.1 by ordinary upgrade, so a yank buys
  nothing. It would also actively hurt: yanking 0.5.0 resolves a user pinned to
  `<0.6` down to 0.4.0, which carries **both** defects at identical source lines
  (`analysis/geographic.py:25`, `analysis/disparity.py:36`) with fewer features.
  Both defects are present in every published release — verified against the
  published sdists, `geographic.py:21` / `disparity.py:31` in 0.1.0 through
  0.2.1, and `:25` / `:36` in 0.3.0 through 0.5.0. There is no release to yank
  *toward*.
- **No `Programming Language :: Python :: X.Y` classifiers were added.**
  `requires-python` stays the single source of the support claim; a second list
  is a second thing to keep in step with the CI matrix, and nothing reads it. The
  decision is now recorded as a comment beside the line itself.
- **The declared dependency lower bounds are unchanged — and, for the first time,
  measured.** `pandas>=1.4.0` and `numpy>=1.21.0` had never been installed by any
  job; the expectation going in was that they were false floors. They are not.
  The full suite passes at exactly `pandas==1.4.0` / `numpy==1.21.0` on Python
  3.9: 396 passed, 11 `FutureWarning`s, no failures. The declared floors are
  honest.

  This matters more after 0.6.1 than before it, and in the opposite direction to
  the obvious one. Lowering `requires-python` widens the resolution space toward
  those floors — a 3.9 resolver has old pandas and numpy versions available that
  a 3.12 resolver does not, and `pandas==1.4.0` cannot even be built on 3.12. So
  the declared minimum is reachable *only* on the interpreters this release
  re-admits. Restoring the floor is what made the dependency floor testable at
  all. No pin changed: that would be a behaviour change, and this is not that
  kind of release.

- **Eight findings are deferred to 0.6.2, deliberately and by name.** This
  release holds users on a defective version, so it ships the four corrections it
  can make safely and defers everything that is new logic. Each of these was
  reproduced before being written down:
  - **Nothing links the README's six-version list or `requires-python` to the
    workflow files.** Reverting all three matrices to 3.11–3.14 still gives 396
    passed while `README.md:31-33` goes on asserting six. The release's central
    claim is checked by nothing. First item in 0.6.2.
  - **No job asserts its own interpreter** — no `python -V`, no `sys.version` in
    either workflow, so the matrix is unverifiable from its own logs even when it
    works. Three lines per matrixed job.
  - **3.9 has no `ubuntu-26.04` build in the `actions/python-versions` manifest**
    and every job is unpinned `ubuntu-latest`; when that label flips, the 3.9 row
    stops provisioning in all three matrices, two of which gate publish. It fails
    loud, so it is a will-fail-later, not a cannot-fail. The `runs-on:
    ubuntu-24.04` pin waits for the flip to be announced.
  - **`CONTRIBUTING.md:71-78` lists four of the release workflow's six jobs**
    (missing `test-sdist` and `docs-check`) and says publish happens "only after
    steps 1–3 all pass" when it needs five. This release edited line 75 of that
    exact block and left the count wrong.
  - **The floor test's regex reads `>3.9` and `!=3.9` as floor 3.9** — it
    swallows the operator into a character class — and is not anchored to
    `[project]`. Neither is reachable today. Anchoring to `>=` closes both and
    makes every other operator fail loud, which is the polarity the rest of the
    test already has.
  - **`tests/test_backlog_0_6_0.py:456`'s docstring says "all four invocations
    that run this suite"** and names `docs-check` as the fourth, but
    `tools/docs_check.py:745` runs `pytest --collect-only`. Three invocations run
    it.
  - **`README.md:47` says "the same module object"** — the two modules are
    distinct objects; the functions are identical, which is what the executed
    block correctly asserts. One word: module → function.
  - **`cra_proxy_distribution(load_sample())` still raises `MissingColumnError`**
    (`ffiec_msa_md_median_family_income` is absent from the sample frame).

### Correction to the 0.6.0 entry

- **The 0.6.0 entry states the suite size in four places; three of the figures
  are wrong.** Measured by live collection: v0.5.0 ran **114**, 0.6.0 and 0.6.1
  run **396**, `tests/test_backlog_0_6_0.py` contributes **38** of those, so the
  suite immediately before that file was **358**. Against that — "Suite goes
  from 215 to 253" is wrong at **both** ends; it is 358 to 396, understating the
  suite by 143, and no prior document mentioned it. "has grown from 114 to 253"
  is wrong only at the second end: **114 is accurate**. "the suite now collects
  253" is wrong. **The number is 396** in all three places, which is what the
  README claims and what `docs-check` assertion 3 verifies against live
  collection.

  That 114 survives is worth stating rather than leaving implied. It is the
  count from which `FLOOR = 55` was correctly derived at v0.5.0, so a reader
  re-deriving this history has exactly one anchor that holds.
- **`FLOOR` is corrected from 125 to 198 in this release**, and it is the only
  live change here. It had been derived as "half of 253" from the figure above;
  against the real 396 its own stated rule gives 198. At 125 the gate stood at
  31.6% of the suite and caught only total deselection — a run executing 149
  tests, with 247 silently deselected, passed it. Every interpreter runs 396, so
  198 leaves 198 of headroom and cannot redden a true run. The integer changed;
  the derivation shell did not.
- **A live CI constant was derived from ungated prose and was wrong by 36%.**
  `docs-check` assertion 3 checks the test-count claim against live collection in
  the README, which says 396 and is right. It has no CHANGELOG assertion, so the
  copy the constant was actually read from was checked by nothing. That is the
  finding, and it is the argument for deriving `FLOOR` from the README rather
  than hardcoding it — deferred to 0.6.2, because it is new logic in the publish
  path.
- 0.6.0's entry is **correct** about the small-N suppression's span. It says
  `denial_rate_by_race` "has always dropped `derived_race` groups with fewer than
  five actionable applications", which matches the published sdists; it does not
  date the defect to 0.5.0. No correction needed there.

## [0.6.0] - 2026-08-05

### UPGRADING FROM 0.5.0 — READ THIS FIRST

**Calls that used to return a number now raise.** If you upgrade and something
throws, this section is why. Every new refusal subclasses `ValueError`, so an
existing `except ValueError` still catches it — which means a broad handler will
turn a refusal into whatever your fallback path does. Check your handlers.

| If you were doing this | You now get | Do this instead |
|---|---|---|
| `lending_by_tract(df)` where `df` pools 2021 with 2022 | `GeographyVintageError` | The tract delineation changed at that boundary; the same GEOID means different ground. Split at the boundary and present two panels, or narrow: `lending_by_tract(df, vintage=2010)` / `vintage=2020`. |
| `lending_by_county(df)` where `df` pools 2023 with 2024 | `GeographyVintageError` | Connecticut replaced eight counties with nine planning regions. Split at the boundary into two panels, or narrow: `lending_by_county(df, vintage=2020)` for the 2023 rows / `vintage=2023` for the 2024 rows. Filtering Connecticut out does **not** clear it — the verdict is on the years the frame spans, not the rows it holds. |
| Any guarded aggregation pooling 2024 or 2025 with another year | `GeographyVintageError` | 2024 and 2025 are **UNKNOWN**: no cited basis exists for them yet. A single-year 2024 or 2025 analysis still works and is *not* refused. Pooling needs a human to read the FFIEC census file vintage and add a cited entry. |
| `lending_desert_score(df)` on a frame with ≤ 4 tracts | `UnreachableFlagError` | `is_lending_desert` cannot be `True` below 5 tracts, so the old all-`False` output was a fabricated negative. Use `lending_by_tract(df)` for the underlying counts, or widen the frame. |
| `lending_desert_score(df, vintage=…)` that narrows below 5 tracts | `UnreachableFlagError` | Same. The floor is checked **after** narrowing, deliberately. |
| `lending_by_tract(df, vintage=2020)` where no year in `df` uses basis 2020 | `GeographyVintageError` | The narrowing selected zero rows. That is a malformed question, not a finding — the answer is not "nothing here". The message names the bases the frame actually contains. |
| `disparity_ratio(df, reference=…)` with an absent reference group | `ReferenceGroupError` (was a bare `ValueError`) | Unchanged behaviour, now typed. `except ValueError` still works. |
| `generate_disparity_report(df)` on a vintage-spanning frame | The refusal **propagates** | It used to be typeset into a markdown table cell, producing a report that looked complete with a refusal inside it. A report that fails to generate is the correct outcome. |
| `generate_disparity_report(df)` with a non-numeric `income` | `MissingColumnError`, raised up front | Previously `pd.cut` raised a bare `ValueError` mid-render that destroyed the whole report. Coerce: `df["income"] = pd.to_numeric(df["income"], errors="coerce")`. |
| Reading `denial_rate_by_race(df)` output | Three extra columns | `suppressed_groups`, `suppressed_applications`, `suppressed_group_names`. The n≥5 suppression is unchanged; it is no longer silent. Code selecting columns by position should select by name. |
| `lender_vs_market(df, lei)` output | Suppression columns are prefixed | `lender_suppressed_*` and `market_suppressed_*`. |
| Reading a `load_from_api` frame | One extra column | `limit_truncated`. |
| `from hmdaanalyzer.data.schema import CACHE_DIR` | `ImportError` | Removed with `loader.get_cache_dir()`. Neither was ever called and no cache was ever written. |
| `cra_proxy_distribution(df, include_purchased=True)` on a frame with no `action_taken == 6` rows | `EmptyUniverseError` (new) | It used to return four category rows with every count `0` over a zero denominator — which reads as "purchased no LMI loans" when the fact is "purchased loans were never fetched". The `EMPTY PURCHASED CUT` caveat that mitigated it sat on `table.caveat`, a sibling of `table.distribution`, so charting/exporting/concatenating the distribution dropped it. Supply purchased loans via `load_from_file`, or drop the flag — `include_purchased=False` is the default and is unaffected. |
| `racial_composition_by_tract(df)` | **Different numbers.** See "Changed output" below. | Not a refusal — read the next section before comparing against a 0.5.0 figure. |

**Nothing that was correct before is refused now**, with one correction to that
claim. A single-year frame, a frame whose years share a basis, and a frame with
no `activity_year` column at all are all unaffected.

The correction: a `decimal.Decimal` `income` column **was** briefly refused by
the 0.6.0 build's dtype gate and is accepted again — see "Fixed" below. It is
called out here because the sentence above was falsified by it, and a promise
that has been wrong once should say so rather than be quietly re-asserted.

### Changed output — `racial_composition_by_tract` denominator

**The numbers this function returns move, and they move up.** Read this before
comparing a 0.6.0 figure against a 0.5.0 one, or against any other package's.

It was the only analysis in this package with no `action_taken` filter. Its
denominator included action 4 (withdrawn by the applicant), action 5 (file closed
for incompleteness) and action 6 (purchased loan — an origination somebody else
made). Its nine siblings all filter `action_taken.isin([1, 2, 3])`. Both it and
they emit a column named `denial_rate`.

On a tract carrying one row per action 1–6:

| | `applications` | `denial_rate` |
|---|---|---|
| `lending_by_tract` (unchanged) | 3 | 0.333 |
| `racial_composition_by_tract` **0.5.0** | 6 | **0.167** |
| `racial_composition_by_tract` **0.6.0** | 3 | **0.333** |

The bias had a direction. Non-decision rows can only enlarge a denominator, so a
per-`(tract, race)` fair-lending rate was systematically **understating denials**
— the direction that matters most in this domain. Anyone who compared a 0.5.0
figure from this function against another package's denial rate, or against
`lending_by_tract` in this one, was comparing incompatible denominators.

`applications` narrows too, not only `denial_rate`. `applications` means
*actionable* applications at the nine other sites that emit it, and a tenth
meaning for one column name is the drift rather than the cure for it. The cost,
stated plainly: the racial **composition** is now the composition of actionable
applications, not of every LAR row touching the tract. A tract whose rows are all
withdrawals and purchases now yields no row at all — the honest answer, where a
0.0 denial rate over a denominator of withdrawals was not.

Pinned by `tests/test_action_taken_denominator.py`, which fails if the filter is
removed from either column.

### Added — the census-geography vintage rule

- **`hmdaanalyzer.geography_vintage`** — three declarative, individually cited
  `data year -> geography-key basis year` maps (`TRACT_GEOID_BASIS_BY_YEAR`,
  `COUNTY_CODE_BASIS_BY_YEAR`, `MSA_CODE_BASIS_BY_YEAR`) and one guard helper,
  `resolve_geography_vintage`, called from every geography-keyed aggregation.
  The full decision record is `hmdaanalyzer/methodology/tract_vintage_methodology.md`.
- **`GeographyVintageError`**, **`UnreachableFlagError`**, **`ReferenceGroupError`**
  — new typed refusals, all exported from the package root.
- **`vintage=` narrowing** on `lending_by_tract`, `lending_by_county`,
  `lending_desert_score`, `racial_composition_by_tract` and `lender_summary`.
  It selects the rows whose data year uses that basis; it never merges two
  delineations. A narrowing that selects no rows **raises** rather than returning
  an empty result.
- **Provenance columns on aggregation output.** A tract aggregation carries
  `tract_geoid_vintage` and `county_code_vintage` — both maps govern it — each
  with a `<column>_status` companion taking `CITED` / `UNKNOWN` /
  `NO_YEAR_COLUMN`. `lender_summary` carries the same facts as dict keys.
  `_clean` derives `tract_geoid_vintage` on loaded frames.

### Changed — BREAKING

- **Aggregations that pool data years whose geography keys do not mean the same
  thing now RAISE `GeographyVintageError` instead of returning a number.** This
  affects `lending_by_tract`, `lending_by_county`, `lending_desert_score`,
  `racial_composition_by_tract` and `lender_summary`. Code that concatenated
  years across a basis boundary and aggregated received a plausible, wrong
  result with no signal; it now receives a refusal naming the boundary, what
  would have merged, and four documented ways forward. **A single unmapped year
  on its own is not refused** — a 2025-only analysis works.
- **`lending_desert_score` raises `UnreachableFlagError`** below
  `DESERT_TRACT_FLOOR` tracts, where `is_lending_desert` is arithmetically
  unreachable and every tract would be returned `False` whatever the data says.
  The floor is derived at import from `DESERT_PERCENTILE_THRESHOLD`.
- **The report layer no longer swallows refusals.** Five `except` sites in
  `report/generator.py` are inverted onto a named `RENDERABLE_ERRORS` allowlist,
  so a refusal propagates instead of being typeset into a markdown table cell.
- **`disparity_ratio`** raises `ReferenceGroupError` (a `ValueError` subclass,
  so existing `except ValueError` callers are unaffected) where it raised a bare
  `ValueError`.
- **`EXPECTED_LAR_COLUMNS` is now the union of `RAW_LAR_COLUMNS` and
  `DERIVED_LAR_COLUMNS`.** The schema guard compares against the raw CFPB set
  only, so it detects *CFPB* drift rather than ours. The public name is
  unchanged and still importable.
- **`lending_by_state` is deliberately NOT guarded**, on a stated argument from
  absence (methodology coverage item 3).

### Fixed — build 2, from the hostile audit

- `DESERT_TRACT_FLOOR` is **derived** from `DESERT_PERCENTILE_THRESHOLD` at
  import instead of being a second hand-written constant. Moving the threshold
  previously left the floor arithmetically wrong with the whole suite green,
  fabricating `is_lending_desert=False` for every tract in frames of 5–10 tracts.
- A **null `activity_year`** no longer bypasses the guard, and neither does a
  **`float64` year column** — one blank cell flipped the dtype, `int("2021.0")`
  raised, every year collapsed to unmapped, and a decennial-spanning frame passed
  the guard silently. `vintage=` narrowing on such a frame is answerable again.
- The **uncited 2024 tract entry is removed**; 2024 is UNKNOWN in the tract map.
  It changes no refusal decision over any year-pair in 2018–2025.
- The refusal message **names constants that exist** (it built
  `CENSUS_TRACT_BASIS_BY_YEAR`, which never existed) and no longer sends the
  reader solely to a CFPB publication series that stops at 2023.
- The 2023→2024 refusal, which fires nationwide for a Connecticut-confined
  cause, now **says so and gives two exact ways through**.
- `§M6.5`'s harm claim is restated with **one denominator** — 1,695 of 1,742
  tract-years, not 845 of 871. The old phrasing understated the measured harm.
- Both county-boundary change records are now **cited per entry** (87 FR 34235 /
  FR Doc. 2022-12063 for Connecticut; Census *Substantial Changes* for Alaska),
  closing the methodology's last release blocker.

### Fixed — build 3, from the scoped hostile audit

Ten findings. One changed a computed number (`racial_composition_by_tract`, in
"Changed output" above); the rest put wrong instructions in front of a user at
the moment of refusal, which in a fair-lending tool is its own category.

- **A documented remedy that does not work is removed from all six places it
  appeared.** "Exclude Connecticut and re-run" — `df[df["state_code"] != "CT"]` —
  was in the README, the live `GeographyVintageError` message, this CHANGELOG's
  upgrade table, the methodology document shipped inside the wheel, the README's
  exception table, and **a test asserting it was present**, which meant deleting
  it broke the suite.

  It cannot work. `resolve_geography_vintage` compares the frame's **year set**
  against the basis maps and never reads `state_code` or `county_code`, so no row
  filter changes the verdict. Measured on a CT+IL 2023+2024 frame: after dropping
  every Connecticut row, `lending_by_county` still refuses and `lending_by_tract`
  still refuses. It was never executed before shipping.

  Making the guard honour it was not an option — methodology coverage item 19
  rejected state-scoping precisely because a verdict that depends on which rows a
  frame holds can be disarmed by subsetting. Replaced by the two paths that were
  executed and do work on both call paths: **split at the boundary into two
  panels**, and **`vintage=` narrowing**. Every message now also states
  positively that filtering the frame is not a way through.
  `tests/test_refusal_remedies_execute.py` runs each replacement remedy against
  the frame that triggers the refusal.
- **The exception lede contradicted its own table.** It said "every type
  subclasses `ValueError`, so existing `except ValueError` handlers keep working
  unchanged", six lines above a row stating `CFPBAPIError` is a `RuntimeError`.
  A reader who trusted the lede wrote `except ValueError` and every CFPB 403
  escaped it. The lede now splits the types by what went wrong and says there is
  no single base class that catches everything.
- **A `decimal.Decimal` `income` column is accepted again.** 0.6.0's new dtype
  gate used `is_numeric_dtype`, which is `False` for the `object` dtype a
  `Decimal` column has — so a column v0.5.0 accepted, and on which it produced
  byte-identical output to `float64`, became a `MissingColumnError`. `Decimal` is
  the natural dtype for a monetary column out of SQL `NUMERIC`. `Fraction`,
  `numpy` scalars and mixed numeric objects are accepted on the same footing;
  `datetime64` and numeric strings — the two defects the gate was built for —
  stay refused.

  Two things the widening also closed, found while testing it: a **`bool`
  `income` column passed the gate** (`is_numeric_dtype` is `True` for `bool`) and
  was binned as a column of 1s and 0s, a fabricated income distribution produced
  silently; a **`complex`** column reached `pd.cut` the same way. Both now raise.

  An object column containing **nulls** is refused, and the asymmetry with
  `float64` is deliberate and measured: `pd.cut` bins a `float64` column with
  `NaN` correctly but cannot bin *any* null in an object column, failing with
  `decimal.InvalidOperation` or `TypeError` — neither a `ValueError`, so neither
  catchable by anything this README documents, and both raised from inside the
  report's rendering. v0.5.0 did not accept that column either; it crashed. The
  refusal names `pd.to_numeric(..., errors="coerce")` as the fix, and the suite
  executes that fix on the refused frame.
- **`vintage_dropped_rows` is always present**, `0` when nothing was dropped, and
  `lender_summary`'s `dropped_rows_by_year` likewise (`{}`). It was the last
  field in either channel still signalling by its own absence — the exact defect
  the `*_status` columns were added to fix, left one field over in the same
  output. A `vintage=` call that dropped nothing and a call with no `vintage=`
  produced byte-identical column sets.

  Making it unconditional exposed a second defect: `lender_summary` merges two
  `provenance_keys()` dicts, and the county resolution — which never narrows and
  so always reports `{}` — **overwrote the tract narrowing's real count**. Fixed
  by keeping the record from the call that can narrow.
- **`cra_proxy_distribution(..., include_purchased=True)` raises** on a frame
  with no purchased loans instead of returning a zero table. See the upgrade
  table above.
- **The "every analysis" denominator claim is restated.** The README and
  `schema.py` both said widening the fetched action set "would change the
  denominator of every denial-rate, disparity and tract analysis in the package."
  Measured: **one of ten** — and only because of the
  `racial_composition_by_tract` defect above. With that fixed, **zero of ten**.
  The decision not to widen is unchanged and stands on the argument that holds:
  a purchased loan is not an application to this institution.
- **The README attributed the tract refusal to the wrong mechanism.** It gave the
  same example — a tract frame pooling 2023 with 2024 — for both the
  consulted-map rule and the UNKNOWN rule, and only the second is real. Since the
  uncited 2024 tract entry was removed, 2024 is UNMAPPED for tracts and the
  UNKNOWN rule fires first; the county consult has no live case as shipped, which
  `geography_vintage.py` already said and the README did not.
- **Threshold literals removed from two docstrings.** `geographic.py` wrote
  `denial_rate > 0.15` into the `lending_desert_score` formula display and
  claimed "the 0.15 denial-rate floor is a bare literal at the comparison site" —
  false since 0.6.0, and contradicted by a code comment ninety lines below it.
  `exceptions.py` re-typed `app_percentile < 25` and `For n <= 4`. Both now name
  the constants. The existing drift test splits source on `"""` and checks what
  comes *after* — so docstrings were outside it, which is how two copies survived
  a release that existed to remove them. Docstrings are now covered.
- **`docs-check.toml` described its own boundary wrongly.** It listed "20.7M LAR
  rows" and "the 42% GEOID figure" as unchecked README prose numbers. Neither is
  in `README.md`; 20.7M lives in the `GeographyVintageError` message. Corrected,
  and the skip-marked-block limitation is now recorded as a **demonstrated** gap
  with the remedy defect as its instance, not as a theoretical one.

### Fixed — the pre-existing backlog

Six independent defects found in the August 2 portfolio README-gap audit and the
recon, each re-verified against current code before being touched.

- **`limit` truncates; it does not sample — and the frame now says so.**
  `load_from_api` returns the first `limit` rows in the server's file order,
  which is not random with respect to lender, geography, race or outcome. Every
  returned row now carries **`limit_truncated`** (`True`/`False`), written even
  when `False` so that absence is never the signal. Under `load_range` the flag
  is per year, because a range can be complete in one year and truncated in
  another. The loader also prints a distinct line for a truncated fetch.
- **Small-N suppression is no longer silent.** `denial_rate_by_race` has always
  dropped `derived_race` groups with fewer than five actionable applications;
  the threshold is now the named constant `MIN_APPLICATIONS_FOR_RATE` and the
  output carries `suppressed_groups`, `suppressed_applications` and
  `suppressed_group_names`. `generate_disparity_report` renders an explicit note
  when it fires. Measured on `load_sample(n=60)`: eight race groups enter, three
  come out, and five protected classes previously vanished with no signal
  anywhere. **The threshold is unchanged** — moving it would silently change
  every number this package has ever produced. Not applied at tract level;
  that is a disclosure-methodology decision this release deliberately does not
  make.
- **`include_purchased` is documented as inert on frames this package loads.**
  `load_from_api`/`load_range` query the CFPB Data Browser with
  `actions_taken=1,2,3,4,5` (now the named constant `API_ACTIONS_TAKEN`) and
  `load_sample` generates only actions 1, 3 and 4, so no loader here can produce
  an `action_taken == 6` row. `cra_proxy_distribution(..., include_purchased=True)`
  therefore selected nothing and returned a zero-denominator table with four zero
  counts — indistinguishable from "this institution purchased no LMI loans". That
  table now carries an explicit `EMPTY PURCHASED CUT` caveat naming the cause.
  The default action set is deliberately **not** widened: that would change the
  denominator of every analysis in the package to fix a flag on one function.
- **`lending_desert_score`'s documentation matches its behaviour.** The docstring
  claimed a tract was scored "relative to its expected volume based on housing
  units". No housing-unit figure is read anywhere in the package —
  `tract_owner_occupied_units` and `tract_one_to_four_family_homes` arrive in the
  LAR and are never used. The docstring and README now state both rules exactly:
  `desert_score` is a 0.6/0.4 weighted composite for *ranking*, and
  `is_lending_desert` is a *conjunction* of a percentile cut and a denial-rate
  floor — **not** a threshold on `desert_score`, so a tract can top the ranking
  and still be `False`. The denial-rate floor is now the named constant
  `DESERT_DENIAL_RATE_FLOOR` (0.15) rather than a bare literal at the comparison
  site, matching what was already done for `DESERT_PERCENTILE_THRESHOLD`. It is
  recorded as unvalidated: it is not a CFPB threshold. No behaviour changed.
- **A non-numeric `income` no longer destroys the whole report.** `pd.cut` raised
  a bare `ValueError` on e.g. a `datetime64` income column; since the report
  layer's allowlist is inverted (correctly), that escaped and killed every
  section, including the four that never touch income. Fixed at the **input**:
  `denial_rate_by_income_band` and `generate_disparity_report` both validate the
  dtype through a shared `_require_numeric` helper and raise `MissingColumnError`
  naming the column and the fix. **`RENDERABLE_ERRORS` was deliberately not
  widened** — `ValueError` is `GeographyVintageError`'s base class, so admitting
  it would restore exactly the swallowing this release removed.
- **`CACHE_DIR` and `loader.get_cache_dir()` are removed.** Neither was called
  anywhere in the package or the suite, and no byte was ever written to that
  path. A name promising a cache that does not exist gets planned around.

### Added — release infrastructure

- **`docs-check`** (`tools/docs_check.py`, `docs-check.toml`,
  `docs-check-denylist.txt`), ported byte-identical from nmtc-mapper `5a4728a`.
  Six assertions against the **installed wheel**, run from a directory
  containing no package source: executed README blocks match committed output ·
  every symbol the README names is importable · the test count matches
  collection · no retired claim survives in prose or metadata · the artifact
  tested is the artifact built · every name in `__all__` appears in the README.
  It runs on every PR (`.github/workflows/test.yml`) and again in `release.yml`,
  where **`publish` now depends on it** — a README that misdescribes the
  artifact blocks the upload.

  Configured with `import_name = ["hmdaanalyzer", "hmda_analyzer"]`, so both
  documented import paths are vetted rather than one.

  **Assertion 6 found fourteen undocumented exports** out of 32 in `__all__`,
  including all three of this release's new exceptions — the fail-loud contract
  was the part the README never named. All fourteen were written up rather than
  laddered into the known-failures ledger, which is therefore empty. Each of the
  six assertions was individually verified capable of failing before the config
  was committed; the probes are recorded in `docs-check.toml`.
- **`docs/README.expected/`** — committed stdout for the four README blocks
  marked `run`, including a real `GeographyVintageError` refusal that is now
  executed on every PR rather than merely described.
- **`tests/test_backlog_0_6_0.py`** — 38 tests covering the six backlog items
  and the README-value coupling docs-check structurally cannot check.
  Suite goes from 215 to 253, still with zero skip markers.

### Changed — packaging and CI

- **Version is 0.6.0.** `pyproject.toml` is the single source of truth;
  `hmdaanalyzer.__version__` derives from installed metadata via
  `importlib.metadata`, and `release.yml`'s `verify-version` guard compares the
  git tag against `pyproject.toml` alone. There is no second place to bump.
- **`authors` metadata added** to `pyproject.toml`. It was absent through 0.5.0,
  so every published release carried an empty Author field on PyPI.
- **`test.yml`'s display name is now `CI`**, matching the other four repos in the
  portfolio. The **filename is unchanged** — GitHub keys run history to an id
  derived from the file path, so renaming the display name preserves every
  existing run while renaming the file would orphan them.
- **`MANIFEST.in`** ships `docs-check.toml`, `docs-check-denylist.txt`, `tools/`
  and `docs/README.expected/`, so the tarball carries everything needed to re-run
  the gate that certified it.
- **`release.yml`'s sdist execution floor re-derived** from 55 to 125. The rule
  stated in its own comment is "half of what the suite genuinely runs, rounded
  down to a round number"; the suite has grown from 114 to 253, so 55 had drifted
  to roughly a fifth and no longer meant what the comment said.

### Documentation

- `CONTRIBUTING.md` states the supported Python range as **3.11–3.14**, matching
  `requires-python` and all three CI matrices (it said 3.9–3.12 in two places).
- **README rewritten for 0.6.0.** It claimed **86 tests** where the suite now
  collects 253 — a live false claim, and the one docs-check assertion 3 exists to
  catch. Beyond the count: the vintage rule, both paths through the 2023→2024
  refusal, the `vintage=` parameter including that it can narrow to nothing, the
  five-tract floor, the provenance columns in an output-columns table, a full
  typed-exception table with a what-to-do column, `limit` truncation, small-N
  suppression, the real desert-score rules, and `include_purchased`'s inertness
  are all now documented. Python floor stated as 3.11 with the 3.11–3.14 matrix.
- **The "no columns are year-conditional" claim is retired as false.** The CFPB
  *header* is 99 columns in every year 2018–2025 — asserted by the suite — but
  values are year-conditional: `derived_msa_md` carries a `'0'` sentinel in 2018
  and 2019 and not later (CT 784 and 705 rows; MI 2,623 and 4,000; zero for both
  2020–2025). A consumer filtering `!= "0"` gets a test that is meaningful for
  one year and vacuous for the next, with no schema signal. The README now
  separates header stability from value stability explicitly.

## [0.5.0] - 2026-07-06

### Added

- **`cra_proxy_distribution(df, *, by="borrower"|"tract"|"both", include_purchased=False,
  year_column="activity_year")`** — a pure descriptive transform that computes the
  CRA-**proxy** borrower-income and geographic (tract-income) distribution of mortgage
  **originations** (`action_taken == 1`) from a HMDA LAR frame (the frame returned by
  `load_from_api` / `load_range`). No fetch, no network. Reachable under both
  `hmdaanalyzer` and `hmda_analyzer`.
  - Returns tidy per-`(dimension, universe, year)` tables (`category`, `count`,
    `cra_proxy_share`) plus, for each, the **classified denominator** and an explicit
    **excluded/unclassified count**. **No composite scalar** — a single score invites
    being read as a CRA grade.
  - **Bands (12 CFR §25/§228/§345):** Low `0 < MFI% < 50`, Moderate `[50, 80)`, Middle
    `[80, 120)`, Upper `≥ 120`; LMI = Low + Moderate. Lower-inclusive, upper-exclusive.
  - **Fabrication firewall (the whole point):**
    - **Unknown-first (tract).** `tract_to_msa_income_percentage` reserves `0` for
      "Unknown / not available" (verified at recon as the literal string `"0"` in the
      public LAR); Unknown rows (null / blank / `0`) are routed to an excluded tally
      **before** any threshold, so a literal `0` never reaches the `< 50` gate and is
      never fabricated into Low.
    - **No `1111`/"Exempt" drop (borrower).** `income` is in *thousands* and
      always-required; `1111` == a real **$1,111,000** Upper-income borrower and is kept.
    - **Missing area-median guard (borrower).** `ffiec_msa_md_median_family_income == "0"`
      (FFIEC-unmatched tracts) is a missing denominator — excluded, never divided
      (`income / 0 == inf` would fabricate Upper).
    - **Out-of-range & unknown-year exclusions.** Out-of-range values and unknown-year rows are excluded and surfaced (`out_of_range_tract_pct` / `out_of_range_income` / `unknown_year` reasons).
  - **Multi-year:** a frame spanning ≥2 `activity_year`s yields per-year distributions;
    each year's own annual `ffiec_msa_md_median_family_income` is applied (never one year's
    MFI across the panel).
  - **Purchased loans** (`action_taken == 6`) are excluded by default; `include_purchased=True`
    adds them as a **separate, labeled** `universe="purchased"` cut — never blended.
  - **Proxy firewall in the output shape:** the share column is named `cra_proxy_share`
    (so "CRA" never appears without "proxy" adjacent, even in a copied cell); **every table**
    carries the `STANDARD_CRA_PROXY_CAVEAT` (not-assessment-area-bound, not-a-performance-measure)
    and the explicit "distribution only; no comparator — not interpretable as CRA
    performance" line; borrower tables also carry the combined-income upward-bias caveat and,
    when `by="both"`, the differing-denominators warning.
- **`STANDARD_CRA_PROXY_CAVEAT`** — the standing proxy caveat string, exported under both
  import aliases.
- **`get_methodology_path(filename="cra_proxy_methodology.md")`** — accessor returning the
  path to the CRA-proxy methodology bundled **inside the wheel**, so the firewall and
  limitations travel with the installed tool. Raises `FileNotFoundError` for an unknown name.

### Notes

- **This is a PROXY, not CRA analysis.** It is never a CRA rating, grade, metric, or
  performance evaluation. It is **not assessment-area-bound** (HMDA has no assessment-area
  concept), mortgage-only, and its reporter population ≠ CRA-covered institutions.
- **No comparator/benchmark in v1** — the meaningful CRA comparator is a demographic
  (ACS/census) baseline, deferred to v2 with the census join. `income` and the two FFIEC
  fields are **census-appended to the public LAR** (not "HMDA-only").
- Borrower and tract distributions use **different denominators** (NA-income multifamily /
  non-natural-person loans carry a valid tract) — **do not difference the two LMI%s**.

## [0.4.0] - 2026-07-06

### Added

- **`load_range(start_year, end_year, ...)`** — fetch HMDA LAR across an inclusive
  range of years and return one vertically-concatenated DataFrame with an
  `activity_year` provenance column. Reachable under both `hmdaanalyzer` and
  `hmda_analyzer`. Single-year `load_from_api` is unchanged.
  - Each year is fetched with the existing single-year path, so `state`, `lei`,
    `county`, and `limit` apply **identically to every year** (`limit` is
    per-year).
  - **Fail-loud, no partial:** if any year's fetch fails, `load_range` re-raises
    immediately with the failing year named (a `CFPBAPIError` keeps its
    status/body) and returns no partial frame.
  - **Schema guard:** every fetched year is validated against a canonical column
    set; a missing or unexpected column raises the new
    **`SchemaValidationError`** (naming the year) rather than being silently
    NaN-filled or dropped — a regression guard against a silent CFPB schema change.
  - **Provenance:** the native `activity_year` field is used and asserted to match
    the requested year; a wrong-year payload raises the new
    **`ActivityYearMismatchError`**.
  - **Legitimate empty:** a valid year matching zero rows is not an error — its
    correctly-columned empty frame participates in the concat.
- **`SchemaValidationError`** and **`ActivityYearMismatchError`** typed exceptions
  (both subclass `ValueError`), importable from `hmdaanalyzer` / `hmda_analyzer`.

### Notes

- The CFPB Data Browser column schema is **identical across 2018–2025**
  (empirically verified), so no columns are year-conditional — a single canonical
  expected-column set validates every year.
- Multi-year national pulls are enormous: the same filters apply to every year, so
  always filter multi-year loads. `load_range` streams each year to `limit`; it
  does not silently cap or block.

## [0.3.1] - 2026-06-23

### Fixed

- API requests now send an identifying User-Agent + Accept/Accept-Language
  headers, resolving an HTTP 403 "Access Denied" from the Akamai edge that
  was reproduced from cloud/datacenter environments (e.g. Google Colab).
  Residential connections were unaffected.
- HTTP errors now raise a typed `CFPBAPIError` (subclass of `RuntimeError`, so
  existing `except RuntimeError` handlers keep working) with a status-aware,
  accurate message and the API response body attached. A 403 is now correctly
  described as an edge/access block common from cloud notebooks — not a
  problem with the query's year/state/county values, which the previous
  message wrongly implied.

### Notes

- Cloud/hosted environments may still hit edge blocks under some conditions;
  the new message explains the situation and the local/manual-download fallback.

## [0.3.0] - 2026-06-01

This is a **SemVer-breaking** release (0.2.1 → 0.3.0). When a required column is
missing, analysis functions now **raise** `hmdaanalyzer.MissingColumnError` (a
subclass of `ValueError`, so existing `except ValueError` handlers keep working).
Some of these functions previously **silently returned an empty result**; others
already raised a generic `ValueError`. In a fair-lending context a silent empty
result could read as "no disparity"; a schema problem must now fail loudly — with a
typed, diagnosable error — instead of masking a bad query.

### Changed (BREAKING)

- **Missing required column now raises `MissingColumnError`.** The error message
  names the function and the missing column(s). Two prior behaviors are unified
  under the new typed error:
  - **Previously returned an empty result *silently*** (the dangerous case — an
    empty result that could read as "no disparity"): `racial_composition_by_tract`,
    `lending_by_state`, `top_lenders_by_volume`, and `denial_reasons_by_race`.
  - **Previously raised a generic `ValueError`** (now upgraded to the typed
    `MissingColumnError`, which still subclasses `ValueError`):
    `denial_rate_by_race`, `lending_by_tract`, and `lending_by_county`.

- **Silent filter-skips now raise.** When a filtering argument is supplied but the
  column it filters on is absent, the call no longer silently computes
  whole-market results — it raises `MissingColumnError`:
  - `lender_summary(df, lei=...)` when `df` has no `lei` column
  - `lender_vs_market(df, lei=...)` when `df` has no `lei` column (previously
    compared the whole market against itself, yielding an all-zero `vs_market`)
  - `generate_disparity_report(df, lei=...)` when `df` has no `lei` column
  - `top_lenders_by_volume(df, state=...)` when `df` has no `state_code` column

- **`lei=""` is now a real empty-matching filter value.** In 0.2.1 a falsy `lei`
  (`""`) was treated as "all lenders"; truthiness guards (`if lei and ...`) are now
  `if lei is not None`, so an empty string is an explicit filter that matches no
  rows rather than silently widening the scope to the whole market.

- **`generate_disparity_report` validates its schema up front and no longer emits a
  misleading report.** It now checks the columns its sections require
  (`action_taken`, `derived_race`, `is_denied`, `income`) before rendering and
  raises `MissingColumnError` on a missing column, instead of swallowing the error
  into a table cell and producing an empty "Key Findings" section that read as
  "no disparity." For a `lei` that matches zero rows (including `lei=""`) it now
  returns a clean *no-records* report instead of raising `IndexError`.

### Added

- **`MissingColumnError`** exported from both `hmdaanalyzer` and the `hmda_analyzer`
  shim. Distinguishes a *schema problem* (missing column → raises) from a
  *legitimate empty result* (well-formed query that matched no rows → still returns
  an empty DataFrame/dict, e.g. `lender_summary` for an unknown but validly-typed
  LEI).

- **`tests/test_missing_column.py`** — through-function contract tests on real
  `load_sample()` data covering every raising function, the filter-skip guards, the
  legitimate-empty paths, and `MissingColumnError`'s `ValueError` compatibility.

## [0.2.1] - 2026-05-29

### Fixed

- **`denial_reasons_by_race()` returned empty on every live CFPB dataset.** The CFPB Data
  Browser CSV names enumerated fields with hyphens (`denial_reason-1`, `applicant_race-1`,
  etc.), but `_clean()` only lowercased and stripped column names — the hyphen survived,
  the underscore name `denial_reason_1` that the analysis code expected never matched, and
  the function silently returned an empty DataFrame. The existing synthetic test was
  falsely green because `load_sample()` emitted the underscore form directly, skipping
  the normalization gap. `_clean()` now replaces hyphens with underscores so live data and
  synthetic data take the same path.

### Changed

- **`load_sample()` now generates the raw `denial_reason-1` field with a hyphen**, matching
  the CFPB Data Browser CSV format. After `_clean()`, the observable output column is still
  `denial_reason_1` (underscore), so this is a fidelity-only change with no consumer-visible
  effect. The other enumerated fields are intentionally left on underscore form in this
  release; broader fixture fidelity is a tracked follow-up.

- **Strengthened `test_denial_reasons_by_race`.** The previous assertion was
  `isinstance(result, pd.DataFrame)`, which passed even when the function returned empty
  on every live dataset. The test now asserts the result is non-empty, has the documented
  columns, and that mapped denial-reason labels (not "Unknown") are present.

- **Added `test_denial_reasons_by_race_handles_cfpb_hyphenated_columns`** — a regression
  test that builds a raw frame with the hyphenated CFPB column name, runs it through
  `_clean()`, and asserts the analysis returns mapped, non-empty results. This is the test
  that would have caught the v0.2.0 bug.

### Added

- **Release CI** (`.github/workflows/release.yml`): tag-triggered pipeline with four gates —
  `verify-version` (tag vs. `pyproject.toml` via `tomllib`), `build` (uploads wheel as
  artifact), `test-wheel` (installs the wheel into a fresh venv on Python 3.9–3.12, asserts
  `hmdaanalyzer.__file__` resolves under site-packages so tests can't accidentally import
  the source tree, then runs `pytest -m "not live" --import-mode=importlib`), and `publish`
  (OIDC trusted publishing). All five third-party actions are SHA-pinned.

- **Test CI** (`.github/workflows/test.yml`): push/PR matrix across Python 3.9–3.12, plus a
  dual-import shim check (`import hmdaanalyzer` and `import hmda_analyzer` both work and
  report the same version).

- **`CONTRIBUTING.md`**: release runbook documenting the bump → tag → push flow, the
  single-source version invariant, OIDC trusted-publisher setup, the yank policy, and the
  anti-patterns the CI guards against.

### Internal

- **Single version source of truth.** `pyproject.toml` is now canonical; `setup.py` is
  removed, and `hmdaanalyzer/__init__.py` derives `__version__` at import time via
  `importlib.metadata.version("hmda-analyzer")`. The previous three-place hardcoded
  version (pyproject, setup.py, `__init__`) made tag/version drift easy; only
  `pyproject.toml` is now editable. The `hmda_analyzer` shim continues to re-export
  `__version__` unchanged.

- Package discovery moved from `setup.py`'s `find_packages()` into
  `[tool.setuptools.packages.find]` in `pyproject.toml`, with explicit `include` for both
  `hmda_analyzer*` and `hmdaanalyzer*`.

- `pyproject.toml` license field updated to the SPDX-string form
  (`license = "MIT"`), requiring `setuptools>=77`.

- Pytest configured with `--import-mode=importlib` so the source tree is not implicitly
  prepended to `sys.path` — the wheel-test job needs this to verify imports resolve to
  site-packages.

## [0.2.0] — 2026-05-19

### Fixed

- **`load_from_api(limit=N)` now works correctly.** The CFPB Data Browser API ignores a
  row-count query parameter and returns the full state/county file on every call. The loader
  now streams the response line-by-line and stops at `limit` rows, so
  `load_from_api(state="IL", limit=10_000)` returns ≤ 10,000 records without downloading
  the entire multi-hundred-thousand-record state dataset.

- **API errors now raise `RuntimeError`.** Previously, any API failure (timeout, HTTP error,
  network error) was silently caught and returned as an empty DataFrame, making it impossible
  to distinguish "no data matched" from "the API is down." `load_from_api` now raises
  `RuntimeError` with a descriptive message and the root cause attached.

- **`load_sample()` loan amounts corrected to dollars.** Loan amounts were generated in
  thousands (e.g. 361), while the live CFPB API returns actual dollars (e.g. 225000).
  Sample data now produces dollar-scale values consistent with the live API.

- **README quickstart: lending-desert example called the wrong function.** `deserts` was
  assigned from `lending_by_tract()` (a copy of the line above) instead of
  `lending_desert_score()`. Fixed — the quickstart now demonstrates the lending-desert
  feature correctly.

### Added

- **`import hmda_analyzer` now works** as an alias for `import hmdaanalyzer`, matching the
  pip install name `hmda-analyzer`. Both import forms are equivalent after
  `pip install hmda-analyzer`.

- **`load_sample()` now includes all real CFPB `derived_race` categories.** The categories
  `"2 or more minority races"`, `"Race Not Available"`, and `"Joint"` are now generated with
  realistic weights, matching the full shape of live CFPB data.

### Deferred (noted, not fixed in this release)

- Tests are bundled in the wheel (non-standard; tests belong only in the source tarball)
- No docs site or API reference beyond inline docstrings
- No README badges
- Example notebook (`examples/hmda_disparity_demo.ipynb`) not included in wheel
