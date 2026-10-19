"""Tests for src/target.py.

Each test builds a tiny dataset whose correct answer can be worked out by hand.
The hand calculation is written next to every expected value, so a reviewer can
check the expectation without reading the implementation.

Run from the repository root:  pytest -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.target import (  # noqa: E402
    ADJ, adjust_claims, adjust_motor_claims, build_model_target, build_target, completeness,
    load_claims, load_policies, match_claims,
)


# ----------------------------------------------------------------- helpers
def policy(row_id, policy_id, start, end, exposure=None, vol=200, comp=100):
    """One policy period. Exposure defaults to days / 365. Excess defaults to 200 + 100 = 300."""
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    return dict(row_id=row_id, policy_id=policy_id,
                period_start=pd.Timestamp(start).date(), period_end=pd.Timestamp(end).date(),
                exposure=days / 365 if exposure is None else exposure,
                voluntary_excess=vol, compulsory_excess=comp)


def claim(claim_id, policy_id, peril, loss, incurred, recoveries=0.0, status="closed",
          report=None, line="motor"):
    return dict(claim_id=claim_id, policy_id=policy_id, line=line, peril=peril,
                loss_date=pd.Timestamp(loss).date(),
                report_date=pd.Timestamp(report or loss).date(), status=status,
                paid_to_date=incurred if status == "closed" else 0.0,
                incurred_to_date=incurred, recoveries=recoveries)


def write_data(tmp_path, policies, claims, line="motor"):
    pd.DataFrame(policies).to_parquet(tmp_path / f"policies_{line}.parquet")
    pd.DataFrame(claims).to_parquet(tmp_path / "claims.parquet")
    return load_policies(line, "train", data_dir=tmp_path), load_claims(data_dir=tmp_path)


def target_of(tmp_path, claims, excess_on_liability=True, cap=None):
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2023-01-01", "2023-12-31")], claims)
    return build_target(cl, pol, "motor", excess_on_liability, cap)[0]


# ------------------------------------------------------- per-claim net cost
def test_net_cost_basic(tmp_path):
    # own_damage: 1,000 incurred - 300 excess - 100 recovered = 600
    assert target_of(tmp_path, [claim("C1", "P1", "own_damage", "2023-05-01", 1000, 100)]) == pytest.approx(600)


def test_net_cost_never_negative(tmp_path):
    # 400 - 300 excess = 100; 100 - 500 recovered = -400 -> floored at 0
    assert target_of(tmp_path, [claim("C1", "P1", "own_damage", "2023-05-01", 400, 500)]) == 0


def test_claim_below_excess_is_zero(tmp_path):
    # 250 incurred is below the 300 excess -> 0
    assert target_of(tmp_path, [claim("C1", "P1", "own_damage", "2023-05-01", 250)]) == 0


def test_excess_on_liability_perils(tmp_path):
    # Host: excess applies to every peril. bodily_injury 1,000 - 300 excess = 700 by default;
    # the earlier assumption (excess_on_liability=False) gives 1,000
    c = [claim("C1", "P1", "bodily_injury", "2023-05-01", 1000)]
    assert target_of(tmp_path, c) == pytest.approx(700)
    assert target_of(tmp_path, c, excess_on_liability=False) == pytest.approx(1000)


def test_large_loss_cap(tmp_path):
    # bodily_injury 800,000 - 300 excess: uncapped 799,700; capped at 500,000
    c = [claim("C1", "P1", "bodily_injury", "2023-05-01", 800_000)]
    assert target_of(tmp_path, c) == pytest.approx(799_700)
    assert target_of(tmp_path, c, cap=500_000) == pytest.approx(500_000)


def test_claims_in_a_row_are_summed(tmp_path):
    # own_damage 1,000 - 300 = 700; third_party_prop 500 - 300 = 200; total 900
    c = [claim("C1", "P1", "own_damage", "2023-03-01", 1000),
         claim("C2", "P1", "third_party_prop", "2023-08-01", 500)]
    assert target_of(tmp_path, c) == pytest.approx(900)


# --------------------------------------------------------------- exposure
def test_exposure_correction(tmp_path):
    pols = [
        policy("OK", "P1", "2023-01-01", "2023-12-31"),                   # 1.0, correct
        policy("D360", "P2", "2023-01-01", "2023-12-31", exposure=1.0139),  # 365/360 -> 1.0
        policy("DAYS", "P3", "2023-01-01", "2023-11-23", exposure=327),     # 327 days -> 327/365
        policy("HALF", "P4", "2023-01-01", "2023-07-01"),                  # 182 days, correct
    ]
    pol, _ = write_data(tmp_path, pols, [claim("C1", "P1", "own_damage", "2023-05-01", 1000)])
    pol = pol.set_index("row_id")
    assert pol.loc["OK", "exp_flag"] == "ok"
    assert pol.loc["D360", "exp_flag"] == "basis_360"
    assert pol.loc["DAYS", "exp_flag"] == "in_days"
    assert pol.loc["D360", "exposure_clean"] == pytest.approx(1.0)
    assert pol.loc["DAYS", "exposure_clean"] == pytest.approx(327 / 365)
    assert pol.loc["HALF", "exposure_clean"] == pytest.approx(182 / 365)


# ----------------------------------------------------------- claims cleaning
def test_duplicates_and_repudiated_removed(tmp_path):
    # C2 duplicates C1 except claim_id -> dropped; C3 repudiated -> dropped; 1 claim left
    c = [claim("C1", "P1", "own_damage", "2023-05-01", 1000),
         claim("C2", "P1", "own_damage", "2023-05-01", 1000),
         claim("C3", "P1", "theft", "2023-06-01", 0, status="repudiated")]
    _, cl = write_data(tmp_path, [policy("R1", "P1", "2023-01-01", "2023-12-31")], c)
    assert list(cl["claim_id"]) == ["C1"]


def test_amount_columns_stay_numeric(tmp_path):
    # Regression test for the date-conversion bug: amount columns ending in "_date" stay numbers
    _, cl = write_data(tmp_path, [policy("R1", "P1", "2023-01-01", "2023-12-31")],
                       [claim("C1", "P1", "own_damage", "2023-05-01", 1000)])
    assert pd.api.types.is_numeric_dtype(cl["paid_to_date"])
    assert pd.api.types.is_numeric_dtype(cl["incurred_to_date"])
    assert pd.api.types.is_datetime64_any_dtype(cl["loss_date"])


# --------------------------------------------------------------- matching
def test_period_boundaries_inclusive(tmp_path):
    # Loss on the last day of period 1 goes to R1; loss on the first day of period 2 goes to R2
    pols = [policy("R1", "P1", "2022-01-01", "2022-12-31"),
            policy("R2", "P1", "2023-01-01", "2023-12-31")]
    c = [claim("C1", "P1", "own_damage", "2022-12-31", 1000),
         claim("C2", "P1", "own_damage", "2023-01-01", 2000)]
    pol, cl = write_data(tmp_path, pols, c)
    m = match_claims(cl, pol, "motor")
    assert len(m) == 2                                   # each claim matched exactly once
    assert dict(zip(m["claim_id"], m["row_id"])) == {"C1": "R1", "C2": "R2"}


def test_claim_outside_any_period_is_dropped(tmp_path):
    # 2020 loss, before the only policy period -> not matched; row target 0
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2021-01-01", "2021-12-31")],
                         [claim("C1", "P1", "own_damage", "2020-06-01", 1000)])
    assert len(match_claims(cl, pol, "motor")) == 0
    assert build_target(cl, pol, "motor")[0] == 0


# ------------------------------------------------------------ development
def test_completeness(tmp_path):
    # Reference (2021) claims all reported 400 days after loss.
    # At 2024-12-30, every 2024 loss is under 400 days old -> 0% reported.
    # 2021 losses are all over 1,000 days old -> 100% reported.
    pols = [policy(f"R{y}", "P1", f"{y}-01-01", f"{y}-12-31") for y in (2021, 2024)]
    c = [claim(f"C{i}", "P1", "own_damage", f"2021-0{i}-01", 1000,
               report=str((pd.Timestamp(f"2021-0{i}-01") + pd.Timedelta(days=400)).date()))
         for i in range(1, 4)]
    pol, cl = write_data(tmp_path, pols, c)
    m = match_claims(cl, pol, "motor")
    assert completeness(m, "own_damage", 2021) == pytest.approx(1.0)
    assert completeness(m, "own_damage", 2024) == pytest.approx(0.0)


# --------------------------------------------------- 2025-level adjustment
def adjusted_net(tmp_path, peril, loss, incurred, vol=200, comp=100):
    year = pd.Timestamp(loss).year
    pol, cl = write_data(tmp_path, [policy("R1", "P1", f"{year}-01-01", f"{year}-12-31", vol=vol, comp=comp)],
                         [claim("C1", "P1", peril, loss, incurred)])
    return adjust_motor_claims(match_claims(cl, pol, "motor", cap=None))["net_adj"].iloc[0]


def test_bi_reform_factor(tmp_path):
    # BI 2022, trend 0%: 10,000 x 0.83 = 8,300 gross; minus 300 excess = 8,000
    assert adjusted_net(tmp_path, "bodily_injury", "2022-06-01", 10_000) == pytest.approx(8_000)


def test_bi_after_reform_unchanged(tmp_path):
    # BI 2023: no reform factor, trend 0% -> 10,000 - 300 excess = 9,700
    assert adjusted_net(tmp_path, "bodily_injury", "2023-06-01", 10_000) == pytest.approx(9_700)


def test_trend_applies_before_excess(tmp_path):
    # own_damage 2024, trend 4%: 1,000 x 1.04 = 1,040; minus 300 excess = 740
    # (trending the net instead would give 700 x 1.04 = 728: the leverage effect)
    assert adjusted_net(tmp_path, "own_damage", "2024-06-01", 1000) == pytest.approx(740)


def test_frequency_shift_before_2023(tmp_path):
    # own_damage 2022, no excess: 1,000 x 1.04^3 = 1,124.864; x 0.93 frequency shift = 1,046.12352
    assert adjusted_net(tmp_path, "own_damage", "2022-06-01", 1000, vol=0, comp=0) == pytest.approx(1046.12352)


def test_model_weight_is_exposure_times_completeness(tmp_path):
    # Every claim reported on the loss day -> completeness 1 for 2021-2023.
    # 2024: the valuation date is 2024-12-30, so losses on Dec 31 cannot have happened yet:
    # 365 of 366 days (leap year) are observed -> 365/366.
    pols = [policy(f"R{y}", "P1", f"{y}-01-01", f"{y}-12-31") for y in (2021, 2022, 2023, 2024)]
    c = [claim(f"C{y}", "P1", "own_damage", f"{y}-03-01", 1000) for y in (2021, 2022, 2023, 2024)]
    pol, cl = write_data(tmp_path, pols, c)
    df, comp, _ = build_model_target(cl, pol)
    assert np.allclose(comp.values, [1.0, 1.0, 1.0, 365 / 366])
    assert np.allclose(df["weight"], df["exposure_clean"] * df["year"].map(comp))


def test_model_target_excess_on_liability_option(tmp_path):
    # bodily_injury 2024 (trend 0%, no reform factor from 2023): 1,000 - 300 excess = 700 by default;
    # earlier assumption (excess_on_liability=False): 1,000
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2024-01-01", "2024-12-31")],
                         [claim("C1", "P1", "bodily_injury", "2024-03-01", 1000)])
    assert build_model_target(cl, pol)[0]["target"].iloc[0] == pytest.approx(700)
    df, _, _ = build_model_target(cl, pol, excess_on_liability=False)
    assert df["target"].iloc[0] == pytest.approx(1000)


def test_home_trend_and_cap(tmp_path):
    # buildings fire 2024, trend 0%, excess 300, cap 300,000:
    # 600,000 - 300 = 599,700 -> capped at 300,000; loading carries the 299,700 above the cap
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2024-01-01", "2024-12-31")],
                         [claim("C1", "P1", "fire", "2024-03-01", 600_000, line="buildings")],
                         line="buildings")
    df, comp, loading = build_model_target(cl, pol, "buildings")
    assert df["target"].iloc[0] == pytest.approx(300_000)
    assert loading * df["weight"].sum() == pytest.approx(299_700)


def test_contents_trend_no_cap(tmp_path):
    # contents theft 2022, trend 4%: 10,000 x 1.04^3 = 11,248.64; minus 300 excess = 10,948.64
    pol, cl = write_data(tmp_path, [policy("R1", "P1", "2022-01-01", "2022-12-31")],
                         [claim("C1", "P1", "theft", "2022-03-01", 10_000, line="contents")],
                         line="contents")
    m = adjust_claims(match_claims(cl, pol, "contents", cap=None), ADJ["contents"])
    assert m["net_adj"].iloc[0] == pytest.approx(10_948.64)


# --------------------------------------------------------------- evaluation
def test_d2_perfect_and_constant():
    from src.evaluate import d2_tweedie
    actual = np.array([0.0, 0.0, 100.0, 300.0])
    base = np.full(4, actual.mean())
    assert d2_tweedie(actual, actual + 1e-9, base) == pytest.approx(1.0, abs=1e-4)   # perfect model (tiny floor on zero rows)
    assert d2_tweedie(actual, base, base) == pytest.approx(0.0)                       # constant model


def test_leakage_columns_never_used_as_features():
    from src.features import EXCLUDE
    for col in ["renewal_decision", "customer_service_contacts", "written_premium", "row_id", "exposure"]:
        assert col in EXCLUDE
