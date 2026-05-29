# CHANGELOG

## [Unreleased]

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
