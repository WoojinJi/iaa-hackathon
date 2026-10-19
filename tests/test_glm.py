"""Tests for src/glm.py (balance correction).

Run from the repository root:  pytest -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.glm import BandedTweedieGLM  # noqa: E402


def toy(n=4000, seed=0):
    """Two features with known effects: region B costs 2x region A; rate rises with x."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"region": rng.choice(["A", "B"], n), "x": rng.uniform(0, 1, n)})
    mu = 100 * np.where(X.region == "B", 2.0, 1.0) * np.exp(X.x)
    w = rng.uniform(0.5, 1.0, n)
    # Tweedie-like target: many zeros, some large values
    claims = rng.poisson(0.1 * w)
    y = np.where(claims > 0, rng.gamma(2.0, mu * w / 0.1 / 2.0 / np.maximum(claims, 1)) * claims, 0.0)
    return X, y / w, w


def test_balance_makes_training_total_match():
    # Hand rule: with balance=True, sum(pred_rate * w) over training rows = sum(actual cost)
    X, y_rate, w = toy()
    m = BandedTweedieGLM(alpha=1.0, n_bands=5, drop=None, balance=True).fit(X, y_rate, w)
    assert np.isclose(np.sum(m.predict_rate(X) * w), np.sum(y_rate * w), rtol=1e-9)


def test_balance_changes_level_only():
    # Same fit with and without balance: predictions differ by the single factor k on every row,
    # so ratios between rows (relativities) are identical.
    X, y_rate, w = toy()
    raw = BandedTweedieGLM(alpha=1.0, n_bands=5, drop=None).fit(X, y_rate, w)
    bal = BandedTweedieGLM(alpha=1.0, n_bands=5, drop=None, balance=True).fit(X, y_rate, w)
    ratio = bal.predict_rate(X) / raw.predict_rate(X)
    assert np.allclose(ratio, bal.k_) and raw.k_ == 1.0


def test_strong_ridge_lowers_total_without_balance():
    # The reason for the correction: shrinking log-relativities lowers the money total (k > 1).
    X, y_rate, w = toy()
    m = BandedTweedieGLM(alpha=1.0, n_bands=5, drop=None, balance=True).fit(X, y_rate, w)
    assert m.k_ > 1.0
