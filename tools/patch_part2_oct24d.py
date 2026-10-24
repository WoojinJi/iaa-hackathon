"""Patch for Part 2 (Oct 24): developed data as training data (E17), v3. Run once from the repository root, after
tools/patch_part2_oct24c.py:   python tools/patch_part2_oct24d.py

  developed_training[line] = "developed": the line's GLM is fitted on the developed market (2021-24, Part 1 target and
      adjustments, common features), and its level is set on the emerging training rows (one factor).
  developed_training[line] = "combined": fitted on developed + emerging training rows with a "market" factor; level set
      on the emerging training rows.
  peril_models[...]["train"] = "combined": that peril's GLM (with its pairs, bands learned on the combined data) is
      fitted on both markets the same way.
  construction_codes: emerging local codes mapped to the developed names (BRK -> brick, ...), so both markets share levels.
Developed ages are banded like the emerging age bands. The developed table drops the same flat-rated and separately
modelled perils as the emerging one. v3 (E17, notebook 23): motor "developed", contents "combined", buildings flood
"combined" (other perils emerging only, fire flat). Part 1 does not change.
Every replacement checks that the old text occurs exactly once.
"""
from pathlib import Path

CONFIG_ADD = '''
# Oct 24 (E17, notebook 23): developed data as training data (v3)
PART2["construction_codes"] = {"BRK": "brick", "STN": "stone", "WOD": "timber", "MIX": "non-standard"}
PART2["developed_training"] = {"motor": "developed", "contents": "combined"}
PART2["peril_models"]["buildings"][0]["train"] = "combined"
'''

DEV_FN = '''AGE_BANDS = ([0, 24, 34, 49, 64, 200], ["17-24", "25-34", "35-49", "50-64", "65+"])
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


def feature_order(line, p, cfg):'''

EDITS = {
    "src/pipeline.py": [
        ('''def feature_order(line, p, cfg):''', DEV_FN),
        # construction codes mapped right after loading
        ('''    if cfg.get("fix_sum_insured") and "sum_insured" in p:''',
         '''    cc = cfg.get("construction_codes")
    if cc and "construction_type" in p:
        p = p.assign(construction_type=p.construction_type.map(cc).fillna(p.construction_type))
        pt = pt.assign(construction_type=pt.construction_type.map(cc).fillna(pt.construction_type))
    if cfg.get("fix_sum_insured") and "sum_insured" in p:'''),
        # main GLM on developed / combined data
        ('''    if cfg["model"][line] == "glm":
        g = BandedTweedieGLM(**cfg["glm"][line]).fit(tr[feats], tr.target / tr.weight, tr.weight)
        rate, info = g.predict_rate(X_new[feats]), f"GLM, k={g.k_:.4f}"''',
         '''    if cfg["model"][line] == "glm":
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
            rate, info = g.predict_rate(X_new[feats]), f"GLM, k={g.k_:.4f}"'''),
        # peril GLM on combined data
        ('''        for spec in cfg.get("peril_models", {}).get(line, []):
            f = [c for c in spec["features"] if c in tr.columns] + [pair_name(*x) for x in spec.get("pairs", [])]
            col = f"target_{spec['peril']}"
            gp = BandedTweedieGLM(**dict(cfg["glm"][line], alpha=spec["alpha"])).fit(tr[f], tr[col] / tr.weight, tr.weight)
            rate = rate + gp.predict_rate(X_new[f])
            info += f" + {spec['peril']} GLM ({len(f)} features, alpha {spec['alpha']}, k={gp.k_:.4f})"''',
         '''        for spec in cfg.get("peril_models", {}).get(line, []):
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
            info += f" + {spec['peril']} GLM ({len(f)} features, alpha {spec['alpha']}, k={gp.k_:.4f})"'''),
    ],
}

for path, edits in EDITS.items():
    f = Path(path)
    s = f.read_text()
    for old, new in edits:
        n = s.count(old)
        assert n == 1, f"{path}: expected the old text once, found {n}:\n{old[:200]}"
        s = s.replace(old, new)
    f.write_text(s)
    print(f"patched {path}")

f = Path("src/config.py")
s = f.read_text()
assert "peril_models" in s, "run tools/patch_part2_oct24c.py first"
assert "developed_training" not in s, "src/config.py already has this patch"
f.write_text(s.replace("\nMARKETS = {", CONFIG_ADD + "\nMARKETS = {"))
print("patched src/config.py")
print("next:  python -m src.pipeline --market part2 --validate")
