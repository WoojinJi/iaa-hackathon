"""Report figures (docs/REPORT_OUTLINE.md, figure plan). Writes PNGs to docs/figures/.

  fig1_freq_sev.png   frequency and severity by loss year per line: raw vs brought to 2025 level
  fig1b_bi_reform.png BI mean severity by loss quarter, all vs closed claims (the 2023 reform step)
  fig2_leaderboard.png expected leaderboard change written before each submission vs observed
  fig3_ai_roles.png   roles (builder AI -> reviewer AI -> team decides) and AI_USE_LOG entries by type
  fig4_tails.png      buildings A/E by decile: GLM + interactions (v11) vs blend with a GBM vs GBM alone

Usage (repository root):  python tools/figures.py            (all, about 3 minutes)
                          python tools/figures.py --only 2 3  (the quick ones, no model fitting)
"""
import argparse
import copy
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "figures"
BLUE, GREY, RED, GREEN, ORANGE = "#0b3d63", "#9aa4ae", "#b42318", "#2e7d32", "#d4a017"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "axes.titleweight": "bold"})


# ------------------------------------------------------------------ figure 1
def fig1(cfg):
    from src.target import ADJ, REFORM_YEAR, TARGET_YEAR, completeness, load_claims, load_policies, match_claims
    claims = load_claims(cfg["data_dir"])
    years = cfg["years"]
    fig, ax = plt.subplots(2, 3, figsize=(10, 5.6))
    for j, line in enumerate(cfg["lines"]):
        p = load_policies(line, "train", cfg["data_dir"])
        m = match_claims(claims, p, line, True, cap=None)
        m = m[m.loss_year.isin(years)]
        expo = p.groupby("year").exposure_clean.sum()
        # frequency: reported counts, and grossed up by peril completeness (Lynden-Bell)
        raw = m.groupby("loss_year").size() / expo
        adj_n = sum(m[(m.peril == per)].groupby("loss_year").size().reindex(years, fill_value=0)
                    / pd.Series({y: completeness(m, per, y, valuation_date=cfg["valuation_date"],
                                                 method="lynden_bell") for y in years})
                    for per in m.peril.unique())
        adj = adj_n / expo
        ax[0, j].plot(years, raw / raw.iloc[0], "o-", color=GREY, label="reported")
        ax[0, j].plot(years, adj / adj.iloc[0], "o-", color=BLUE, label="incl. late-reported (IBNR)")
        ax[0, j].set_title(f"{line}: frequency (2021 = 1)")
        # severity: mean gross incurred, raw vs 2025 level (trend, reform), capped as in the target
        a = ADJ[line]
        cap = a["cap"] or np.inf
        s = m[m.incurred_to_date > 0]
        f = (1 + s.peril.map(a["sev_trend"]).fillna(0.0)) ** (TARGET_YEAR - s.loss_year)
        f = f * np.where(s.loss_year < REFORM_YEAR, s.peril.map(a["reform"]).fillna(1.0), 1.0)
        sr = s.incurred_to_date.clip(upper=cap).groupby(s.loss_year).mean()
        sa = (s.incurred_to_date * f).clip(upper=cap).groupby(s.loss_year).mean()
        ax[1, j].plot(years, sr / sr.iloc[0], "o-", color=GREY, label="as recorded")
        ax[1, j].plot(years, sa / sr.iloc[0], "o-", color=BLUE, label="at 2025 level")
        ax[1, j].set_title(f"{line}: severity (2021 = 1)")
        for k in (0, 1):
            ax[k, j].set_xticks(years); ax[k, j].axhline(1, color="#ddd", lw=0.8, zorder=0)
    ax[0, 0].legend(frameon=False, fontsize=8); ax[1, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Bringing 2021–24 claims to the 2025 level", fontweight="bold")
    fig.text(0.5, 0.005, "Frequency: all reported claims (declined excluded), grossed up by peril completeness. Severity: mean "
             "over all perils of the line, so 2024 motor is lower partly because late-reported large BI claims are "
             "still missing; 2024 includes case reserves on open claims.", ha="center", fontsize=7, color="#555", wrap=True)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96)); fig.savefig(OUT / "fig1_freq_sev.png", dpi=160); plt.close(fig)

    # 1b: BI reform step, equal maturity (reported within 180 days)
    p = load_policies("motor", "train", cfg["data_dir"])
    b = match_claims(claims, p, "motor", True, cap=None)
    b = b[(b.peril == "bodily_injury") & (b.report_lag <= 180) & (b.incurred_to_date > 0)
          & (b.loss_date <= cfg["valuation_date"] - pd.Timedelta(days=180))]
    b = b.assign(q=b.loss_date.dt.to_period("Q"), sev=b.incurred_to_date.clip(upper=ADJ["motor"]["cap"]))
    allq, closed = b.groupby("q").sev.mean(), b[b.status == "closed"].groupby("q").sev.mean()
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = np.arange(len(allq))
    ax.plot(x, allq.values / 1000, "o-", color=GREY, label="all claims (open claims carry reserves)")
    ax.plot(x, closed.reindex(allq.index).values / 1000, "o-", color=BLUE, label="closed claims only")
    k = list(allq.index.astype(str)).index("2023Q1")
    ax.axvline(k - 0.5, color=RED, ls="--", lw=1); ax.text(k - 0.4, ax.get_ylim()[1] * 0.97, "reform, 2023 Q1",
                                                          color=RED, va="top", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(allq.index.astype(str), rotation=45, fontsize=7.5)
    ax.set_ylabel("mean incurred (thousand)")
    ax.set_title("Bodily injury severity by loss quarter (reported within 180 days)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "fig1b_bi_reform.png", dpi=160); plt.close(fig)


# ------------------------------------------------------------------ figure 2
# Expected change written in DECISIONS.md before each submission (low, high) and observed public change.
SUBMISSIONS = [
    ("v3", 0.0005, 0.0005, 0.00074), ("blend v1*", 0.0020, 0.0030, 0.00315), ("v4", 0.0010, 0.0010, 0.00109),
    ("blend v2*", 0.0029, 0.0029, 0.00279), ("v5", 0.0005, 0.0010, 0.00089), ("v6", 0.0005, 0.0015, -0.00045),
    ("v7", 0.0002, 0.0005, 0.00022), ("v8", -0.0003, 0.0005, 0.00294), ("v8a*", 0.00247, 0.00297, 0.00264),
    ("v9", -0.0002, 0.0005, 0.00007), ("v10", -0.0002, 0.0003, -0.00009), ("v11", 0.0005, 0.0012, 0.00042),
]


NEAR = 0.00025   # a single number cannot be hit exactly: "near" = within 0.00025 of the written range


def fig2():
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    tally = {"inside": 0, "near": 0, "outside": 0}
    for i, (name, lo, hi, obs) in enumerate(SUBMISSIONS):
        y = len(SUBMISSIONS) - 1 - i
        if lo == hi:
            ax.plot(lo * 1000, y, "|", color=BLUE, ms=14, mew=3, alpha=0.5)
        else:
            ax.plot([lo * 1000, hi * 1000], [y, y], color=BLUE, lw=6, alpha=0.35, solid_capstyle="butt")
        kind = "inside" if lo <= obs <= hi else ("near" if lo - NEAR <= obs <= hi + NEAR else "outside")
        tally[kind] += 1
        ax.plot(obs * 1000, y, "o", color={"inside": GREEN, "near": ORANGE, "outside": RED}[kind], ms=6, zorder=3)
    ax.axvspan(-1, 1, color="#f2f2f2", zorder=0)
    ax.text(-0.95, len(SUBMISSIONS) - 0.6, "±0.001 noise range", ha="left", fontsize=7.5, color="#777")
    ax.axvline(0, color="#bbb", lw=0.8)
    ax.set_yticks(range(len(SUBMISSIONS))); ax.set_yticklabels([s[0] for s in SUBMISSIONS][::-1])
    ax.set_xlabel("change in public score (× 0.001)")
    ax.set_title("Expected change, written before submitting (bar or tick) vs observed (dot)")
    for k, c, lab in [("inside", GREEN, "inside the range"), ("near", ORANGE, "within 0.00025 of it"),
                      ("outside", RED, "outside")]:
        ax.plot([], [], "o", color=c, label=f"{lab}: {tally[k]}")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.text(0.01, 0.01, "* experiments, not candidates for the final entry. Outside: v6 (motor level), v8 (weather; "
             "attributed with v8a).", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(OUT / "fig2_leaderboard.png", dpi=160); plt.close(fig)
    print(f"fig2: {tally}")


# ------------------------------------------------------------------ figure 3
CODE_WORDS = r"code|script|test|notebook|label|column|file|kernel|function|parquet|csv|bug|crash"


def ai_log_counts(path=ROOT / "AI_USE_LOG.md"):
    """One record per log row; a row typed "A/E" counts as both A and E; rows typed "—" (notes) are skipped."""
    rows = [l for l in path.read_text().splitlines() if re.match(r"^\| ?\d+ ?\| ?[AHE](/[AHE])? ?\|", l)]
    recs = []
    for l in rows:
        cells = [c.strip() for c in l.strip("|").split("|")]
        for t in cells[1].split("/"):
            recs.append({"n": int(cells[0]), "type": t, "text": " ".join(cells[2:])})
    d = pd.DataFrame(recs)
    d["error_kind"] = np.where(d.type != "E", "",
                               np.where(d.text.str.contains(CODE_WORDS, case=False), "code", "judgement"))
    return d


def fig3():
    d = ai_log_counts()
    d[d.type == "E"][["n", "error_kind", "text"]].assign(text=lambda x: x.text.str[:110]) \
        .to_csv(OUT / "fig3_error_classification.csv", index=False)
    fig = plt.figure(figsize=(10, 3.6))
    ax = fig.add_axes([0.0, 0.0, 0.58, 1]); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 6)
    boxes = [(0.3, 3.3, "Builder AI", "code, analysis,\nfirst drafts"), (3.6, 3.3, "Reviewer AI", "separate chat,\nno shared context:\nfinds errors"),
             (6.9, 3.3, "Team", "sets rules before\nresults; decides")]
    for x, y, t, sub in boxes:
        ax.add_patch(plt.Rectangle((x, y), 2.8, 2.2, fc="#eef3f8", ec=BLUE, lw=1.2))
        ax.text(x + 1.4, y + 1.6, t, ha="center", fontweight="bold", color=BLUE)
        ax.text(x + 1.4, y + 0.75, sub, ha="center", va="center", fontsize=8)
    for x0, x1 in [(3.1, 3.6), (6.4, 6.9)]:
        ax.annotate("", (x1, 4.4), (x0, 4.4), arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.4))
    ax.annotate("", (1.7, 3.2), (8.3, 3.2), arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.2,
                                                           connectionstyle="arc3,rad=-0.3"))
    ax.text(5, 1.0, "questions, tests and out-of-time checks go back to the builder", ha="center",
            fontsize=8, color="#8a5300")
    ax2 = fig.add_axes([0.66, 0.18, 0.31, 0.68])
    counts = d.type.value_counts().reindex(["A", "H", "E"]).fillna(0)
    kinds = d[d.type == "E"].error_kind.value_counts().reindex(["code", "judgement"]).fillna(0)
    ax2.barh(["AI proposed,\nteam verified", "team questioned\nor challenged"], [counts["A"], counts["H"]], color=BLUE)
    ax2.barh(["AI error caught"], [kinds["code"]], color=GREY, label="in code (tests, checks)")
    ax2.barh(["AI error caught"], [kinds["judgement"]], left=[kinds["code"]], color=RED,
             label="in judgement (questions, data)")
    for i, v in enumerate([counts["A"], counts["H"], counts["E"]]):
        ax2.text(v + 0.5, i, f"{int(v)}", va="center", fontsize=8)
    ax2.invert_yaxis(); ax2.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=2)
    ax2.set_title(f"AI_USE_LOG: {d.n.nunique()} entries (A/E rows count in both)", fontsize=9)
    fig.savefig(OUT / "fig3_ai_roles.png", dpi=160, bbox_inches="tight"); plt.close(fig)
    print(f"fig3: {({k: int(v) for k, v in counts.items()})}; AI errors {({k: int(v) for k, v in kinds.items()})} "
          f"(keyword split, review docs/figures/fig3_error_classification.csv)")


# ------------------------------------------------------------------ figure 4
def fig4(cfg, w=0.75, seeds=(42, 43, 44)):
    from src.config import GBM_BASE
    from src.evaluate import evaluate
    from src.glm import BandedTweedieGLM
    from src.pipeline import build_line, fit_gbm, prep2
    from src.target import load_claims
    line = "buildings"
    d = build_line(line, cfg, load_claims(cfg["data_dir"]))
    tr, feats = d["tr"], d["feats"]
    gfeats = [f for f in feats if "*" not in f]
    params = dict(GBM_BASE, num_leaves=7, min_data_in_leaf=5000, lambda_l2=50)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for a, (vy, tys) in zip(ax, cfg["folds"]):
        trn, val = tr[tr.year.isin(tys)], tr[tr.year == vy]
        g = BandedTweedieGLM(**cfg["glm"][line]).fit(trn[feats], trn.target / trn.weight, trn.weight)
        gr = g.predict_rate(val[feats])
        br = np.zeros(len(val))
        for s in seeds:
            m, cats, k, _ = fit_gbm(trn, gfeats, dict(params, seed=s))
            br += m.predict(prep2(val[gfeats], cats)[0]) * k / len(seeds)
        for name, rate, col in [("GLM + interactions (v11)", gr, BLUE), (f"blend, {int(w * 100)}% GBM", (1 - w) * gr + w * br, RED),
                                ("GBM alone", br, GREY)]:
            r = evaluate(val.target, rate * val.weight.to_numpy(), val.weight, show=False)
            ae = r["lift"]["A/E"].to_numpy()
            a.plot(range(1, len(ae) + 1), ae, "o-", color=col, label=f"{name}  (D² {r['D2']:.4f})")
        a.axhline(1, color="#bbb", lw=0.8); a.axhspan(0.9, 1.1, color="#f2f2f2", zorder=0)
        a.set_title(f"Buildings, validation {vy}"); a.set_xlabel("decile of predicted risk (1 = safest)")
        a.set_xticks(range(1, 11)); a.legend(frameon=False, fontsize=7.5)
    ax[0].set_ylabel("actual / expected")
    fig.text(0.5, 0.005, "A/E below 1 = over-priced. The GBM's extra D² comes with the safest decile over-priced "
             "by about a quarter; D² barely penalises this because those policies' expected cost is small.",
             ha="center", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(OUT / "fig4_tails.png", dpi=160); plt.close(fig)


def main():
    from src.config import PART1
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", type=int, help="figure numbers to make (1-4)")
    ap.add_argument("--data")
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    cfg = copy.deepcopy(PART1)
    if a.data:
        cfg["data_dir"] = Path(a.data)
    OUT.mkdir(parents=True, exist_ok=True)
    todo = a.only or [1, 2, 3, 4]
    if 1 in todo: fig1(cfg); print("fig1 done")       # noqa: E701
    if 2 in todo: fig2()                              # noqa: E701
    if 3 in todo: fig3()                              # noqa: E701
    if 4 in todo: fig4(cfg); print("fig4 done")       # noqa: E701
    print(f"saved in {OUT}")


if __name__ == "__main__":
    main()
