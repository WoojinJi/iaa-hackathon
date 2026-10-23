"""Experiment E11: frequency x severity GLMs in place of the single Tweedie GLM (motor, buildings).

Open since Oct 19 (AI_USE_LOG 44): NCB lowers frequency but raises claim size, so two GLMs (how often x how
much) may price better than one Tweedie GLM. It was deprioritised by reasoning, never tested. Here it is
tested under the rule fixed on Oct 19 for a GLM setting: adopted if the average validation D2 rises by
>= 0.0005 and the safest / riskiest decile A/E are no more than 0.1 further from 1 than v11's, in both years.

Same as v11: target (2025 level, caps, completeness weight), features (incl. buildings interactions),
bands from the config, large-loss loading. Ridge strength: chosen separately for each part on the last
training year from a fixed list (v11's alpha is on the Tweedie cost scale and over-shrinks both parts). The two parts:
  frequency  claims with net cost > 0 per row (2025 level, capped), Poisson GLM, weight = exposure x completeness
  severity   that row's target / its claim count, Gamma GLM, weight = claim count (rows with a claim only)
  rate       frequency x severity, then one factor so training predictions sum to training actuals
Still transparent: two rating tables instead of one.

Usage (repository root, terminal):
  python tools/exp_freqsev.py --validate                         # motor and buildings, about 5-15 minutes
  python tools/exp_freqsev.py --directions                       # how each feature moves frequency vs severity
  python tools/exp_freqsev.py --out submissions/v12_freqsev.csv --compare submissions/v11.csv
      (only if the rule passes; lines that fail keep the v11 model)
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import PART1  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.glm import BandedTweedieGLM  # noqa: E402
from src.pipeline import apply_loading, build_line, compare, log, predict_rate  # noqa: E402
from src.target import adjust_claims, load_claims, match_claims  # noqa: E402


def add_counts(d, cfg, line, claims):
    """Claims with net cost > 0 per row, on the same claim basis as the target (2025 level, capped)."""
    mc = adjust_claims(match_claims(claims, d["p"], line, True, cap=None), cfg["adj"][line])
    n = mc[mc.net_adj > 0].groupby("row_id").size()
    d["tr"]["n_claims"] = d["tr"].row_id.map(n).fillna(0).astype(float)
    return d


ALPHAS = [0.5, 0.1, 0.03, 0.01, 0.003, 0.001]   # candidate ridge strengths, fixed before any result


def _glm(cfg, line, power, alpha):
    g = cfg["glm"][line]
    return BandedTweedieGLM(power=power, alpha=alpha, n_bands=g["n_bands"], drop=g["drop"], balance=True)


def _choose_alpha(cfg, line, power, inner, hold, feats, y, w):
    """Ridge strength for one part, chosen on the last training year by that part's own deviance.
    v11's alpha was tuned for the Tweedie cost scale; frequency (Poisson) and severity (Gamma) deviances
    are on a much smaller scale, so the same alpha flattens them (found on Oct 22)."""
    from sklearn.metrics import mean_gamma_deviance, mean_poisson_deviance
    dev = mean_poisson_deviance if power == 1.0 else mean_gamma_deviance
    scores = {}
    for a in ALPHAS:
        m = _glm(cfg, line, power, a).fit(inner[feats], y(inner), w(inner))
        scores[a] = dev(y(hold), np.maximum(m.predict_rate(hold[feats]), 1e-9), sample_weight=w(hold))
    return min(scores, key=scores.get)


def fit_parts(cfg, line, tr, feats):
    last = tr.year.max()
    inner, hold = tr[tr.year < last], tr[tr.year == last]
    yf, wf = (lambda d: d.n_claims / d.weight), (lambda d: d.weight)
    ys, ws = (lambda d: d.target / d.n_claims), (lambda d: d.n_claims)
    pos_i, pos_h = inner[inner.n_claims > 0], hold[hold.n_claims > 0]
    af = _choose_alpha(cfg, line, 1.0, inner, hold, feats, yf, wf)
    as_ = _choose_alpha(cfg, line, 2.0, pos_i, pos_h, feats, ys, ws)
    f = _glm(cfg, line, 1.0, af).fit(tr[feats], yf(tr), wf(tr))
    pos = tr[tr.n_claims > 0]
    s = _glm(cfg, line, 2.0, as_).fit(pos[feats], ys(pos), ws(pos))
    log(f"{line}: alpha chosen on {last}: frequency {af}, severity {as_}")
    return f, s


def freqsev_rate(cfg, line, tr, new, feats):
    f, s = fit_parts(cfg, line, tr, feats)
    k = tr.target.sum() / (f.predict_rate(tr[feats]) * s.predict_rate(tr[feats]) * tr.weight).sum()
    return f.predict_rate(new[feats]) * s.predict_rate(new[feats]) * k, k


def directions(cfg, lines):
    """(1) Per feature: spread of frequency and severity relativities and whether they move together
    (correlation across the feature's levels, weighted by level size). (2) Within customers: given the
    features, is a claim on a row with 2+ claims larger or smaller than on a row with one claim?"""
    claims = load_claims(cfg["data_dir"])
    for line in lines:
        d = add_counts(build_line(line, cfg, claims), cfg, line, claims)
        tr, feats = d["tr"], d["feats"]
        f, s = fit_parts(cfg, line, tr, feats)
        Bf, Bs = f._band(tr[feats]), s._band(tr[feats])
        pf, ps = f.predict_rate(tr[feats]), s.predict_rate(tr[feats])
        rows = []
        for c in feats:
            g = pd.DataFrame({"lvl": Bf[c].to_numpy(), "f": np.log(pf), "s": np.log(ps), "w": tr.weight.to_numpy()})
            # partial effect of the feature: average log prediction by level, centred
            m = g.groupby("lvl").apply(lambda x: pd.Series({"f": np.average(x.f, weights=x.w),
                                                            "s": np.average(x.s, weights=x.w),
                                                            "w": x.w.sum()}), include_groups=False)
            if len(m) < 2:
                continue
            fr, sr = np.exp(m.f - np.average(m.f, weights=m.w)), np.exp(m.s - np.average(m.s, weights=m.w))
            cov = np.cov(m.f, m.s, aweights=m.w)
            corr = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1]) if cov[0, 0] > 0 and cov[1, 1] > 0 else np.nan
            rows.append({"feature": c, "freq range": f"{fr.min():.2f}-{fr.max():.2f}",
                         "sev range": f"{sr.min():.2f}-{sr.max():.2f}",
                         "freq spread": fr.max() / fr.min(), "sev spread": sr.max() / sr.min(),
                         "together (corr)": corr})
        t = pd.DataFrame(rows).sort_values("freq spread", ascending=False)
        t["direction"] = np.where(t["together (corr)"] > 0.3, "same", np.where(t["together (corr)"] < -0.3, "OPPOSITE", "mixed"))
        print(f"\n{line}: how each feature moves frequency vs severity (averages by level; all training years)")
        print("  Tweedie (v11) forces 'same'; features marked OPPOSITE are where freq x sev can help.")
        print(t.round(3).to_string(index=False))
        pos = tr[tr.n_claims > 0].assign(sev=lambda x: x.target / x.n_claims)
        pos["ratio"] = pos.sev / s.predict_rate(pos[feats])
        grp = pos.assign(n=np.where(pos.n_claims >= 2, "2+", "1")).groupby("n").apply(
            lambda x: pd.Series({"rows": len(x), "actual / predicted severity": np.average(x.ratio, weights=x.n_claims)}),
            include_groups=False)
        print(f"\n{line}: within customers (same features): claim size on rows with 1 vs 2+ claims")
        print(grp.round(3).to_string())
        r = grp["actual / predicted severity"]
        if "2+" in r.index and "1" in r.index:
            print(f"  2+ vs 1: {r['2+'] / r['1'] - 1:+.1%}  (positive: frequent claimers also claim larger; "
                  f"near 0: independence holds)")


def metrics(va, rate):
    r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
    lf = r["lift"]["A/E"]
    return {"D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}


def validate(cfg, lines):
    claims = load_claims(cfg["data_dir"])
    rows = []
    for line in lines:
        t0 = time.time()
        d = add_counts(build_line(line, cfg, claims), cfg, line, claims)
        for vy, tys in cfg["folds"]:
            tr, va = d["tr"][d["tr"].year.isin(tys)], d["tr"][d["tr"].year == vy]
            base, _ = predict_rate(line, cfg, tr, va, d["feats"])
            fs, k = freqsev_rate(cfg, line, tr, va, d["feats"])
            rows.append({"line": line, "year": vy, "model": "v11 Tweedie GLM", **metrics(va, base)})
            rows.append({"line": line, "year": vy, "model": "freq x sev GLM", **metrics(va, fs)})
            log(f"{line} {vy}: D2 v11 {rows[-2]['D2']:.4f}  freq x sev {rows[-1]['D2']:.4f}  (k {k:.3f}; "
                f"{time.time() - t0:.0f}s)")
    r = pd.DataFrame(rows)
    t = r.pivot_table(index=["line", "model"], columns="year", values=["D2", "A/E", "low", "top"])
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    t["D2_avg"] = t[["D2_2023", "D2_2024"]].mean(axis=1)
    print("\nOut-of-time validation (low / top = A/E of the safest / riskiest 10%)")
    print(t.round(4).to_string())
    print("\nRule (Oct 19, GLM setting): D2 +0.0005 and tails no more than 0.1 further from 1, both years")
    passed = []
    for line in lines:
        a, b = t.loc[(line, "v11 Tweedie GLM")], t.loc[(line, "freq x sev GLM")]
        gain = b.D2_avg - a.D2_avg
        tails = all(abs(b[f"{m}_{y}"] - 1) <= abs(a[f"{m}_{y}"] - 1) + 0.1 for y in [2023, 2024] for m in ["low", "top"])
        ok = gain >= 0.0005 and tails
        passed += [line] if ok else []
        print(f"  {line:9s} D2 {gain:+.4f}  tails {'ok' if tails else 'FAIL'}  -> {'ADOPT' if ok else 'not adopted'}")
    return passed


def run(cfg, out, fs_lines):
    claims = load_claims(cfg["data_dir"])
    sample = pd.read_parquet(Path(cfg["data_dir"]) / "sample_submission.parquet")
    id_col, val_col = sample.columns[:2]
    parts = []
    for line in cfg["lines"]:
        d = build_line(line, cfg, claims)
        if line in fs_lines:
            d = add_counts(d, cfg, line, claims)
            rate, _ = freqsev_rate(cfg, line, d["tr"], d["te"], d["feats"])
            info = "freq x sev GLM"
        else:
            rate, info = predict_rate(line, cfg, d["tr"], d["te"], d["feats"])
        rate, load_info = apply_loading(line, cfg, rate, d["tr"], d, claims)
        expo = d["te"].exposure_clean.to_numpy()
        pred = np.maximum(rate * expo, 0)
        log(f"{line}: {info}; {load_info}; total {pred.sum():,.0f}")
        parts.append(pd.DataFrame({id_col: d["te"].row_id.to_numpy(), val_col: pred}))
    sub = sample[[id_col]].merge(pd.concat(parts), on=id_col, how="left")
    assert len(sub) == len(sample) and sub[val_col].notna().all()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(out, index=False)
    log(f"saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--directions", action="store_true", help="frequency vs severity direction by feature")
    ap.add_argument("--out")
    ap.add_argument("--compare")
    ap.add_argument("--lines", nargs="+", default=["motor", "buildings"])
    ap.add_argument("--data")
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    cfg = copy.deepcopy(PART1)
    if a.data:
        cfg["data_dir"] = Path(a.data)
    if a.directions:
        directions(cfg, a.lines)
        return
    if a.validate:
        validate(cfg, a.lines)
        return
    if not a.out:
        ap.error("give --validate or --out")
    log("validating first: only lines that pass the rule use freq x sev")
    fs_lines = validate(cfg, a.lines)
    run(cfg, a.out, fs_lines)
    if a.compare:
        compare(a.compare, a.out)


if __name__ == "__main__":
    main()
