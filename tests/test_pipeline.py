"""Tests for the Oct 21 additions: reform date, Lynden-Bell completeness, Pareto loading, pipeline helpers,
check helpers. Each expected value is worked out in a comment, or comes from a simulation with a known answer.

Run from the repository root:  pytest -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.checks import schema_diff, step_test  # noqa: E402
from src.loading import expected_excess, pareto_alpha, pareto_loading  # noqa: E402
from src.pipeline import hist_levels, rel_premium  # noqa: E402
from src.target import ADJ, adjust_claims, completeness, lag_cdf_lynden_bell  # noqa: E402

VAL = pd.Timestamp("2024-12-30")


def one_claim(loss_date, peril="bodily_injury", incurred=10_000, excess=0):
    d = pd.Timestamp(loss_date)
    return pd.DataFrame({"peril": [peril], "loss_date": [d], "loss_year": [d.year],
                         "incurred_to_date": [incurred], "recoveries": [0.0], "excess": [excess]})


# ------------------------------------------------------------- reform date
def test_reform_date_default_matches_calendar_year():
    # BI, trend 0%: a 2022 loss gets the 0.83 reform factor, a 2023 loss does not (default date 2023-01-01)
    adj = ADJ["motor"]
    assert adjust_claims(one_claim("2022-12-31"), adj)["net_adj"].iloc[0] == pytest.approx(8_300)
    assert adjust_claims(one_claim("2023-01-01"), adj)["net_adj"].iloc[0] == pytest.approx(10_000)


def test_reform_date_mid_year():
    # with the break on 2023-07-01, a loss on 2023-03-01 is still before the change: 10,000 x 0.83 = 8,300
    adj = dict(ADJ["motor"], reform_date="2023-07-01")
    assert adjust_claims(one_claim("2023-03-01"), adj)["net_adj"].iloc[0] == pytest.approx(8_300)
    assert adjust_claims(one_claim("2023-07-01"), adj)["net_adj"].iloc[0] == pytest.approx(10_000)


# ------------------------------------------------------ Lynden-Bell estimator
def simulated_claims(n=200_000, mean_lag=300, seed=0):
    """Losses spread over 2021-2024, exponential report lag; only claims reported by VAL are seen."""
    rng = np.random.default_rng(seed)
    loss = pd.Timestamp("2021-01-01") + pd.to_timedelta(rng.uniform(0, 1460, n), unit="D")
    lag = np.round(rng.exponential(mean_lag, n))
    window = (VAL - loss).days.to_numpy()
    seen = lag <= window
    loss, lag = loss[seen], lag[seen]
    return pd.DataFrame({"peril": "x", "loss_date": loss.normalize(), "loss_year": loss.year, "report_lag": lag})


def test_lynden_bell_recovers_known_distribution():
    # true F(t) = 1 - exp(-t/300); the estimator is relative to the longest observable lag (~1460 days)
    m = simulated_claims()
    F = lag_cdf_lynden_bell(m.report_lag, (VAL - m.loss_date).dt.days)
    for t in [30, 180, 365, 730]:
        true = (1 - np.exp(-t / 300)) / (1 - np.exp(-1460 / 300))
        assert F(t) == pytest.approx(true, abs=0.01)


def test_completeness_lynden_bell_close_to_truth():
    # 2024 losses: true share reported by VAL = average over loss days of F(age)
    m = simulated_claims()
    ages = (VAL - pd.date_range("2024-01-01", "2024-12-31")).days.to_numpy()
    true = np.where(ages >= 0, 1 - np.exp(-np.clip(ages, 0, None) / 300), 0).mean() / (1 - np.exp(-1460 / 300))
    assert completeness(m, "x", 2024, valuation_date=VAL, method="lynden_bell") == pytest.approx(true, abs=0.01)


def test_completeness_unknown_method():
    with pytest.raises(ValueError):
        completeness(simulated_claims(1000), "x", 2024, valuation_date=VAL, method="other")


# --------------------------------------------------------------- Pareto
def test_expected_excess_formula():
    # u = 100k, cap = 500k, alpha = 2: 100,000^2 x 500,000^-1 / 1 = 20,000
    assert expected_excess(100_000, 500_000, 2.0) == pytest.approx(20_000)


def test_pareto_fit_and_loading_on_simulated_tail():
    # Pareto(alpha 2.5, scale 100k): MLE close to 2.5; the excess over 500k per claim above 100k
    # matches the simulated mean of (X - 500k)+
    rng = np.random.default_rng(1)
    x = 100_000 * (1 - rng.random(400_000)) ** (-1 / 2.5)
    a, n = pareto_alpha(x, 100_000)
    assert a == pytest.approx(2.5, rel=0.01) and n == len(x)
    sim = np.maximum(x - 500_000, 0).mean()
    assert expected_excess(100_000, 500_000, a) == pytest.approx(sim, rel=0.05)
    # loading per weight: 400,000 claims over a weight of 1e8 -> 0.004 x excess per claim
    r = pareto_loading(x, 1e8, 100_000, 500_000)
    assert r["loading"] == pytest.approx(0.004 * r["excess_per_claim"])


# --------------------------------------------------------- pipeline helpers
def test_rel_premium_divides_by_the_year_average():
    # 2024: premiums 100 and 300 on exposure 1 each -> average 200 -> 0.5 and 1.5
    # 2025: premium 220 on exposure 0.5 -> 440 a year; its year's average is 440 -> 1.0
    d = pd.DataFrame({"year": [2024, 2024, 2025], "written_premium": [100, 300, 220], "exposure_clean": [1, 1, 0.5]})
    assert rel_premium(d).tolist() == pytest.approx([0.5, 1.5, 1.0])


def test_rel_premium_by_start_month():
    # same year, two start months: Jan premiums 100, 300 (average 200); Jul premium 600 (average 600)
    # -> 0.5, 1.5, 1.0: a mid-year rate change is not read as a difference in risk
    d = pd.DataFrame({"year": 2021, "written_premium": [100, 300, 600], "exposure_clean": 1.0,
                      "period_start": pd.to_datetime(["2021-01-01", "2021-01-15", "2021-07-01"])})
    assert rel_premium(d, by="month").tolist() == pytest.approx([0.5, 1.5, 1.0])


def test_hist_levels():
    s = hist_levels(pd.Series([0, 1, 2, 5, np.nan]))
    assert s.iloc[:4].tolist() == ["0", "1", "2+", "2+"] and pd.isna(s.iloc[4])


# ------------------------------------------------------------ check helpers
def test_step_test_finds_a_planted_step_and_not_a_trend():
    rng = np.random.default_rng(2); t = np.arange(16)
    step = 1000 * np.where(t >= 8, 0.8, 1.0) * np.exp(rng.normal(0, 0.02, 16))
    trend = 1000 * 1.05 ** (t / 4) * np.exp(rng.normal(0, 0.02, 16))
    r = step_test(step, np.ones(16), 1, 4)
    assert r["k"] == 8 and r["step"] == pytest.approx(0.8, abs=0.03) and r["dbic"] > 10
    assert step_test(trend, np.ones(16), 1, 4)["dbic"] < 10


def test_schema_diff_reports_changes():
    ref = {"a.parquet": {"rows": 1, "columns": {"x": "int64", "y": "object"}}, "_status": ["closed"]}
    new = {"a.parquet": {"rows": 1, "columns": {"x": "float64", "z": "object"}}, "_status": ["closed", "open"]}
    d = schema_diff(new, ref)
    assert set(d.change) == {"type changed", "new column", "missing column", "values differ"}
