"""Planted-error test: do our diagnostics tell assumption (target) errors from model errors?

Claim under test (AI_USE_LOG entry 28): errors in frequency/severity assumptions shift the
level of whole years, while model errors distort differences between segments within a year.
We plant known errors of each kind and check how each diagnostic attributes them.
"""
import copy

import numpy as np
import pandas as pd

from .target import ADJ, YEARS, adjust_claims, build_model_target, match_claims, completeness
from .glm import BandedTweedieGLM
from .evaluate import d2_tweedie

FOLDS = [(2023, [2021, 2022]), (2024, [2021, 2022, 2023])]   # (validation year, training years)


def _segment_ae(actual, pred, seg):
    """A/E by segment level; numeric columns cut into quintiles."""
    s = seg.reset_index(drop=True)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s) and s.nunique() > 10:
        s = pd.qcut(s, 5, duplicates="drop")
    s = s.astype(str).fillna("missing")
    g = pd.DataFrame({"a": actual, "p": pred, "s": s.values}).groupby("s")[["a", "p"]].sum()
    return g["a"] / g["p"], g["p"] / g["p"].sum()


def shape_error(actual, pred, segments):
    """Prediction-weighted spread of log(A/E) across segment levels, averaged over segment columns.
    Also returns the spread per column, to show which segment is distorted."""
    per = {}
    for c in segments.columns:
        ae, w = _segment_ae(actual, pred, segments[c])
        la = np.log(ae.clip(1e-6))
        m = np.average(la, weights=w)
        per[c] = float(np.sqrt(np.average((la - m) ** 2, weights=w)))
    return float(np.mean(list(per.values()))), per


def target_check(target_df):
    """Model-free check (diagnostic 1): spread of 2025-level cost per weight across years."""
    g = target_df.groupby("year")[["target", "weight"]].sum()
    r = g["target"] / g["weight"]
    return float(r.max() / r.min() - 1), r


def freq_sev_check(matched_adj, policies, comp_by_peril=True):
    """Model-free check (diagnostic 2): per peril and year, completeness-adjusted frequency and
    severity at 2025 level, each relative to its all-year average. Returns the largest deviation
    of each component.
    Returns peril x year tables; summarise() compares them cell by cell with the baseline."""
    exp_y = policies.groupby("year")["exposure_clean"].sum()
    rows = []
    for p in matched_adj["peril"].unique():
        for y in YEARS:
            s = matched_adj[(matched_adj["peril"] == p) & (matched_adj["loss_year"] == y)]
            c = completeness(matched_adj, p, y) if comp_by_peril else 1.0
            pos = s[s["net_adj"] > 0]
            rows.append({"peril": p, "year": y,
                         "freq": len(pos) / max(c, 1e-9) / exp_y[y],
                         "sev": pos["net_adj"].mean() if len(pos) else np.nan})
    t = pd.DataFrame(rows)
    return {comp: t.pivot(index="peril", columns="year", values=comp) for comp in ["freq", "sev"]}


def run_case(name, claims, policies, features, seg_cols, adj=None, comp_2024_one=False,
             drop_features=(), glm_kwargs=None):
    """Build the target under (possibly wrong) assumptions, fit the GLM on each fold, and
    return the level and shape metrics plus the model-free checks."""
    adj = copy.deepcopy(ADJ["motor"] if adj is None else adj)
    mt, comp, _ = build_model_target(claims, policies, "motor", adj)
    if comp_2024_one:                                   # planted error: ignore 2024 immaturity
        mt.loc[mt["year"] == 2024, "weight"] = mt.loc[mt["year"] == 2024, "exposure_clean"]
    df = mt.merge(features, on="row_id", how="left", validate="one_to_one")
    feats = [c for c in features.columns if c != "row_id" and c not in drop_features]

    res = {"case": name}
    res["target_check_spread"], _ = target_check(mt)
    m_adj = adjust_claims(match_claims(claims, policies, "motor", cap=None), adj)
    fs = freq_sev_check(m_adj, policies)
    res["_freq_table"], res["_sev_table"] = fs["freq"], fs["sev"]

    for vy, tys in FOLDS:
        tr, va = df[df["year"].isin(tys)], df[df["year"] == vy]
        glm = BandedTweedieGLM(**(glm_kwargs or {})).fit(tr[feats], tr["target"] / tr["weight"], tr["weight"])
        pv = glm.predict_rate(va[feats]) * va["weight"].to_numpy()
        pt = glm.predict_rate(tr[feats]) * tr["weight"].to_numpy()
        av, at = va["target"].to_numpy(), tr["target"].to_numpy()
        base = av.sum() / va["weight"].sum() * va["weight"].to_numpy()
        res[f"D2_{vy}"] = d2_tweedie(av, pv, base)
        res[f"AE_{vy}"] = av.sum() / pv.sum()
        # training-year tilt: A/E by training year (a pooled model should fit each year if the target is consistent)
        yr = pd.DataFrame({"y": tr["year"].to_numpy(), "a": at, "p": pt}).groupby("y")[["a", "p"]].sum()
        res[f"train_year_tilt_{vy}"] = float(np.std(np.log(yr["a"] / yr["p"])))
        res[f"shape_valid_{vy}"], per = shape_error(av, pv, va[seg_cols])
        res[f"shape_train_{vy}"], _ = shape_error(at, pt, tr[seg_cols])
        res[f"worst_segment_{vy}"] = max(per, key=per.get)
    return res


def summarise(results):
    """Level and shape errors, changes against the baseline, and the attribution of each diagnostic."""
    t = pd.DataFrame(results).set_index("case")
    t["level_err"] = t[["AE_2023", "AE_2024"]].apply(lambda r: np.log(r).abs().mean(), axis=1) \
        + t[["train_year_tilt_2023", "train_year_tilt_2024"]].mean(axis=1)
    t["shape_err"] = t[["shape_valid_2023", "shape_valid_2024"]].mean(axis=1)
    b = t.loc["baseline"]
    t["d_level"] = t["level_err"] - b["level_err"]
    t["d_shape"] = t["shape_err"] - b["shape_err"]
    # attribution by each diagnostic
    t["diag1_target_check"] = np.where((t["target_check_spread"] - b["target_check_spread"]).abs() > 0.01, "target", "model")
    # diagnostic 2: largest relative change in any peril-year cell against the baseline
    for comp in ["freq", "sev"]:
        bt = b[f"_{comp}_table"]
        t[f"{comp}_change"] = [float((x / bt - 1).abs().max().max()) for x in t[f"_{comp}_table"]]
    t["diag2_freq_sev"] = np.where(t["sev_change"] > 0.01, "target (severity)",
                                   np.where(t["freq_change"] > 0.01, "target (frequency)", "model"))
    d23 = abs(np.log(t["AE_2023"] / b["AE_2023"]))
    d24 = abs(np.log(t["AE_2024"] / b["AE_2024"]))
    t["diag3_mature_year"] = np.where((d24 > 0.02) & (d23 < 0.01), "target (immaturity)",
                                      np.where((d24 > 0.02) | (d23 > 0.02), "target", "model"))
    over = (t["shape_valid_2024"] - b["shape_valid_2024"]) > 0.01
    in_train = (t["shape_train_2024"] - b["shape_train_2024"]) > 0.01
    t["diag4_train_vs_valid"] = np.where(over & ~in_train, "model (over-fit)",
                                         np.where(over, "model (structure)", "target"))
    t["signature_rule"] = np.where(t["d_level"] > t["d_shape"], "target", "model")
    return t.drop(columns=["_freq_table", "_sev_table"])
