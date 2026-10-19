"""Tweedie GLM on banded features.

Numeric features are cut into quantile bands (edges learned on the training data), so each
band gets its own relativity and missing values get their own level. Categorical features are
one-hot encoded; rare levels are pooled. With a log link, exp(coefficient) is the rating
relativity of that level against the base.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import TweedieRegressor
from sklearn.preprocessing import OneHotEncoder

from .features import feature_types


class BandedTweedieGLM:
    def __init__(self, power=1.5, alpha=1e-4, n_bands=10, min_frequency=0.002, max_iter=300,
                 drop="first", balance=False):
        """drop="first": each feature's first level is the base (ridge shrinks toward it).
        drop=None: every level gets a coefficient; ridge shrinks each feature toward its average
        level (credibility-style). Needs alpha > 0.
        balance=True: after fitting, scale all predictions by one factor k so that weighted training
        predictions sum to the training actuals (off-balance). A log-link Tweedie GLM with p != 1 does
        not do this by itself, and ridge widens the gap. k changes the level only, not relativities."""
        self.power, self.alpha, self.n_bands = power, alpha, n_bands
        self.min_frequency, self.max_iter, self.drop = min_frequency, max_iter, drop
        self.balance = balance

    # ------------------------------------------------------------ banding
    def _fit_bands(self, X):
        self.num_, self.cat_ = feature_types(X)
        self.edges_ = {}
        for c in self.num_:
            q = X[c].quantile(np.linspace(0, 1, self.n_bands + 1)).to_numpy()
            self.edges_[c] = np.unique(q[1:-1])          # interior edges only

    def _band(self, X):
        out = pd.DataFrame(index=X.index)
        for c in self.num_:
            b = np.searchsorted(self.edges_[c], X[c].to_numpy(), side="right")
            out[c] = np.where(X[c].isna(), "missing", "b" + pd.Series(b, index=X.index).astype(str).str.zfill(2))
        for c in self.cat_:
            out[c] = X[c].astype("string").fillna("missing")
        return out.astype(str)

    # ---------------------------------------------------------- fit/predict
    def fit(self, X, y_rate, weight):
        """X: features (no row_id); y_rate: target / weight; weight: exposure x completeness."""
        self._fit_bands(X)
        B = self._band(X)
        self.enc_ = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=self.min_frequency,
                                  drop=self.drop, sparse_output=True)
        Z = self.enc_.fit_transform(B)
        self.model_ = TweedieRegressor(power=self.power, link="log", alpha=self.alpha,
                                       max_iter=self.max_iter, solver="newton-cholesky")
        self.model_.fit(Z, y_rate, sample_weight=weight)
        self.k_ = 1.0
        if self.balance:
            w = np.asarray(weight, float)
            self.k_ = float(np.sum(np.asarray(y_rate, float) * w) / np.sum(self.model_.predict(Z) * w))
        return self

    def predict_rate(self, X):
        return self.k_ * self.model_.predict(self.enc_.transform(self._band(X)))

    def relativities(self):
        """exp(coefficient) for each encoded level: against the first level (drop="first") or the
        feature's average level (drop=None)."""
        names = self.enc_.get_feature_names_out()
        feats = sorted(self.enc_.feature_names_in_, key=len, reverse=True)
        feature = [next(f for f in feats if n.startswith(f + "_")) for n in names]
        level = [n[len(f) + 1:] for n, f in zip(names, feature)]
        return pd.DataFrame({"feature": feature, "level": level,
                             "relativity": np.exp(self.model_.coef_)})
