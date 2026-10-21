"""Large-loss loading from a fitted Pareto tail (DECISIONS.md, Oct 19: motor large-loss loading).

Individual claims are capped for modelling; the capped-off cost is put back as a loading. With few
very large claims the observed capped-off cost is unstable (one open 11.9m claim was 96% of it), so the
loading is taken from a Pareto tail fitted above a threshold u:

    alpha = n / sum(ln(x_i / u))                         (maximum likelihood, x_i > u)
    E[(X - c)+ | X > u] = u^alpha c^(1 - alpha) / (alpha - 1)   (c = cap >= u, alpha > 1)
    loading per unit of weight = (claims above u / total weight) x E[(X - c)+ | X > u]
"""
import numpy as np


def pareto_alpha(x, u):
    x = np.asarray(x, float)
    x = x[x > u]
    if len(x) == 0:
        raise ValueError("no claims above the threshold")
    return len(x) / np.log(x / u).sum(), len(x)


def expected_excess(u, cap, alpha):
    """E[(X - cap)+ | X > u] for a Pareto tail with scale u and shape alpha (> 1)."""
    if alpha <= 1:
        raise ValueError("alpha must exceed 1 for a finite mean")
    return u ** alpha * cap ** (1 - alpha) / (alpha - 1)


def pareto_loading(amounts, total_weight, u, cap):
    """Loading per unit of weight. amounts: individual claims at target level (uncapped, net of excess)."""
    alpha, n = pareto_alpha(amounts, u)
    per_claim = expected_excess(u, cap, alpha)
    return {"alpha": alpha, "n_above": n, "excess_per_claim": per_claim,
            "loading": n / total_weight * per_claim}
