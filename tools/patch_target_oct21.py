"""Patch for src/target.py (Oct 21). Run once from the repository root:  python tools/patch_target_oct21.py

Adds options without changing any result by default:
  1. adjust_claims: steps (reform, frequency shift) apply to losses before adj["reform_date"]
     (default 1 January of REFORM_YEAR, identical to the previous loss_year < 2023), so a mid-year
     change can be split at its own date (Part 2 playbook).
  2. completeness(method="lynden_bell"): report-lag pattern from all loss years, each claim observed
     up to its own window (corrects right truncation; notebook 15, rule R1). Passed through
     year_completeness and build_model_target(completeness_method=...). Default stays "ref_year".
  3. valuation_date and years can be passed to year_completeness / build_model_target, so another
     market's data (Part 2) does not use Part 1's valuation date.
Every replacement checks that the old text occurs exactly once, so the patch stops if the file differs.
"""
from pathlib import Path

f = Path("src/target.py")
s = f.read_text()

REPL = [
    # 1. Lynden-Bell estimator + method option on completeness
    ('''def completeness(matched, peril, year, ref_year=2021,
                 valuation_date=VALUATION_DATE, weight_col=None):
    """Share of a loss year's claims expected to be reported by the valuation date.

    Uses the report-lag distribution of `ref_year` losses (the most mature year),
    assuming losses are spread evenly over the year. With weight_col (e.g. "net_cap")
    the share is amount-weighted instead of count-based.
    """
''',
     '''def lag_cdf_lynden_bell(lag, window):
    """Report-lag distribution under right truncation: a claim is seen only if lag <= its window
    (valuation date - loss date). Lynden-Bell estimator:
    F(t) = prod_{s > t} (1 - d(s) / R(s)),  R(s) = #{lag <= s <= window},  d(s) = #{lag = s}.
    Returns a function of t (days). F is relative to the longest lag that can be observed."""
    lag, window = np.asarray(lag, float), np.asarray(window, float)
    s, d = np.unique(lag, return_counts=True)
    R = np.searchsorted(np.sort(lag), s, side="right") - np.searchsorted(np.sort(window), s, side="left")
    logq = np.log(np.clip(1 - d / R, 1e-12, 1))
    tail = np.concatenate([np.cumsum(logq[::-1])[::-1][1:], [0.0]])   # sum over s_j > s_k

    def F(t):
        k = np.searchsorted(s, np.asarray(t, float), side="right") - 1
        return np.where(k >= 0, np.exp(tail[np.clip(k, 0, None)]), 0.0)
    return F


def completeness(matched, peril, year, ref_year=2021,
                 valuation_date=VALUATION_DATE, weight_col=None, method="ref_year"):
    """Share of a loss year's claims expected to be reported by the valuation date.

    method="ref_year": report-lag distribution of `ref_year` losses (the most mature year),
    assuming losses are spread evenly over the year. With weight_col (e.g. "net_cap")
    the share is amount-weighted instead of count-based.
    method="lynden_bell": lag distribution from all loss years of the peril, each claim observed
    only up to its own window, which corrects the right truncation of the ref_year pattern
    (count-based; notebook 15: within 0.3 points of ref_year on Part 1 data).
    """
    if method == "lynden_bell":
        ref = matched[matched["peril"] == peril]
        if ref.empty:
            return 1.0
        F = lag_cdf_lynden_bell(ref["report_lag"], (valuation_date - ref["loss_date"]).dt.days)
        ages = (valuation_date - pd.date_range(f"{year}-01-01", f"{year}-12-31")).days.to_numpy()
        return float(F(ages).mean())
    if method != "ref_year":
        raise ValueError(method)
'''),
    # 2. reform date
    ('''    c = matched.copy()
    pre = c["loss_year"] < reform_year
''',
     '''    c = matched.copy()
    # steps apply to losses before the break date (default 1 January of reform_year; a mid-year
    # change in another market is split at its own date: adj["reform_date"])
    pre = c["loss_date"] < pd.Timestamp(adj.get("reform_date", f"{reform_year}-01-01"))
'''),
    # 3. year_completeness passes the method
    ('''def year_completeness(adjusted, years=YEARS):
    """Line-level completeness by loss year: reported / ultimate, on adjusted amounts."""''',
     '''def year_completeness(adjusted, years=YEARS, method="ref_year", valuation_date=VALUATION_DATE):
    """Line-level completeness by loss year: reported / ultimate, on adjusted amounts."""'''),
    ('''        ult = sum(rep.loc[rep["peril"] == p, "net_adj"].sum() / completeness(adjusted, p, y)''',
     '''        ult = sum(rep.loc[rep["peril"] == p, "net_adj"].sum() / completeness(adjusted, p, y, valuation_date=valuation_date,
                                                                    method=method)'''),
    # 4. build_model_target passes the method
    ('''def build_model_target(claims, policies, line="motor", adj=None, excess_on_liability=True):''',
     '''def build_model_target(claims, policies, line="motor", adj=None, excess_on_liability=True,
                       completeness_method="ref_year", valuation_date=VALUATION_DATE, years=YEARS):'''),
    ('''    comp = year_completeness(mc)''',
     '''    comp = year_completeness(mc, years=years, method=completeness_method, valuation_date=valuation_date)'''),
]

for old, new in REPL:
    n = s.count(old)
    assert n == 1, f"expected the text once, found {n} times:\n{old[:120]}"
    s = s.replace(old, new)
f.write_text(s)
print("src/target.py patched (6 replacements). Run: pytest -q")
