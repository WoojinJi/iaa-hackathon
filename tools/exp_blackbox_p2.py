"""Experiment E9-P2: the "black box max" next to our model on the emerging market (benchmark, never a candidate).

Prediction written on Oct 22, before the Part 2 data (DECISIONS.md, REPORT_OUTLINE.md):
  "The black box scores higher, but when it is wrong we cannot say why, and its errors fall on the
   safest customers."
Part 2 adds a concrete test: the 2023 buildings fire cluster (DECISIONS Oct 23). We removed it by pricing fire
separately; a black box sees only the data.

Black box (same as E9 in Part 1): LightGBM in every line, 127 leaves, 200 rows per leaf, light L2, 3 seeds;
every non-leaking feature (occupation, region, previous insurer, discount, relative premium); no peril split,
no hand-built interactions. Same target, weights, caps and motor loading as ours.
Part 2 difference: one training year in the fold, so the number of trees is chosen on a 20% holdout of
policies inside the training data (grouped), then refit on all training rows.

Outputs (--validate): out-of-time fold (fit 2023, validate 2024) for ours (PART2) and the black box, all perils:
  D2, A/E, lowest / highest decile, new business A/E, seed spread; pooled D2 over the lines;
  buildings by predicted decile (A/E), and the black box's buildings prediction in the 2023 fire-cluster area
  (address-average hail days <= 16.25) against elsewhere, with the 2024 actual cost.

Usage (repository root):
  python tools/exp_blackbox_p2.py --validate                 # about 5-15 minutes
  python tools/exp_blackbox_p2.py --out submissions/p2_blackbox_experiment.csv --compare submissions/p2_v1.csv
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import GBM_BASE, PART2  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
import src.pipeline as P  # noqa: E402
from src.pipeline import build_line, compare, log, predict_rate, prep2, run  # noqa: E402
from src.target import load_claims  # noqa: E402

BB_PARAMS = dict(GBM_BASE, num_leaves=127, min_data_in_leaf=200, lambda_l2=1.0, learning_rate=0.05,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                 min_data_per_group=200, cat_smooth=10, max_cat_threshold=32)


def fit_gbm_grouped(tr, feats, params, patience=300):
    """Trees chosen on a 20% holdout of policies (x1.1), refit on all rows; k scales to training actuals."""
    groups = tr["policy_id"] if "policy_id" in tr else tr["row_id"]
    i, j = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=params.get("seed", 42)).split(tr, groups=groups))
    inner, hold = tr.iloc[i], tr.iloc[j]
    Xi, cats = prep2(inner[feats]); Xh, _ = prep2(hold[feats], cats)
    di = lgb.Dataset(Xi, inner.target / inner.weight, weight=inner.weight)
    dh = lgb.Dataset(Xh, hold.target / hold.weight, weight=hold.weight, reference=di)
    b = lgb.train(params, di, num_boost_round=5000, valid_sets=[dh], callbacks=[lgb.early_stopping(patience, verbose=False)])
    n_trees = max(int(b.best_iteration * 1.1), 1)
    Xt, cats = prep2(tr[feats])
    model = lgb.train(params, lgb.Dataset(Xt, tr.target / tr.weight, weight=tr.weight), num_boost_round=n_trees)
    k = tr.target.sum() / (model.predict(Xt) * tr.weight).sum()
    return model, cats, k, n_trees


P.fit_gbm = fit_gbm_grouped          # the pipeline's GBM path uses this for Part 2 (one training year per fold)


def blackbox_config(base=PART2):
    cfg = copy.deepcopy(base)
    cfg["name"] = "blackbox_max_p2"
    cfg["model"] = {line: "gbm" for line in cfg["lines"]}
    cfg["gbm"] = {line: dict(BB_PARAMS) for line in cfg["lines"]}
    cfg["drop"] = {line: ["customer_tenure"] for line in cfg["lines"]}
    cfg["premium_lines"] = list(cfg["lines"])
    cfg["interactions"] = {}
    cfg["peril_split"] = {}
    cfg["loading"]["buildings"] = {"method": "observed"}
    return cfg


def by_seed(tr, new, feats, params, seeds):
    out = []
    for s in seeds:
        m, cats, k, _ = fit_gbm_grouped(tr, feats, dict(params, seed=s))
        Xn, _ = prep2(new[feats], cats)
        out.append(m.predict(Xn) * k)
    return np.vstack(out)


def validate(lines, data_dir=None):
    cfgs = {"ours (p2_v1)": copy.deepcopy(PART2), "black box max": blackbox_config()}
    if data_dir:
        for c in cfgs.values():
            c["data_dir"] = Path(data_dir)
    claims = load_claims(cfgs["ours (p2_v1)"]["data_dir"])
    rows, pooled, keep = [], {}, {}
    for line in lines:
        for name, cfg in cfgs.items():
            t0 = time.time()
            d = build_line(line, cfg, claims)
            tr0 = d["tr"].merge(d["p"][["row_id", "policy_id"]], on="row_id")
            vy, tys = cfg["folds"][0]
            tr, va = tr0[tr0.year.isin(tys)], tr0[tr0.year == vy]
            if cfg["model"][line] == "gbm":
                Pm = by_seed(tr, va, d["feats"], cfg["gbm"][line], cfg["gbm_seeds"])
                rate = Pm.mean(axis=0)
                spread = float(np.average(Pm.std(axis=0) / np.maximum(rate, 1e-9), weights=va.weight))
            else:
                rate, _ = predict_rate(line, cfg, tr, va, d["feats"])
                spread = 0.0
            rate = rate + d.get("sep_rate", 0.0)
            act = (va.target_all if "target_all" in va else va.target).to_numpy()
            pv = rate * va.weight.to_numpy()
            r = evaluate(pd.Series(act), pv, va.weight.reset_index(drop=True), show=False)
            nb = va.new_business.astype(bool).to_numpy()
            lf = r["lift"]["A/E"]
            rows.append({"line": line, "model": name, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0],
                         "top": lf.iloc[-1], "A/E new": act[nb].sum() / pv[nb].sum(), "seed spread": spread})
            pooled.setdefault(name, []).append(pd.DataFrame({"a": act, "p": pv, "w": va.weight.to_numpy()}))
            if line == "buildings":
                keep[name] = va.assign(pred=pv, actual=act)
            log(f"{line} {name}: D2 {r['D2']:.4f} low {lf.iloc[0]:.3f} top {lf.iloc[-1]:.3f} ({time.time() - t0:.0f}s)")
    for name, parts in pooled.items():
        a = pd.concat(parts)
        r = evaluate(a.a, a.p, a.w, show=False)
        rows.append({"line": "ALL (pooled)", "model": name, "D2": r["D2"], "A/E": r["A/E"]})
    pd.set_option("display.width", 200)
    print("\n======== fit 2023 -> validate 2024, all perils (low / top = A/E of safest / riskiest 10%)")
    print(pd.DataFrame(rows).round(4).to_string(index=False))

    if keep:
        print("\n======== buildings 2024, A/E by each model's own predicted decile")
        dec = {}
        for name, v in keep.items():
            q = pd.qcut((v.pred / v.weight).rank(method="first"), 10, labels=range(1, 11))
            g = v.groupby(q, observed=True)[["actual", "pred"]].sum()
            dec[name] = g.actual / g.pred
        print(pd.DataFrame(dec).round(2).to_string())
        if "hail_days" in keep["black box max"]:
            bb = keep["black box max"]
            area = bb.hail_days <= 16.25
            print("\n======== 2023 fire-cluster area (address-average hail days <= 16.25) vs elsewhere, buildings")
            for name, v in keep.items():
                ar = v.hail_days <= 16.25
                print(f"  {name:15s} predicted rate in area / elsewhere: "
                      f"{(v.pred[ar].sum() / v.weight[ar].sum()) / (v.pred[~ar].sum() / v.weight[~ar].sum()):.3f}; "
                      f"2024 actual in area / elsewhere: "
                      f"{(v.actual[ar].sum() / v.weight[ar].sum()) / (v.actual[~ar].sum() / v.weight[~ar].sum()):.3f}")
            print(f"  (area share of 2024 weight: {bb.weight[area].sum() / bb.weight.sum():.1%})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--compare")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--lines", nargs="+", default=list(PART2["lines"]))
    ap.add_argument("--data")
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    if a.validate:
        validate(a.lines, a.data)
        return
    cfg = blackbox_config()
    if a.data:
        cfg["data_dir"] = Path(a.data)
    run(cfg, a.out)
    if a.out and a.compare:
        compare(a.compare, a.out)


if __name__ == "__main__":
    main()
