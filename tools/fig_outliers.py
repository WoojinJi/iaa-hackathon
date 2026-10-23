"""Outlier figure: which line x peril has extreme claims, and how extreme.

Writes docs/figures/fig5_outliers.png and prints a table to the terminal.

  For every line x peril (claims with incurred > 0, duplicates and declined claims removed, before any cap):
    p99, p99.9, max, max / p99, and the share of the peril's total cost from its 10 largest claims.
  The figure shows the six perils with the most extreme tails (largest max / p99), one panel each:
    a histogram of claim size on a log scale, the 99th and 99.9th percentiles, the cap used in the target,
    and the five largest claims in red (open claims marked, because their amount is a case reserve).

Usage (repository root):  python tools/fig_outliers.py           (about 30 seconds)
                          python tools/fig_outliers.py --top 9   (more panels)
"""
import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "figures"
BLUE, GREY, RED, ORANGE = "#0b3d63", "#9aa4ae", "#b42318", "#d4a017"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "axes.titleweight": "bold"})


def summarise(claims):
    """claims: one row per claim with columns line, peril, incurred_to_date, status."""
    c = claims[claims.incurred_to_date > 0]
    rows = []
    for (line, peril), g in c.groupby(["line", "peril"]):
        x = g.incurred_to_date.sort_values(ascending=False)
        p99, p999 = np.percentile(x, 99), np.percentile(x, 99.9)
        rows.append(dict(line=line, peril=peril, n=len(x), median=x.median(), p99=p99, p999=p999,
                         max=x.iloc[0], max_over_p99=x.iloc[0] / p99,
                         top10_share=x.iloc[:10].sum() / x.sum(),
                         open_in_top5=int((g.loc[x.index[:5], "status"] == "open").sum())))
    return pd.DataFrame(rows).sort_values("max_over_p99", ascending=False).reset_index(drop=True)


def plot(claims, table, caps, top, path):
    c = claims[claims.incurred_to_date > 0]
    sel = table.head(top)
    ncol = 3
    nrow = int(np.ceil(len(sel) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(11, 3.1 * nrow), squeeze=False)
    for ax, (_, r) in zip(axes.ravel(), sel.iterrows()):
        g = c[(c.line == r.line) & (c.peril == r.peril)]
        x = g.incurred_to_date
        bins = np.logspace(np.log10(max(x.min(), 1)), np.log10(x.max() * 1.05), 50)
        ax.hist(x, bins=bins, color=GREY)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        for v, lab, col in [(r.p99, "p99", BLUE), (r.p999, "p99.9", BLUE)]:
            ax.axvline(v, color=col, lw=1, ls="--")
            ax.text(v, ax.get_ylim()[1], f" {lab}", color=col, fontsize=7, va="top")
        cap = caps.get(r.line)
        if cap:
            ax.axvline(cap, color=ORANGE, lw=1.5)
            ax.text(cap, ax.get_ylim()[1] * 0.3, f" cap {cap / 1e3:.0f}k", color=ORANGE, fontsize=7, va="top")
        big = g.nlargest(5, "incurred_to_date")
        for i, (_, b) in enumerate(big.iterrows()):
            ax.plot(b.incurred_to_date, 1.5 + i * 0.6, "o", color=RED, ms=5,
                    mfc="white" if b.status == "open" else RED)
        b0 = big.iloc[0]
        ax.annotate(f"{b0.incurred_to_date / 1e3:,.0f}k{' (open)' if b0.status == 'open' else ''}",
                    (b0.incurred_to_date, 1.5), xytext=(-4, 10), textcoords="offset points",
                    ha="right", fontsize=8, color=RED)
        ax.set_title(f"{r.line} · {r.peril}\nmax = {r.max_over_p99:.0f}× p99, top 10 = {r.top10_share:.0%} of cost")
        ax.set_xlabel("incurred (log)")
    for ax in axes.ravel()[len(sel):]:
        ax.axis("off")
    fig.suptitle("Where the extreme claims are: the perils with the longest tails "
                 "(red: 5 largest claims; hollow = open, amount is a reserve)", fontsize=10, weight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def load(cfg):
    from src.target import load_claims, load_policies, match_claims
    claims = load_claims(cfg["data_dir"])
    out = []
    for line in cfg["lines"]:
        p = load_policies(line, "train", cfg["data_dir"])
        m = match_claims(claims, p, line, True, cap=None)
        out.append(m.assign(line=line)[["line", "peril", "incurred_to_date", "status", "loss_year"]])
    return pd.concat(out, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args()
    from src.config import PART1 as cfg
    claims = load(cfg)
    table = summarise(claims)
    caps = {line: cfg["adj"][line]["cap"] for line in cfg["lines"]}
    OUT.mkdir(parents=True, exist_ok=True)
    plot(claims, table, caps, a.top, OUT / "fig5_outliers.png")
    pd.set_option("display.width", 160)
    fmt = table.copy()
    for col in ["median", "p99", "p999", "max"]:
        fmt[col] = (fmt[col] / 1e3).round(1)
    fmt["max_over_p99"] = fmt["max_over_p99"].round(1)
    fmt["top10_share"] = (fmt["top10_share"] * 100).round(1)
    print("Amounts in thousands; top10_share in % of the peril's total incurred.")
    print(fmt.to_string(index=False))
    print(f"\nWrote {OUT / 'fig5_outliers.png'}")


if __name__ == "__main__":
    main()
