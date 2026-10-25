"""Tests for the Oct 24 target changes (Part 2): amounts net of excess, trend leverage, row completeness.

Same style as test_target.py: tiny datasets, the hand calculation next to every expected value.
Run from the repository root:  pytest -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
import src.target as T  # noqa: E402
from src.target import ADJ, adjust_claims, build_model_target, load_claims, load_policies, match_claims  # noqa: E402


def policy(row_id, policy_id, start, end, vol=200, comp=100):
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    return dict(row_id=row_id, policy_id=policy_id, period_start=pd.Timestamp(start).date(),
                period_end=pd.Timestamp(end).date(), exposure=days / 365, voluntary_excess=vol, compulsory_excess=comp)


def claim(claim_id, policy_id, peril, loss, incurred, recoveries=0.0, report=None, line="motor"):
    return dict(claim_id=claim_id, policy_id=policy_id, line=line, peril=peril, loss_date=pd.Timestamp(loss).date(),
                report_date=pd.Timestamp(report or loss).date(), status="closed", paid_to_date=incurred,
                incurred_to_date=incurred, recoveries=recoveries)


def write_data(tmp_path, policies, claims, line="motor"):
    pd.DataFrame(policies).to_parquet(tmp_path / f"policies_{line}.parquet")
    pd.DataFrame(claims).to_parquet(tmp_path / "claims.parquet")
    return load_policies(line, "train", data_dir=tmp_path), load_claims(data_dir=tmp_path)


def test_net_amounts_are_not_reduced_by_the_excess_again(tmp_path):
    # amounts already net of excess: 1,000 incurred - 100 recovered = 900 (the 300 excess is not deducted again)
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2023-01-01", "2023-12-31")],
                         [claim("C1", "P1", "own_damage", "2023-05-01", 1000, 100)])
    m = match_claims(cl, pol, "motor", cap=None, amounts_net=True)
    assert m["net"].iloc[0] == pytest.approx(900)
    assert m["excess_in_amount"].iloc[0] == pytest.approx(300)


def test_leverage_net_amounts_match_the_ground_up_calculation(tmp_path):
    # own_damage 2024, trend 4%: ground-up 1,000 (net 700 + excess 300) x 1.04 = 1,040; minus 300 = 740,
    # the same as test_trend_applies_before_excess on gross amounts. Trending the net (700 x 1.04 = 728) is wrong.
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2024-01-01", "2024-12-31")],
                         [claim("C1", "P1", "own_damage", "2024-06-01", 700)])
    m = adjust_claims(match_claims(cl, pol, "motor", cap=None, amounts_net=True), ADJ["motor"])
    assert m["net_adj"].iloc[0] == pytest.approx(740)


def test_leverage_with_recoveries(tmp_path):
    # own_damage 2024, trend 4%: (700 + 300) x 1.04 = 1,040; - 300 excess = 740; - 100 x 1.04 recovered = 636
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2024-01-01", "2024-12-31")],
                         [claim("C1", "P1", "own_damage", "2024-06-01", 700, 100)])
    m = adjust_claims(match_claims(cl, pol, "motor", cap=None, amounts_net=True), ADJ["motor"])
    assert m["net_adj"].iloc[0] == pytest.approx(636)


def test_no_trend_leaves_net_amounts_unchanged(tmp_path):
    # bodily_injury 2024: trend 0%, no reform after 2023 -> the net amount 1,000 is unchanged
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2024-01-01", "2024-12-31")],
                         [claim("C1", "P1", "bodily_injury", "2024-03-01", 1000)])
    m = adjust_claims(match_claims(cl, pol, "motor", cap=None, amounts_net=True), ADJ["motor"])
    assert m["net_adj"].iloc[0] == pytest.approx(1000)


def test_row_completeness_keeps_the_year_total_and_lowers_late_rows(tmp_path, monkeypatch):
    # Two 2024 rows: one for the whole year, one starting 1 Dec. Claims are reported 60 days after loss, so the
    # December row is less complete at the valuation date (2024-12-30). Row completeness must keep the year's
    # total weight and give the December row a lower weight per exposure than the full-year row.
    pols = [policy("R1", "P1", "2024-01-01", "2024-12-31"), policy("R2", "P2", "2024-12-01", "2024-12-31")]
    cs = [claim(f"C{i}", "P1", "own_damage", f"2024-0{m}-01", 500, report=f"2024-0{m + 2}-01")
          for i, m in enumerate([1, 2, 3, 4, 5], 1)]
    pol, cl = write_data(tmp_path, pols, cs)
    monkeypatch.setattr(T, "AMOUNTS_NET", True)
    monkeypatch.setattr(T, "ROW_COMPLETENESS", False)
    base, _, _ = build_model_target(cl, pol, "motor", completeness_method="lynden_bell", years=[2024])
    monkeypatch.setattr(T, "ROW_COMPLETENESS", True)
    rowc, _, _ = build_model_target(cl, pol, "motor", completeness_method="lynden_bell", years=[2024])
    assert rowc["weight"].sum() == pytest.approx(base["weight"].sum())
    per_exp = (rowc["weight"] / rowc["exposure_clean"]).to_numpy()
    assert per_exp[1] < per_exp[0]
