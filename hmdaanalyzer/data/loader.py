"""
Load HMDA LAR data from CFPB Data Browser API or local CSV.
Free public API — no authentication required.
"""
import io
import os
import datetime
import requests
import pandas as pd
from pathlib import Path
from hmdaanalyzer._http import fetch, CFPBAPIError
from hmdaanalyzer.exceptions import SchemaValidationError, ActivityYearMismatchError
from hmdaanalyzer.data.schema import (
    HMDA_API_BASE, CACHE_DIR, ACTION_TAKEN,
    APPROVED_ACTIONS, DENIED_ACTIONS,
    RACE_CODES, ETHNICITY_CODES, LOAN_PURPOSE, LOAN_TYPE,
    EARLIEST_HMDA_YEAR, EXPECTED_LAR_COLUMNS,
)


def get_cache_dir() -> Path:
    path = Path(CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_from_api(
    year: int = 2023,
    state: str = None,
    lei: str = None,
    county: str = None,
    limit: int = 10_000,
) -> pd.DataFrame:
    """
    Load HMDA LAR data from CFPB Data Browser API.

    The CFPB API returns full state/county datasets as pre-built CSV files.
    The ``limit`` parameter streams and stops at that many rows so you don't
    have to download an entire multi-hundred-thousand-record state file.

    Args:
        year:   Data year e.g. 2023
        state:  Two-letter state code e.g. "IL"
        lei:    Lender LEI identifier
        county: County FIPS code e.g. "17031"
        limit:  Maximum number of records to return (default 10,000)

    Returns:
        Clean pandas DataFrame with standardized columns.

    Raises:
        RuntimeError: If the API returns an HTTP error, times out, or fails.
    """
    params = {
        "years": year,
        "actions_taken": "1,2,3,4,5",
    }
    if state:
        params["states"] = state.upper()
    if lei:
        params["leis"] = lei
    if county:
        params["counties"] = county

    url = f"{HMDA_API_BASE}/csv"

    print(f"Fetching HMDA data from CFPB API (year={year}, limit={limit:,})...")
    resp = None
    try:
        # fetch() sends the verified-passing CFPB header bundle and raises a typed
        # CFPBAPIError (a RuntimeError) on an HTTP error status. Connection/timeout
        # errors propagate unwrapped and are handled below.
        resp = fetch(url, params=params, timeout=120, stream=True)

        # The CFPB API ignores a row-count query parameter — it returns the full
        # state/county file. Stream line-by-line and stop at limit rows so we
        # don't download hundreds of thousands of records the caller didn't ask for.
        lines = []
        for i, line in enumerate(resp.iter_lines(decode_unicode=True)):
            if i > limit:   # row 0 is the header; stop before appending row limit+1
                break
            lines.append(line)

        df = pd.read_csv(io.StringIO("\n".join(lines)), dtype=str, low_memory=False)
        print(f"Loaded {len(df):,} LAR records")
        return _clean(df)

    except requests.Timeout:
        raise RuntimeError(
            "CFPB API timed out after 120s. "
            "Try a smaller state or use load_sample() for offline testing."
        ) from None
    except (RuntimeError, KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to load HMDA data from CFPB API: {e}") from e
    finally:
        if resp is not None:
            resp.close()


def _validate_year_range(start_year, end_year):
    """Validate the requested [start_year, end_year] range (inclusive).

    Raises ``TypeError`` if either bound is not a plain ``int`` (``bool`` is
    rejected even though it subclasses ``int``), and ``ValueError`` if a bound is
    below the earliest served year (2018), above the current calendar year, or if
    ``start_year > end_year``. Runs BEFORE any network call so a bad range never
    touches the API.
    """
    current_year = datetime.date.today().year
    for label, y in (("start_year", start_year), ("end_year", end_year)):
        if isinstance(y, bool) or not isinstance(y, int):
            raise TypeError(
                f"{label} must be an int, got {type(y).__name__}: {y!r}"
            )
        if y < EARLIEST_HMDA_YEAR:
            raise ValueError(
                f"{label}={y} is before the earliest HMDA year the CFPB API serves "
                f"({EARLIEST_HMDA_YEAR})."
            )
        if y > current_year:
            raise ValueError(
                f"{label}={y} is in the future (current year is {current_year})."
            )
    if start_year > end_year:
        raise ValueError(
            f"start_year ({start_year}) must be <= end_year ({end_year})."
        )


def _validate_lar_schema(df: pd.DataFrame, year: int):
    """Raise :class:`SchemaValidationError` if ``df`` deviates from the canonical
    CFPB LAR column set for a 2018+ query. Names the year and the offending
    columns. This is the regression guard against a silent CFPB schema change."""
    actual = set(df.columns)
    missing = EXPECTED_LAR_COLUMNS - actual
    unexpected = actual - EXPECTED_LAR_COLUMNS
    if missing or unexpected:
        raise SchemaValidationError(
            f"HMDA year {year} returned an unexpected column schema. "
            f"missing={sorted(missing)}; unexpected={sorted(unexpected)}. "
            f"The CFPB Data Browser schema may have changed; "
            f"update EXPECTED_LAR_COLUMNS (with the drift documented) before trusting this load."
        )


def _assert_activity_year(df: pd.DataFrame, year: int):
    """Assert the native ``activity_year`` in ``df`` matches the requested ``year``.

    Catches the API returning the wrong year's data. An empty frame (a legitimate
    zero-row year) has no values to check and passes. The native column is a string
    (e.g. ``"2023"``), so we compare against ``str(year)``.
    """
    if len(df) == 0:
        return
    returned = set(df["activity_year"].dropna().astype(str).unique())
    if returned != {str(year)}:
        raise ActivityYearMismatchError(
            f"Requested HMDA year {year} but the API returned rows with "
            f"activity_year={sorted(returned)}. The API returned the wrong year's data."
        )


def load_range(
    start_year: int,
    end_year: int,
    state: str = None,
    lei: str = None,
    county: str = None,
    limit: int = 10_000,
) -> pd.DataFrame:
    """
    Load HMDA LAR data across an INCLUSIVE range of years and return one
    vertically-concatenated DataFrame with an ``activity_year`` provenance column.

    Each year in ``[start_year, end_year]`` is fetched with the single-year
    :func:`load_from_api` path (same headers, streaming, ``limit``, and typed
    error handling), so all other filters — ``state``, ``lei``, ``county``,
    ``limit`` — apply IDENTICALLY to every year. Single-year ``load_from_api`` is
    unchanged; this is a strict addition.

    Contract:
      * **Fail-loud, no partial.** If ANY year's fetch raises, ``load_range``
        re-raises immediately with the failing year named and returns NO frame —
        there is no catch-and-continue and no partial result.
      * **Schema guard.** Every fetched year is validated against the canonical
        2018+ column set; a missing or unexpected column raises
        :class:`~hmdaanalyzer.SchemaValidationError` (naming the year).
      * **Provenance.** The native ``activity_year`` field is used and asserted to
        match the requested year; a wrong-year payload raises
        :class:`~hmdaanalyzer.ActivityYearMismatchError`.
      * **Legitimate empty.** A valid year that simply matches zero rows is NOT an
        error — its correctly-columned empty frame participates in the concat.

    Args:
        start_year: First year (inclusive). int, ``2018 <= start_year``.
        end_year:   Last year (inclusive). int, ``end_year <= current year``.
        state:      Two-letter state code e.g. "IL" (forwarded to every year).
        lei:        Lender LEI identifier (forwarded to every year).
        county:     County FIPS code e.g. "17031" (forwarded to every year).
        limit:      Max records PER YEAR (default 10,000; applied to each year).

    Returns:
        One concatenated, index-reset DataFrame spanning all requested years.

    Raises:
        TypeError:  If a year bound is not a plain int.
        ValueError: If a year bound is out of range or ``start_year > end_year``.
        CFPBAPIError / RuntimeError: If any year's fetch fails (year named).
        SchemaValidationError:       If any year's columns deviate from the canonical set.
        ActivityYearMismatchError:   If any year returns the wrong year's data.

    Scale note:
        Multi-year national pulls are enormous — the SAME filters apply to every
        year, so a multi-year call with no ``state``/``county`` filter multiplies a
        full national LAR file by the number of years. Always filter multi-year
        loads; this function does not silently cap or block, it just streams each
        year to ``limit``.
    """
    _validate_year_range(start_year, end_year)

    years = list(range(start_year, end_year + 1))
    print(
        f"Loading HMDA range {start_year}–{end_year} "
        f"({len(years)} year{'s' if len(years) != 1 else ''}), limit={limit:,}/year..."
    )

    frames = []
    for year in years:
        try:
            year_df = load_from_api(
                year=year, state=state, lei=lei, county=county, limit=limit,
            )
        except CFPBAPIError as e:
            # Preserve the typed CFPB error (status/body/url) but name the year.
            # FAIL-LOUD, no partial: we abort before any concat.
            raise CFPBAPIError(
                f"load_range failed fetching year {year}: {e}",
                status_code=e.status_code,
                response_body=e.response_body,
                url=e.url,
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"load_range failed fetching year {year}: {e}"
            ) from e

        _validate_lar_schema(year_df, year)
        _assert_activity_year(year_df, year)
        frames.append(year_df)

    combined = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(combined):,} LAR records across {len(years)} year(s)")
    return combined


def load_from_file(path: str) -> pd.DataFrame:
    """
    Load HMDA LAR data from a local CSV file.
    Compatible with CFPB modified LAR files.
    """
    print(f"Loading HMDA data from {path}...")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    print(f"Loaded {len(df):,} LAR records")
    return _clean(df)


def load_sample(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic HMDA LAR data for testing and demos.
    Realistic distribution based on 2023 national HMDA statistics.
    No internet connection required.

    Units follow HMDA FIG conventions:
      - ``income`` is in thousands of dollars (e.g. 85 → $85,000)
      - ``loan_amount`` is in dollars (e.g. 225000 → $225,000)
    """
    import numpy as np
    rng = np.random.default_rng(seed)

    states = ["IL", "NY", "CA", "TX", "GA", "NC", "OH", "PA", "FL", "MI"]
    leis = [f"LEI{i:06d}" for i in range(1, 11)]

    # Realistic denial rates by race (based on 2023 HMDA national data).
    # Includes all derived_race values that appear in live CFPB data.
    race_denial_rates = {
        "White":                                         0.095,
        "Black or African American":                     0.195,
        "Asian":                                         0.090,
        "Hispanic or Latino":                            0.145,
        "American Indian or Alaska Native":              0.175,
        "Native Hawaiian or Other Pacific Islander":     0.160,
        "2 or more minority races":                      0.130,
        "Race Not Available":                            0.115,
        "Joint":                                         0.100,
    }

    races = list(race_denial_rates.keys())
    race_weights = [0.60, 0.12, 0.06, 0.09, 0.02, 0.03, 0.03, 0.04, 0.01]

    records = []
    for i in range(n):
        race = rng.choice(races, p=race_weights)
        denial_prob = race_denial_rates[race]

        # Income in thousands (HMDA convention), loan amount in dollars (HMDA convention)
        income = max(20, rng.normal(85, 45))
        loan_amount = max(50_000, income * 1_000 * rng.uniform(2.5, 5.5))

        # Action taken based on race denial probability
        r = rng.random()
        if r < denial_prob:
            action = 3
        elif r < denial_prob + 0.05:
            action = 4
        else:
            action = 1

        state = rng.choice(states)
        county_num = rng.integers(1, 200)
        state_fips = {
            "IL": "17", "NY": "36", "CA": "06", "TX": "48",
            "GA": "13", "NC": "37", "OH": "39", "PA": "42",
            "FL": "12", "MI": "26",
        }[state]
        county_code = f"{state_fips}{county_num:03d}"
        tract = f"{county_code}{rng.integers(100000, 999999)}"

        records.append({
            "action_taken": str(action),
            "loan_type": str(rng.choice([1, 1, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.05, 0.05])),
            "loan_purpose": str(rng.choice([1, 31, 32, 2], p=[0.5, 0.3, 0.15, 0.05])),
            "loan_amount": str(round(loan_amount)),
            "income": str(round(income)),
            "derived_race": race,
            "derived_ethnicity": (
                "Hispanic or Latino" if race == "Hispanic or Latino"
                else "Not Hispanic or Latino"
            ),
            "derived_sex": rng.choice(["Male", "Female", "Joint"], p=[0.45, 0.3, 0.25]),
            "census_tract": tract,
            "county_code": county_code,
            "state_code": state_fips,
            "denial_reason-1": str(rng.choice([1, 3, 4, 9, 10], p=[0.3, 0.25, 0.2, 0.15, 0.1])) if action == 3 else "10",
            "interest_rate": str(round(rng.uniform(5.5, 8.5), 2)) if action == 1 else "",
            "rate_spread": str(round(rng.uniform(-0.5, 2.0), 2)) if action == 1 else "",
            "lei": rng.choice(leis),
            "activity_year": "2023",
        })

    df = pd.DataFrame(records)
    return _clean(df)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize and clean a raw HMDA LAR DataFrame.

    The CFPB Data Browser CSV names enumerated fields with hyphens
    (e.g. ``denial_reason-1``, ``applicant_race-1``). We normalize those to
    underscores so downstream code can address them by a single canonical name.
    """
    df.columns = df.columns.str.lower().str.strip().str.replace("-", "_", regex=False)

    numeric_cols = ["loan_amount", "income", "interest_rate", "rate_spread"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    int_cols = ["action_taken", "loan_type", "loan_purpose",
                "denial_reason_1", "denial_reason_2"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    if "action_taken" in df.columns:
        df["is_approved"] = df["action_taken"].isin(APPROVED_ACTIONS)
        df["is_denied"] = df["action_taken"].isin(DENIED_ACTIONS)

    if "derived_race" not in df.columns and "applicant_race_1" in df.columns:
        df["derived_race"] = df["applicant_race_1"].map(
            lambda x: RACE_CODES.get(int(x), "Unknown") if pd.notna(x) else "Unknown"
        )

    return df.reset_index(drop=True)
