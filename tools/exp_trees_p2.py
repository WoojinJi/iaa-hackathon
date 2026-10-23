"""Experiment E13 (screening): shallow trees on frequency and on severity, by line and peril (Part 2, emerging).

Purpose: find where the GLM's additive structure misses something, as candidates for the GLM (as E7 did in
Part 1: trees as detectors, never as the pricing model). Nothing here changes a submission.

For each line and peril (perils with at least MIN_FREQ claims in 2023 for frequency, MIN_SEV for severity):
  frequency  rows = all policy rows; label = claims with net cost > 0 per unit of weight (Poisson LightGBM)
  severity   rows = claims with net cost > 0 only; label = 2025-level net cost per claim, capped (Gamma LightGBM)
  Two models, both fitted on 2023 and checked on 2024:
    depth 1 (main effects only: each tree splits once)    vs    depth 2 (pairs of features can interact)
  2024 D2 for both, after scaling predictions to the 2024 total (so the comparison is about shape, not level).
  "interaction gain" = D2(depth 2) - D2(depth 1) on 2024: positive = interactions that hold out of time.
  Top pairs: in each depth-2 tree, the root feature and the feature split under it, with the gain of that split,
  summed over trees (share of all depth-2 split gain).
  Top main effects: total split gain per feature in the depth-1 model.
Screening rule (set before running): a peril's pairs go forward to a GLM test only if the 2024 interaction gain is
at least +0.002 (frequency) or +0.005 (severity, fewer and noisier rows). The GLM test itself uses the Part 1 rule.

Usage (repository root):  python tools/exp_trees_p2.py            (about 5-15 minutes)
"""
import copy
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_gamma_deviance, mean_poisson_deviance

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import PART2  # noqa: E402
from src.pipeline import build_line, log, prep2  # noqa: E402
from src.target import adjust_claims, load_claims, match_claims  # noqa: E402

MIN_FREQ, MIN_SEV = 40, 100
ROUNDS, LR = 300, 0.05


def params(obj, depth, min_leaf):
    return dict(objective=obj, learning_rate=LR, num_leaves=2 ** depth, max_depth=depth, min_data_in_leaf=min_leaf,
                lambda_l2=10.0, feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1, verbose=-1, seed=7,
                min_data_per_group=100, cat_smooth=20, max_cat_threshold=16)


def d2(y, mu, w, kind):
    mu = np.maximum(mu * (np.sum(y * w) / np.sum(mu * w)), 1e-9)          # scale to the 2024 total
    base = np.full_like(mu, np.sum(y * w) / np.sum(w))
    f = mean_poisson_deviance if kind == "freq" else mean_gamma_deviance
    return 1 - f(y, mu, sample_weight=w) / f(y, base, sample_weight=w)


def pairs_from(model, top=5):
    t = model.booster_.trees_to_dataframe() if hasattr(model, "booster_") else model.trees_to_dataframe()
    s = t[t.split_feature.notna()]
    root = s[s.node_depth == 1].set_index(["tree_index", "node_index"]).split_feature
    kid = s[s.node_depth == 2]
    out = {}
    for r in kid.itertuples():
        a = root.get((r.tree_index, r.parent_index))
        if a is None or a == r.split_feature:
            continue
        k = tuple(sorted((a, r.split_feature)))
        out[k] = out.get(k, 0.0) + r.split_gain
    tot = s[s.node_depth == 2].split_gain.sum()
    ranked = sorted(out.items(), key=lambda x: -x[1])[:top]
    return "; ".join(f"{a}*{b} ({g / tot:.0%})" for (a, b), g in ranked) if tot > 0 else ""


def mains_from(model, top=6):
    t = model.trees_to_dataframe()
    g = t[t.split_feature.notna()].groupby("split_feature").split_gain.sum().sort_values(ascending=False)
    return "; ".join(f"{f} ({v / g.sum():.0%})" for f, v in g.head(top).items())


def fit(X, y, w, obj, depth, min_leaf):
    return lgb.train(params(obj, depth, min_leaf), lgb.Dataset(X, y, weight=w), num_boost_round=ROUNDS)


def screen(kind, X23, y23, w23, X24, y24, w24, min_leaf):
    obj = "poisson" if kind == "freq" else "gamma"
    m1 = fit(X23, y23, w23, obj, 1, min_leaf)
    m2 = fit(X23, y23, w23, obj, 2, min_leaf)
    a, b = d2(y24, m1.predict(X24), w24, kind), d2(y24, m2.predict(X24), w24, kind)
    return {"2024 D2 depth1": a, "2024 D2 depth2": b, "interaction gain": b - a,
            "top pairs": pairs_from(m2), "top main effects": mains_from(m1)}


def main():
    cfg = copy.deepcopy(PART2)
    cfg["peril_split"] = {}                       # every peril, including fire
    claims = load_claims(cfg["data_dir"])
    rows = []
    for line in cfg["lines"]:
        t0 = time.time()
        d = build_line(line, cfg, claims)
        tr, feats = d["tr"], [f for f in d["feats"]]
        X, cats = prep2(tr[feats])
        m = adjust_claims(match_claims(claims, d["p"], line, True, cap=None), cfg["adj"][line])
        m = m[m.net_adj > 0]
        y23, y24 = (tr.year == 2023).to_numpy(), (tr.year == 2024).to_numpy()
        for peril in sorted(m.peril.unique()):
            mp = m[m.peril == peril]
            n = tr.row_id.map(mp.groupby("row_id").size()).fillna(0).to_numpy()
            n23, n24 = int(n[y23].sum()), int(n[y24].sum())
            if n23 >= MIN_FREQ and n24 >= MIN_FREQ / 2:
                w = tr.weight.to_numpy()
                r = screen("freq", X[y23], n[y23] / w[y23], w[y23], X[y24], n[y24] / w[y24], w[y24], min_leaf=500)
                rows.append({"line": line, "peril": peril, "part": "frequency", "claims 2023": n23, "claims 2024": n24, **r})
            sev = mp.merge(tr[["row_id", "year"]], on="row_id")
            s23, s24 = sev[sev.year == 2023], sev[sev.year == 2024]
            if len(s23) >= MIN_SEV and len(s24) >= MIN_SEV / 2:
                idx = tr.reset_index(drop=True).reset_index().set_index("row_id")["index"]
                Xs23, Xs24 = X.iloc[idx[s23.row_id].to_numpy()], X.iloc[idx[s24.row_id].to_numpy()]
                r = screen("sev", Xs23, s23.net_adj.to_numpy(), np.ones(len(s23)), Xs24, s24.net_adj.to_numpy(),
                           np.ones(len(s24)), min_leaf=max(20, len(s23) // 25))
                rows.append({"line": line, "peril": peril, "part": "severity", "claims 2023": len(s23),
                             "claims 2024": len(s24), **r})
        log(f"{line} done ({time.time() - t0:.0f}s)")
    R = pd.DataFrame(rows)
    R["goes to GLM test"] = np.where(R.part == "frequency", R["interaction gain"] >= 0.002, R["interaction gain"] >= 0.005)
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print("\n======== screening (fit 2023, check 2024); D2 after scaling to the 2024 total")
    print(R[["line", "peril", "part", "claims 2023", "claims 2024", "2024 D2 depth1", "2024 D2 depth2",
             "interaction gain", "goes to GLM test"]].round(4).to_string(index=False))
    print("\n======== top pairs (depth 2) and main effects (depth 1)")
    for _, r in R.iterrows():
        print(f"\n[{r['line']} / {r['peril']} / {r['part']}]  pairs: {r['top pairs']}\n    main effects: {r['top main effects']}")
    out = Path("results/trees_p2.csv")
    out.parent.mkdir(exist_ok=True)
    R.to_csv(out, index=False)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
