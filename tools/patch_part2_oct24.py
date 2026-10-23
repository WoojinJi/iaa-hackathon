"""Patch for Part 2 (Oct 24). Run once from the repository root:  python tools/patch_part2_oct24.py

Adds a Part 2 market configuration and the options it needs. Part 1 results do not change
(every new option is off in PART1). src/target.py is not touched.

  src/clean.py     new: sum_insured x1000 entry error -> divided by 1000 (DECISIONS Oct 23)
  src/config.py    PART2 config + MARKETS = {"part1": PART1, "part2": PART2}
  src/history.py   data_start as a parameter (Part 2 data start in 2023, not 2021)
  src/pipeline.py  --market part1|part2; sum_insured fix; history columns and data start from the config;
                   relative premium by="annual" (written_premium is the annual premium, Oct 23);
                   Pareto loading with a borrowed tail shape (alpha); sample_submission as CSV;
                   validation also reports A/E for new business and renewals (rule 2, Oct 23)
Every replacement checks that the old text occurs exactly once, so the patch stops if a file differs.
"""
from pathlib import Path

CLEAN = '''"""Corrections to a market's raw tables that are not part of the target definition (DECISIONS.md Oct 23)."""


def fix_sum_insured(p, pt, factor=100, unit=1000):
    """sum_insured entered x1000 (emerging market, about 0.2% of rows in train and test).
    Evidence (Oct 23): the same policy's other years differ by about x1000 (median ratio 1,030 with 2-3%
    indexation), the written premium equals that of normal rows, and no buildings rows lie between 5x and
    100x the median. Rows above `factor` x the training median are divided by `unit`.
    Returns corrected copies of p and pt and the number of rows changed in each."""
    med = p["sum_insured"].median()
    out, n = [], []
    for d in (p, pt):
        big = d["sum_insured"] > factor * med
        d = d.copy()
        d.loc[big, "sum_insured"] = d.loc[big, "sum_insured"] / unit
        out.append(d)
        n.append(int(big.sum()))
    return out[0], out[1], n
'''

CONFIG_ADD = '''

# ------------------------------------------------------------------ Part 2 (emerging market)
# Day 1 checks and team rules: DECISIONS.md Oct 23. Baseline = Part 1 structure with what the emerging data
# require; anything else is an experiment judged by the Part 1 rules.
PART2 = copy.deepcopy(PART1)
PART2.update({
    "name": "part2",
    "data_dir": DATA_DIR.parent / "data_part2" / "emerging",
    "years": [2023, 2024],
    "data_start": pd.Timestamp("2023-01-01"),  # history windows before this are not observable
    "hist": ["hist_1y"],                       # a 2-year window is never observable in training (2023 start)
    "fix_sum_insured": True,                   # x1000 entry error (Oct 23)
    "model": {"motor": "glm", "buildings": "glm", "contents": "glm"},   # rule 4: a GBM must pass the Part 1 rule here
    "premium_lines": [],                       # relative premium: an experiment in Part 2 (+0.0005 rule)
    "premium_norm": "annual",                  # written_premium is the full annual premium (Oct 23)
    "interactions": {},                        # Part 1 pairs were selected on developed data; re-select before use
    "loading": {"motor": {"method": "pareto", "threshold": 100_000, "alpha": 2.05},   # tail shape borrowed (rule 3)
                "buildings": {"method": "observed"},
                "contents": {"method": "none"}},
    "folds": [(2024, [2023])],                 # one out-of-time fold (rule 2)
})
PART2["adj"]["motor"]["reform"] = {}           # BI reform 0.83 is a developed-market change (Oct 23)
for _line in PART2["drop"]:                    # occupation is free text in the emerging market
    if "occupation" not in PART2["drop"][_line]:
        PART2["drop"][_line] = PART2["drop"][_line] + ["occupation"]

MARKETS = {"part1": PART1, "part2": PART2}
'''

EDITS = {
    "src/config.py": [
        ("import copy\n", "import copy\n\nimport pandas as pd\n"),
    ],
    "src/history.py": [
        ("def claim_history(target_pol, all_pol_same_line, claims, years=(1, 2), perils=None, prefix=\"pol_claims\"):",
         "def claim_history(target_pol, all_pol_same_line, claims, years=(1, 2), perils=None, prefix=\"pol_claims\",\n"
         "                  data_start=DATA_START):"),
        ("        observable = (start >= DATA_START) & t[\"seen_before\"]",
         "        observable = (start >= data_start) & t[\"seen_before\"]"),
    ],
    "src/pipeline.py": [
        ("from .config import PART1\n", "from .clean import fix_sum_insured\nfrom .config import MARKETS, PART1\n"),
        ("from .loading import pareto_loading\n", "from .loading import expected_excess, pareto_loading\n"),
        ('''def add_history(F, p_rows, p_all_same_line, claims):
    h = claim_history(p_rows, p_all_same_line, claims)''',
         '''def add_history(F, p_rows, p_all_same_line, claims, data_start=None, cols=HIST):
    h = claim_history(p_rows, p_all_same_line, claims,
                      **({} if data_start is None else {"data_start": data_start}))'''),
        ('''    out = F.merge(h[["row_id"] + HIST], on="row_id", how="left", validate="one_to_one")''',
         '''    out = F.merge(h[["row_id"] + list(cols)], on="row_id", how="left", validate="one_to_one")'''),
        ('''    (the checks found a +50% step in premium per year from mid-2021) does not show up as risk."""
''',
         '''    (the checks found a +50% step in premium per year from mid-2021) does not show up as risk.
    by="annual" (Part 2): written_premium is the full annual premium whatever the row length (Oct 23),
    so it is divided by the policy year's average premium, not by exposure."""
    if by == "annual":
        return d.written_premium / d.year.map(d.written_premium.groupby(d.year).mean())
'''),
        ('''    return [c for c in cols if c != "row_id" and c not in cfg["drop"][line]] + HIST''',
         '''    return [c for c in cols if c != "row_id" and c not in cfg["drop"][line]] + list(cfg.get("hist", HIST))'''),
        ('''    p, pt = load_policies(line, "train", cfg["data_dir"]), load_policies(line, "test", cfg["data_dir"])
    mt, comp, observed_loading''',
         '''    p, pt = load_policies(line, "train", cfg["data_dir"]), load_policies(line, "test", cfg["data_dir"])
    if cfg.get("fix_sum_insured") and "sum_insured" in p:
        p, pt, n = fix_sum_insured(p, pt)
        log(f"{line}: sum_insured x1000 entries divided by 1000: train {n[0]}, test {n[1]}")
    mt, comp, observed_loading'''),
        ('''    F = add_history(build_features(line, "train", cfg["data_dir"], policies=p, weather_mode=wm), p, [p, pt], claims)
    Ft = add_history(build_features(line, "test", cfg["data_dir"], policies=pt, weather_mode=wm), pt, [p, pt], claims)''',
         '''    hk = dict(data_start=cfg.get("data_start"), cols=cfg.get("hist", HIST))
    F = add_history(build_features(line, "train", cfg["data_dir"], policies=p, weather_mode=wm), p, [p, pt], claims, **hk)
    Ft = add_history(build_features(line, "test", cfg["data_dir"], policies=pt, weather_mode=wm), pt, [p, pt], claims, **hk)'''),
        ('''        mc = adjust_claims(match_claims(claims, d["p"], line, True, cap=None), adj)
        fit = pareto_loading''',
         '''        mc = adjust_claims(match_claims(claims, d["p"], line, True, cap=None), adj)
        if spec.get("alpha"):   # Part 2: tail shape borrowed from the developed market, frequency from this one
            n = int((mc.net_adj_uncapped > spec["threshold"]).sum())
            used = n / tr.weight.sum() * expected_excess(spec["threshold"], adj["cap"], spec["alpha"])
            f = 1 + used / (tr.target.sum() / tr.weight.sum())
            return rate * f, (f"Pareto, alpha {spec['alpha']} borrowed: {n} claims above {spec['threshold']:,}, "
                              f"loading {used:.2f} -> factor {f:.4f}")
        fit = pareto_loading'''),
        ('''    sample = pd.read_parquet(Path(cfg["data_dir"]) / "sample_submission.parquet")''',
         '''    sp = Path(cfg["data_dir"])
    sample = (pd.read_parquet(sp / "sample_submission.parquet") if (sp / "sample_submission.parquet").exists()
              else pd.read_csv(sp / "sample_submission.csv", dtype=str))'''),
        ('''            r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
            lf = r["lift"]["A/E"]
            rows.append({"line": line, "year": vy, "D2": r["D2"], "A/E": r["A/E"],
                         "low": lf.iloc[0], "top": lf.iloc[-1]})
            log(f"validate {line} {vy}: D2 {r['D2']:.4f}  A/E {r['A/E']:.3f}")''',
         '''            pv = rate * va.weight.to_numpy()
            r = evaluate(va.target, pv, va.weight, show=False)
            lf = r["lift"]["A/E"]
            row = {"line": line, "year": vy, "D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}
            if "new_business" in va:            # rule 2 (Oct 23): new business is 76% of the Part 2 test
                nb = va.new_business.astype(bool).to_numpy()
                act = va.target.to_numpy()
                row["A/E new"] = act[nb].sum() / pv[nb].sum() if nb.any() else np.nan
                row["A/E renewal"] = act[~nb].sum() / pv[~nb].sum() if (~nb).any() else np.nan
            rows.append(row)
            log(f"validate {line} {vy}: D2 {r['D2']:.4f}  A/E {r['A/E']:.3f}"
                + (f"  new {row['A/E new']:.3f}  renewal {row['A/E renewal']:.3f}" if "A/E new" in row else ""))'''),
        ('''    ap.add_argument("--out", help="write the submission here")''',
         '''    ap.add_argument("--market", choices=sorted(MARKETS), default="part1", help="market configuration")
    ap.add_argument("--out", help="write the submission here")'''),
        ('''    cfg = copy.deepcopy(PART1)
    if a.data:''',
         '''    cfg = copy.deepcopy(MARKETS[a.market])
    if a.data:'''),
    ],
}

for path, edits in EDITS.items():
    f = Path(path)
    s = f.read_text()
    for old, new in edits:
        n = s.count(old)
        assert n == 1, f"{path}: expected the old text once, found {n}:\n{old[:200]}"
        s = s.replace(old, new)
    if path == "src/config.py":
        assert "PART2 = " not in s, "src/config.py already has PART2"
        s = s.rstrip("\n") + "\n" + CONFIG_ADD
    f.write_text(s)
    print(f"patched {path}")

c = Path("src/clean.py")
assert not c.exists(), "src/clean.py already exists"
c.write_text(CLEAN)
print("created src/clean.py")
print("Part 1 check:  python -m src.pipeline --out submissions/v11_check.csv --compare submissions/v11.csv  (expect identical)")
print("Part 2:        python -m src.pipeline --market part2 --validate")
