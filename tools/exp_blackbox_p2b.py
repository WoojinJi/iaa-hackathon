"""Experiment E9-P2b: the black box with the same data as ours (developed + emerging training rows). Benchmark only.

E9-P2 (Oct 23) trained the black box on emerging data only, while v3 (Oct 24, E17) learns relativities from the
developed market too. A fair comparison needs the same data, so here the black box is LightGBM (E9 settings) fitted
on developed 2021-24 + emerging training rows with a "market" factor, every feature the two markets share, no peril
split; its level is set on the emerging training rows (one factor), as ours is.

Outputs
  --validate   fit (developed + emerging 2023) -> validate emerging 2024, all perils: ours (current PART2 = v3) vs the
               black box on emerging only (E9-P2) vs the black box on combined data; D2, A/E, lowest / highest decile,
               new-business A/E, seed spread; pooled D2.
  --out FILE   submission from the combined black box (experiment; never the final selection).
Usage (repository root):
  python tools/exp_blackbox_p2b.py --validate            # 10-30 minutes (LightGBM on about one million rows)
  python tools/exp_blackbox_p2b.py --out submissions/p2_blackbox_combined_experiment.csv --compare submissions/p2_v3_developed.csv
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exp_blackbox_p2 as E  # noqa: E402  (also patches the pipeline's GBM fit for one-year folds)
import src.pipeline as P  # noqa: E402
from src.config import PART1, PART2  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.target import load_claims  # noqa: E402
import src.target as T  # noqa: E402

_DEV = {}


def dev_table(line):
    """Developed training rows on the emerging basis (age bands), all perils (the black box has no peril split)."""
    if line not in _DEV:
        c1 = load_claims(PART1["data_dir"])
        d1 = P.build_line(line, PART1, c1)
        t = d1["tr"].merge(d1["p"][["row_id", "policy_id"]], on="row_id", how="left")
        age, band = P.AGE_COLS[line]
        if age not in t:
            t = t.merge(d1["p"][["row_id", age]], on="row_id", how="left")
        t[band] = pd.cut(t[age], P.AGE_BANDS[0], labels=P.AGE_BANDS[1]).astype(str)
        _DEV[line] = t
    return _DEV[line]


def fit_combined(em, dev, feats, params, seed):
    f = [c for c in feats if c in dev.columns]
    cols = f + ["target", "weight", "policy_id"]
    both = pd.concat([dev[cols].assign(market="developed", policy_id=lambda x: "D" + x.policy_id.astype(str)),
                      em[cols].assign(market="emerging", policy_id=lambda x: "E" + x.policy_id.astype(str))],
                     ignore_index=True)
    m, cats, _, n = E.fit_gbm_grouped(both, f + ["market"], dict(params, seed=seed))
    Xe, _ = P.prep2(em[f].assign(market="emerging"), cats)
    lvl = em.target.sum() / (m.predict(Xe) * em.weight).sum()
    return lambda X: m.predict(P.prep2(X[f].assign(market="emerging"), cats)[0]) * lvl, len(f), n


def bb_rates(em, dev, X, feats, cfg, line):
    out = []
    for s in cfg["gbm_seeds"]:
        pr, nf, nt = fit_combined(em, dev, feats, cfg["gbm"][line], s)
        out.append(pr(X))
        P.log(f"{line} combined black box seed {s}: {nf} features, {nt} trees")
    return np.vstack(out)


def validate(lines, data_dir=None):
    ours, bb = copy.deepcopy(PART2), E.blackbox_config()
    T.AMOUNTS_NET, T.ROW_COMPLETENESS = bool(ours.get("amounts_net")), bool(ours.get("row_completeness"))  # as pipeline.validate
    if data_dir:
        ours["data_dir"] = bb["data_dir"] = Path(data_dir)
    claims = load_claims(ours["data_dir"])
    rows, pooled = [], {}
    for line in lines:
        dev = dev_table(line)
        for name in ["ours (current PART2)", "black box, emerging only", "black box, combined"]:
            t0 = time.time()
            cfg = ours if name.startswith("ours") else bb
            d = P.build_line(line, cfg, claims)
            tr0 = d["tr"].merge(d["p"][["row_id", "policy_id"]], on="row_id")
            vy, tys = cfg["folds"][0]
            tr, va = tr0[tr0.year.isin(tys)], tr0[tr0.year == vy]
            if name.startswith("ours"):
                rate, _ = P.predict_rate(line, cfg, tr, va, d["feats"])
                spread = 0.0
            elif name.endswith("emerging only"):
                Pm = E.by_seed(tr, va, d["feats"], cfg["gbm"][line], cfg["gbm_seeds"])
                rate = Pm.mean(axis=0)
                spread = float(np.average(Pm.std(axis=0) / np.maximum(rate, 1e-9), weights=va.weight))
            else:
                Pm = bb_rates(tr, dev, va, d["feats"], cfg, line)
                rate = Pm.mean(axis=0)
                spread = float(np.average(Pm.std(axis=0) / np.maximum(rate, 1e-9), weights=va.weight))
            rate = rate + d.get("sep_rate", 0.0)
            act = (va.target_all if "target_all" in va else va.target).to_numpy()
            w = va.weight.to_numpy()
            pv = rate * w
            r = evaluate(pd.Series(act), pv, pd.Series(w), show=False)
            nb = va.new_business.astype(bool).to_numpy()
            lf = r["lift"]["A/E"]
            rows.append({"line": line, "model": name, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1],
                         "A/E new": act[nb].sum() / pv[nb].sum(), "seed spread": spread})
            pooled.setdefault(name, []).append(pd.DataFrame({"a": act, "p": pv, "w": w}))
            P.log(f"{line} {name}: D2 {r['D2']:.4f} ({time.time() - t0:.0f}s)")
    for name, parts in pooled.items():
        a = pd.concat(parts)
        r = evaluate(a.a, a.p, a.w, show=False)
        rows.append({"line": "ALL (pooled)", "model": name, "D2": r["D2"], "A/E": r["A/E"]})
    pd.set_option("display.width", 200)
    print("\n======== fit 2023 (+ developed 2021-24 for v3 and the combined black box) -> validate 2024, all perils")
    print(pd.DataFrame(rows).round(4).to_string(index=False))


def run(out, data_dir=None):
    cfg = E.blackbox_config()
    T.AMOUNTS_NET, T.ROW_COMPLETENESS = bool(cfg.get("amounts_net")), bool(cfg.get("row_completeness"))  # as pipeline.run
    if data_dir:
        cfg["data_dir"] = Path(data_dir)
    claims = load_claims(cfg["data_dir"])
    sp = Path(cfg["data_dir"])
    sample = (pd.read_parquet(sp / "sample_submission.parquet") if (sp / "sample_submission.parquet").exists()
              else pd.read_csv(sp / "sample_submission.csv", dtype=str))
    id_col, val_col = sample.columns[:2]
    parts = []
    for line in cfg["lines"]:
        d = P.build_line(line, cfg, claims)
        tr = d["tr"].merge(d["p"][["row_id", "policy_id"]], on="row_id")
        rate = bb_rates(tr, dev_table(line), d["te"], d["feats"], cfg, line).mean(axis=0)
        rate, info = P.apply_loading(line, cfg, rate, d["tr"], d, claims)
        expo = d["te"].exposure_clean.to_numpy()
        pred = np.maximum(rate * expo, 0)
        P.log(f"{line}: {info}; mean rate {np.average(rate, weights=expo):.2f}")
        parts.append(pd.DataFrame({id_col: d["te"].row_id.to_numpy(), val_col: pred}))
    sub = sample[[id_col]].merge(pd.concat(parts), on=id_col, how="left")
    assert len(sub) == len(sample) and sub[val_col].notna().all()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(out, index=False)
    P.log(f"saved {out}")


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
    run(a.out, a.data)
    if a.compare:
        P.compare(a.compare, a.out)


if __name__ == "__main__":
    main()
