"""
Census-geography key vintage: the declarative year→basis maps and the single
guard helper that every geography-keyed aggregation calls.

The defect this closes: an HMDA LAR geography key does not mean the same thing in
every data year. A GEOID such as ``24510130400`` exists in both the 2021 and the
2022 LAR and denotes a different piece of ground in each. Concatenate the two
years and ``groupby("census_tract")`` silently sums two different places into one
row — a plausible, wrong, tract-level result with no signal in the object, the
console, or the column set.

The full decision record, including every rejected alternative and the
measurement behind it, is
``hmdaanalyzer/methodology/tract_vintage_methodology.md``. Section references
below (§M1.2, §M1.3, …) point into it.

**The rule is entirely declarative.** Every guard reads ``activity_year``, looks
up one or two cited maps, and raises or does not. Nothing here compares key sets
and nothing here carries a tuned constant. A measured per-county disjointness
limb was specified through v3 of the methodology and removed in v4: zero unique
findings across every year-pair measured, a 5:0 false-positive record, and a row
floor fitted to the same sample that produced both classes (§M1.2b). The gap that
removal leaves — a within-county key re-scheme at a year no basis map moves — is
stated as an open, undefended gap in coverage item 15, not covered here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from hmdaanalyzer.exceptions import GeographyVintageError

# ── The three declarative maps ────────────────────────────────────────────────
#
# Data year -> geography-key BASIS YEAR. Values are plain ``int`` basis years
# (§M1.2, §M4.2): orderable with ``<``, identical to the provenance column's
# representation, and survive a CSV round-trip. Deliberately NOT a threshold
# constant (cannot express a third value, so the 2030 delineations would force a
# breaking change at exactly the boundary this rule exists to survive), NOT a
# ``Categorical`` (``pd.concat`` of disjoint int categories returns plain
# ``int64``, silently discarding the closed-domain guarantee that is the only
# reason to pay for one), and NOT an enum (does not survive serialization).
#
# The three maps carry DIFFERENT basis years for the same data year because the
# three keys are redrawn by different authorities on different schedules —
# Census decennial delineation for tracts, Census county-equivalent changes for
# counties, OMB delineation bulletins for MSAs. Do not collapse them into one
# map: a single "geography basis year" would be wrong for at least one key at
# every boundary the methodology measures (§M1.2).
#
# The name deliberately differs from nmtc-mapper's ``TRACT_VINTAGE``. There it
# means "the one binding in force"; here it means "a year-indexed lookup". Same
# name for different shapes, in one portfolio, is how a future edit copies the
# wrong semantics across repos (§M1.2).
#
# EVERY ENTRY CARRIES ITS CITATION. Adding a year is a deliberate human act with
# a citation attached, every time (§M1.3). Do not extrapolate an entry from
# measurement: measurement cannot establish a basis, and "assume the newest
# vintage we know about" is wrong in the exact way this module exists to
# eliminate — silently, and exactly at a boundary (§M1.3, §M6.4).

#: The controlling rule for all three maps: Regulation C, Supplement I, Official
#: Interpretation of Paragraph 4(a)(9)(ii)(C), Comment 1 — "A financial
#: institution complies with § 1003.4(a)(9)(ii)(C) if it uses the boundaries and
#: codes in effect on January 1 of the calendar year covered by the
#: loan/application register that it is reporting." Retrieved 2026-08-03 and
#: 2026-08-04 from consumerfinance.gov/rules-policy/regulations/1003/4/.
#:
#: Note what the comment does NOT settle: it is a safe harbor fixing WHEN the
#: codes are read, not WHICH delineation will be in effect on that date. The
#: per-year facts below carry that load. The FFIEC Filing Instructions Guide was
#: proposed as the citation and does not carry it — the 2022 FIG's entire
#: instruction is "Enter the 11-digit census tract number as defined by the U.S.
#: Census Bureau. Do not use decimals." (§M1.1)
REG_C_COMMENT = "12 CFR Part 1003, Supp. I, Comment 4(a)(9)(ii)(C)-1"

#: Census-tract GEOID delineation basis, by HMDA data year.
TRACT_GEOID_BASIS_BY_YEAR: dict[int, int] = {
    # 2010 Census tract delineations. CFPB, *Summary of 2021 Data on Mortgage
    # Lending* (pub. 2022-06-16): "The 2021 HMDA data use the census tract
    # delineations, population, and housing characteristic data from the
    # 2011-2015 American Community Survey (ACS)." The ACS does not delineate
    # tracts — it uses the 2010 decennial delineations; CFPB's sentence
    # conflates the geometry basis with the demographic vintage (§M1.1, §M4.3).
    # 2018-2020 are the same delineation by the same source, unchanged.
    2018: 2010,
    2019: 2010,
    2020: 2010,
    2021: 2010,
    # 2020 Census tract delineations. CFPB, *Summary of 2022 Data on Mortgage
    # Lending* (pub. 2023-06-29): "The 2022 HMDA data use the census tract
    # delineations, population, and housing characteristic data from the 2020
    # Census." The two-year lag from the 2020 Census is real and was contingent
    # on publication timing — it is not computable in advance, which is why
    # §M1.3 forbids predicting the next one.
    2022: 2020,
    # CFPB, *Summary of 2023 Data on Mortgage Lending* (pub. 2024-07-11): "The
    # 2023 HMDA data use the census tract delineations ... from the 2020
    # Census."
    2023: 2020,
    # 2024: NO per-year CFPB citation exists — the *Summary of ... Data* series
    # stops at 2023 (2024 and 2025 slugs return HTTP 404), so it may be a
    # discontinued publication rather than a pending one (§M1.3, §O item 2).
    # This entry rests on REG_C_COMMENT plus a matter of record: the Census
    # Bureau published no new tract delineation between the 2020 Census
    # delineations and 2024-01-01, so the boundaries "in effect on January 1" of
    # 2024 are the 2020 ones. That is the cited rule applied to an
    # already-published delineation, not a prediction of a future one — the
    # distinction §M1.3 turns on. Corroborated, NOT established, by the LAR:
    # CT 2023 and 2024 carry an identical 872-member tract-suffix multiset.
    2024: 2020,
    # 2025 is DELIBERATELY ABSENT — see UNKNOWN below. The 2025 data year is
    # already served (AK 19,621 rows, CT 123,752 rows), and no citation for its
    # basis exists. Single-year 2025 analysis works; pooling 2025 with any other
    # year refuses, which is correct until a human reads a citation. Do not add
    # an entry here because the measurements "are consistent with" 2020 —
    # consistency is not a citation, and that inference is the defect this whole
    # module exists to prevent (§M1.3).
}

#: County FIPS code basis, by HMDA data year.
#:
#: The county map is consulted by the TRACT guard as well as the county guard,
#: because the county code is the first five digits of the tract GEOID, so a
#: county-scheme change is *necessarily* a tract-key change. This is the only
#: thing that catches Connecticut 2023→2024, where the tract delineation basis is
#: unchanged (2020) but every tract GEOID changes because the planning-region
#: switch renumbers every county prefix (§M1.2b, §M6.5).
#:
#: OPEN ITEM (§O item 1, a stated release blocker of the methodology): these
#: entries are LAR measurement restated, not per-entry citations. The boundaries
#: are established — 2021→2022 by Alaska's 02261 split, 2023→2024 by
#: Connecticut's planning regions — but the Census county-equivalent change
#: notices behind them, with their FFIEC adoption years, have not been read. The
#: methodology records that leaving it this way is more expensive now that this
#: map is load-bearing for the tract guard.
COUNTY_CODE_BASIS_BY_YEAR: dict[int, int] = {
    # Pre-2020-Census county equivalents.
    2018: 2010,
    2019: 2010,
    2020: 2010,
    2021: 2010,
    # 2020-Census-cycle county equivalents. Boundary located at 2021→2022 by the
    # LAR: Alaska's 02261 (Valdez-Cordova Census Area, 323 rows in 2021) is
    # retired and split into 02063 (Chugach, 158 rows) + 02066 (Copper River, 40
    # rows), live at exactly the decennial boundary. Needs the Census change
    # notice per §O item 1.
    2022: 2020,
    2023: 2020,
    # Connecticut's nine planning regions replace its eight legacy counties for
    # federal statistical use, adopted by the LAR at 2023→2024: county codes go
    # from 09001..09015 to 09110..09190, sharing ZERO members. Needs the Census
    # change notice and the FFIEC adoption year per §O item 1.
    2024: 2023,
    # 2025 DELIBERATELY ABSENT — see TRACT_GEOID_BASIS_BY_YEAR's 2025 note.
}

#: MSA / metropolitan-division code basis, by HMDA data year.
#:
#: This map has NO internal caller: the AST sweep finds zero aggregations on
#: ``derived_msa_md`` anywhere in the package, so there is no site to guard
#: (§M6.2). It ships anyway, because §M5.2 option 2 sends users to an MSA
#: aggregation as an escape route from the tract rule, and a user doing their own
#: ``groupby`` deserves a documented, citable constant rather than having to
#: re-derive OMB's adoption schedule. That is a weaker instrument than a raise
#: and is named as one (§M6.6, coverage item 2).
#:
#: Both boundaries are CITATIONS, not measurements, and the distinction matters:
#: OMB's 2020 delineations left the measured states' code sets essentially
#: untouched, so the instrument this methodology *proves* cannot see a basis
#: change duly failed to see one (§M2.3).
MSA_CODE_BASIS_BY_YEAR: dict[int, int] = {
    2018: 2010,
    2019: 2010,
    2020: 2010,
    2021: 2010,
    # OMB delineations released 2020 (Bulletin 20-01, 2020-03-06). CFPB,
    # *Summary of 2023 Data on Mortgage Lending* (pub. 2024-07-11): "the data
    # reflect metropolitan statistical area (MSA) definitions released by the
    # Office of Management and Budget in 2020 that became effective for HMDA
    # purposes in 2022."
    2022: 2020,
    2023: 2020,
    # OMB Bulletin No. 23-01, *Revised Delineations of Metropolitan Statistical
    # Areas, Micropolitan Statistical Areas, and Combined Statistical Areas*,
    # issued 2023-07-21; updates and supersedes Bulletin 20-01 and is the first
    # delineation to use 2020 Decennial Census data. Applying REG_C_COMMENT, a
    # bulletin issued 2023-07-21 is in effect on 2024-01-01, so its first LAR
    # year is 2024. FFIEC's own adoption notice was not read (HTTP 403 to every
    # automated request, §O item 3), so this rests on Reg C plus the bulletin.
    2024: 2023,
    # 2025 DELIBERATELY ABSENT — see TRACT_GEOID_BASIS_BY_YEAR's 2025 note.
}

#: ``state_code`` has an aggregation site (``lending_by_state``) and gets NO map
#: and NO guard, on an argument from absence: nothing was measured to move a
#: state code in 2018–2025. That is not a demonstration that they cannot. If a
#: state-level equivalent of the Connecticut restructuring occurs, this key fails
#: exactly as the county key did and nothing here would notice (coverage item 3).
#: It is enumerated by the AST site-list test so it stays visible.
STATE_CODE_HAS_NO_BASIS_MAP = True

#: The three maps, addressable by the key column they govern.
BASIS_MAPS: dict[str, dict[int, int]] = {
    "census_tract": TRACT_GEOID_BASIS_BY_YEAR,
    "county_code": COUNTY_CODE_BASIS_BY_YEAR,
    "derived_msa_md": MSA_CODE_BASIS_BY_YEAR,
}

#: The maps each guarded key consults. The tract key consults BOTH its own map
#: and the county map — not redundancy, the only thing that catches Connecticut
#: 2023→2024 (§M1.2b, §M2.1).
CONSULTED_MAPS: dict[str, tuple[str, ...]] = {
    "census_tract": ("census_tract", "county_code"),
    "county_code": ("county_code",),
}

#: The provenance column. Named ``tract_geoid_vintage`` and not ``tract_vintage``
#: because the LAR carries two tract-related things that change on different
#: schedules: the tract *delineation* (decennial) and the FFIEC *demographic
#: appends* (``tract_population``, ``tract_to_msa_income_percentage``, …,
#: refreshed annually against a rolling 5-year ACS). A column called
#: ``tract_vintage`` will be read by a consumer that has never seen the
#: methodology as covering both. It covers only the first (§M4.3, coverage
#: item 5).
VINTAGE_COLUMN = "tract_geoid_vintage"

#: Provenance column name per guarded key. The county site gets its own name for
#: the same reason the tract one is not called ``tract_vintage``: a column must
#: name the thing it governs and buy nothing else. Writing ``tract_geoid_vintage``
#: onto a county aggregation would assert a tract fact about a county row, and
#: every gate in this portfolio that misdescribed its own coverage became a defect
#: later (§M4.3).
VINTAGE_COLUMN_BY_KEY: dict[str, str] = {
    "census_tract": VINTAGE_COLUMN,
    "county_code": "county_code_vintage",
}

#: Percentile floor below which ``lending_desert_score``'s flag is arithmetically
#: unreachable. ``rank(pct=True)`` over *n* rows has minimum ``1/n``, so
#: ``app_percentile`` has minimum ``100/n``; ``is_lending_desert`` requires
#: ``app_percentile < 25``. The flag is therefore unreachable for n ≤ 4 — not
#: merely for n = 1. Ties only RAISE the minimum, so this holds unconditionally.
#: Derived from the threshold, not chosen (§M3.3a).
DESERT_TRACT_FLOOR = 5


def basis_year(key: str, year: int) -> int | None:
    """Return the basis year ``key`` uses in HMDA data year ``year``.

    Returns ``None`` for an UNMAPPED year — the ``UNKNOWN`` state (§M1.3). That
    is an assertion of ignorance, never an inference: it says only that no
    human has added a cited entry for this year yet.
    """
    return BASIS_MAPS[key].get(year)


def _years_in(df: pd.DataFrame) -> list[int | None]:
    """Distinct ``activity_year`` values, as ints where parseable.

    A value that is not an integer year (a fabricated or corrupt
    ``activity_year``) becomes ``None`` and is therefore treated as UNMAPPED, so
    it cannot be pooled with anything. A frame with a fabricated *plausible*
    year defeats the guard entirely — the guard derives the basis from this
    column and has nothing else to check it against (coverage item 9).
    """
    raw = df["activity_year"].dropna().unique()
    out: list[int | None] = []
    for v in raw:
        try:
            out.append(int(str(v).strip()))
        except (TypeError, ValueError):
            out.append(None)
    # dedupe, keeping None once, ordered for a stable message
    seen: list[int | None] = []
    for v in out:
        if v not in seen:
            seen.append(v)
    return sorted(seen, key=lambda y: (y is None, y))


def _overlap_context(df: pd.DataFrame, key: str, years: list[int | None]) -> str:
    """The measurement the refusal message carries alongside the verdict.

    §M3.1: a message that says "frame spans multiple tract vintages" tells a user
    they are blocked without telling them whether it matters. This reports how
    many keys are shared between the years and what share of rows land on them.

    The count is a FACT. The interpretation is stated as a range, not a verdict,
    because that is what the measurement supports: the word "materially" is
    retired — nationally about 42% of GEOIDs shared across the 2021|2022 boundary
    are ≥99% unchanged ground, while 49% kept less than half of theirs. The
    overlap figure is context in the message, never the trigger; the frame is
    refused for spanning two bases, which is a declarative fact (§M3.1, §M6.4).

    Keys are sentinel-filtered with ``.dropna()``. ``census_tract`` and
    ``county_code`` carry the literal string ``NA`` as a valid reported value in
    every state-year measured; ``read_csv`` has already coerced it to ``NaN`` by
    the time a frame reaches here, so ``df[df[key] != "NA"]`` is a NO-OP that
    looks like the fix (§M1.2a).
    """
    if key not in df.columns:
        return ""
    real = [y for y in years if y is not None]
    if len(real) < 2:
        return ""
    per_year = {}
    for y in real:
        rows = df[df["activity_year"].astype(str) == str(y)]
        per_year[y] = (set(rows[key].dropna().unique()), len(rows))
    shared = set.intersection(*(s for s, _ in per_year.values()))
    total_keys = len(set.union(*(s for s, _ in per_year.values())))
    shares = []
    for y in real:
        keys, n = per_year[y]
        if n:
            on_shared = int(df[(df["activity_year"].astype(str) == str(y))
                               & (df[key].isin(shared))].shape[0])
            shares.append(f"{on_shared / n * 100:.1f}% ({y})")
    msg = (f"{len(shared)} of {total_keys} {key} keys appear in every year present "
           f"and would be merged")
    if shares:
        msg += f"; they carry {' and '.join(shares)} of rows"
    msg += ".\n"
    if len(shared) == 0:
        msg += ("  No key is shared, so nothing merges — but the years still cannot be "
                "pooled: every statistic derived from a reference distribution "
                "(app_percentile, desert_score, is_lending_desert) is computed over the "
                "combined key set and is wrong for both years. Connecticut 2023+2024 is "
                "the measured case: 0 shared keys and 25 flipped desert verdicts.\n")
    elif key == "census_tract":
        msg += ("  Sharing a GEOID across the boundary does not by itself mean the ground "
                "changed — nationally about 42% of such GEOIDs are >=99% unchanged — but "
                "it does mean the two years cannot be summed without deciding which.\n")
    return msg


def _next_actions(fn_name: str, key: str) -> str:
    """The four options, in order of preference (§M5.2). An error a user routes
    around versus an error a user learns from."""
    return (
        f"  What to do instead (methodology §M5.2):\n"
        f"    1. ENDORSED: split at the boundary and present two panels with an "
        f"explicit, labelled break. No estimation, no non-random subsetting.\n"
        f"    2. Narrow to one basis: {fn_name}(df, vintage=<basis year>). This "
        f"selects a coherent subset; it never merges two delineations.\n"
        f"    3. Aggregating up to county or MSA is NOT an escape route — those keys "
        f"move too, and at overlapping boundaries (§M2.3). The county key is guarded; "
        f"derived_msa_md is not, because the package has no aggregation on it.\n"
        f"    4. Build a crosswalk yourself, outside the library, and own the estimate. "
        f"The library will not: HMDA carries no sub-tract location, so any conversion "
        f"allocates proportionally and produces fractional loan counts (§M5.1).\n"
    )


@dataclass(frozen=True)
class VintageResolution:
    """What the guard learned, and the provenance it owes the caller's output.

    ``basis_year`` is ``None`` only when the frame's single year is UNMAPPED —
    a legitimate, allowed analysis about which no basis can be asserted.
    """

    key: str
    fn_name: str
    frame: pd.DataFrame
    basis_year: int | None
    years: tuple[int | None, ...]
    dropped_rows_by_year: dict[str, int] = field(default_factory=dict)

    def attach(self, result: pd.DataFrame) -> pd.DataFrame:
        """Write the provenance onto an aggregation's OUTPUT.

        This is necessary rather than tidy. ``.agg()`` drops the column — and
        ``lending_by_tract`` *is* an ``.agg()``, so the function most in need of
        the guard is the one that discards its provenance (§M4.1). Nothing
        carries the column through by itself; it has to be written deliberately.

        This does not make the column a mechanism. The guard derived the basis
        from ``activity_year`` before this ran; the column is provenance and is
        never read back as the source of truth (§M4.1).
        """
        if self.basis_year is None:
            # No basis can be asserted for a single UNMAPPED year. Writing NaN
            # would flip the column to float64 and writing a guess would be the
            # defect this module exists to prevent, so the column is omitted and
            # its absence is the signal.
            return result
        out = result.copy()
        out[VINTAGE_COLUMN_BY_KEY[self.key]] = int(self.basis_year)
        if self.dropped_rows_by_year:
            # §M3.3a: the dropped years need a NAMED channel. A print or a
            # warnings.warn dies exactly as warnings die — invisible on notebook
            # re-run, absent from the artefact that outlives the session. The
            # channel is the returned object.
            out["vintage_dropped_rows"] = sum(self.dropped_rows_by_year.values())
        return out

    def provenance_keys(self) -> dict:
        """Provenance for a caller that returns a ``dict`` and cannot carry a
        column. ``lender_summary`` is the case (§M3.3a, §M4.5)."""
        keys: dict = {}
        if self.basis_year is not None:
            keys[f"{self.key}_basis_year"] = int(self.basis_year)
        if self.dropped_rows_by_year:
            keys["dropped_rows_by_year"] = dict(self.dropped_rows_by_year)
        return keys


def resolve_geography_vintage(
    df: pd.DataFrame,
    key: str,
    fn_name: str,
    vintage: int | None = None,
) -> VintageResolution:
    """The single guard. Six call sites, one implementation.

    One helper called from N places, not N copies of a check — because six
    guards can drift apart and one cannot, and this portfolio has just spent
    three consecutive passes reconciling five drifted copies of one CI gate
    (§M2.4). A future seventh site is a call, not a re-implementation, and
    cannot drift because there is nothing to drift from.

    Args:
        df:      the frame about to be aggregated.
        key:     the geography column being used as an identity —
                 ``"census_tract"`` or ``"county_code"``.
        fn_name: the public function that will refuse, for the message.
        vintage: optional narrowing. Selects the rows whose year maps to this
                 basis under ``key``'s own map, BEFORE the guard runs. It cannot
                 produce a wrong number because it never merges two
                 delineations; the guard still runs afterwards, so a narrowing
                 that leaves an incoherent frame still refuses (§M3.3).

    Returns:
        A :class:`VintageResolution` carrying the possibly-narrowed frame and
        the provenance to write onto the output.

    Raises:
        GeographyVintageError: if the frame spans more than one basis for
            ``key`` or for any map ``key`` consults; if an unmapped year is
            pooled with any other year; or if ``vintage`` selects no rows.
    """
    if key not in CONSULTED_MAPS:
        raise ValueError(
            f"resolve_geography_vintage: {key!r} has no basis map. "
            f"Guarded keys are {sorted(CONSULTED_MAPS)}."
        )

    if "activity_year" not in df.columns:
        # The guard derives the basis from activity_year and has nothing else to
        # read. ``load_from_file`` accepts an arbitrary CSV and does not assert
        # the column exists, so a user-supplied frame may carry no year at all
        # (coverage item 9). Refusing here would refuse analyses that were always
        # correct — a single-year CSV with no year column is exactly as coherent
        # as a single-year API frame — which is the false-refusal shape §M2.4
        # rejects a load-time raise for. So the guard does not fire, and it says
        # so by omitting the provenance column rather than asserting a basis it
        # cannot know. A ``vintage=`` request, by contrast, IS unanswerable.
        if vintage is not None:
            raise GeographyVintageError(
                f"{fn_name} was given vintage={vintage!r} but the frame has no "
                f"'activity_year' column, so no row can be assigned a geography "
                f"basis. Narrowing is not possible on this frame. "
                f"(methodology §M3.3, coverage item 9)"
            )
        return VintageResolution(key=key, fn_name=fn_name, frame=df,
                                 basis_year=None, years=())

    dropped: dict[str, int] = {}
    if vintage is not None:
        own = BASIS_MAPS[key]
        wanted_years = {y for y, b in own.items() if b == vintage}
        year_str = df["activity_year"].astype(str)
        keep = year_str.isin({str(y) for y in wanted_years})
        narrowed = df[keep]
        if narrowed.empty:
            # §M3.3a. An empty narrowing is a CALLER ERROR, not a finding.
            # exceptions.py holds that an empty result can never silently read as
            # "no disparity" in a fair-lending context, and lender_summary's {}
            # is documented as meaning a legitimate empty result. Returning zero
            # rows here would produce exactly the artefact the package says must
            # never exist: zero deserts, no warning, indistinguishable from a
            # clean bill of health. This is distinct from a legitimately empty
            # INPUT frame, which keeps its current behaviour — the distinguishing
            # fact is that the narrowing removed the rows, and we know it did.
            present = _bases_present(df, key)
            raise GeographyVintageError(
                f"{fn_name}(vintage={vintage!r}) selected no rows: no year in this "
                f"frame uses {key} basis {vintage}.\n"
                f"  bases present for {key}: {present}\n"
                f"  years present: {_years_in(df)}\n"
                f"  This is a malformed question, not a finding — the answer is not "
                f"'nothing here'. Name a basis the frame actually contains.\n"
                f"  (methodology §M3.3a)"
            )
        for y, n in df[~keep]["activity_year"].astype(str).value_counts().items():
            dropped[str(y)] = int(n)
        df = narrowed

    years = _years_in(df)
    if not years:
        return VintageResolution(key=key, fn_name=fn_name, frame=df,
                                 basis_year=None, years=())

    # ── The UNKNOWN rule (§M1.3) ──────────────────────────────────────────────
    # An unmapped year ALONE in a frame is allowed. An unmapped year pooled with
    # any other year raises.
    #
    # This asserts nothing whatever about the unmapped year's basis, which is the
    # point: measurement cannot establish a basis, and this rule will not let an
    # inference wear a citation's clothes. It keeps every safety property — two
    # years cannot be pooled unless both are mapped and agree — while letting a
    # 2025-only tract analysis proceed, which is exactly as coherent as a
    # 2023-only one. Without this state the rule would refuse a correct
    # single-year analysis because a *different* analysis would be wrong.
    for map_key in CONSULTED_MAPS[key]:
        unmapped = [y for y in years if y is None or y not in BASIS_MAPS[map_key]]
        if unmapped and len(years) > 1:
            raise GeographyVintageError(
                f"{fn_name} refused: this frame pools data year(s) "
                f"{_fmt_years(unmapped)} — for which no cited {map_key} basis exists — "
                f"with {_fmt_years([y for y in years if y not in unmapped])}.\n"
                f"  A single unmapped year on its own is fine and is NOT refused; "
                f"pooling one with another year is refused because nobody can say "
                f"whether the keys mean the same thing.\n"
                f"  To add a year: read the CFPB *Summary of {{year}} Data on Mortgage "
                f"Lending*, confirm the delineation basis, add the entry to "
                f"{map_key.upper()}_BASIS_BY_YEAR in hmdaanalyzer/geography_vintage.py, "
                f"and cite it in the comment. Do NOT infer it from the data — that is "
                f"the defect this rule exists to prevent (methodology §M1.3).\n"
                + _next_actions(fn_name, key)
            )

    # ── The basis comparison, per consulted map ───────────────────────────────
    # Only mapped years reach here with anything to compare. A single UNMAPPED
    # year has already been allowed through by the rule above and has no basis
    # to compare — looking one up would be the inference the rule forbids (and,
    # before this was written as a lookup that can miss, a KeyError).
    for map_key in CONSULTED_MAPS[key]:
        bases: dict[int, list[int]] = {}
        for y in years:
            b = BASIS_MAPS[map_key].get(y) if y is not None else None
            if b is None:
                continue
            bases.setdefault(b, []).append(y)
        if len(bases) > 1:
            via = ("its own map" if map_key == key
                   else f"the {map_key} map — the county code is the tract GEOID's "
                        f"first five digits, so a county-scheme change is necessarily "
                        f"a tract-key change")
            spans = "; ".join(
                f"basis {b} ({', '.join(str(y) for y in sorted(ys))})"
                for b, ys in sorted(bases.items())
            )
            raise GeographyVintageError(
                f"{fn_name} refused: this frame spans more than one {map_key} basis — "
                f"{spans}.\n"
                f"  Caught by {via}.\n"
                f"  {_overlap_context(df, map_key, years)}"
                + _next_actions(fn_name, key)
            )

    own_bases = {b for y in years if (b := BASIS_MAPS[key].get(y)) is not None}
    resolved = own_bases.pop() if len(own_bases) == 1 else None
    return VintageResolution(
        key=key, fn_name=fn_name, frame=df, basis_year=resolved,
        years=tuple(years), dropped_rows_by_year=dropped,
    )


def _bases_present(df: pd.DataFrame, key: str) -> list[int]:
    return sorted({b for y in _years_in(df)
                   if (b := BASIS_MAPS[key].get(y)) is not None})


def _fmt_years(years) -> str:
    return ", ".join("<unparseable>" if y is None else str(y) for y in years)


__all__ = [
    "TRACT_GEOID_BASIS_BY_YEAR",
    "COUNTY_CODE_BASIS_BY_YEAR",
    "MSA_CODE_BASIS_BY_YEAR",
    "BASIS_MAPS",
    "CONSULTED_MAPS",
    "VINTAGE_COLUMN",
    "VINTAGE_COLUMN_BY_KEY",
    "DESERT_TRACT_FLOOR",
    "REG_C_COMMENT",
    "basis_year",
    "resolve_geography_vintage",
    "VintageResolution",
]
