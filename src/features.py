"""Feature table for each line: policy + customer + address + weather.

Every column used or excluded is listed here, so the choice can be reviewed in one place.
"""
from pathlib import Path

import pandas as pd

from .target import DATA_DIR, load_policies

# Columns never used as model features, with the reason.
EXCLUDE = {
    # identifiers
    "row_id": "identifier", "policy_id": "identifier", "customer_id": "identifier",
    "address_id": "identifier",
    # period and exposure: handled through the target and weight, not as features
    "period_start": "period", "period_end": "period", "exposure": "raw exposure (corrected copy used as weight)",
    "days": "derived from period", "exp_dates": "derived from period", "exp_flag": "data-quality flag",
    "exposure_clean": "used as weight", "year": "all years brought to 2025 level",
    # leakage
    "renewal_decision": "train only; known after the period (leakage)",
    "customer_service_contacts": "may respond to claims during the period (leakage check pending)",
    # the insurer's existing price: excluded from the baseline so the model is a pure risk model
    "written_premium": "existing price; tested separately",
    # personal or marketing data: no plausible risk link, privacy and fairness concerns
    "surname": "personal data", "date_of_birth": "age already in policy table",
    "email_domain": "personal data", "marketing_consent": "marketing",
    "document_preference": "marketing", "campaign_code": "marketing",
    "marketing_segment": "marketing", "branch_id": "administrative",
    "vehicle_colour": "no plausible risk link",
    "make_model": "very high cardinality; for tree models only",
}

WEATHER_COLS = ["hail_days", "wind_exposure_index", "freezing_days", "dry_summer_index",
                "wildfire_index", "rainfall_mm", "mean_temperature_c"]


def build_features(line, split="train", data_dir=DATA_DIR, policies=None, weather_mode="actual"):
    """Return one row per row_id with policy, customer, address and weather features.

    weather_mode="actual": weather of the policy year (2025 for test).
    weather_mode="average": each address's average weather over 2021-2024 (practicality check:
    next year's weather is not known when pricing).
    """
    data_dir = Path(data_dir)
    p = load_policies(line, split, data_dir) if policies is None else policies
    cust = pd.read_parquet(data_dir / "customers.parquet")
    addr = pd.read_parquet(data_dir / "addresses.parquet")
    wthr = pd.read_parquet(data_dir / "weather.parquet")

    df = p.merge(cust, on="customer_id", how="left").merge(addr, on="address_id", how="left")
    if weather_mode == "actual":
        df = df.merge(wthr, on=["address_id", "year"], how="left")
    elif weather_mode == "average":
        avg = wthr[wthr["year"] <= 2024].groupby("address_id")[WEATHER_COLS].mean().reset_index()
        df = df.merge(avg, on="address_id", how="left")
    else:
        raise ValueError(weather_mode)

    # derived features
    df["customer_tenure"] = df["year"] - df["customer_since_year"]
    if "year_built" in df:
        df["building_age"] = df["year"] - df["year_built"]
    df = df.drop(columns=["customer_since_year", "year_built"], errors="ignore")

    keep = [c for c in df.columns if c not in EXCLUDE]
    out = df[["row_id"] + keep].copy()
    assert out["row_id"].is_unique, "joins must not duplicate rows"
    return out


def feature_types(features):
    """Split feature columns into numeric and categorical (bool and text are categorical)."""
    cols = [c for c in features.columns if c != "row_id"]
    num = [c for c in cols if pd.api.types.is_numeric_dtype(features[c])
           and not pd.api.types.is_bool_dtype(features[c])]
    cat = [c for c in cols if c not in num]
    return num, cat
