"""Corrections to a market's raw tables that are not part of the target definition (DECISIONS.md Oct 23)."""


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
