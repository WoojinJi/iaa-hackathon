"""Experiment E8: blend the buildings GLM (with interactions, v11) with a regularised LightGBM.

Earlier (Oct 19) a GBM or blend replaced the plain GLM only if it gained >= 0.003 D² with tails within
0.1; buildings failed on the tails (safest decile over-priced). The GLM now has the flood interactions
(v11), so the blend may need less of the GBM. Here, per fold:
  1. fit the GLM (v11 features) and a regularised GBM (7 leaves, min 5,000 per leaf, L2 50; 3 seeds;
     main features only) on the training years before the last;
  2. choose the blend weight w in {0, 0.25, 0.5, 0.75, 1} by D² on the LAST TRAINING YEAR;
  3. refit both on all training years and evaluate (1 - w) GLM + w GBM on the validation year.

Rule fixed before results (Oct 21, same as Oct 19): the blend replaces the v11 buildings GLM if the average
validation D² rises by >= 0.003 and the lowest / highest decile A/E stay within 0.1 of the GLM's in both
years. GBM alone (w = 1) is shown for reference.

Usage: python tools/exp_blend.py   or, in a notebook:  %run /Users/woojinji/IAA/tools/exp_blend.py
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
from src.pipeline import build_line, fit_gbm, log, prep2  # noqa: E402
from src.target import load_claims  # noqa: E402

WEIGHTS = [0, 0.25, 0.5, 0.75, 1]
GBM_PARAMS = dict(GBM_BASE, num_leaves=7, min_data_in_leaf=5000, lambda_l2=50)


def metrics(va, rate):
    r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
    lf = r["lift"]["A/E"]
    return {"D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", default="buildings")
    ap.add_argument("--data")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    cfg = copy.deepcopy(PART1)
    if a.data:
        cfg["data_dir"] = Path(a.data)
    line, seeds = a.line, [42, 43, 44][:a.seeds]
    d = build_line(line, cfg, load_claims(cfg["data_dir"]))
    tr, feats = d["tr"], d["feats"]
    gfeats = [f for f in feats if "*" not in f]          # the GBM finds interactions itself

    def glm_rate(trn, new):
        g = BandedTweedieGLM(**cfg["glm"][line]).fit(trn[feats], trn.target / trn.weight, trn.weight)
        return g.predict_rate(new[feats])

    def gbm_rate(trn, new, n_trees=None):
        """Trees chosen inside fit_gbm (last year of trn held out); with a single training year, the
        number of trees found for the full fold is reused (n_trees, one per seed)."""
        out, used = np.zeros(len(new)), []
        for i, s in enumerate(seeds):
            p = dict(GBM_PARAMS, seed=s)
            if n_trees is None:
                m, cats, k, n = fit_gbm(trn, gfeats, p)
            else:
                X, cats = prep2(trn[gfeats]); n = n_trees[i]
                m = lgb.train(p, lgb.Dataset(X, trn.target / trn.weight, weight=trn.weight), num_boost_round=n)
                k = trn.target.sum() / (m.predict(X) * trn.weight).sum()
            Xn, _ = prep2(new[gfeats], cats)
            out += m.predict(Xn) * k / len(seeds); used.append(n)
        return out, used

    rows = []
    for vy, tys in cfg["folds"]:
        t0 = time.time()
        trn, val = tr[tr.year.isin(tys)], tr[tr.year == vy]
        last = max(tys)
        inner, hold = trn[trn.year < last], trn[trn.year == last]
        gv = glm_rate(trn, val)
        bv, n_fold = gbm_rate(trn, val)
        gh = glm_rate(inner, hold)
        bh, _ = gbm_rate(inner, hold, None if inner.year.nunique() > 1 else n_fold)
        scores = {w: metrics(hold, (1 - w) * gh + w * bh)["D2"] for w in WEIGHTS}
        w_star = max(scores, key=scores.get)
        print(f"\nfold {vy}: D2 on {last} by GBM weight " + "  ".join(f"{w}: {v:.4f}" for w, v in scores.items())
              + f"  -> w = {w_star}")
        for name, w in [("GLM + interactions (v11)", 0), (f"blend (chosen w)", w_star), ("GBM alone", 1)]:
            rows.append({"year": vy, "model": name, "w": w, **metrics(val, (1 - w) * gv + w * bv)})
        log(f"fold {vy} done ({time.time() - t0:.0f}s)")

    r = pd.DataFrame(rows)
    t = r.pivot(index="model", columns="year", values=["D2", "A/E", "low", "top", "w"])
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    t["D2_avg"] = t[["D2_2023", "D2_2024"]].mean(axis=1)
    print(f"\n{line}: validation")
    print(t.round(4).to_string())
    b = t.loc["GLM + interactions (v11)"]
    for name in ["blend (chosen w)", "GBM alone"]:
        x = t.loc[name]
        gain = x.D2_avg - b.D2_avg
        tails = all(abs(x[f"{m}_{y}"] - 1) <= abs(b[f"{m}_{y}"] - 1) + 0.1 for y in [2023, 2024] for m in ["low", "top"])
        print(f"{name:18s} gain {gain:+.4f}  tails {'ok' if tails else 'FAIL'}  -> "
              f"{'ADOPT' if gain >= 0.003 and tails and name.startswith('blend') else 'not adopted'}")


if __name__ == "__main__":
    main()
