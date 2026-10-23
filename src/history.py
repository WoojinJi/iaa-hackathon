"""Claim-history features: past claims known when a policy year is priced.

"Known" = reported before 1 Jan of the policy year. A 2025 test row therefore sees claims reported
up to the end of 2024, the same information a training row of year Y sees up to the end of Y-1.

Counts include zero-net claims (the claim itself is the signal). A count is set to missing, not 0,
when the history cannot be observed:
  - the window starts before the data do (DATA_START), e.g. every 2021 row;
  - the policy has no earlier period in the data (new to us), so its past is unknown.
"""
import numpy as np
import pandas as pd

DATA_START = pd.Timestamp("2021-01-01")


def claim_history(target_pol, all_pol_same_line, claims, years=(1, 2), perils=None, prefix="pol_claims",
                  data_start=DATA_START):
    """Per row_id of target_pol: number of claims on the same policy_id with loss date in the
    `years` years before 1 Jan of the policy year and reported before that date.

    all_pol_same_line: train (and test) periods of the same line, used to tell whether the policy
    has an earlier period in the data.
    perils: count only these perils (None = all). Columns are named f"{prefix}_{y}y".
    Amounts are deliberately not used: they are valued at the data end (2024-12-30), so for
    training rows they include development after the cutoff, which a test row cannot see.
    """
    t = target_pol[["row_id", "policy_id", "year"]].copy()
    t["cutoff"] = pd.to_datetime(t["year"].astype(int).astype(str) + "-01-01")

    starts = pd.concat([p[["policy_id", "period_start"]] for p in all_pol_same_line])
    first_start = pd.to_datetime(starts["period_start"]).groupby(starts["policy_id"]).min()
    t["seen_before"] = t["policy_id"].map(first_start) < t["cutoff"]

    c = claims if perils is None else claims[claims["peril"].isin(perils)]
    c = c[["policy_id", "loss_date", "report_date"]]
    j = t[["row_id", "policy_id", "cutoff"]].merge(c, on="policy_id", how="inner")
    j = j[j["report_date"] < j["cutoff"]]

    out = t[["row_id"]].copy()
    for y in years:
        start = t["cutoff"] - pd.DateOffset(years=y)
        w = j[j["loss_date"] >= j["cutoff"] - pd.DateOffset(years=y)]
        n = t["row_id"].map(w.groupby("row_id").size()).fillna(0.0)
        observable = (start >= data_start) & t["seen_before"]
        out[f"{prefix}_{y}y"] = np.where(observable, n, np.nan)
    return out
