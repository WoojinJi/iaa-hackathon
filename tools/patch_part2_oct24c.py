"""Patch for Part 2 (Oct 24): E12 candidate C in the pipeline. Run once from the repository root, after
tools/patch_part2_oct24.py and tools/patch_part2_oct23b.py:   python tools/patch_part2_oct24c.py

  1 peril_models: a peril modelled by its own GLM (own features, optional pairs, own ridge strength); the line's main
    GLM then models the remaining perils. Part 2 buildings: flood (12 features + Part 1's five flood pairs, alpha 0.5)
    + other perils (alpha 10) + fire at the developed rate (peril_split). Values fixed from notebook 23.
  2 validation also reports the tail condition on the modelled part ("low b", "top b"; rule of Oct 24) when a peril is
    priced at a flat rate.
Part 1 does not change. Every replacement checks that the old text occurs exactly once.
"""
from pathlib import Path

CONFIG_ADD = '''
# Oct 24 (E12 re-judged, notebook 23): buildings flood priced by its own GLM
PART2["peril_models"] = {"buildings": [{
    "peril": "flood", "alpha": 0.5,
    "features": ["flood_zone", "elevation_m", "distance_to_river_km", "rainfall_mm", "basement", "property_type",
                 "sum_insured", "building_age", "urban_density", "soil_type", "construction_type", "voluntary_excess"],
    "pairs": [["flood_zone", "sum_insured"], ["elevation_m", "flood_zone"], ["elevation_m", "sum_insured"],
              ["building_age", "flood_zone"], ["distance_to_river_km", "flood_zone"]]}]}
'''

EDITS = {
    "src/pipeline.py": [
        # 1a. per-peril targets and pairs in build_line
        ('''    missing = [c for c in feats if c not in tr.columns]
    assert not missing, f"features missing from the table: {missing}"''',
         '''    pms = cfg.get("peril_models", {}).get(line, [])
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
    assert not missing, f"features missing from the table: {missing}"'''),
        # 1b. add the peril GLMs to the predicted rate
        ('''    if cfg["model"][line] == "glm":
        g = BandedTweedieGLM(**cfg["glm"][line]).fit(tr[feats], tr.target / tr.weight, tr.weight)
        return g.predict_rate(X_new[feats]), f"GLM, k={g.k_:.4f}"''',
         '''    if cfg["model"][line] == "glm":
        g = BandedTweedieGLM(**cfg["glm"][line]).fit(tr[feats], tr.target / tr.weight, tr.weight)
        rate, info = g.predict_rate(X_new[feats]), f"GLM, k={g.k_:.4f}"
        for spec in cfg.get("peril_models", {}).get(line, []):
            f = [c for c in spec["features"] if c in tr.columns] + [pair_name(*x) for x in spec.get("pairs", [])]
            col = f"target_{spec['peril']}"
            gp = BandedTweedieGLM(**dict(cfg["glm"][line], alpha=spec["alpha"])).fit(tr[f], tr[col] / tr.weight, tr.weight)
            rate = rate + gp.predict_rate(X_new[f])
            info += f" + {spec['peril']} GLM ({len(f)} features, alpha {spec['alpha']}, k={gp.k_:.4f})"
        return rate, info'''),
        # 2. validation: tail condition on the modelled part
        ('''            pv = (rate + d.get("sep_rate", 0.0)) * va.weight.to_numpy()
            if "target_all" in va:              # separately priced peril: evaluate on all perils
                va = va.assign(target=va.target_all)''',
         '''            pv = (rate + d.get("sep_rate", 0.0)) * va.weight.to_numpy()
            tails_b = None
            if "target_all" in va:              # flat-rated peril: tails on the modelled part (rule of Oct 24)
                act_mod = (va["target_modelled"] if "target_modelled" in va else va["target"]).to_numpy()
                pm = rate * va.weight.to_numpy()
                q = pd.qcut(pd.Series(pm / va.weight.to_numpy()).rank(method="first"), 10, labels=False).to_numpy()
                tails_b = (act_mod[q == 0].sum() / pm[q == 0].sum(), act_mod[q == 9].sum() / pm[q == 9].sum())
                va = va.assign(target=va.target_all)'''),
        ('''            row = {"line": line, "year": vy, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}''',
         '''            row = {"line": line, "year": vy, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}
            if tails_b:
                row["low b"], row["top b"] = tails_b'''),
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
assert "peril_split" in s, "run tools/patch_part2_oct23b.py first"
assert "peril_models" not in s, "src/config.py already has this patch"
f.write_text(s.replace("\nMARKETS = {", CONFIG_ADD + "\nMARKETS = {"))
print("patched src/config.py")
print("next:  python -m src.pipeline --market part2 --validate")
