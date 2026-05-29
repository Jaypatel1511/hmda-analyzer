# Contributing to hmda-analyzer

## Release Process

**Every PyPI release must follow these steps in order.** The CI release workflow
enforces step 3 automatically and will refuse to publish if the invariant is violated.

### Invariant

> The git tag and `pyproject.toml` version must agree. `hmdaanalyzer.__version__` is
> derived at import time from the installed package metadata (via `importlib.metadata`),
> so it automatically matches the wheel that was built — no second place to edit.
> A tag/pyproject mismatch causes the release workflow to fail at the version-guard step,
> before any wheel reaches PyPI.

### Step-by-step

**1. Implement changes on a feature branch; merge to `main` via pull request.**
- All `main` pushes and PRs run `test.yml` (pytest, Python 3.9–3.12)
- Do not push version bumps directly to `main` — include them in the PR

**2. Bump the version.**

Edit `pyproject.toml` — this is the **only** place:
```toml
version = "0.2.1"   # was 0.2.0
```

`hmdaanalyzer/__init__.py` reads the version from package metadata at import time
(`importlib.metadata.version("hmda-analyzer")`), so it automatically reflects
whatever is in `pyproject.toml`. Do NOT hardcode a version string there.

Version policy (SemVer for 0.x packages):
- `0.x.y` → `0.x.(y+1)` (PATCH): bug fixes, docs, no API changes
- `0.x.y` → `0.(x+1).0` (MINOR): new features or any backwards-incompatible API change
- Adding a required parameter without a default is always a MINOR bump, not a patch

**3. Update CHANGELOG.md.**

Move changes from `[Unreleased]` to `[0.2.1] — YYYY-MM-DD`. Be honest: if anything
was broken in a prior release, say so.

**4. Commit.**

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release v0.2.1"
```

**5. Tag the commit.**

```bash
git tag -a v0.2.1 -m "Release v0.2.1"
```

The tag must match `pyproject.toml` exactly (without the `v` prefix). The CI release
workflow extracts `GITHUB_REF` and compares it to `pyproject.toml`; a mismatch fails
the `verify-version` job before the wheel is built.

**6. Push the commit and tag together.**

```bash
git push origin main
git push origin v0.2.1
```

Pushing the tag triggers `.github/workflows/release.yml`.

**7. CI does the rest — do not publish manually.**

The release workflow:
1. **verify-version** — fails immediately if tag ≠ pyproject.toml version
2. **build** — `python -m build` from the tagged commit; uploads wheel as artifact
3. **test-wheel** — installs the wheel (not editable source) into a fresh venv on each
   of Python 3.9, 3.10, 3.11, 3.12; asserts `hmdaanalyzer.__file__` resolves to
   site-packages (not the source tree); runs `pytest -m "not live"` against the installed
   package; fails the release if any test fails on any Python version
4. **publish** — publishes to PyPI via OIDC trusted publishing only after steps 1–3 all pass

**8. Verify on PyPI.**

```
pip install hmda-analyzer==0.2.1
python -c "import hmdaanalyzer; print(hmdaanalyzer.__version__)"
# Expected: 0.2.1
```

---

### Yanking a Release

If a version must be yanked:

1. Yank on PyPI manually (Web UI or `twine yank hmda-analyzer==0.2.1`)
2. Add a `YANKED` notice to its `CHANGELOG.md` entry explaining why
3. Do NOT delete the git tag — the tag and the yank notice constitute the audit trail
4. Ship a corrective release as the next version

---

### PyPI Trusted Publishing Setup

The release workflow uses OIDC trusted publishing (no API token required). One-time setup
by the repository owner:

1. Go to PyPI → Account Settings → Publishing → Add a new publisher
2. Project: `hmda-analyzer`
3. Owner: `Jaypatel1511`
4. Repository: `hmda-analyzer`
5. Workflow: `release.yml`
6. Environment: `pypi`

Once configured, the `publish` job in `release.yml` authenticates automatically.

---

### What NOT to do

- **Do not** run `twine upload` locally. The release workflow is the only publish path.
- **Do not** push a tag before bumping `pyproject.toml` — the guard will fail the release
  and the tag will be stranded.
- **Do not** hardcode a version string in `hmdaanalyzer/__init__.py`. The version is
  derived from package metadata; editing it there has no effect on the installed wheel.
- **Do not** amend commits that have already been tagged. Delete the tag, amend, re-tag.
- **Do not** set `pyproject.toml` version ahead of the tag to "reserve" a number. The
  guard compares the pushed tag to `pyproject.toml` at that exact commit.
