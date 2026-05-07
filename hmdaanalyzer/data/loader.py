"""
Load HMDA LAR data from CFPB Data Browser API or local CSV.
Free public API — no authentication required.
"""
import os
import requests
import pandas as pd
from pathlib import Path
from hmdaanalyzer.data.schema import (
    HMDA_API_BASE, CACHE_DIR, ACTION_TAKEN,
    APPROVED_ACTIONS, DENIED_ACTIONS,
    RACE_CODES, ETHNICITY_CODES, LOAN_PURPOSE, LOAN_TYPE,
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

    Args:
        year:   Data year e.g. 2023
        state:  Two-letter state code e.g. "IL"
        lei:    Lender LEI identifier
        county: County FIPS code e.g. "17031"
        limit:  Max records to fetch

    Returns:
        Clean pandas DataFrame with standardized columns
    """
    params = {
        "years": year,
        "actions_taken": "1,2,3,4,5",
        "limit": min(limit, 1_000_000),
    }
    if state:
        params["states"] = state.upper()
    if lei:
        params["leis"] = lei
    if county:
        params["counties"] = county

    url = f"{HMDA_API_BASE}/csv"

    try:
        print(f"Fetching HMDA data from CFPB API (year={year})...")
        r = requests.get(url, params=params, timeout=120, stream=True)
        r.raise_for_status()

        from io import StringIO
        content = r.content.decode("utf-8")
        df = pd.read_csv(StringIO(content), dtype=str, low_memory=False)
        print(f"Loaded {len(df):,} LAR records")
        return _clean(df)

    except Exception as e:
        print(f"API error: {e}. Use load_sample() for testing.")
        return pd.DataFrame()


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
    """
    import numpy as np
    rng = np.random.default_rng(seed)

    states = ["IL", "NY", "CA", "TX", "GA", "NC", "OH", "PA", "FL", "MI"]
    leis = [f"LEI{i:06d}" for i in range(1, 11)]

    # Realistic denial rates by race (based on 2023 HMDA national data)
    race_denial_rates = {
        "White":                       0.095,
        "Black or African American":   0.195,
        "Asian":                       0.090,
        "Hispanic or Latino":          0.145,
        "American Indian or Alaska Native": 0.175,
        "Native Hawaiian or Other Pacific Islander": 0.160,
    }

    races = list(race_denial_rates.keys())
    race_weights = [0.65, 0.13, 0.07, 0.10, 0.02, 0.03]

    records = []
    for i in range(n):
        race = rng.choice(races, p=race_weights)
        denial_prob = race_denial_rates[race]

        # Income and loan amount correlated
        income = max(20, rng.normal(85, 45))
        loan_amount = max(50, income * rng.uniform(2.5, 5.5))

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
            "denial_reason_1": str(rng.choice([1, 3, 4, 9, 10], p=[0.3, 0.25, 0.2, 0.15, 0.1])) if action == 3 else "10",
            "interest_rate": str(round(rng.uniform(5.5, 8.5), 2)) if action == 1 else "",
            "rate_spread": str(round(rng.uniform(-0.5, 2.0), 2)) if action == 1 else "",
            "lei": rng.choice(leis),
            "activity_year": "2023",
        })

    df = pd.DataFrame(records)
    return _clean(df)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize and clean a raw HMDA LAR DataFrame."""
    df.columns = df.columns.str.lower().str.strip()

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
