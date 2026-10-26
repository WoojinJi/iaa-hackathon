"""Pricing walkthrough for the Part 2 (emerging) market: one figure and a few numbers per step.

Built for discussion (Woojin and Krista, Oct 26), not for the submission. Each step recomputes its numbers from
the raw data with the functions in src/target.py, so the walkthrough doubles as a re-run of the pipeline's
target steps. Model, validation and submission steps reuse the saved report figures (results/report_figs).

Usage (repository root):  python tools/walkthrough_p2.py      -> results/walkthrough/ (figures + numbers.json)
"""
import copy
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import warnings

import numpy as np
import pandas as pd
warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import target as T                      # noqa: E402
from src.clean import fix_sum_insured            # noqa: E402
from src.config import PART2                     # noqa: E402

OUT = ROOT / "results" / "walkthrough"
LINES = ["motor", "buildings", "contents"]
BLUE, GREY, RED, GREEN = "#1f6feb", "#9aa5b1", "#d1242f", "#1a7f37"
cfg = copy.deepcopy(PART2)
DATA = cfg["data_dir"]
VAL = cfg["valuation_date"]
NUM = {}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=180)
    plt.close(fig)


def clean_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)


def load():
    T.AMOUNTS_NET, T.ROW_COMPLETENESS = True, True
    claims = T.load_claims(DATA)
    pol = {}
    for line in LINES:
        p, pt = T.load_policies(line, "train", DATA), T.load_policies(line, "test", DATA)
        if "sum_insured" in p:
            p, pt, n = fix_sum_insured(p, pt)
            NUM.setdefault("step1", {})[f"{line}_sum_insured_x1000"] = {"train": int(n[0]), "test": int(n[1])}
        pol[line] = (p, pt)
    return claims, pol


# ---------------------------------------------------------------- step 1: data and exposure
def step1(claims, pol):
    rows = []
    for line in LINES:
        p, pt = pol[line]
        bad = (p.exp_flag != "ok")
        rows.append({"line": line, "rows": len(p), "test_rows": len(pt), "bad_exposure_rows": int(bad.sum()),
                     "bad_share": float(bad.mean()), "exposure_original": float(p.exposure.sum()),
                     "exposure_from_dates": float(p.exposure_clean.sum())})
        m = T.match_claims(claims, p, line, True, cap=None)
        own = claims[claims.line == line]
        rows[-1]["claims"] = int(len(own))
        rows[-1]["claims_matched"] = int(m.claim_id.nunique() if "claim_id" in m else len(m))
    d = pd.DataFrame(rows)
    NUM["step1"]["table"] = d.round(4).to_dict("records")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(d))
    ax.bar(x - 0.2, d.exposure_original, 0.4, color=GREY, label="exposure column as given")
    ax.bar(x + 0.2, d.exposure_from_dates, 0.4, color=BLUE, label="re-computed from the dates")
    for i, r in d.iterrows():
        ax.annotate(f"{r.bad_share:.1%} rows wrong", (i, max(r.exposure_original, r.exposure_from_dates)),
                    textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(d.line); ax.set_ylabel("total exposure (policy-years)")
    ax.set_title("Step 1. A few wrong exposure entries inflate the total; we use the dates", fontsize=10)
    ax.legend(frameon=False, fontsize=8); clean_axes(ax)
    save(fig, "step1_exposure.png")


# ---------------------------------------------------------------- step 2: target, the excess question
def step2(claims, pol):
    rows = []
    for line in LINES:
        p, _ = pol[line]
        e = p.exposure_clean.sum()
        wrong = T.match_claims(claims, p, line, True, cap=None, amounts_net=False).net.sum() / e
        right = T.match_claims(claims, p, line, True, cap=None, amounts_net=True).net.sum() / e
        rows.append({"line": line, "cost_per_exposure_excess_deducted_again": wrong, "cost_per_exposure_net_as_recorded": right,
                     "ratio": right / wrong})
    d = pd.DataFrame(rows)
    NUM["step2"] = d.round(4).to_dict("records")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(d))
    ax.bar(x - 0.2, d.cost_per_exposure_excess_deducted_again, 0.4, color=RED, label="excess deducted again (Oct 16-24, wrong)")
    ax.bar(x + 0.2, d.cost_per_exposure_net_as_recorded, 0.4, color=BLUE, label="amounts already net of excess (fixed Oct 24)")
    for i, r in d.iterrows():
        ax.annotate(f"x{r.ratio:.2f}", (i + 0.2, r.cost_per_exposure_net_as_recorded), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(d.line); ax.set_ylabel("cost per exposure, raw (no trend)")
    ax.set_title("Step 2. Reading the data dictionary: the excess was already out of the amounts", fontsize=10)
    ax.legend(frameon=False, fontsize=8); clean_axes(ax)
    save(fig, "step2_excess.png")


# ---------------------------------------------------------------- step 3: completeness (IBNR)
def step3(claims, pol):
    p, _ = pol["motor"]
    mc = T.adjust_claims(T.match_claims(claims, p, "motor", True, cap=None), cfg["adj"]["motor"])
    comp = {}
    for line in LINES:
        pl, _ = pol[line]
        ml = T.adjust_claims(T.match_claims(claims, pl, line, True, cap=None), cfg["adj"][line])
        comp[line] = T.year_completeness(ml, years=cfg["years"], method=cfg["completeness_method"], valuation_date=VAL).round(4).to_dict()
    NUM["step3"] = {"year_completeness": {k: {str(y): v for y, v in c.items()} for k, c in comp.items()}}
    f = T.row_timing_factor(mc, p, VAL)
    yc = comp["motor"][2024]
    q = p.assign(rowc=f * np.where(p.year == 2024, yc, comp["motor"][2023]), m=p.period_start.dt.month)
    g = q[q.year == 2024].groupby("m").apply(lambda s: np.average(s.rowc, weights=s.exposure_clean))
    nb = q[(q.year == 2024)].groupby("new_business").apply(lambda s: np.average(s.rowc, weights=s.exposure_clean))
    NUM["step3"]["motor_2024_row_completeness_by_start_month"] = g.round(3).to_dict()
    NUM["step3"]["motor_2024_by_new_business"] = {str(k): round(float(v), 3) for k, v in nb.items()}
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(g.index, g.values, marker="o", color=BLUE, label="each row's own period (E22, used)")
    ax.axhline(yc, color=GREY, ls="--", label=f"one number for the whole year ({yc:.3f}, before E22)")
    ax.set_xticks(range(1, 13)); ax.set_xlabel("start month of the 2024 policy row"); ax.set_ylabel("share of claims already reported")
    ax.set_title("Step 3. Rows that start late in the year are less complete at the 30 Dec 2024 valuation (motor)", fontsize=10)
    ax.legend(frameon=False, fontsize=8); clean_axes(ax)
    save(fig, "step3_completeness.png")


# ---------------------------------------------------------------- step 4: trend to 2025, with leverage
def step4(claims, pol):
    rows = []
    for line in LINES:
        p, _ = pol[line]
        adj = cfg["adj"][line]
        m = T.match_claims(claims, p, line, True, cap=None)
        e = p.exposure_clean.sum()
        no_trend = dict(adj, sev_trend={k: 0.0 for k in adj["sev_trend"]})
        base = T.adjust_claims(m, no_trend).net_adj.sum() / e
        lev = T.adjust_claims(m, adj).net_adj.sum() / e
        m0 = m.assign(excess_in_amount=0.0)
        nolev = T.adjust_claims(m0, adj).net_adj.sum() / e
        rows.append({"line": line, "no_trend": base, "trend_without_leverage": nolev, "trend_with_leverage": lev})
    d = pd.DataFrame(rows)
    NUM["step4"] = d.round(3).to_dict("records")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(d)); w = 0.27
    for k, (c, col, lab) in enumerate([("no_trend", GREY, "past cost, no trend"),
                                       ("trend_without_leverage", "#79c0ff", "trend on the net amount"),
                                       ("trend_with_leverage", BLUE, "trend on the ground-up loss, excess fixed (used)")]):
        ax.bar(x + (k - 1) * w, d[c], w, color=col, label=lab)
    ax.set_xticks(x); ax.set_xticklabels(d.line); ax.set_ylabel("cost per exposure, capped")
    ax.set_title("Step 4. Bringing past claims to the 2025 cost level", fontsize=10)
    ax.legend(frameon=False, fontsize=8); clean_axes(ax)
    save(fig, "step4_trend.png")


# ---------------------------------------------------------------- step 5: large losses and the fire cluster
def step5(claims, pol):
    p, _ = pol["buildings"]
    m = T.match_claims(claims, p, "buildings", True, cap=None)
    fire = m[m.peril == "fire"]
    e = p.groupby("year").exposure_clean.sum()
    fy = fire.groupby(p.set_index("row_id").loc[fire.row_id, "year"].to_numpy()).size()
    freq = (fy / e * 1000).round(2)
    caps = {}
    for line in LINES:
        pl, _ = pol[line]
        ml = T.match_claims(claims, pl, line, True, cap=None)
        cap = cfg["adj"][line]["cap"]
        caps[line] = {"cap": cap, "claims_above_cap": int((ml.net > cap).sum()) if cap else 0,
                      "largest_claim": float(ml.net.max()), "p99_claim": float(ml.net[ml.net > 0].quantile(0.99))}
    NUM["step5"] = {"buildings_fire_claims_by_year": {str(k): int(v) for k, v in fy.items()},
                    "buildings_fire_per_1000_exposure": {str(k): float(v) for k, v in freq.items()},
                    "developed_fire_rate_per_exposure": 97.05, "caps": caps}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].bar([str(y) for y in fy.index], fy.values, color=[RED if y == 2023 else BLUE for y in fy.index])
    axes[0].set_title("Buildings fire claims by year", fontsize=9); axes[0].set_ylabel("claims"); clean_axes(axes[0])
    for i, line in enumerate(LINES):
        pl, _ = pol[line]
        ml = T.match_claims(claims, pl, line, True, cap=None)
        v = np.sort(ml.net[ml.net > 0].to_numpy())[::-1][:30]
        axes[1].plot(range(1, len(v) + 1), v, marker=".", label=line)
    axes[1].set_yscale("log"); axes[1].set_xlabel("rank of claim (largest first)"); axes[1].set_ylabel("net claim (log)")
    axes[1].set_title("The 30 largest claims per line", fontsize=9); axes[1].legend(frameon=False, fontsize=8); clean_axes(axes[1])
    fig.suptitle("Step 5. Is a big loss risk or bad luck? Fire 2023 was a local cluster, so fire gets a flat developed rate", fontsize=10)
    save(fig, "step5_large_losses.png")


# ---------------------------------------------------------------- step 6: frequency and severity by peril
def step6(claims, pol):
    rows = []
    for line in LINES:
        p, _ = pol[line]
        m = T.match_claims(claims, p, line, True, cap=None)
        m = m[m.net > 0].merge(p[["row_id", "year"]], on="row_id")
        e = p.groupby("year").exposure_clean.sum()
        for (peril, y), g in m.groupby(["peril", "year"]):
            rows.append({"line": line, "peril": peril, "year": y, "claims": len(g), "freq_per_1000": len(g) / e[y] * 1000,
                         "mean_severity": g.net.mean(), "median_severity": g.net.median()})
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "step6_freq_sev.csv", index=False)
    NUM["step6"] = d.round(2).to_dict("records")
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, line in zip(axes, LINES):
        s = d[d.line == line]
        for y, mk in [(2023, "o"), (2024, "s")]:
            t = s[s.year == y]
            ax.scatter(t.freq_per_1000, t.mean_severity, marker=mk, label=str(y), color=RED if y == 2023 else BLUE)
            for _, r in t.iterrows():
                ax.annotate(r.peril.replace("_", " "), (r.freq_per_1000, r.mean_severity), fontsize=6, xytext=(2, 2),
                            textcoords="offset points")
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_title(line, fontsize=9)
        for a in (ax.xaxis, ax.yaxis):
            a.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}"))
            a.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel("claims per 1,000 exposure"); clean_axes(ax)
    axes[0].set_ylabel("mean net claim"); axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Step 6. How often (frequency) and how big (severity), by peril and year", fontsize=10)
    save(fig, "step6_freq_sev.png")


# ---------------------------------------------------------------- step 9: the broker book in the test year
def step9(pol):
    rows = []
    for line in LINES:
        p, pt = pol[line]
        for y in (2023, 2024):
            q = p[p.year == y]
            rows.append({"line": line, "year": str(y), "new_business_share": float(np.average(q.new_business, weights=q.exposure_clean)),
                         "broker_share": float(np.average(q.channel == "broker", weights=q.exposure_clean))})
        rows.append({"line": line, "year": "2025 test", "new_business_share": float(np.average(pt.new_business, weights=pt.exposure_clean)),
                     "broker_share": float(np.average(pt.channel == "broker", weights=pt.exposure_clean))})
    d = pd.DataFrame(rows)
    NUM["step9"] = d.round(3).to_dict("records")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, col, title in [(axes[0], "new_business_share", "share of new business"), (axes[1], "broker_share", "share sold by brokers")]:
        piv = d.pivot(index="line", columns="year", values=col).loc[LINES]
        piv.plot.bar(ax=ax, color=[GREY, "#79c0ff", RED], rot=0, width=0.75)
        ax.set_title(title, fontsize=9); ax.set_xlabel(""); ax.legend(frameon=False, fontsize=8); clean_axes(ax)
    fig.suptitle("Step 9. The 2025 test is a different book: 77% new customers (6-9% before), same channel mix", fontsize=10)
    save(fig, "step9_broker_book.png")


# ---------------------------------------------------------------- step 11: office premium decomposition
def step11():
    f = ROOT / "results" / "office_premium_v9" / "reference_20_decomposed.csv"
    if not f.exists():
        print("step 11 skipped: run the decomposition cell in notebook 31 first"); return
    r = pd.read_csv(f)
    NUM["step11"] = r[["row_id", "line", "channel", "expected_LR", "expense_mult", "office/current"]].round(2).to_dict("records")
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(r))
    ax.bar(x, np.log(r.expected_LR), color=BLUE, label="risk part: risk premium / current premium (below x1 = risk covered)")
    ax.bar(x, np.log(r.expense_mult), bottom=np.log(r.expected_LR), color=GREY,
           label="expense part: office / risk premium (commission, expenses, tax, profit, fixed 85)")
    ax.scatter(x, np.log(r["office/current"]), color="black", zorder=3, s=14, label="office / current premium (total)")
    ax.axhline(0, color="black", lw=0.8)
    ticks = [0.25, 0.5, 1, 2, 4, 8]
    ax.set_yticks(np.log(ticks)); ax.set_yticklabels([f"x{t:g}" for t in ticks])
    ax.set_xticks(x); ax.set_xticklabels(r.row_id, rotation=90, fontsize=7)
    ax.set_title("Step 11. Why the office premium is 2-6x the current premium: risk in buildings and motor, expenses in contents", fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc="upper left"); clean_axes(ax)
    save(fig, "step11_office_premium.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    claims, pol = load()
    for name, fn in [("1", lambda: step1(claims, pol)), ("2", lambda: step2(claims, pol)), ("3", lambda: step3(claims, pol)),
                     ("4", lambda: step4(claims, pol)), ("5", lambda: step5(claims, pol)), ("6", lambda: step6(claims, pol)),
                     ("9", lambda: step9(pol)), ("11", step11)]:
        fn(); print(f"step {name} done", flush=True)
    (OUT / "numbers.json").write_text(json.dumps(NUM, indent=1, default=float))
    print(f"saved to {OUT}")


if __name__ == "__main__":
    main()
