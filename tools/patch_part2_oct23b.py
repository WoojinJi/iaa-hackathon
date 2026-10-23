"""Patch for Part 2, first submission (Oct 23 afternoon). Run once from the repository root, after
tools/patch_part2_oct24.py:   python tools/patch_part2_oct23b.py

Puts the decisions of Oct 23 (afternoon, notebook 21_part2_baseline) into the pipeline. Part 1 does not change.
  1 ridge strength per line chosen by 5-fold CV inside the training year (grouped by policy):
    motor 10, buildings 10 (perils other than fire), contents 2. Part 1's values over-fitted (D2 <= 0).
  2 buildings fire priced separately at one rate per exposure: the developed market's 2021-24 average at 2025
    level (uncapped). Emerging 2023 fire was 2.5x that (a regional cluster that did not recur in 2024; 2024
    matched developed). The GLM models the other perils; the buildings large-loss loading is then not needed.
  3 validation: buildings evaluated on all perils (GLM + fire rate); a pooled D2 over the three lines, the
    basis for the expected leaderboard range (the score pools the lines).
Every replacement checks that the old text occurs exactly once, so the patch stops if a file differs.
"""
from pathlib import Path

CONFIG_ADD = '''
# Oct 23 afternoon (notebook 21_part2_baseline): ridge by CV inside the training year; buildings fire separate
PART2["glm"]["motor"]["alpha"] = 10
PART2["glm"]["buildings"]["alpha"] = 10
PART2["glm"]["contents"]["alpha"] = 2
PART2["peril_split"] = {"buildings": {"peril": "fire", "rate": "developed"}}   # or a number per exposure
PART2["loading"]["buildings"] = {"method": "none"}                              # fire rate is uncapped
'''

EDITS = {
    "src/pipeline.py": [
        ('''def feature_order(line, p, cfg):''',
         '''def developed_peril_rate(line, peril):
    """Uncapped cost per exposure of one peril in the developed market (Part 1 data), 2021-24 at 2025 level."""
    p1, c1 = load_policies(line, "train", PART1["data_dir"]), load_claims(PART1["data_dir"])
    m1 = adjust_claims(match_claims(c1, p1, line, True, cap=None), PART1["adj"][line])
    return float(m1.loc[m1.peril == peril, "net_adj_uncapped"].sum() / p1.exposure_clean.sum())


def feature_order(line, p, cfg):'''),
        ('''    wm = cfg["weather_mode"]
    hk = dict''',
         '''    sep_rate = 0.0
    fs = cfg.get("peril_split", {}).get(line)
    if fs:                                      # one peril priced separately (Part 2: buildings fire)
        ms = adjust_claims(match_claims(claims, p, line, True, cap=None), cfg["adj"][line])
        sep = ms[ms.peril == fs["peril"]].groupby("row_id").net_adj.sum()
        mt = mt.assign(target_all=mt.target, target=mt.target - mt.row_id.map(sep).fillna(0.0))
        sep_rate = developed_peril_rate(line, fs["peril"]) if fs["rate"] == "developed" else float(fs["rate"])
        log(f"{line}: {fs['peril']} priced separately at {sep_rate:.2f} per exposure ({fs['rate']})")
    wm = cfg["weather_mode"]
    hk = dict'''),
        ('''    return {"p": p, "pt": pt, "tr": tr, "te": te, "feats": feats, "comp": comp,
            "observed_loading": observed_loading}''',
         '''    return {"p": p, "pt": pt, "tr": tr, "te": te, "feats": feats, "comp": comp,
            "observed_loading": observed_loading, "sep_rate": sep_rate}'''),
        ('''        rate, load_info = apply_loading(line, cfg, rate, d["tr"], d, claims)
''',
         '''        rate, load_info = apply_loading(line, cfg, rate, d["tr"], d, claims)
        if d.get("sep_rate"):
            rate = rate + d["sep_rate"]
            load_info += f"; + separate peril rate {d['sep_rate']:.2f}"
'''),
        ('''    claims = load_claims(cfg["data_dir"])
    rows = []
    for line in lines or cfg["lines"]:''',
         '''    claims = load_claims(cfg["data_dir"])
    rows, pooled = [], {}
    for line in lines or cfg["lines"]:'''),
        ('''            pv = rate * va.weight.to_numpy()
            r = evaluate(va.target, pv, va.weight, show=False)''',
         '''            pv = (rate + d.get("sep_rate", 0.0)) * va.weight.to_numpy()
            if "target_all" in va:              # separately priced peril: evaluate on all perils
                va = va.assign(target=va.target_all)
            r = evaluate(va.target, pv, va.weight, show=False)
            pooled.setdefault(vy, []).append(pd.DataFrame({"a": va.target.to_numpy(), "p": pv, "w": va.weight.to_numpy()}))'''),
        ('''                + (f"  new {row['A/E new']:.3f}  renewal {row['A/E renewal']:.3f}" if "A/E new" in row else ""))
    return pd.DataFrame(rows)''',
         '''                + (f"  new {row['A/E new']:.3f}  renewal {row['A/E renewal']:.3f}" if "A/E new" in row else ""))
    for vy, parts in pooled.items():            # the leaderboard pools the lines
        a = pd.concat(parts)
        r = evaluate(a.a, a.p, a.w, show=False)
        rows.append({"line": "ALL (pooled)", "year": vy, "D2": r["D2"], "A/E": r["A/E"]})
        log(f"validate pooled {vy}: D2 {r['D2']:.4f}  A/E {r['A/E']:.3f}")
    return pd.DataFrame(rows)'''),
    ],
}

for path, edits in EDITS.items():
    f = Path(path)
    s = f.read_text()
    for old, new in edits:
        n = s.count(old)
        assert n == 1, f"{path}: expected the old text once, found {n}:\\n{old[:200]}"
        s = s.replace(old, new)
    f.write_text(s)
    print(f"patched {path}")

f = Path("src/config.py")
s = f.read_text()
assert "PART2 = " in s, "run tools/patch_part2_oct24.py first"
assert "peril_split" not in s, "src/config.py already has this patch"
f.write_text(s.replace("\nMARKETS = {", CONFIG_ADD + "\nMARKETS = {"))
print("patched src/config.py")
print("next:  python -m src.pipeline --market part2 --validate")
