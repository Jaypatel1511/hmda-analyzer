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
    # 2024 and 2025 are DELIBERATELY ABSENT — both UNKNOWN (§M1.3, §O item 10).
    #
    # A 2024 entry of 2020 SHIPPED IN BUILD 1 AND WAS REMOVED. It was uncited,
    # and its stated premise was wrong at the granularity HMDA actually keys on.
    # The premise was continuity of the 2020 decennial *delineation* — true, and
    # not the question. HMDA tract codes follow the FFIEC census file, which
    # adopts a Census *geography vintage* per year; the 2024 file uses 2023
    # geographies. That question is OPEN here: ffiec.gov returns HTTP 403 to
    # every automated request, so the FFIEC Census FAQ could not be read
    # directly, and secondary sourcing is not a citation. A future 2024 entry
    # must be founded on the FFIEC annual vintage, not on the decennial
    # delineation (§O item 10).
    #
    # Removal changes NO refusal decision. Measured over every year-pair in
    # 2018-2025: the map with the 2024 entry and the map without it accept the
    # same seven distinct pairs, at both the tract and the county key. In the
    # narrowing path removal is a net ACCEPT — vintage=2020 on a 2022+2023+2024
    # frame used to select all three years and then refuse on the county map,
    # and now selects the two coherent ones and answers.
    #
    # The 2025 data year is already served (AK 19,621 rows, CT 123,752 rows).
    # Single-year 2024 or 2025 analysis works; pooling either with any other
    # year refuses, which is correct until a human reads a citation. Do not add
    # an entry here because the measurements "are consistent with" 2020 —
    # consistency is not a citation, and that inference is the defect this whole
    # module exists to prevent (§M1.3).
}

#: County FIPS code basis, by HMDA data year.
#:
#: The county map is consulted by the TRACT guard as well as the county guard,
#: because the county code is the first five digits of the tract GEOID, so a
#: county-scheme change is *necessarily* a tract-key change.
#:
#: That consult is the only thing that can catch a county re-scheme at a year
#: whose TRACT basis is cited and unchanged — Connecticut 2023→2024 is the
#: measured instance, where the tract delineation stays 2020 while every tract
#: GEOID changes under the planning-region renumbering (§M1.2b, §M6.5).
#:
#: As shipped it has NO LIVE CASE, and that is worth stating plainly rather than
#: leaving the older claim standing. Since the uncited 2024 tract entry was
#: removed (§O item 10), 2024 is UNMAPPED for tracts, so a CT 2023+2024 tract
#: frame is refused by the UNKNOWN rule before the basis comparison is reached —
#: ``CONSULTED_MAPS`` is iterated for the unmapped-year check first. No shipped
#: year-pair now has agreeing tract bases and disagreeing county bases.
#:
#: Do not delete the consult on that basis. It re-arms the moment a human adds a
#: cited 2024 tract entry, which is exactly when Connecticut becomes invisible to
#: the tract map again. It is exercised by a test that restores the entry for its
#: duration, and that test says it is conditional.
#:
#: §O item 1 — the last release blocker — is CLOSED by the two primary sources
#: cited per entry below. Both boundaries now rest on a published change record,
#: not on LAR measurement restated as a citation.
#:
#: What reading them established, and what it did NOT: the change records give
#: the CENSUS effective date. They do not give the year the LAR adopts it, and
#: Alaska measures the difference at TWO YEARS (see the 2022 entry). The LAR's
#: county key scheme follows the FFIEC census file's vintage, which lags the
#: Census effective date by an amount neither REG_C_COMMENT nor the change
#: notice predicts. The adoption year in each entry below is therefore still LAR
#: measurement — and that is now stated as what it is, rather than left to look
#: like part of the citation (§O item 1, §O item 10).
COUNTY_CODE_BASIS_BY_YEAR: dict[int, int] = {
    # Pre-2020-Census county equivalents.
    2018: 2010,
    2019: 2010,
    2020: 2010,
    2021: 2010,
    # 2020-Census-cycle county equivalents.
    #
    # CITATION: U.S. Census Bureau, *Substantial Changes to Counties and County
    # Equivalent Entities: 1970-Present*, 2010s list, retrieved 2026-08-05:
    # "Valdez-Cordova Census Area, Alaska (02-261): Split to form Chugach Census
    # Area (02-063) and Copper River Census Area (02-066) effective January 02,
    # 2019."
    #
    # ADOPTION YEAR IS MEASURED, NOT CITED, AND THE TWO DISAGREE. The Census
    # effective date is 2019-01-02, so REG_C_COMMENT — "boundaries and codes in
    # effect on January 1 of the calendar year covered by the register" —
    # predicts the split appears in the 2020 LAR. Measured across full-state AK
    # pulls, 02261 carries 168/223/311/323 rows in 2018/2019/2020/2021 and zero
    # thereafter; 02063+02066 first appear in 2022. The LAR adopted it TWO YEARS
    # after the rule alone would put it.
    #
    # This is the single most useful thing reading the change notices produced,
    # and it is a negative result: Reg C plus a published change does NOT
    # determine the LAR's key scheme. The FFIEC census file's vintage does. An
    # entry reasoned from "the change was published before January 1, therefore
    # the LAR uses it" is measurably wrong in the one case this package can
    # check — which is exactly the reasoning the removed 2024 tract entry rested
    # on (§O item 10).
    2022: 2020,
    2023: 2020,
    # Connecticut's nine planning regions replace its eight legacy counties for
    # federal statistical use: county codes go from 09001..09015 to
    # 09110..09190, sharing ZERO members.
    #
    # CITATION: Census Bureau, *Change to County-Equivalents in the State of
    # Connecticut*, 87 FR 34235 (2022-06-06), FR Doc. 2022-12063: "By 2024, all
    # Census Bureau operations and publications, both internal and external,
    # will use the nine new county-equivalent boundaries, names, and codes,
    # except for 2020 Decennial Census data publications and other datasets
    # referencing the eight legacy counties as published before June 1, 2022."
    # Listed as the SOLE 2020s entry in Census's *Substantial Changes to
    # Counties and County Equivalent Entities* — which is the published basis
    # for COUNTY_BOUNDARY_SCOPE's claim that this boundary is
    # Connecticut-confined, independent of this package's own 50-state pull.
    #
    # Adoption year measured at 2023→2024, matching the notice's "by 2024" —
    # but see the 2022 entry for why matching once is not a rule.
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
#: and the county map — not redundancy, the only thing that can catch a county
#: re-scheme at a year whose tract basis is unchanged (§M1.2b, §M2.1).
CONSULTED_MAPS: dict[str, tuple[str, ...]] = {
    "census_tract": ("census_tract", "county_code"),
    "county_code": ("county_code",),
}

#: Map column name → the name of the module constant that holds it.
#:
#: This exists because the refusal message used to BUILD the name arithmetically
#: — ``f"{map_key.upper()}_BASIS_BY_YEAR"`` — which yields
#: ``CENSUS_TRACT_BASIS_BY_YEAR`` for the tract case. No such constant exists;
#: it is ``TRACT_GEOID_BASIS_BY_YEAR``. The message's ONLY actionable
#: instruction told the reader to edit a name they would not find, and the test
#: covering that message passed because it never checked the name. Two of the
#: three keys happened to round-trip, which is exactly how a derived name
#: survives review.
BASIS_MAP_CONSTANT_NAMES: dict[str, str] = {
    "census_tract": "TRACT_GEOID_BASIS_BY_YEAR",
    "county_code": "COUNTY_CODE_BASIS_BY_YEAR",
    "derived_msa_md": "MSA_CODE_BASIS_BY_YEAR",
}

#: What a human must read to establish a basis for a new year, per key.
#:
#: The message used to send every reader to the CFPB *Summary of {year} Data on
#: Mortgage Lending* — a series this module's own comments record as stopping at
#: 2023. For 2024 onward that instruction is a dead end, and it was the only
#: instruction the message gave. Each key names the authority that actually
#: governs it.
BASIS_SOURCE_HINT: dict[str, str] = {
    "census_tract": (
        "the Census geography vintage the FFIEC census file for that year "
        "adopts (HMDA tract codes follow the FFIEC file, not the decennial "
        "delineation directly — a year can keep the 2020 delineation and still "
        "change file vintage). The CFPB *Summary of {year} Data on Mortgage "
        "Lending* states it for 2021-2023; the series does not continue past "
        "2023, so for 2024 onward the FFIEC file is the source"
    ),
    "county_code": (
        "the Census Bureau's *Substantial Changes to Counties and County "
        "Equivalent Entities* record for that year, together with the FFIEC "
        "census file year that adopts the change"
    ),
    "derived_msa_md": (
        "the OMB delineation bulletin in effect on January 1 of that year, per "
        + REG_C_COMMENT
    ),
}

#: Why a county-basis boundary moved, and what refusing at it costs a user who
#: is nowhere near the change. Keyed by the ``(earlier basis, later basis)``
#: pair a frame spans.
#:
#: The refusal at 2020→2023 is NATIONWIDE and its cause is one state. That is
#: the conservative call and it stands — a national key scheme did change, and
#: this library will not decide on a user's behalf that their state was
#: unaffected. But the message printed the evidence against itself (30 of 30
#: shared county keys carrying 99.8% of rows) and refused anyway, leaving a user
#: in Alaska to work out from a shared-key count that their analysis was fine.
#: Silence about the cost is not defensible even when the refusal is right.
#:
#: "SCHEME changes" is the exact word and it is not hedging. Over 51
#: jurisdictions and 20.7M rows, THREE states' in-state ``county_code`` SETS
#: differ between 2023 and 2024. Two of the three are presence noise, not
#: boundary changes, and the distinction is checkable rather than asserted:
#:
#:   SD 46017 (Buffalo County) and TX 48269 (King County) — the
#:   sparsest county in each state — each carry a handful of rows in every year
#:   2018-2023, ZERO in 2024, and rows again in 2025 (5 and 1). The codes never
#:   left the county universe; nobody applied for a mortgage there in 2024.
#:   Connecticut's eight codes share ZERO members with its nine successors.
#:
#: This is §M6.7's measured hazard — a set comparison reads a low-volume
#: jurisdiction's empty year as a boundary change — and it is why the message
#: says "scheme" rather than "set". "No other state's county_code set changes"
#: would have been a shipped claim a user could falsify with one query.
#:
#: The 2010→2020 boundary gets NO entry. Alaska's ``02261`` split is the change
#: that LOCATED it (§M6.7), but "located by" is not "confined to": no 50-state
#: measurement was made at that boundary, and asserting confinement without one
#: would be the same uncited inference this module exists to refuse. It is also
#: the decennial boundary, where the tract map moves on its own.
COUNTY_BOUNDARY_SCOPE: dict[tuple[int, int], str] = {
    (2020, 2023): (
        "This boundary is CONNECTICUT-CONFINED. The 2023->2024 county change is "
        "Connecticut replacing its eight legacy counties (09001..09015) with "
        "nine planning regions (09110..09190) for federal statistical use "
        "(87 FR 34235, 2022-06-06); Census lists it as the SOLE county-equivalent "
        "change of the 2020s. Measured independently here across all 50 states "
        "and DC (20.7M LAR rows), Connecticut is the only state whose "
        "county_code SCHEME changes. If your frame contains no Connecticut "
        "rows, the keys really do mean the same thing in both years and this "
        "refusal is costing you an analysis that would have been correct.\n"
        "    It is still a refusal, deliberately: a national key scheme did "
        "change, and deciding on your behalf that your rows are unaffected is "
        "the silent inference this library exists to not make. Two ways "
        "through, both exact:\n"
        "      a. Exclude Connecticut and re-run: df[df['state_code'] != 'CT'] "
        "(or df[~df['county_code'].astype(str).str.startswith('09')]). Every "
        "remaining key is unchanged across the boundary.\n"
        "      b. Split at the boundary and present two panels, which is the "
        "endorsed path for any vintage break and keeps Connecticut in "
        "(§M5.2 option 1)."
    ),
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

#: Why no basis is stamped, when none is — as an explicit value rather than as
#: an absent column.
#:
#: An UNKNOWN-year output and a no-``activity_year`` output used to be
#: BYTE-IDENTICAL in columns and shape, in both the DataFrame and the dict
#: channel. Two different epistemic situations — "there is a year and nobody has
#: cited its basis" versus "there is no year to derive a basis from" — carried
#: one signal, and the signal was an *absence*: it reaches the artefact and is
#: unreadable there. A reader cannot distinguish a missing column from a column
#: that was never going to be written.
#:
#: So the status is always written, including when the basis IS cited. A status
#: column that appears only in the unhappy cases would re-create the original
#: defect one level up, with its own absence as the signal. Strings, not a
#: nullable numeric: a string column has no NaN-dtype problem, survives
#: ``pd.concat`` and a CSV round-trip unchanged, and asserts no basis.
BASIS_STATUS_CITED = "CITED"
BASIS_STATUS_UNKNOWN = "UNKNOWN"
BASIS_STATUS_NO_YEAR_COLUMN = "NO_YEAR_COLUMN"

#: Status column name per key. ``<provenance column>_status``, so the two names
#: sort together and a reader who finds one finds the other.
VINTAGE_STATUS_COLUMN_BY_KEY: dict[str, str] = {
    key: f"{col}_status" for key, col in VINTAGE_COLUMN_BY_KEY.items()
}

#: The ``app_percentile`` threshold ``is_lending_desert`` compares against. It
#: lives HERE, not as a literal at the comparison site, because the floor below
#: is arithmetic *on this number* and the two must move together. They did not:
#: the constant was written out four times — at the comparison, in the refusal
#: message, and in two tests that each re-hardcoded it — with nothing tying them
#: together, so moving the threshold left the floor arithmetically wrong and the
#: whole suite green. ``lending_desert_score`` reads this; so does the test that
#: checks the derivation (§M3.3a).
DESERT_PERCENTILE_THRESHOLD = 25

#: The denial-rate floor ``is_lending_desert`` ALSO requires. Named in 0.6.0 for
#: the same reason its sibling above was: it was a bare literal at the
#: comparison site while the docstring describing the flag was being written
#: from it, which is how the pair drifts.
#:
#: It is deliberately NOT part of ``_derive_desert_floor``. The tract-count floor
#: is arithmetic on the PERCENTILE threshold alone — ``rank(pct=True)`` bounds
#: ``app_percentile`` from below and says nothing about denial rates — so this
#: constant has no derived companion and adding one would assert a relationship
#: that does not exist.
#:
#: UNVALIDATED, and recorded as such. 0.15 is not a CFPB threshold, is unrelated
#: to ``schema.DISPARITY_THRESHOLDS``, and nothing was fitted to produce it. It
#: is a shipped default that has never been justified in writing; naming it does
#: not validate it, it only makes the one place to change it findable.
DESERT_DENIAL_RATE_FLOOR = 0.15


def _derive_desert_floor(threshold: float) -> int:
    """The smallest tract count at which ``is_lending_desert`` can be True.

    ``rank(pct=True)`` over *n* rows has minimum ``1/n``, so ``app_percentile``
    has minimum ``round(100/n, 1)`` — the rounding is part of the site's
    arithmetic and so it is part of this derivation. The flag needs
    ``app_percentile < threshold``, so the floor is the first *n* that clears
    it. Ties only RAISE the minimum, so the floor holds unconditionally.

    This is a search rather than ``floor(100/threshold) + 1`` so that the
    rounding is honoured exactly rather than approximated: the point of deriving
    it at all is that it cannot be off by one when someone moves the threshold.
    """
    for n in range(1, 10001):
        if round(100 / n, 1) < threshold:
            return n
    raise ValueError(
        f"is_lending_desert threshold {threshold!r} is unreachable at any tract "
        f"count. app_percentile has minimum 100/n > 0, so a threshold at or "
        f"below 0 makes the flag arithmetically impossible everywhere."
    )


#: Tract-count floor below which ``lending_desert_score``'s flag is
#: arithmetically unreachable, DERIVED from
#: ``DESERT_PERCENTILE_THRESHOLD`` at import — not chosen, and not written down
#: a second time. At the shipped threshold of 25 this is 5: the flag is
#: unreachable for n ≤ 4, not merely for n = 1 (§M3.3a).
DESERT_TRACT_FLOOR = _derive_desert_floor(DESERT_PERCENTILE_THRESHOLD)


def basis_year(key: str, year: int) -> int | None:
    """Return the basis year ``key`` uses in HMDA data year ``year``.

    Returns ``None`` for an UNMAPPED year — the ``UNKNOWN`` state (§M1.3). That
    is an assertion of ignorance, never an inference: it says only that no
    human has added a cited entry for this year yet.
    """
    return BASIS_MAPS[key].get(year)


def _parse_year(value) -> int | None:
    """One ``activity_year`` cell → an int year, or ``None`` for "no usable year".

    ``None`` means UNMAPPED, so it cannot be pooled with anything. There is
    exactly ONE way for a cell to be unusable and it does not depend on how the
    unusability is spelled — this is the whole content of the fix:

    * **Null of any kind** — ``NaN``, ``None``, ``pd.NA``, ``pd.NaT`` — is a row
      whose year nobody knows, which is precisely what ``None`` means here. The
      caller used to ``.dropna()`` these away BEFORE parsing, so null-year rows
      were invisible to the guard and were pooled in silently, while a
      non-numeric string in the same cell correctly blocked pooling. Two
      spellings of the same fact, opposite safety outcomes.

    * **A float that is really an integer year** — ``2021.0`` — is that year. It
      must NOT become ``None``, and this is the sharper half. One blank cell is
      enough to make ``read_csv`` hand back ``float64``; ``int("2021.0")``
      raises, so under the old parser EVERY year in such a frame collapsed to
      ``None``, the ``None``\\ s deduped to a single unmapped year, and a
      decennial-spanning frame passed the guard as a coherent single-year
      analysis. Mapping null to ``None`` alone does not close that: it is the
      *real* years that were being discarded.

    * Everything else that is not an integer year — a non-numeric string, a
      non-finite float, ``2021.5`` — is ``None``, as before.

    A frame with a fabricated *plausible* year still defeats the guard: the
    guard derives the basis from this column and has nothing else to check it
    against (coverage item 9).
    """
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass                     # not a scalar pandas can test; try to parse it
    if isinstance(value, bool):  # bool is an int subclass; True is not year 1
        return None
    try:
        as_float = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        return None
    if as_float != int(as_float):
        return None              # 2021.5 is not a data year
    return int(as_float)


def _parsed_years(df: pd.DataFrame) -> pd.Series:
    """``activity_year`` parsed row-wise, so every year comparison in this module
    goes through :func:`_parse_year`.

    Narrowing and the overlap context used to compare ``astype(str)`` against
    ``str(year)``, which offers ``'2021.0'`` where ``'2021'`` is wanted. One
    parser, one answer, at every site.

    Built as an explicit ``dtype=object`` Series rather than via ``.map()``:
    pandas infers ``float64`` from a list of ints and ``None``\\ s, which turns
    every ``None`` back into a ``NaN`` — and ``NaN != NaN``, so the UNKNOWN
    values would not dedupe and the refusal message would name one unparseable
    year per row. The whole point of this function is that ``None`` stays
    ``None``.
    """
    return pd.Series(
        [_parse_year(v) for v in df["activity_year"]],
        index=df.index, dtype=object,
    )


def _years_in(df: pd.DataFrame) -> list[int | None]:
    """Distinct ``activity_year`` values, as ints where parseable."""
    out = list(_parsed_years(df))
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
    parsed = _parsed_years(df)
    per_year = {}
    for y in real:
        rows = df[parsed == y]
        per_year[y] = (set(rows[key].dropna().unique()), len(rows))
    shared = set.intersection(*(s for s, _ in per_year.values()))
    total_keys = len(set.union(*(s for s, _ in per_year.values())))
    shares = []
    for y in real:
        keys, n = per_year[y]
        if n:
            on_shared = int(df[(parsed == y) & (df[key].isin(shared))].shape[0])
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

    ``basis_year`` is the basis for this resolution's OWN key, and is ``None``
    only when that key's year is UNMAPPED — a legitimate, allowed analysis about
    which no basis can be asserted.

    ``consulted_bases`` carries one entry per map the key consults, which for
    the tract key is TWO. That is the point of it: ``lending_by_tract`` is
    governed by the tract map *and* the county map, and stamping only the first
    produced an output that under-described what governed it. Two guarded
    outputs from opposite sides of the Connecticut boundary both carried
    ``tract_geoid_vintage = 2020`` — truthfully, the tract basis genuinely
    agrees — so re-concatenating the two panels from the endorsed
    split-at-the-boundary path yielded a frame the guard had just refused, now
    labelled coherent by its own provenance.
    """

    key: str
    fn_name: str
    frame: pd.DataFrame
    basis_year: int | None
    years: tuple[int | None, ...]
    dropped_rows_by_year: dict[str, int] = field(default_factory=dict)
    #: Basis per consulted map key; ``None`` where none can be asserted.
    consulted_bases: dict[str, int | None] = field(default_factory=dict)
    #: Whether the frame had an ``activity_year`` column at all. Distinguishes
    #: UNKNOWN from NO_YEAR_COLUMN, which were previously indistinguishable.
    has_year_column: bool = True

    def _status(self, basis: int | None) -> str:
        if basis is not None:
            return BASIS_STATUS_CITED
        return (BASIS_STATUS_UNKNOWN if self.has_year_column
                else BASIS_STATUS_NO_YEAR_COLUMN)

    def attach(self, result: pd.DataFrame) -> pd.DataFrame:
        """Write the provenance onto an aggregation's OUTPUT.

        This is necessary rather than tidy. ``.agg()`` drops the column — and
        ``lending_by_tract`` *is* an ``.agg()``, so the function most in need of
        the guard is the one that discards its provenance (§M4.1). Nothing
        carries the column through by itself; it has to be written deliberately.

        This does not make the columns a mechanism. The guard derived every
        basis from ``activity_year`` before this ran; these are provenance and
        are never read back as the source of truth (§M4.1).

        Every consulted map gets a column pair — its basis year, where one can
        be asserted, and its status, always. A basis column is still OMITTED
        rather than set to NaN when no basis exists, because NaN would flip the
        column to float64 and a guess would be the defect this module exists to
        prevent; the status column is what makes that omission readable instead
        of merely observable.
        """
        out = result.copy()
        for map_key, basis in self.consulted_bases.items():
            if basis is not None:
                out[VINTAGE_COLUMN_BY_KEY[map_key]] = int(basis)
            out[VINTAGE_STATUS_COLUMN_BY_KEY[map_key]] = self._status(basis)
        if self.dropped_rows_by_year:
            # §M3.3a: the dropped years need a NAMED channel. A print or a
            # warnings.warn dies exactly as warnings die — invisible on notebook
            # re-run, absent from the artefact that outlives the session. The
            # channel is the returned object.
            out["vintage_dropped_rows"] = sum(self.dropped_rows_by_year.values())
        return out

    def provenance_keys(self) -> dict:
        """Provenance for a caller that returns a ``dict`` and cannot carry a
        column. ``lender_summary`` is the case (§M3.3a, §M4.5).

        Carries the same facts as :meth:`attach`, including the status, because
        the dict channel had the identical defect: an UNKNOWN-year summary and a
        no-year-column summary were byte-identical dicts.
        """
        keys: dict = {}
        for map_key, basis in self.consulted_bases.items():
            if basis is not None:
                keys[f"{map_key}_basis_year"] = int(basis)
            keys[f"{map_key}_basis_status"] = self._status(basis)
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
        return VintageResolution(
            key=key, fn_name=fn_name, frame=df, basis_year=None, years=(),
            consulted_bases={mk: None for mk in CONSULTED_MAPS[key]},
            has_year_column=False,
        )

    dropped: dict[str, int] = {}
    if vintage is not None:
        own = BASIS_MAPS[key]
        wanted_years = {y for y, b in own.items() if b == vintage}
        # Parsed, not ``astype(str)``: a float64 year column offers '2021.0'
        # where '2021' is wanted, matches nothing, and a perfectly answerable
        # narrowing raises the message reserved for a malformed question.
        parsed_years = _parsed_years(df)
        keep = parsed_years.isin(wanted_years)
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
        for y, n in parsed_years[~keep].value_counts(dropna=False).items():
            dropped[_fmt_years([y])] = int(n)
        df = narrowed

    years = _years_in(df)
    if not years:
        return VintageResolution(
            key=key, fn_name=fn_name, frame=df, basis_year=None, years=(),
            consulted_bases={mk: None for mk in CONSULTED_MAPS[key]},
        )

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
                f"  To add a year: read {BASIS_SOURCE_HINT[map_key]}; confirm the "
                f"basis; add the entry to {BASIS_MAP_CONSTANT_NAMES[map_key]} in "
                f"hmdaanalyzer/geography_vintage.py; and cite it in the comment. "
                f"Do NOT infer it from the data — that is the defect this rule "
                f"exists to prevent (methodology §M1.3).\n"
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
            # If the spanned boundary has a known scope, say so. A refusal whose
            # cause is one state, applied nationwide, must price itself.
            scope = ""
            if map_key == "county_code" and len(bases) == 2:
                lo, hi = sorted(bases)
                if (lo, hi) in COUNTY_BOUNDARY_SCOPE:
                    scope = f"  {COUNTY_BOUNDARY_SCOPE[(lo, hi)]}\n"
            raise GeographyVintageError(
                f"{fn_name} refused: this frame spans more than one {map_key} basis — "
                f"{spans}.\n"
                f"  Caught by {via}.\n"
                f"  {_overlap_context(df, map_key, years)}"
                + scope
                + _next_actions(fn_name, key)
            )

    # Past both limbs, every consulted map is internally coherent, so each one
    # resolves to at most one basis. Collect them ALL — the output owes
    # provenance for everything that governed it, not only for its own key.
    consulted_bases: dict[str, int | None] = {}
    for map_key in CONSULTED_MAPS[key]:
        found = {b for y in years if (b := BASIS_MAPS[map_key].get(y)) is not None}
        consulted_bases[map_key] = found.pop() if len(found) == 1 else None

    return VintageResolution(
        key=key, fn_name=fn_name, frame=df, basis_year=consulted_bases[key],
        years=tuple(years), dropped_rows_by_year=dropped,
        consulted_bases=consulted_bases,
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
    "BASIS_MAP_CONSTANT_NAMES",
    "BASIS_SOURCE_HINT",
    "COUNTY_BOUNDARY_SCOPE",
    "CONSULTED_MAPS",
    "VINTAGE_COLUMN",
    "VINTAGE_COLUMN_BY_KEY",
    "VINTAGE_STATUS_COLUMN_BY_KEY",
    "BASIS_STATUS_CITED",
    "BASIS_STATUS_UNKNOWN",
    "BASIS_STATUS_NO_YEAR_COLUMN",
    "DESERT_PERCENTILE_THRESHOLD",
    "DESERT_DENIAL_RATE_FLOOR",
    "DESERT_TRACT_FLOOR",
    "REG_C_COMMENT",
    "basis_year",
    "resolve_geography_vintage",
    "VintageResolution",
]
