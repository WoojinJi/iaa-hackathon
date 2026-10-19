"""Tests for src/history.py. Each expected value is worked out by hand in the comment.

Run from the repository root:  pytest -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.history import claim_history  # noqa: E402


def periods(*rows):
    return pd.DataFrame([dict(row_id=r, policy_id=p, year=y, period_start=pd.Timestamp(f"{y}-01-01"))
                         for r, p, y in rows])


def claims(*rows):
    return pd.DataFrame([dict(policy_id=p, loss_date=pd.Timestamp(l), report_date=pd.Timestamp(r))
                         for p, l, r in rows])


POL = periods(("R21", "P1", 2021), ("R22", "P1", 2022), ("R23", "P1", 2023), ("R24", "P1", 2024),
              ("N23", "P2", 2023))
CL = claims(("P1", "2021-03-01", "2021-03-10"),   # 2021 loss, reported in 2021
            ("P1", "2022-12-20", "2023-01-05"),   # 2022 loss, reported after 1 Jan 2023
            ("P1", "2023-06-01", "2023-06-02"))   # 2023 loss, reported in 2023


def h():
    return claim_history(POL, [POL], CL).set_index("row_id")


def test_2021_rows_are_missing():
    # The window starts before the data (2020) -> unknown, not 0
    assert np.isnan(h().loc["R21", "pol_claims_1y"])


def test_one_year_window_counts_known_claims():
    # R22 (2022): 2021 claim reported 2021-03-10 < 2022-01-01 -> 1
    assert h().loc["R22", "pol_claims_1y"] == 1


def test_claim_reported_after_cutoff_is_excluded():
    # R23 (2023): the 2022 loss was reported 2023-01-05, after the 1 Jan 2023 cutoff -> not known -> 0
    assert h().loc["R23", "pol_claims_1y"] == 0


def test_two_year_window_needs_two_observed_years():
    # R22: 2-year window starts 2020 -> missing. R24: window 2022-2023; known claims:
    # 2022 loss (reported 2023-01-05 < 2024-01-01) + 2023 loss -> 2
    assert np.isnan(h().loc["R22", "pol_claims_2y"])
    assert h().loc["R24", "pol_claims_2y"] == 2


def test_policy_new_to_the_data_is_missing():
    # N23: P2 has no period before 2023 -> its history is unknown
    assert np.isnan(h().loc["N23", "pol_claims_1y"])
