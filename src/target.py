"""Data loading, cleaning and target construction for the IAA hackathon.

Every rule implemented here is documented, with evidence, in DECISIONS.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LINES = ("motor", "buildings", "contents")
YEARS = (2021, 2022, 2023, 2024)

# Data valuation date: the last report_date in claims.parquet.
VALUATION_DATE = pd.Timestamp("2024-12-30")

# Motor liability perils: excess is not deducted (UK practice; see DECISIONS.md).
LIABILITY_PERILS = {"bodily_injury", "third_party_prop"}

# Individual claims are capped here for modelling; the excess becomes a loading.
LARGE_LOSS_CAP = 500_000

# Two claims identical on all of these columns are one duplicated record.
DUP_KEY = ["policy_id", "line", "peril", "loss_date", "report_date", "status",
           "paid_to_date", "incurred_to_date", "recoveries"]


# ---------------------------------------------------------------- policies
def classify_exposure(df):
    """Label each row's exposure: ok / basis_360 / in_days / other."""
    ok = np.isclose(df["exposure"], df["exp_dates"], atol=1e-3)
    basis360 = np.isclose(df["exposure"], df["days"] / 360, atol=5e-4) & ~ok
    in_days = np.isclose(df["exposure"], df["days"]) & ~ok
    return pd.Series(
        np.select([ok, basis360, in_days], ["ok", "basis_360", "in_days"], "other"),
        index=df.index,
    )


def load_policies(line, split="train", data_dir=DATA_DIR):
    """Load one line's policy table with parsed dates and corrected exposure.

    Adds: days, exp_dates (= days / 365), exp_flag, exposure_clean, year.
    exposure_clean keeps the original value where it is consistent with the
    period dates and replaces it with days / 365 otherwise.
    """
    fname = f"policies_{line}.parquet" if split == "train" else f"test_{line}.parquet"
    df = pd.read_parquet(Path(data_dir) / fname)
    df["period_start"] = pd.to_datetime(df["period_start"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["days"] = (df["period_end"] - df["period_start"]).dt.days + 1  # both ends inclusive
    df["exp_dates"] = df["days"] / 365
    df["exp_flag"] = classify_exposure(df)
    df["exposure_clean"] = np.where(df["exp_flag"] == "ok", df["exposure"], df["exp_dates"])
    df["year"] = df["period_start"].dt.year
    return df


# ------------------------------------------------------------------ claims
def load_claims(data_dir=DATA_DIR, drop_duplicates=True, drop_repudiated=True):
    """Load claims with parsed dates, optionally removing duplicates and repudiated claims.

    Only loss_date and report_date are converted to datetime; the amount
    columns (paid_to_date, incurred_to_date) also end in "_date" but are numbers.
    """
    c = pd.read_parquet(Path(data_dir) / "claims.parquet")
    c["loss_date"] = pd.to_datetime(c["loss_date"])
    c["report_date"] = pd.to_datetime(c["report_date"])
    if drop_duplicates:
        c = c[~c.duplicated(subset=DUP_KEY, keep="first")]
    if drop_repudiated:
        c = c[c["status"] != "repudiated"]
    c = c.copy()
    c["report_lag"] = (c["report_date"] - c["loss_date"]).dt.days
    c["loss_year"] = c["loss_date"].dt.year
    return c


def match_claims(claims, policies, line, excess_on_liability=False, cap=LARGE_LOSS_CAP):
    """Attach each claim to the policy period containing its loss date.

    Returns one row per matched claim with:
      excess   = voluntary + compulsory (0 for liability perils unless excess_on_liability)
      net      = max(max(incurred - excess, 0) - recoveries, 0)
      net_cap  = min(net, cap)   (equal to net when cap is None)
    """
    p = policies[["row_id", "policy_id", "period_start", "period_end",
                  "voluntary_excess", "compulsory_excess"]]
    c = claims[claims["line"] == line].merge(p, on="policy_id")
    c = c[(c["loss_date"] >= c["period_start"]) & (c["loss_date"] <= c["period_end"])].copy()
    c["excess"] = c["voluntary_excess"] + c["compulsory_excess"]
    if not excess_on_liability:
        c.loc[c["peril"].isin(LIABILITY_PERILS), "excess"] = 0
    c["net"] = np.maximum(np.maximum(c["incurred_to_date"] - c["excess"], 0) - c["recoveries"], 0)
    c["net_cap"] = c["net"] if cap is None else np.minimum(c["net"], cap)
    return c


def build_target(claims, policies, line, excess_on_liability=False, cap=None):
    """Target per row_id = sum of per-claim net cost (0 for rows with no claims).

    cap=None gives the uncapped target; pass LARGE_LOSS_CAP for the modelling target.
    """
    c = match_claims(claims, policies, line, excess_on_liability, cap)
    per_row = c.groupby("row_id")["net_cap"].sum()
    return policies["row_id"].map(per_row).fillna(0.0).to_numpy()


def cost_per_exposure(policies, target):
    """Net cost per unit of corrected exposure, by policy year."""
    g = pd.DataFrame({"year": policies["year"], "net": target,
                      "exp": policies["exposure_clean"]}).groupby("year").sum()
    return g["net"] / g["exp"]


# ------------------------------------------------------------- development
def completeness(matched, peril, year, ref_year=2021,
                 valuation_date=VALUATION_DATE, weight_col=None):
    """Share of a loss year's claims expected to be reported by the valuation date.

    Uses the report-lag distribution of `ref_year` losses (the most mature year),
    assuming losses are spread evenly over the year. With weight_col (e.g. "net_cap")
    the share is amount-weighted instead of count-based.
    """
    ref = matched[(matched["peril"] == peril) & (matched["loss_year"] == ref_year)]
    ref = ref.sort_values("report_lag")
    w = np.ones(len(ref)) if weight_col is None else ref[weight_col].to_numpy()
    cum = np.cumsum(w) / w.sum()
    ages = (valuation_date - pd.date_range(f"{year}-01-01", f"{year}-12-31")).days.to_numpy()
    idx = np.searchsorted(ref["report_lag"].to_numpy(), ages, side="right")
    return float(np.where(idx > 0, cum[idx - 1], 0.0).mean())
# ------------------------------------------------------- modelling target (motor)
TARGET_YEAR = 2025

MOTOR_ADJ = {
    # Annual severity trend, gross of excess (notebook 02, section 10)
    "sev_trend": {"bodily_injury": 0.0, "glass_hail": 0.08, "own_damage": 0.04,
                  "theft": 0.03, "third_party_prop": 0.08},
    # BI losses before 2023 are on-levelled to the post-reform cost level
    "bi_reform_factor": 0.83,
    # Frequency level shift in 2023, applied to losses before 2023
    "freq_shift": {"own_damage": 0.93, "third_party_prop": 0.95},
}


def adjust_motor_claims(matched, adj=MOTOR_ADJ, target_year=TARGET_YEAR, cap=LARGE_LOSS_CAP):
    """Bring each matched motor claim to the target-year level.

    Severity trend and the BI reform factor scale incurred and recoveries (excess is fixed);
    the net is capped; the frequency shift then scales pre-2023 claims of the affected perils.
    Adds net_adj.
    """
    c = matched.copy()
    pre = c["loss_year"] < 2023
    sev = (1 + c["peril"].map(adj["sev_trend"]).fillna(0.0)) ** (target_year - c["loss_year"])
    sev = np.where(pre & (c["peril"] == "bodily_injury"), sev * adj["bi_reform_factor"], sev)
    gross = c["incurred_to_date"] * sev
    rec = c["recoveries"] * sev
    net = np.maximum(np.maximum(gross - c["excess"], 0) - rec, 0)
    freq = np.where(pre, c["peril"].map(adj["freq_shift"]).fillna(1.0), 1.0)
    c["net_adj"] = np.minimum(net, cap) * freq
    return c


def year_completeness(adjusted, years=YEARS):
    """Line-level completeness by loss year: reported / ultimate, on adjusted amounts."""
    out = {}
    for y in years:
        rep = adjusted[adjusted["loss_year"] == y]
        ult = sum(rep.loc[rep["peril"] == p, "net_adj"].sum() / completeness(adjusted, p, y)
                  for p in rep["peril"].unique())
        out[y] = rep["net_adj"].sum() / ult
    return pd.Series(out, name="completeness")


def build_model_target(claims, policies, adj=MOTOR_ADJ):
    """Motor modelling frame: row_id, year, target (2025 level) and weight.

    weight = exposure_clean x completeness of the policy year, so immature years count
    as partially observed exposure instead of having their losses grossed up row by row.
    """
    mc = adjust_motor_claims(match_claims(claims, policies, "motor", cap=None), adj)
    per_row = mc.groupby("row_id")["net_adj"].sum()
    comp = year_completeness(mc)
    df = policies[["row_id", "year", "exposure_clean"]].copy()
    df["target"] = df["row_id"].map(per_row).fillna(0.0)
    df["weight"] = df["exposure_clean"] * df["year"].map(comp)
    return df, comp