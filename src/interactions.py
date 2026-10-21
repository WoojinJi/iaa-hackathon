"""Interactions for the GLM as coarse cross-classified factors (experiment E7, DECISIONS.md Oct 21).

Each pair (a, b) becomes one categorical column "a*b" whose levels are band(a) | band(b): 5 quantile bands
for a numeric feature (learned on the training data), the levels themselves for a categorical one, and
"na" for missing. The GLM's ridge penalty shrinks thinly populated cells toward the average, and the
result is still a rating table: one relativity per combination of the two bands.
"""
import numpy as np
import pandas as pd

BANDS = 5


def coarse(s_fit, s, bands=BANDS):
    """Coarse bands learned on s_fit, applied to s."""
    if pd.api.types.is_numeric_dtype(s_fit) and not pd.api.types.is_bool_dtype(s_fit) and s_fit.nunique() > bands:
        edges = np.unique(s_fit.quantile(np.linspace(0, 1, bands + 1)).to_numpy()[1:-1])
        out = pd.Series(np.searchsorted(edges, s.to_numpy(), side="right"), index=s.index).astype(str)
        return out.where(s.notna(), "na")
    return s.astype("string").fillna("na").astype(str)


def pair_name(a, b):
    return f"{a}*{b}"


def add_pairs(fit, frames, pairs, bands=BANDS):
    """Add one cross-classified column per pair to every frame; bands learned on `fit` (training data)."""
    out = []
    for f in frames:
        f = f.copy()
        for a, b in pairs:
            f[pair_name(a, b)] = coarse(fit[a], f[a], bands) + "|" + coarse(fit[b], f[b], bands)
        out.append(f)
    return out
