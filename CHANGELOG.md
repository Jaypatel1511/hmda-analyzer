# CHANGELOG

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
