"""Experiment E7: interactions in the buildings GLM (recover part of the GBM's gain, keep rating tables).

The GBM beats the buildings GLM by about +0.009 D² but over-prices the safest 10% (DECISIONS.md Oct 19).
Part of its gain should come from interactions a main-effects GLM cannot represent. Here:
  1. rank feature pairs by how often a GBM of depth-2 trees splits on one feature right after the other
     (sum of split gain of child nodes, by parent-child pair);
  2. for the top 6 pairs, add each as one coarse cross-classified factor (5 x 5 bands) to the GLM and keep it
     if it raises D² on the held-out LAST TRAINING YEAR by >= 0.0003 (selection never sees the validation year);
  3. fit the GLM with the kept pairs and evaluate on the validation year.
Done per fold (2023 on 2021-22; 2024 on 2021-23) and once on all years (holdout 2024) for the final list.

Rule fixed before results (Oct 21): the interactions are adopted if the average validation D² rises by
>= 0.0005 over the main-effects GLM and the lowest / highest decile A/E stay within 0.1 of it in both years.
Reported: the share of the GBM's gain (+0.009) recovered.

Usage (repository root):  python tools/exp_interactions.py [--line buildings] [--data DIR]
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import GBM_BASE, PART1  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.glm import BandedTweedieGLM  # noqa: E402
from src.pipeline import build_line, log, prep2  # noqa: E402
from src.target import load_claims  # noqa: E402

TOP, MIN_GAIN, BANDS = 6, 0.0003, 5


def metrics(va, rate):
    r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
    lf = r["lift"]["A/E"]
    return {"D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}


def rank_pairs(tr, feats, top=TOP):
    X, _ = prep2(tr[feats])
    p = dict(GBM_BASE, num_leaves=4, max_depth=2, learning_rate=0.05, min_data_in_leaf=1000, verbose=-1)
    b = lgb.train(p, lgb.Dataset(X, tr.target / tr.weight, weight=tr.weight), num_boost_round=400)
    t = b.trees_to_dataframe()
    split = t[t.split_feature.notna()][["tree_index", "node_index", "split_feature"]]
    child = t[t.split_feature.notna() & t.parent_index.notna()][["tree_index", "parent_index", "split_feature", "split_gain"]]
    m = child.merge(split.rename(columns={"node_index": "parent_index", "split_feature": "parent"}),
                    on=["tree_index", "parent_index"])
    m = m[m.parent != m.split_feature]
    m["pair"] = [tuple(sorted(x)) for x in zip(m.parent, m.split_feature)]
    g = m.groupby("pair").split_gain.sum().sort_values(ascending=False)
    return list(g.index[:top]), g


def coarse(s_fit, s):
    """Coarse bands learned on s_fit: 5 quantile bands for numeric, levels for categorical."""
    if pd.api.types.is_numeric_dtype(s_fit) and not pd.api.types.is_bool_dtype(s_fit) and s_fit.nunique() > BANDS:
        edges = np.unique(s_fit.quantile(np.linspace(0, 1, BANDS + 1)).to_numpy()[1:-1])
        out = pd.Series(np.searchsorted(edges, s.to_numpy(), side="right"), index=s.index).astype(str)
        return out.where(s.notna(), "na")
    return s.astype("string").fillna("na").astype(str)


def with_pairs(fit, frames, pairs):
    """Add one cross-classified column per pair; bands learned on `fit`, applied to every frame."""
    out = []
    for f in frames:
        f = f.copy()
        for a, b in pairs:
            f[f"{a}*{b}"] = coarse(fit[a], f[a]) + "|" + coarse(fit[b], f[b])
        out.append(f)
    return out


def glm_rate(cfg, line, trn, new, feats):
    g = BandedTweedieGLM(**cfg["glm"][line]).fit(trn[feats], trn.target / trn.weight, trn.weight)
    return g.predict_rate(new[feats])


def select(cfg, line, trn, feats):
    """Rank pairs on the training years before the last; keep those that help on the last training year."""
    last = trn.year.max()
    inner, hold = trn[trn.year < last], trn[trn.year == last]
    pairs, gains = rank_pairs(inner, feats)
    base = metrics(hold, glm_rate(cfg, line, inner, hold, feats))["D2"]
    kept, rows = [], []
    for pr in pairs:
        i2, h2 = with_pairs(inner, [inner, hold], [pr])
        d2 = metrics(h2, glm_rate(cfg, line, i2, h2, feats + [f"{pr[0]}*{pr[1]}"]))["D2"]
        rows.append({"pair": f"{pr[0]} x {pr[1]}", "gbm_gain": gains[pr], "holdout_D2_change": d2 - base})
        if d2 - base >= MIN_GAIN:
            kept.append(pr)
    return kept, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", default="buildings")
    ap.add_argument("--data")
    a = ap.parse_args()
    cfg = copy.deepcopy(PART1)
    if a.data:
        cfg["data_dir"] = Path(a.data)
    line = a.line
    cfg["model"][line] = "glm"
    d = build_line(line, cfg, load_claims(cfg["data_dir"]))
    tr, feats = d["tr"], d["feats"]
    res = []
    for vy, tys in cfg["folds"]:
        t0 = time.time()
        trn, val = tr[tr.year.isin(tys)], tr[tr.year == vy]
        kept, table = select(cfg, line, trn, feats)
        print(f"\nfold {vy}: pairs ranked on {sorted(set(tys) - {max(tys)})}, kept on {max(tys)}")
        print(table.round(5).to_string(index=False))
        res.append({"year": vy, "model": "GLM main effects", **metrics(val, glm_rate(cfg, line, trn, val, feats))})
        t2, v2 = with_pairs(trn, [trn, val], kept)
        res.append({"year": vy, "model": "GLM + interactions",
                    **metrics(v2, glm_rate(cfg, line, t2, v2, feats + [f"{x}*{y}" for x, y in kept])),
                    "pairs": "; ".join(f"{x} x {y}" for x, y in kept)})
        log(f"fold {vy}: {len(kept)} pairs kept ({time.time() - t0:.0f}s)")
    r = pd.DataFrame(res)
    t = r.pivot(index="model", columns="year", values=["D2", "A/E", "low", "top"])
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    t["D2_avg"] = t[["D2_2023", "D2_2024"]].mean(axis=1)
    print(f"\n{line}: validation")
    print(t.round(4).to_string())
    b, x = t.loc["GLM main effects"], t.loc["GLM + interactions"]
    gain = x.D2_avg - b.D2_avg
    tails = all(abs(x[f"{m}_{y}"] - 1) <= abs(b[f"{m}_{y}"] - 1) + 0.1 for y in [2023, 2024] for m in ["low", "top"])
    print(f"gain {gain:+.4f} (GBM about +0.009: {gain / 0.009:.0%} recovered); tails {'ok' if tails else 'FAIL'} "
          f"-> {'ADOPT' if gain >= 0.0005 and tails else 'not adopted'}")
    kept, table = select(cfg, line, tr, feats)
    print("\nfinal list (ranked on 2021-23, kept on 2024):", [f"{x} x {y}" for x, y in kept])
    print(table.round(5).to_string(index=False))


if __name__ == "__main__":
    main()
