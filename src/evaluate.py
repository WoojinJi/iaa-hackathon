"""Standard checks run on every model.

All functions take row-level actual cost and predicted cost (same units: currency per row).
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_tweedie_deviance

POWER = 1.5


def d2_tweedie(actual, pred, base_rate_pred, power=POWER):
    """D² = 1 - deviance(model) / deviance(constant-rate model). Higher is better; 0 = no skill."""
    pred = np.maximum(pred, 1e-9)
    base = np.maximum(base_rate_pred, 1e-9)
    return 1 - mean_tweedie_deviance(actual, pred, power=power) / mean_tweedie_deviance(actual, base, power=power)


def actual_to_expected(df, by=None):
    """Sum of actual / sum of predicted, overall or by a column. 1.00 = level is right."""
    if by is None:
        return df["actual"].sum() / df["pred"].sum()
    g = df.groupby(by, observed=True)[["actual", "pred", "weight"]].sum()
    g["A/E"] = g["actual"] / g["pred"]
    g["share_of_weight"] = g["weight"] / g["weight"].sum()
    return g[["share_of_weight", "A/E"]]


def lift(df, n=10):
    """Rows sorted by predicted rate into n bands of equal weight; actual vs predicted rate per band."""
    d = df.assign(rate=df["pred"] / df["weight"]).sort_values("rate")
    d["band"] = pd.qcut(d["weight"].cumsum(), n, labels=range(1, n + 1))
    g = d.groupby("band", observed=True)[["actual", "pred", "weight"]].sum()
    return pd.DataFrame({"pred_rate": g["pred"] / g["weight"], "actual_rate": g["actual"] / g["weight"],
                         "A/E": g["actual"] / g["pred"]})


def evaluate(actual, pred, weight, segments=None, name="model", show=True):
    """Run all standard checks. segments: DataFrame of columns to check A/E by (same row order).

    The baseline for D² is a single rate for all rows (total actual / total weight) x weight.
    """
    actual, pred, weight = np.asarray(actual, float), np.asarray(pred, float), np.asarray(weight, float)
    base = actual.sum() / weight.sum() * weight
    df = pd.DataFrame({"actual": actual, "pred": pred, "weight": weight})
    res = {"name": name, "rows": len(df), "D2": d2_tweedie(actual, pred, base),
           "A/E": actual_to_expected(df), "lift": lift(df)}
    lf = res["lift"]
    res["top/bottom"] = lf["actual_rate"].iloc[-1] / max(lf["actual_rate"].iloc[0], 1e-9)
    res["segments"] = {}
    if segments is not None:
        for c in segments.columns:
            s = segments[c].reset_index(drop=True)
            if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s) and s.nunique() > 10:
                s = pd.qcut(s, 5, duplicates="drop").astype(str)
            res["segments"][c] = actual_to_expected(df.assign(seg=s.fillna("missing").astype(str).values), "seg")
    if show:
        print(f"===== {name}: {res['rows']:,} rows =====")
        print(f"D2 (Tweedie {POWER}): {res['D2']:.4f} | overall A/E: {res['A/E']:.3f} | "
              f"top/bottom decile actual rate: {res['top/bottom']:.1f}x")
        print(lf.round(3).to_string())
        for c, t in res["segments"].items():
            flag = t[(t["share_of_weight"] > 0.02) & ((t["A/E"] < 0.9) | (t["A/E"] > 1.1))]
            if len(flag):
                print(f"\n[segment flag] {c}: A/E outside 0.9-1.1")
                print(flag.round(3).to_string())
    return res
