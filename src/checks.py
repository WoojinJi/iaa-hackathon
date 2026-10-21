"""Day 1 checks for a market's data (docs/PART2_PLAYBOOK.md): look before modelling. No model is fitted.

Sections of the report:
  1 schema           tables, columns, types, perils, statuses; differences from a reference schema
  2 data quality     exposure errors, duplicates, claims outside periods, dates, amounts, missing values
  3 completeness     by peril and year: 2021-pattern ("ref_year") vs Lynden-Bell (all years)
  4 reporting speed  share reported within 30 / 90 / 180 days, by loss half-year
  5 step scan        quarterly claim series (frequency; severity by loss / report / policy-start date;
                     closed-claim severity), trend + one step vs trend only (dBIC)
  6 policy scan      monthly averages and shares by policy start, with month-of-year effects
  7 leakage          same-year vs next-year correlation with claims; train vs test distribution
Rules (from Part 1, fixed in advance): a claim step is flagged if dBIC >= 10 and >= 5%; a policy step if
dBIC >= 10 and >= 3%; a leakage suspect if same-year correlation >= 2x next-year and >= 0.05, or if the
test mean differs from the last training year by more than 20%. Flags are for investigation; nothing
in the target changes from this report alone.

Usage (repository root):
  python -m src.checks --out results/checks_part1
  python -m src.checks --out results/checks_part2 --data <part2 data dir> --reference results/checks_part1/schema.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .target import DATA_DIR, DUP_KEY, LINES, completeness, load_claims, load_policies, match_claims

L = 180                 # equal maturity: claims reported within L days of loss
MIN_COUNT = 60          # skip quarterly claim series with a median count below this


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# --------------------------------------------------------------- 1 schema
def schema(data_dir):
    out = {}
    for f in sorted(Path(data_dir).glob("*.parquet")):
        df = pd.read_parquet(f)
        out[f.name] = {"rows": len(df), "columns": {c: str(t) for c, t in df.dtypes.items()}}
    c = pd.read_parquet(Path(data_dir) / "claims.parquet")
    out["_perils"] = {ln: sorted(c.loc[c.line == ln, "peril"].unique().tolist()) for ln in sorted(c.line.unique())}
    out["_status"] = sorted(c.status.unique().tolist())
    return out


def schema_diff(new, ref):
    rows = []
    for t in sorted(set(new) | set(ref)):
        if t.startswith("_"):
            if new.get(t) != ref.get(t):
                rows.append({"table": t, "change": "values differ", "detail": f"{ref.get(t)} -> {new.get(t)}"})
            continue
        if t not in ref:
            rows.append({"table": t, "change": "new table", "detail": ""}); continue
        if t not in new:
            rows.append({"table": t, "change": "missing table", "detail": ""}); continue
        a, b = ref[t]["columns"], new[t]["columns"]
        for col in sorted(set(a) | set(b)):
            if col not in a:
                rows.append({"table": t, "change": "new column", "detail": f"{col} ({b[col]})"})
            elif col not in b:
                rows.append({"table": t, "change": "missing column", "detail": col})
            elif a[col] != b[col]:
                rows.append({"table": t, "change": "type changed", "detail": f"{col}: {a[col]} -> {b[col]}"})
    return pd.DataFrame(rows, columns=["table", "change", "detail"])


# --------------------------------------------------------- 2 data quality
def data_quality(data_dir, claims_all, valuation):
    rows, miss = [], []
    raw = pd.read_parquet(Path(data_dir) / "claims.parquet")
    for line in LINES:
        p, pt = load_policies(line, "train", data_dir), load_policies(line, "test", data_dir)
        c_line = claims_all[claims_all.line == line]
        m = match_claims(c_line, p, line, True, cap=None)
        r = raw[raw.line == line]
        dup = r.duplicated(subset=DUP_KEY, keep="first").sum()
        rows.append({
            "line": line, "train rows": len(p), "test rows": len(pt),
            "years": f"{p.year.min()}-{p.year.max()}",
            "exposure not consistent with dates": f"{(p.exp_flag != 'ok').mean():.2%}",
            "test exposure not consistent": f"{(pt.exp_flag != 'ok').mean():.2%}",
            "claims": len(r), "duplicates": int(dup),
            "repudiated": f"{(r.status == 'repudiated').mean():.2%}",
            "outside any period": f"{1 - len(m) / max(len(c_line), 1):.2%}",
            "report before loss": int((c_line.report_lag < 0).sum()),
            "negative amounts": int((c_line[["paid_to_date", "incurred_to_date", "recoveries"]] < 0).any(axis=1).sum()),
            "closed with paid != incurred": f"{((c_line.status == 'closed') & ~np.isclose(c_line.paid_to_date, c_line.incurred_to_date)).mean():.2%}",
            "open share": f"{(c_line.status == 'open').mean():.2%}",
        })
        na = p.isna().mean()
        for col, v in na[na > 0].sort_values(ascending=False).head(8).items():
            miss.append({"line": line, "column": col, "missing (train)": f"{v:.1%}",
                         "missing (test)": f"{pt[col].isna().mean():.1%}" if col in pt else "n/a"})
    return pd.DataFrame(rows).set_index("line").T, pd.DataFrame(miss)


# ------------------------------------------------- 3-4 completeness, speed
def completeness_table(m, valuation, years):
    rows = []
    for per in sorted(m.peril.unique()):
        for y in years:
            rows.append({"peril": per, "year": y,
                         "ref_year": completeness(m, per, y, ref_year=min(years), valuation_date=valuation),
                         "lynden_bell": completeness(m, per, y, valuation_date=valuation, method="lynden_bell")})
    t = pd.DataFrame(rows)
    return t.pivot(index="peril", columns="year", values=["ref_year", "lynden_bell"]).round(3)


def reporting_speed(m, valuation):
    rows = []
    m = m.assign(half=m.loss_date.dt.year.astype(str) + np.where(m.loss_date.dt.month <= 6, "H1", "H2"))
    for (per, half), g in m.groupby(["peril", "half"]):
        end = pd.Timestamp(f"{half[:4]}-{'06-30' if half.endswith('H1') else '12-31'}")
        if end + pd.Timedelta(days=365) > valuation:
            continue
        s = g[g.report_lag <= 365].report_lag
        if len(s) < 100:
            continue
        rows.append({"peril": per, "loss half": half, "n": len(s), "30d": (s <= 30).mean(),
                     "90d": (s <= 90).mean(), "180d": (s <= 180).mean()})
    return pd.DataFrame(rows).round(3)


# ---------------------------------------------------------- 5-6 step scans
def step_test(y, w, n_season, period):
    """log series ~ trend (+ season) vs + one step; returns the best break and dBIC."""
    y = np.asarray(y, float); T = len(y); t = np.arange(T)
    w = np.nan_to_num(np.asarray(w, float)); ok = np.isfinite(y) & (y > 0) & (w > 0)
    if ok.sum() < 12:
        return None
    ly = np.log(np.where(ok, y, 1.0))
    cols = [np.ones(T), t / period] + [(t % n_season == j).astype(float) for j in range(1, n_season)]
    X0 = np.column_stack(cols)

    def fit(X):
        sw = np.sqrt(w[ok]); b, *_ = np.linalg.lstsq(X[ok] * sw[:, None], ly[ok] * sw, rcond=None)
        return max((((ly[ok] - X[ok] @ b) * sw) ** 2).sum(), 1e-12), b

    s0, _ = fit(X0); best = None
    for k in range(3, T - 2):
        s1, b1 = fit(np.column_stack([X0, (t >= k).astype(float)]))
        if best is None or s1 < best[0]:
            best = (s1, k, b1)
    n = ok.sum()
    return {"k": best[1], "step": float(np.exp(best[2][-1])), "trend_pa": float(np.exp(best[2][1]) - 1),
            "dbic": float(n * np.log(s0 / best[0]) - 2 * np.log(n))}


def exposure_by_period(p, periods):
    s, e = p.period_start.to_numpy(), p.period_end.to_numpy()
    scale = (p.exposure_clean / p.days).to_numpy()
    out = []
    for q in periods:
        ms, me = np.datetime64(q.start_time.date()), np.datetime64(q.end_time.date())
        ov = (np.minimum(e, me) - np.maximum(s, ms)).astype("timedelta64[D]").astype(int) + 1
        out.append((np.clip(ov, 0, None) * scale).sum())
    return pd.Series(out, index=periods)


def claim_scan(line, p, m, valuation, min_count=MIN_COUNT):
    last = (valuation - pd.Timedelta(days=L)).to_period("Q") - 1
    Q = pd.period_range(f"{p.year.min()}Q1", last, freq="Q")
    expo = exposure_by_period(p, Q)
    m = m.assign(lq=m.loss_date.dt.to_period("Q"), rq=m.report_date.dt.to_period("Q"),
                 pq=m.period_start.dt.to_period("Q"))
    mat = m[(m.report_lag <= L) & (m.lq >= Q[0]) & (m.lq <= Q[-1]) & (m.status != "repudiated")]
    rows = []
    for per, g in mat.groupby("peril"):
        cnt = g.groupby("lq").size().reindex(Q, fill_value=0)
        if cnt.median() < min_count:
            continue
        series = [("frequency", "loss date", cnt / expo, cnt, 4)]
        cap = g.incurred_to_date.quantile(0.995)
        s = g[g.incurred_to_date > 0].assign(sev=lambda d: d.incurred_to_date.clip(upper=cap))
        for basis, col in [("loss date", "lq"), ("report date", "rq"), ("policy start", "pq")]:
            a = s.groupby(col).sev.agg(["mean", "size"]).reindex(Q)
            series.append(("severity", basis, a["mean"], a["size"], 1))
        a = s[s.status == "closed"].groupby("lq").sev.agg(["mean", "size"]).reindex(Q)
        series.append(("severity (closed)", "loss date", a["mean"], a["size"], 1))
        for meas, basis, y, w, ns in series:
            r = step_test(y.to_numpy(), w.to_numpy(), ns, 4)
            if r:
                rows.append({"line": line, "peril": per, "measure": meas, "basis": basis,
                             "break": str(Q[r["k"]]), **{k: v for k, v in r.items() if k != "k"}})
    return pd.DataFrame(rows, columns=["line", "peril", "measure", "basis", "break", "step", "trend_pa", "dbic"])


def policy_scan(line, p):
    M = pd.period_range(p.period_start.min().to_period("M"), p.period_start.max().to_period("M"), freq="M")
    pm = p.period_start.dt.to_period("M")
    pp = p.assign(premium_per_year=p.written_premium / p.exposure_clean) if "written_premium" in p else p
    skip = {"exposure", "days", "exp_dates", "exposure_clean", "year", "row_id"}
    rows = []
    for c in pp.columns:
        if c in skip or c.endswith("_id"):
            continue
        col = pp[c]
        cand = []
        if pd.api.types.is_bool_dtype(col):
            cand = [(f"share {c}", col.astype(float))]
        elif pd.api.types.is_numeric_dtype(col):
            cand = [(f"mean {c}", col)]
        elif 2 <= col.nunique() <= 8:
            cand = [(f"share {c}={lev}", (col == lev).astype(float)) for lev in col.dropna().unique()]
        for name, v in cand:
            y = v.groupby(pm).mean().reindex(M)
            if not (y > 0).all():
                continue
            r = step_test(y.to_numpy(), np.ones(len(M)), 12, 12)
            if r:
                rows.append({"line": line, "series": name, "break": str(M[r["k"]]),
                             **{k: v for k, v in r.items() if k != "k"}})
    return pd.DataFrame(rows, columns=["line", "series", "break", "step", "trend_pa", "dbic"])


# --------------------------------------------------------------- 7 leakage
def leakage(line, p, pt, m):
    claim_rows = set(m.row_id)
    d = p.assign(claim=p.row_id.isin(claim_rows).astype(int))
    nxt = d[["policy_id", "year", "claim"]].assign(year=lambda x: x.year - 1).rename(columns={"claim": "claim_next"})
    d = d.merge(nxt, on=["policy_id", "year"], how="left")
    both = d.claim_next.notna()
    skip = {"exposure", "days", "exp_dates", "exposure_clean", "year", "claim", "claim_next"}
    last = p.year.max()
    rows = []
    for c in p.columns:
        if c in skip or c.endswith("_id") or not pd.api.types.is_numeric_dtype(p[c]) or pd.api.types.is_bool_dtype(p[c]):
            continue
        x = d.loc[both, c]
        if x.nunique() < 2:
            continue
        cs = x.rank().corr(d.loc[both, "claim"].rank())
        cn = x.rank().corr(d.loc[both, "claim_next"].rank())
        t_mean = pt[c].mean() if c in pt else np.nan
        l_mean = p.loc[p.year == last, c].mean()
        rows.append({"line": line, "column": c, "corr same year": cs, "corr next year": cn,
                     "ratio": cs / cn if abs(cn) > 1e-6 else np.inf,
                     f"mean {last}": l_mean, "mean test": t_mean,
                     "test / last year": t_mean / l_mean if l_mean else np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- report
def block(title, df, note=""):
    body = df.to_string() if isinstance(df, pd.DataFrame) and len(df) else "(none)"
    return f"\n## {title}\n{note}\n```\n{body}\n```\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="results/checks_part1")
    ap.add_argument("--data", default=str(DATA_DIR))
    ap.add_argument("--reference", help="schema.json of a previous market to compare with")
    ap.add_argument("--min-count", type=int, default=MIN_COUNT, help="minimum median quarterly claims per series")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    data_dir = Path(a.data)
    parts = [f"# Data checks: {data_dir}\n"]

    sch = schema(data_dir)
    (out / "schema.json").write_text(json.dumps(sch, indent=1))
    if a.reference:
        parts.append(block("1. Schema differences from the reference", schema_diff(sch, json.loads(Path(a.reference).read_text()))))
    else:
        parts.append(block("1. Schema", pd.DataFrame({t: [v["rows"], len(v["columns"])] for t, v in sch.items()
                                                    if not t.startswith("_")}, index=["rows", "columns"]).T,
                           f"Perils: {sch['_perils']}. Statuses: {sch['_status']}."))
    log("schema")

    claims_all = load_claims(data_dir, drop_repudiated=False)
    claims_paid = claims_all[claims_all.status != "repudiated"]
    valuation = claims_all.report_date.max()
    dq, miss = data_quality(data_dir, claims_all, valuation)
    parts.append(block("2. Data quality", dq, f"Valuation date (last report date): {valuation.date()}."))
    parts.append(block("2b. Missing values (top columns)", miss))
    log("data quality")

    scans, pscans, leaks = [], [], []
    for line in LINES:
        p, pt = load_policies(line, "train", data_dir), load_policies(line, "test", data_dir)
        years = sorted(p.year.unique())
        m = match_claims(claims_paid, p, line, True, cap=None)
        parts.append(block(f"3. Completeness by peril and year — {line}", completeness_table(m, valuation, years),
                           "ref_year: lag pattern of the first year; lynden_bell: all years, truncation-corrected."))
        parts.append(block(f"4. Reporting speed (claims reported within 365 days) — {line}", reporting_speed(m, valuation)))
        mc = match_claims(claims_all, p, line, True, cap=None)
        scans.append(claim_scan(line, p, mc, valuation, a.min_count))
        pscans.append(policy_scan(line, p))
        leaks.append(leakage(line, p, pt, m))
        log(f"{line} done")

    sc = pd.concat(scans); sc.to_csv(out / "step_scan_claims.csv", index=False)
    flag = sc[(sc.dbic >= 10) & ((sc.step - 1).abs() >= 0.05)].sort_values("dbic", ascending=False)
    parts.append(block("5. Step scan, claims (quarterly) — flagged", flag.round(3),
                       f"{len(flag)} of {len(sc)} series. Loss date = law or environment; report date = handling "
                       "or reserving; policy start = product. Full table: step_scan_claims.csv."))
    ps = pd.concat(pscans); ps.to_csv(out / "step_scan_policies.csv", index=False)
    pflag = ps[(ps.dbic >= 10) & ((ps.step - 1).abs() >= 0.03)].sort_values("dbic", ascending=False)
    parts.append(block("6. Policy scan (monthly, month-of-year effects) — flagged", pflag.round(3),
                       f"{len(pflag)} of {len(ps)} series. Full table: step_scan_policies.csv."))
    lk = pd.concat(leaks); lk.to_csv(out / "leakage.csv", index=False)
    lflag = lk[((lk.ratio >= 2) & (lk["corr same year"] >= 0.05)) | ((lk["test / last year"] - 1).abs() > 0.2)]
    parts.append(block("7. Leakage suspects", lflag.round(3),
                       "Same-year correlation >= 2x next-year (and >= 0.05), or test mean > 20% from the last "
                       "training year. Full table: leakage.csv."))
    (out / "report.md").write_text("".join(parts))
    log(f"report written: {out / 'report.md'}")


if __name__ == "__main__":
    main()
