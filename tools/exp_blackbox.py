"""Experiment E9: a "black box max" model next to our model (v11), for the data-tracking comparison.

Purpose (team decision, Oct 22): show, with numbers, what a maximum-accuracy black box gains and what it
costs. Written BEFORE the Part 2 data is seen; the expected result is recorded in DECISIONS.md:
  "The black box scores higher, but when it is wrong we cannot say why, and its errors fall on the
   safest customers."

What is the same as v11 (so the comparison isolates the model):
  - target: 2025-level net cost, completeness weight, caps (src/target.py, config PART1)
  - large-loss loading (motor Pareto by risk, buildings observed flat)
  - average weather per address; claim history; leakage still excluded (customer_service_contacts,
    renewal_decision): leakage is not accuracy
What changes ("max accuracy"):
  - LightGBM in every line, high capacity (127 leaves, 200 rows per leaf, light L2), 3 seeds
  - every feature our stability checks removed is put back (previous_insurer, occupation, region,
    home-type features in motor, discount_applied); relative premium in every line
  - no hand-built interactions (the trees find their own)

Outputs
  --out FILE        submission file (an EXPERIMENT: never the final selection)
  --validate        out-of-time folds 2023 / 2024 for the black box AND v11, side by side:
                    D2, overall A/E, lowest / highest decile A/E, and seed spread (how much one
                    customer's prediction moves between seeds: a tracking / stability measure)

Usage (repository root; terminal, or a notebook after a kernel restart):
  python tools/exp_blackbox.py --out submissions/blackbox_experiment.csv --compare submissions/v11.csv
  python tools/exp_blackbox.py --validate
  python tools/exp_blackbox.py --validate --lines buildings        # one line only (faster)
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import GBM_BASE, PART1  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.pipeline import build_line, compare, fit_gbm, log, predict_rate, prep2, run  # noqa: E402
from src.target import load_claims  # noqa: E402

BB_PARAMS = dict(GBM_BASE, num_leaves=127, min_data_in_leaf=200, lambda_l2=1.0, learning_rate=0.05,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                 min_data_per_group=200, cat_smooth=10, max_cat_threshold=32)


def blackbox_config(base=PART1):
    cfg = copy.deepcopy(base)
    cfg["name"] = "blackbox_max"
    cfg["model"] = {line: "gbm" for line in cfg["lines"]}
    cfg["gbm"] = {line: dict(BB_PARAMS) for line in cfg["lines"]}
    cfg["drop"] = {line: ["customer_tenure"] for line in cfg["lines"]}   # exact duplicate of renewal_count
    cfg["premium_lines"] = list(cfg["lines"])
    cfg["interactions"] = {}
    return cfg


def metrics(va, rate):
    r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
    lf = r["lift"]["A/E"]
    return {"D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}


def gbm_by_seed(tr, new, feats, params, seeds):
    preds = []
    for s in seeds:
        m, cats, k, n = fit_gbm(tr, feats, dict(params, seed=s))
        Xn, _ = prep2(new[feats], cats)
        preds.append(m.predict(Xn) * k)
    return np.vstack(preds)


def validate_both(lines, data_dir=None):
    cfgs = {"v11 (ours)": copy.deepcopy(PART1), "black box max": blackbox_config()}
    if data_dir:
        for c in cfgs.values():
            c["data_dir"] = Path(data_dir)
    claims = load_claims(cfgs["v11 (ours)"]["data_dir"])
    rows = []
    for line in lines:
        for name, cfg in cfgs.items():
            t0 = time.time()
            d = build_line(line, cfg, claims)
            for vy, tys in cfg["folds"]:
                tr, va = d["tr"][d["tr"].year.isin(tys)], d["tr"][d["tr"].year == vy]
                if cfg["model"][line] == "gbm":
                    P = gbm_by_seed(tr, va, d["feats"], cfg["gbm"][line], cfg["gbm_seeds"])
                    rate = P.mean(axis=0)
                    spread = float(np.average(P.std(axis=0) / np.maximum(rate, 1e-9), weights=va.weight))
                else:
                    rate, _ = predict_rate(line, cfg, tr, va, d["feats"])
                    spread = 0.0                                  # the GLM has no seed
                rows.append({"line": line, "model": name, "year": vy, **metrics(va, rate), "seed_spread": spread})
                log(f"{line} {name} {vy}: D2 {rows[-1]['D2']:.4f}  low {rows[-1]['low']:.3f}  "
                    f"top {rows[-1]['top']:.3f}  ({time.time() - t0:.0f}s)")
    r = pd.DataFrame(rows)
    out = r.pivot_table(index=["line", "model"], columns="year",
                        values=["D2", "A/E", "low", "top", "seed_spread"])
    out.columns = [f"{m}_{y}" for m, y in out.columns]
    out["D2_avg"] = out[[c for c in out.columns if c.startswith("D2_")]].mean(axis=1)
    print("\nOut-of-time validation (low / top = A/E of the safest / riskiest 10%; 1 = right price,"
          " below 1 = over-priced)")
    print(out.round(4).to_string())
    print("\nBlack box minus v11 (D2 average) and the worst tail distance from 1:")
    for line in lines:
        a, b = out.loc[(line, "v11 (ours)")], out.loc[(line, "black box max")]
        tail = lambda x: max(abs(x[c] - 1) for c in x.index if c.startswith(("low_", "top_")))
        print(f"  {line:9s} D2 {b.D2_avg - a.D2_avg:+.4f}   worst tail: v11 {tail(a):.3f} vs black box {tail(b):.3f}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the black-box submission here (experiment only)")
    ap.add_argument("--compare", help="compare with this submission (e.g. submissions/v11.csv)")
    ap.add_argument("--validate", action="store_true", help="out-of-time folds, black box vs v11")
    ap.add_argument("--lines", nargs="+", default=list(PART1["lines"]))
    ap.add_argument("--data", help="data directory (default: the config's)")
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    if a.validate:
        validate_both(a.lines, a.data)
        return
    cfg = blackbox_config()
    if a.data:
        cfg["data_dir"] = Path(a.data)
    run(cfg, a.out)
    if a.out and a.compare:
        compare(a.compare, a.out)


if __name__ == "__main__":
    main()
