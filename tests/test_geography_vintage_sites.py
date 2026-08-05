"""The site-list gate.

One shared helper stops six *copies* of the vintage check from diverging. It does
nothing about a **seventh site that never calls the helper at all** — and before
this file there was no test, no lint rule and no CI step that enumerated
geography-keyed operations. The inventory in the methodology is a snapshot in a
document, and the document does not run.

This sweep is that inventory, executed. It walks the installed package with
``ast``, collects every call of an identity-forming verb on a geography column,
attributes each to its enclosing function, takes the transitive closure over the
call graph so ``lending_desert_score`` inherits its exposure from
``lending_by_tract``, and asserts **set equality** against a literal expected set.

Set equality, not a subset and not a count, and the distinction is the whole
point: a count passes when one site is added and another deleted; a subset check
passes when a site is added. Equality forces a deliberate edit to the expected
set below, which is the moment the author is asked whether the new site is
guarded.

**What this does NOT cover, stated because a gate that misdescribes its own
coverage is the defect this engagement keeps closing:**

1. It does not cover ``hmdaanalyzer/report/``. The sweep walks that directory,
   but ``report/`` contains no geography-keyed aggregation, so the expected set
   is silent about it. A sixth ``except Exception`` added to
   ``report/generator.py`` tomorrow would swallow ``GeographyVintageError`` and
   **no test here would fail**. The inverted allowlist there is a convention,
   not a gate.
2. It does not cover a site that reaches a geography key by a route the verb
   list misses — a ``.loc`` selection, a hand-rolled dict lookup, or a key
   assembled from string slices (coverage item 10).
3. It asserts that a site is *enumerated*, not that it is *guarded*. The
   ``GUARDED_SITES`` assertion below is the second half, and it is a literal
   too.
"""
import ast
import pathlib

import pytest

import hmdaanalyzer

PACKAGE_ROOT = pathlib.Path(hmdaanalyzer.__file__).parent

# Operations that treat a column's values as object identities: they collapse,
# dedupe, align, or index on them. The v1 draft's grep list
# (groupby|merge|set_index) missed `lender.py`'s `nunique()`, which is why this
# is a verb SET applied by AST rather than a regex.
IDENTITY_VERBS = frozenset({
    "groupby", "nunique", "unique", "value_counts", "drop_duplicates",
    "duplicated", "set_index", "merge", "join", "pivot", "pivot_table",
    "crosstab", "reindex", "isin", "map",
})

GEOGRAPHY_COLUMNS = {
    "census_tract": "tract",
    "county_code": "county",
    "state_code": "state",
    "derived_msa_md": "msa",
}

# ── The declared inventory. Editing either literal is the point. ─────────────

#: Every (function, geography basis) pair the sweep may find. Adding a
#: geography-keyed aggregation anywhere in the package fails this assertion
#: until the author adds it here — and deciding what to write here is the moment
#: they are asked whether it needs a guard.
EXPECTED_SITES = frozenset({
    ("lending_by_tract", "tract"),
    ("lending_desert_score", "tract"),          # inherited via lending_by_tract
    ("racial_composition_by_tract", "tract"),
    ("lender_summary", "tract"),
    ("lending_by_county", "county"),
    ("lender_summary", "county"),
    # DELIBERATELY UNGUARDED, and enumerated so it stays visible. `state_code`
    # gets no basis map on an argument from absence: nothing was measured to move
    # a state code in 2018-2025, which is not a demonstration that they cannot
    # (methodology coverage item 3).
    ("lending_by_state", "state"),
})

#: The subset that a basis map actually guards: six (site, key) pairs across five
#: public functions. `derived_msa_md` has zero aggregation sites in the package,
#: so its map ships with no internal caller (methodology §M6.2, §M6.6).
GUARDED_SITES = frozenset({
    ("lending_by_tract", "tract"),
    ("lending_desert_score", "tract"),
    ("racial_composition_by_tract", "tract"),
    ("lender_summary", "tract"),
    ("lending_by_county", "county"),
    ("lender_summary", "county"),
})


def _string_constants(node):
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


class _Sweep(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.direct = []
        self.calls = {}

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.calls.setdefault(node.name, set())
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        enclosing = self.stack[-1] if self.stack else "<module>"
        if isinstance(node.func, ast.Name):
            self.calls.setdefault(enclosing, set()).add(node.func.id)
        if isinstance(node.func, ast.Attribute) and node.func.attr in IDENTITY_VERBS:
            found = set()
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                found.update(_string_constants(arg))
            # ...AND the subscript the call is made on: `df["census_tract"]
            # .nunique()` carries its key in the receiver, not the arguments.
            found.update(_string_constants(node.func.value))
            for name in found:
                if name in GEOGRAPHY_COLUMNS:
                    self.direct.append(
                        (enclosing, GEOGRAPHY_COLUMNS[name], node.func.attr, name)
                    )
        self.generic_visit(node)


def _sweep_package():
    """Return (sites, detail) for the installed package."""
    exposure, callgraph, detail = {}, {}, []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sweep = _Sweep()
        sweep.visit(tree)
        for fn, basis, verb, col in sweep.direct:
            exposure.setdefault(fn, set()).add(basis)
            detail.append((str(path.relative_to(PACKAGE_ROOT)), fn, verb, col, basis))
        for caller, callees in sweep.calls.items():
            callgraph.setdefault(caller, set()).update(callees)

    # Transitive closure: a function that calls an exposed function is exposed.
    inherited = {fn: set(bases) for fn, bases in exposure.items()}
    changed = True
    while changed:
        changed = False
        for caller, callees in callgraph.items():
            for callee in callees:
                if callee in inherited and not inherited.get(callee, set()) <= inherited.get(caller, set()):
                    inherited.setdefault(caller, set()).update(inherited[callee])
                    changed = True

    sites = frozenset((fn, basis) for fn, bases in inherited.items() for basis in bases)
    return sites, detail


def test_geography_key_site_list_is_exactly_as_declared():
    """Set equality over every geography-keyed operation in the package.

    Fails loudly, naming the offender, when a site is added OR removed. If this
    fails after you added an aggregation: decide whether your new site needs
    ``resolve_geography_vintage``, wire it if so, then add it to both literals
    above. Do not just append to EXPECTED_SITES to make the test pass —
    that is the exact moment the rule is supposed to interrupt you.
    """
    found, detail = _sweep_package()

    unexpected = found - EXPECTED_SITES
    vanished = EXPECTED_SITES - found

    def where(site):
        return [d for d in detail if d[1] == site[0] and d[4] == site[1]] or ["(inherited via the call graph)"]

    assert not unexpected, (
        "UNGUARDED-BY-DEFAULT geography-keyed site(s) found that the site list "
        f"does not declare: {sorted(unexpected)}\n"
        + "\n".join(f"    {s}: {where(s)}" for s in sorted(unexpected))
        + "\n  See hmdaanalyzer/methodology/tract_vintage_methodology.md §M2.4. "
        "A new site must call resolve_geography_vintage() unless there is a "
        "stated reason it cannot be guarded — and then that reason belongs in "
        "the coverage list, not in silence."
    )
    assert not vanished, (
        f"Declared geography-keyed site(s) no longer found: {sorted(vanished)}. "
        "If the site was deliberately removed, delete it from EXPECTED_SITES "
        "(and GUARDED_SITES) in the same change."
    )
    assert found == EXPECTED_SITES


def test_every_guarded_site_actually_calls_the_shared_helper():
    """The site list says a function is guarded; this checks it calls the helper.

    Enumeration alone would pass for a function listed in GUARDED_SITES that
    never guards anything. This asserts the call exists, per function, and that
    a function with two guarded keys makes two calls — ``lender_summary`` has
    both a tract site and a county site and needs both.
    """
    wanted = {}
    for fn, _basis in GUARDED_SITES:
        wanted[fn] = wanted.get(fn, 0) + 1

    calls_per_function = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            n = sum(
                1 for c in ast.walk(node)
                if isinstance(c, ast.Call)
                and isinstance(c.func, ast.Name)
                and c.func.id == "resolve_geography_vintage"
            )
            if n:
                calls_per_function[node.name] = calls_per_function.get(node.name, 0) + n

    # lending_desert_score inherits its guard by calling lending_by_tract; it
    # does not call the helper itself, and must not (that would guard twice).
    direct_guard_expected = {fn: n for fn, n in wanted.items()
                             if fn != "lending_desert_score"}
    assert calls_per_function == direct_guard_expected, (
        f"resolve_geography_vintage() call sites are {calls_per_function}, "
        f"expected {direct_guard_expected}. Six (site, key) pairs across five "
        f"public functions; lending_desert_score inherits from lending_by_tract."
    )


def test_the_sweep_can_actually_fail():
    """A gate nobody has seen fail is a gate nobody knows works.

    Feeds the sweep's own matching logic a synthetic seventh site and asserts it
    is detected. Without this, a sweep broken so that it finds nothing would
    pass ``found == EXPECTED_SITES`` only by accident — and a sweep that finds
    nothing is precisely the vacuous-gate shape this file exists to prevent.
    """
    source = (
        "def newly_added_analysis(df):\n"
        "    return df.groupby('census_tract').size()\n"
    )
    sweep = _Sweep()
    sweep.visit(ast.parse(source))
    assert ("newly_added_analysis", "tract", "groupby", "census_tract") in sweep.direct

    subscript_source = (
        "def another(df):\n"
        "    return df['county_code'].nunique()\n"
    )
    sweep2 = _Sweep()
    sweep2.visit(ast.parse(subscript_source))
    assert ("another", "county", "nunique", "county_code") in sweep2.direct, (
        "The subscript rule regressed: df['county_code'].nunique() carries its "
        "key in the receiver, and a verb-list grep misses it."
    )


def test_sweep_actually_read_the_installed_package():
    """Guards against the sweep silently walking an empty directory.

    If ``PACKAGE_ROOT`` were wrong — a plausible failure when running against an
    installed sdist rather than the source tree — every set above would be empty
    and set equality would fail loudly, but only by luck of EXPECTED_SITES being
    non-empty. This asserts the input was real.
    """
    modules = list(PACKAGE_ROOT.rglob("*.py"))
    assert len(modules) >= 8, f"only found {len(modules)} modules under {PACKAGE_ROOT}"
    assert (PACKAGE_ROOT / "analysis" / "geographic.py").exists()
