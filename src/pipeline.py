"""End-to-end pipeline: data -> 2025-level target -> model per line -> loading -> submission file.

Every number comes from a market configuration (src/config.py), so Part 2 runs the same code with its own
configuration. The steps reproduce the adopted model (v9), previously spread over notebook cells
(11_setup, 14_v8, 20_v9):

  target    build_model_target (trends, reform, frequency shifts, completeness weight, cap)
  features  build_features (average weather) + claim history known by 1 January + relative premium
  model     banded ridge Tweedie GLM with balance factor (motor, buildings); LightGBM, 3 seeds (contents)
  loading   motor: Pareto tail, in proportion to the predicted rate; buildings: observed, flat
  output    prediction = max(rate x exposure, 0), in the order of sample_submission

Usage (from the repository root):
  python -m src.pipeline --out submissions/v9_pipeline.csv --compare submissions/v9.csv
  python -m src.pipeline --validate                    # out-of-time folds, no submission
  python -m src.pipeline --out submissions/v11.csv --no-interactions   # main effects only (= v10)
"""
import argparse
import copy
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .clean import fix_sum_insured
from .config import MARKETS, PART1
from .evaluate import evaluate
from .features import build_features
from .glm import BandedTweedieGLM
from .history import claim_history
from .interactions import add_pairs, pair_name
from .loading import expected_excess, pareto_loading
from .target import adjust_claims, build_model_target, load_claims, load_policies, match_claims

HIST = ["hist_1y", "hist_2y"]


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# ------------------------------------------------------------------ features
def hist_levels(n):
    """Counts -> '0', '1', '2+'; unknown history stays missing (its own level in the GLM)."""
    return pd.Series(np.select([n == 0, n == 1, n >= 2], ["0", "1", "2+"], default=None), index=n.index,
                     dtype="object").where(n.notna())


def add_history(F, p_rows, p_all_same_line, claims, data_start=None, cols=HIST):
    h = claim_history(p_rows, p_all_same_line, claims,
                      **({} if data_start is None else {"data_start": data_start}))
    h["hist_1y"] = hist_levels(h.pol_claims_1y)
    h["hist_2y"] = hist_levels(h.pol_claims_2y)
    out = F.merge(h[["row_id"] + list(cols)], on="row_id", how="left", validate="one_to_one")
    assert len(out) == len(F)
    return out


def rel_premium(d, by="year"):
    """Premium per exposure-year divided by the average of its group (exposure-weighted).
    by="year": policy year (v8, v9). by="month": policy-start month, so a rate change within a year
    (the checks found a +50% step in premium per year from mid-2021) does not show up as risk.
    by="annual" (Part 2): written_premium is the full annual premium whatever the row length (Oct 23),
    so it is divided by the policy year's average premium, not by exposure."""
    if by == "annual":
        return d.written_premium / d.year.map(d.written_premium.groupby(d.year).mean())
    pp = d.written_premium / d.exposure_clean
    key = d.year if by == "year" else d.period_start.dt.to_period("M")
    avg = d.written_premium.groupby(key).sum() / d.exposure_clean.groupby(key).sum()
    return pp / key.map(avg)


def developed_peril_rate(line, peril):
    """Uncapped cost per exposure of one peril in the developed market (Part 1 data), 2021-24 at 2025 level."""
    p1, c1 = load_policies(line, "train", PART1["data_dir"]), load_claims(PART1["data_dir"])
    m1 = adjust_claims(match_claims(c1, p1, line, True, cap=None), PART1["adj"][line])
    return float(m1.loc[m1.peril == peril, "net_adj_uncapped"].sum() / p1.exposure_clean.sum())


AGE_BANDS = ([0, 24, 34, 49, 64, 200], ["17-24", "25-34", "35-49", "50-64", "65+"])
AGE_COLS = {"motor": ("driver_age", "driver_age_band"), "buildings": ("policyholder_age", "policyholder_age_band"),
            "contents": ("policyholder_age", "policyholder_age_band")}
_DEV = {}


def developed_table(line, cfg):
    """Developed-market training table (Part 1 target and adjustments) on the emerging basis: age bands, and the same
    perils removed (flat-rated) or split out (own GLM) as in the emerging table. Cached per line."""
    if line in _DEV:
        return _DEV[line]
    c1 = load_claims(PART1["data_dir"])
    d1 = build_line(line, PART1, c1)
    t = d1["tr"].copy()
    age, band = AGE_COLS[line]
    if age not in t:
        t = t.merge(d1["p"][["row_id", age]], on="row_id", how="left")
    t[band] = pd.cut(t[age], AGE_BANDS[0], labels=AGE_BANDS[1]).astype(str)
    m1 = adjust_claims(match_claims(c1, d1["p"], line, True, cap=None), PART1["adj"][line])

    def peril(p_):
        return t.row_id.map(m1[m1.peril == p_].groupby("row_id").net_adj.sum()).fillna(0.0)
    fs = cfg.get("peril_split", {}).get(line)
    if fs:
        t["target"] = (t.target - peril(fs["peril"])).clip(lower=0.0)
    for spec in cfg.get("peril_models", {}).get(line, []):
        col = f"target_{spec['peril']}"
        t[col] = peril(spec["peril"])
        t["target"] = (t.target - t[col]).clip(lower=0.0)
    _DEV[line] = t
    log(f"{line}: developed training table {len(t):,} rows")
    return t


def feature_order(line, p, cfg):
    """Feature columns in the order of the actual-weather feature table (as in the notebooks; LightGBM's
    feature sampling depends on column order). Built on a few rows only."""
    cols = list(build_features(line, "train", data_dir=cfg["data_dir"], policies=p.head(200)).columns)
    return [c for c in cols if c != "row_id" and c not in cfg["drop"][line]] + list(cfg.get("hist", HIST))


# --------------------------------------------------------------------- tables
def build_line(line, cfg, claims):
    p, pt = load_policies(line, "train", cfg["data_dir"]), load_policies(line, "test", cfg["data_dir"])
    cc = cfg.get("construction_codes")
    if cc and "construction_type" in p:
        p = p.assign(construction_type=p.construction_type.map(cc).fillna(p.construction_type))
        pt = pt.assign(construction_type=pt.construction_type.map(cc).fillna(pt.construction_type))
    if cfg.get("fix_sum_insured") and "sum_insured" in p:
        p, pt, n = fix_sum_insured(p, pt)
        log(f"{line}: sum_insured x1000 entries divided by 1000: train {n[0]}, test {n[1]}")
    mt, comp, observed_loading = build_model_target(claims, p, line, adj=cfg["adj"][line],
                                                    completeness_method=cfg["completeness_method"],
                                                    valuation_date=cfg["valuation_date"], years=cfg["years"])
    sep_rate = 0.0
    fs = cfg.get("peril_split", {}).get(line)
    if fs:                                      # one peril priced separately (Part 2: buildings fire)
        ms = adjust_claims(match_claims(claims, p, line, True, cap=None), cfg["adj"][line])
        sep = ms[ms.peril == fs["peril"]].groupby("row_id").net_adj.sum()
        mt = mt.assign(target_all=mt.target, target=mt.target - mt.row_id.map(sep).fillna(0.0))
        sep_rate = developed_peril_rate(line, fs["peril"]) if fs["rate"] == "developed" else float(fs["rate"])
        log(f"{line}: {fs['peril']} priced separately at {sep_rate:.2f} per exposure ({fs['rate']})")
    wm = cfg["weather_mode"]
    hk = dict(data_start=cfg.get("data_start"), cols=cfg.get("hist", HIST))
    F = add_history(build_features(line, "train", cfg["data_dir"], policies=p, weather_mode=wm), p, [p, pt], claims, **hk)
    Ft = add_history(build_features(line, "test", cfg["data_dir"], policies=pt, weather_mode=wm), pt, [p, pt], claims, **hk)
    tr = mt.merge(F, on="row_id", how="left", validate="one_to_one") \
           .merge(p[["row_id", "written_premium", "period_start"]], on="row_id", how="left", validate="one_to_one")
    te = pt[["row_id", "exposure_clean", "written_premium", "period_start"]].assign(year=2025) \
        .merge(Ft, on="row_id", how="left", validate="one_to_one")
    by = cfg.get("premium_norm", "year")
    tr["prem_rel"], te["prem_rel"] = rel_premium(tr, by), rel_premium(te, by)
    feats = feature_order(line, p, cfg)
    if line in cfg["premium_lines"]:
        feats = feats + ["prem_rel"]
    pairs = [tuple(x) for x in cfg.get("interactions", {}).get(line, [])]
    if pairs:                                   # bands learned on the training table
        tr, te = add_pairs(tr, [tr, te], pairs)
        feats = feats + [pair_name(a, b) for a, b in pairs]
    pms = cfg.get("peril_models", {}).get(line, [])
    if pms:                                     # perils with their own GLM (Part 2: buildings flood)
        mpx = adjust_claims(match_claims(claims, p, line, True, cap=None), cfg["adj"][line])
        tr["target_modelled"] = tr["target"]    # all modelled perils (excludes a flat-rated peril)
        for spec in pms:
            col = f"target_{spec['peril']}"
            tr[col] = tr.row_id.map(mpx[mpx.peril == spec["peril"]].groupby("row_id").net_adj.sum()).fillna(0.0)
            tr["target"] = (tr["target"] - tr[col]).clip(lower=0.0)   # float rounding only
            if spec.get("pairs"):
                tr, te = add_pairs(tr, [tr, te], [tuple(x) for x in spec["pairs"]])
        log(f"{line}: own GLM for {[s['peril'] for s in pms]}; main GLM on the other perils")
    missing = [c for c in feats if c not in tr.columns]
    assert not missing, f"features missing from the table: {missing}"
    return {"p": p, "pt": pt, "tr": tr, "te": te, "feats": feats, "comp": comp,
            "observed_loading": observed_loading, "sep_rate": sep_rate}


# ---------------------------------------------------------------------- models
def prep2(X, cats=None):
    X = X.copy()
    if cats is None:
        cats = {c: sorted(X[c].dropna().astype(str).unique()) for c in X.columns
                if not pd.api.types.is_numeric_dtype(X[c]) and not pd.api.types.is_bool_dtype(X[c])}
    for c, levels in cats.items():
        s = X[c].astype("string")
        X[c] = pd.Categorical(s.where(s.isin(levels)), categories=levels)
    for c in X.columns:
        if pd.api.types.is_bool_dtype(X[c]):
            X[c] = X[c].astype(int)
    return X, cats


def fit_gbm(tr, feats, params, patience=300):
    """Number of trees chosen on the last training year (x1.1), then refit on all training years;
    k scales training predictions to the training actuals."""
    last = tr.year.max()
    inner, hold = tr[tr.year < last], tr[tr.year == last]
    Xi, cats = prep2(inner[feats]); Xh, _ = prep2(hold[feats], cats)
    di = lgb.Dataset(Xi, inner.target / inner.weight, weight=inner.weight)
    dh = lgb.Dataset(Xh, hold.target / hold.weight, weight=hold.weight, reference=di)
    b = lgb.train(params, di, num_boost_round=5000, valid_sets=[dh],
                  callbacks=[lgb.early_stopping(patience, verbose=False)])
    n_trees = max(int(b.best_iteration * 1.1), 1)
    Xt, cats = prep2(tr[feats])
    model = lgb.train(params, lgb.Dataset(Xt, tr.target / tr.weight, weight=tr.weight), num_boost_round=n_trees)
    k = tr.target.sum() / (model.predict(Xt) * tr.weight).sum()
    return model, cats, k, n_trees


def predict_rate(line, cfg, tr, X_new, feats):
    """Fit on tr, return the predicted cost per unit of weight for X_new (before loading)."""
    if cfg["model"][line] == "glm":
        mode = cfg.get("developed_training", {}).get(line)
        if mode:                                # E17: relativities from the developed market (level from emerging)
            dev = developed_table(line, cfg)
            f = [c for c in feats if c in dev.columns]
            kw = PART1["glm"][line]
            if mode == "developed":
                g = BandedTweedieGLM(**kw).fit(dev[f], dev.target / dev.weight, dev.weight)
                pr = lambda X: g.predict_rate(X[f])
            else:
                both = pd.concat([dev[f + ["target", "weight"]].assign(market="developed"),
                                  tr[f + ["target", "weight"]].assign(market="emerging")], ignore_index=True)
                g = BandedTweedieGLM(**kw).fit(both[f + ["market"]], both.target / both.weight, both.weight)
                pr = lambda X: g.predict_rate(X[f].assign(market="emerging"))
            lvl = tr.target.sum() / (pr(tr) * tr.weight).sum()
            rate, info = pr(X_new) * lvl, f"GLM on {mode} data ({len(f)} features), emerging level x{lvl:.4f}"
        else:
            g = BandedTweedieGLM(**cfg["glm"][line]).fit(tr[feats], tr.target / tr.weight, tr.weight)
            rate, info = g.predict_rate(X_new[feats]), f"GLM, k={g.k_:.4f}"
        for spec in cfg.get("peril_models", {}).get(line, []):
            col = f"target_{spec['peril']}"
            kwp = dict(cfg["glm"][line], alpha=spec["alpha"])
            if spec.get("train") == "combined":   # E17: both markets, pairs banded on the combined data
                dev = developed_table(line, cfg)
                raw = [c for c in spec["features"] if c in tr.columns and c in dev.columns]
                prs = [tuple(x) for x in spec.get("pairs", [])]
                pc = [pair_name(*x) for x in prs]
                both = pd.concat([dev[raw + [col, "weight"]].assign(market="developed"),
                                  tr[raw + [col, "weight"]].assign(market="emerging")], ignore_index=True)
                both, trp, Xp = add_pairs(both, [both, tr[raw + [col, "weight"]], X_new[raw]], prs)
                f = raw + pc
                gp = BandedTweedieGLM(**kwp).fit(both[f + ["market"]], both[col] / both.weight, both.weight)
                lvp = trp[col].sum() / (gp.predict_rate(trp[f].assign(market="emerging")) * trp.weight).sum()
                rate = rate + gp.predict_rate(Xp[f].assign(market="emerging")) * lvp
                info += f" + {spec['peril']} GLM on combined data ({len(f)} features, alpha {spec['alpha']}, level x{lvp:.4f})"
                continue
            f = [c for c in spec["features"] if c in tr.columns] + [pair_name(*x) for x in spec.get("pairs", [])]
            gp = BandedTweedieGLM(**kwp).fit(tr[f], tr[col] / tr.weight, tr.weight)
            rate = rate + gp.predict_rate(X_new[f])
            info += f" + {spec['peril']} GLM ({len(f)} features, alpha {spec['alpha']}, k={gp.k_:.4f})"
        return rate, info
    rate = np.zeros(len(X_new))
    for s in cfg["gbm_seeds"]:
        m, cats, k, n = fit_gbm(tr, feats, dict(cfg["gbm"][line], seed=s))
        Xn, _ = prep2(X_new[feats], cats)
        rate += m.predict(Xn) * k / len(cfg["gbm_seeds"])
    return rate, f"LightGBM, {len(cfg['gbm_seeds'])} seeds"


def apply_loading(line, cfg, rate, tr, d, claims):
    spec = cfg["loading"][line]
    if spec["method"] == "pareto":
        adj = cfg["adj"][line]
        mc = adjust_claims(match_claims(claims, d["p"], line, True, cap=None), adj)
        if spec.get("alpha"):   # Part 2: tail shape borrowed from the developed market, frequency from this one
            n = int((mc.net_adj_uncapped > spec["threshold"]).sum())
            used = n / tr.weight.sum() * expected_excess(spec["threshold"], adj["cap"], spec["alpha"])
            f = 1 + used / (tr.target.sum() / tr.weight.sum())
            return rate * f, (f"Pareto, alpha {spec['alpha']} borrowed: {n} claims above {spec['threshold']:,}, "
                              f"loading {used:.2f} -> factor {f:.4f}")
        fit = pareto_loading(mc.net_adj_uncapped, tr.weight.sum(), spec["threshold"], adj["cap"])
        used = spec.get("fixed") or fit["loading"]
        f = 1 + used / (tr.target.sum() / tr.weight.sum())
        info = (f"Pareto refit: alpha {fit['alpha']:.2f}, {fit['n_above']} claims above "
                f"{spec['threshold']:,}, loading {fit['loading']:.2f}; used {used:.2f} -> factor {f:.4f}")
        return rate * f, info
    if spec["method"] == "observed":
        return rate + d["observed_loading"], f"flat loading {d['observed_loading']:.2f}"
    return rate, "no loading"


# --------------------------------------------------------------------- runs
def run(cfg=PART1, out=None):
    claims = load_claims(cfg["data_dir"])
    sp = Path(cfg["data_dir"])
    sample = (pd.read_parquet(sp / "sample_submission.parquet") if (sp / "sample_submission.parquet").exists()
              else pd.read_csv(sp / "sample_submission.csv", dtype=str))
    id_col, val_col = sample.columns[:2]
    parts = []
    for line in cfg["lines"]:
        t0 = time.time()
        d = build_line(line, cfg, claims)
        rate, model_info = predict_rate(line, cfg, d["tr"], d["te"], d["feats"])
        rate, load_info = apply_loading(line, cfg, rate, d["tr"], d, claims)
        if d.get("sep_rate"):
            rate = rate + d["sep_rate"]
            load_info += f"; + separate peril rate {d['sep_rate']:.2f}"
        expo = d["te"].exposure_clean.to_numpy()
        pred = np.maximum(rate * expo, 0)
        log(f"{line}: {model_info}; {load_info}; mean rate {np.average(rate, weights=expo):.2f}; "
            f"total {pred.sum():,.0f}; completeness {d['comp'].round(3).to_dict()} ({time.time() - t0:.0f}s)")
        parts.append(pd.DataFrame({id_col: d["te"].row_id.to_numpy(), val_col: pred}))
    sub = sample[[id_col]].merge(pd.concat(parts), on=id_col, how="left")
    assert len(sub) == len(sample) and sub[val_col].notna().all(), "every sample row needs a prediction"
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        sub.to_csv(out, index=False)
        log(f"saved {out}")
    return sub


def validate(cfg=PART1, lines=None):
    """Out-of-time folds on the capped target (no loading), as in the notebooks."""
    claims = load_claims(cfg["data_dir"])
    rows, pooled = [], {}
    for line in lines or cfg["lines"]:
        d = build_line(line, cfg, claims)
        for vy, tys in cfg["folds"]:
            tr, va = d["tr"][d["tr"].year.isin(tys)], d["tr"][d["tr"].year == vy]
            rate, _ = predict_rate(line, cfg, tr, va, d["feats"])
            pv = (rate + d.get("sep_rate", 0.0)) * va.weight.to_numpy()
            tails_b = None
            if "target_all" in va:              # flat-rated peril: tails on the modelled part (rule of Oct 24)
                act_mod = (va["target_modelled"] if "target_modelled" in va else va["target"]).to_numpy()
                pm = rate * va.weight.to_numpy()
                q = pd.qcut(pd.Series(pm / va.weight.to_numpy()).rank(method="first"), 10, labels=False).to_numpy()
                tails_b = (act_mod[q == 0].sum() / pm[q == 0].sum(), act_mod[q == 9].sum() / pm[q == 9].sum())
                va = va.assign(target=va.target_all)
            r = evaluate(va.target, pv, va.weight, show=False)
            pooled.setdefault(vy, []).append(pd.DataFrame({"a": va.target.to_numpy(), "p": pv, "w": va.weight.to_numpy()}))
            lf = r["lift"]["A/E"]
            row = {"line": line, "year": vy, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}
            if tails_b:
                row["low b"], row["top b"] = tails_b
            if "new_business" in va:            # rule 2 (Oct 23): new business is 76% of the Part 2 test
                nb = va.new_business.astype(bool).to_numpy()
                act = va.target.to_numpy()
                row["A/E new"] = act[nb].sum() / pv[nb].sum() if nb.any() else np.nan
                row["A/E renewal"] = act[~nb].sum() / pv[~nb].sum() if (~nb).any() else np.nan
            rows.append(row)
            log(f"validate {line} {vy}: D2 {r['D2']:.4f}  A/E {r['A/E']:.3f}"
                + (f"  new {row['A/E new']:.3f}  renewal {row['A/E renewal']:.3f}" if "A/E new" in row else ""))
    for vy, parts in pooled.items():            # the leaderboard pools the lines
        a = pd.concat(parts)
        r = evaluate(a.a, a.p, a.w, show=False)
        rows.append({"line": "ALL (pooled)", "year": vy, "D2": r["D2"], "A/E": r["A/E"]})
        log(f"validate pooled {vy}: D2 {r['D2']:.4f}  A/E {r['A/E']:.3f}")
    return pd.DataFrame(rows)


def compare(a_path, b_path):
    a, b = pd.read_csv(a_path), pd.read_csv(b_path)
    id_col, val_col = a.columns[:2]
    m = a.merge(b, on=id_col, suffixes=("_a", "_b"))
    x, y = m[f"{val_col}_a"], m[f"{val_col}_b"]
    ratio = y / x.clip(lower=1e-9) - 1
    print(f"compare {Path(a_path).name} vs {Path(b_path).name}: rows {len(m):,} of {len(a):,}; "
          f"totals {x.sum():,.0f} vs {y.sum():,.0f} ({y.sum() / x.sum() - 1:+.3%}); "
          f"correlation {np.corrcoef(x, y)[0, 1]:.6f}; rows differing by > 1%: {(ratio.abs() > 0.01).mean():.2%}")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", choices=sorted(MARKETS), default="part1", help="market configuration")
    ap.add_argument("--out", help="write the submission here")
    ap.add_argument("--compare", help="compare the new file with this submission")
    ap.add_argument("--validate", action="store_true", help="run the out-of-time folds instead")
    ap.add_argument("--completeness", choices=["ref_year", "lynden_bell"], help="override the config")
    ap.add_argument("--data", help="data directory (default: the config's)")
    ap.add_argument("--lines", nargs="+", help="lines to validate (default: all)")
    ap.add_argument("--premium-norm", choices=["year", "month"], help="relative premium: by year or start month")
    ap.add_argument("--no-interactions", action="store_true", help="drop the GLM interactions from the config")
    a = ap.parse_args()
    cfg = copy.deepcopy(MARKETS[a.market])
    if a.data:
        cfg["data_dir"] = Path(a.data)
    if a.completeness:
        cfg["completeness_method"] = a.completeness
    if a.premium_norm:
        cfg["premium_norm"] = a.premium_norm
    if a.no_interactions:
        cfg["interactions"] = {}
    if a.validate:
        print(validate(cfg, a.lines).round(4).to_string(index=False))
        return
    run(cfg, a.out)
    if a.out and a.compare:
        compare(a.compare, a.out)


if __name__ == "__main__":
    main()
