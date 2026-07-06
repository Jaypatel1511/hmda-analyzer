# CHANGELOG

## [Unreleased]

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
