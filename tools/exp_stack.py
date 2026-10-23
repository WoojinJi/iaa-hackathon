"""Experiment E10: a stacked black box (LightGBM + CatBoost + XGBoost + neural network) next to v11.

Purpose (team decision, Oct 22): the strongest black box we can reasonably build, so the comparison with our
transparent model is fair. E9 (one LightGBM at maximum capacity) scored 0.11602, but a judge could say it was
simply badly tuned. Here every base model is tuned on the held-out last training year, and the four are
combined by weights chosen on that year. When it is wrong, there is no rating table to say why: that is the
point of the comparison.

Written before the result (record in DECISIONS.md): "The stack scores at least as well as v11 in validation,
but when it is wrong we cannot say why, and its errors fall on the safest customers."

Same as v11 (the comparison isolates the model):
  target (2025 level, completeness weight, caps), large-loss loading, average weather, claim history;
  leakage still excluded. Features as in E9: everything except leaking fields, relative premium in all lines.
Base models (all Tweedie p = 1.5, weighted by exposure x completeness, scaled so training totals match):
  lgb   LightGBM, 31 leaves, 1,000 per leaf, L2 10
  cat   CatBoost, depth 6, native categorical handling
  xgb   XGBoost, depth 6, native categorical handling
  mlp   neural network: embeddings for categorical features, 2 hidden layers (256, 128), Tweedie deviance loss
Per fold: each model is fitted on the training years before the last, stopped early on the last training
year; stack weights (non-negative, sum 1) maximise D2 on that year; each model is refitted on all training
years with its chosen length; the stack is evaluated on the validation year.

Usage (repository root, terminal):
  python tools/exp_stack.py --validate                     # folds 2023 / 2024, all lines (about 1-2 hours)
  python tools/exp_stack.py --validate --lines buildings   # one line
  python tools/exp_stack.py --validate --models lgb cat xgb   # without the neural network (faster)
  python tools/exp_stack.py --out submissions/stack_experiment.csv --compare submissions/v11.csv
"""
import argparse
import copy
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.config import GBM_BASE, PART1  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.pipeline import apply_loading, build_line, compare, log, prep2, predict_rate  # noqa: E402
from src.target import load_claims  # noqa: E402
from exp_blackbox import blackbox_config  # noqa: E402

P = 1.5
ALL_MODELS = ["lgb", "cat", "xgb", "mlp"]
SEED = 42


# --------------------------------------------------------------------------- helpers
def d2(y, mu, w):
    """Tweedie D2 on amounts (rate x weight), as src.evaluate: baseline = one rate for every row."""
    a = y * w

    def dev(m):
        m = np.maximum(m, 1e-12)
        t = np.where(a > 0, a ** (2 - P) / ((1 - P) * (2 - P)), 0.0)
        return 2 * np.sum(t - a * m ** (1 - P) / (1 - P) + m ** (2 - P) / (2 - P))
    return 1 - dev(mu * w) / dev(a.sum() / w.sum() * w)


def balance(tr, rate):
    return tr.target.sum() / (rate * tr.weight).sum()


def split(tr):
    last = tr.year.max()
    return tr[tr.year < last], tr[tr.year == last]


# --------------------------------------------------------------------------- base models
class LGB:
    params = dict(GBM_BASE, num_leaves=31, min_data_in_leaf=1000, lambda_l2=10.0, learning_rate=0.03, seed=SEED)

    def fit(self, tr, feats, n=None, valid=None):
        X, self.cats = prep2(tr[feats])
        dt = lgb.Dataset(X, tr.target / tr.weight, weight=tr.weight)
        if n is None:
            Xv, _ = prep2(valid[feats], self.cats)
            dv = lgb.Dataset(Xv, valid.target / valid.weight, weight=valid.weight, reference=dt)
            self.m = lgb.train(self.params, dt, 5000, valid_sets=[dv],
                               callbacks=[lgb.early_stopping(200, verbose=False)])
            self.n = max(self.m.best_iteration, 1)
        else:
            self.m, self.n = lgb.train(self.params, dt, n), n
        self.k = balance(tr, self._raw(tr, feats))
        return self

    def _raw(self, d, feats):
        X, _ = prep2(d[feats], self.cats)
        return self.m.predict(X, num_iteration=self.n)

    def predict(self, d, feats):
        return self._raw(d, feats) * self.k


def _cat_frame(d, feats, cat_cols):
    X = d[feats].copy()
    for c in cat_cols:
        X[c] = X[c].astype("string").fillna("NA").astype(str)
    for c in X.columns:
        if pd.api.types.is_bool_dtype(X[c]):
            X[c] = X[c].astype(int)
    return X


class CAT:
    def fit(self, tr, feats, n=None, valid=None):
        from catboost import CatBoostRegressor, Pool
        X0, cats = prep2(tr[feats])
        self.cat_cols = list(cats)
        pool = Pool(_cat_frame(tr, feats, self.cat_cols), tr.target / tr.weight, weight=tr.weight,
                    cat_features=self.cat_cols)
        args = dict(loss_function=f"Tweedie:variance_power={P}", depth=6, learning_rate=0.05,
                    l2_leaf_reg=10, random_seed=SEED, verbose=False, thread_count=-1)
        if n is None:
            vpool = Pool(_cat_frame(valid, feats, self.cat_cols), valid.target / valid.weight,
                         weight=valid.weight, cat_features=self.cat_cols)
            self.m = CatBoostRegressor(iterations=3000, od_type="Iter", od_wait=150, **args)
            self.m.fit(pool, eval_set=vpool, use_best_model=True)
            self.n = max(self.m.get_best_iteration() or self.m.tree_count_, 1)
        else:
            self.m, self.n = CatBoostRegressor(iterations=n, **args), n
            self.m.fit(pool)
        self.k = balance(tr, self._raw(tr, feats))
        return self

    def _raw(self, d, feats):
        from catboost import Pool
        pool = Pool(_cat_frame(d, feats, self.cat_cols), cat_features=self.cat_cols)
        return self.m.predict(pool, prediction_type="Exponent")

    def predict(self, d, feats):
        return self._raw(d, feats) * self.k


def _xgb_frame(d, feats, cats=None):
    """prep2, then categorical columns with no level in training (e.g. history before it is observable)
    become an all-missing numeric column: XGBoost refuses a categorical feature without categories."""
    X, cats = prep2(d[feats], cats)
    for c, levels in cats.items():
        if len(levels) == 0:
            X[c] = np.nan
    return X, cats


class XGB:
    params = dict(objective="reg:tweedie", tweedie_variance_power=P, eta=0.05, max_depth=6,
                  min_child_weight=50, subsample=0.8, colsample_bytree=0.8, reg_lambda=10,
                  tree_method="hist", max_cat_to_onehot=8, seed=SEED, eval_metric=f"tweedie-nloglik@{P}")

    def fit(self, tr, feats, n=None, valid=None):
        import xgboost as xgb
        X, self.cats = _xgb_frame(tr, feats)
        dt = xgb.DMatrix(X, tr.target / tr.weight, weight=tr.weight, enable_categorical=True)
        if n is None:
            Xv, _ = _xgb_frame(valid, feats, self.cats)
            dv = xgb.DMatrix(Xv, valid.target / valid.weight, weight=valid.weight, enable_categorical=True)
            self.m = xgb.train(self.params, dt, 5000, evals=[(dv, "hold")], early_stopping_rounds=200,
                               verbose_eval=False)
            self.n = max(self.m.best_iteration + 1, 1)
        else:
            self.m, self.n = xgb.train(self.params, dt, n), n
        self.k = balance(tr, self._raw(tr, feats))
        return self

    def _raw(self, d, feats):
        import xgboost as xgb
        X, _ = _xgb_frame(d, feats, self.cats)
        return self.m.predict(xgb.DMatrix(X, enable_categorical=True), iteration_range=(0, self.n))

    def predict(self, d, feats):
        return self._raw(d, feats) * self.k


class MLP:
    """Embeddings for categorical features + standardised numeric features (with missing flags),
    two hidden layers, log link, Tweedie deviance loss weighted by exposure x completeness."""
    max_epochs, patience, batch = 25, 3, 8192

    def _encode(self, d, feats, fit=False):
        import torch
        X, cats = prep2(d[feats], None if fit else self.cats)
        if fit:
            self.cats = cats
            self.num = [c for c in X.columns if c not in cats]
            num = X[self.num].astype(float)
            self.med = num.median()
            self.nan_cols = [c for c in self.num if num[c].isna().any()]
            filled = num.fillna(self.med)
            self.mu, self.sd = filled.mean(), filled.std().replace(0, 1)
        num = X[self.num].astype(float)
        flags = num[self.nan_cols].isna().astype(float).to_numpy()
        z = ((num.fillna(self.med) - self.mu) / self.sd).clip(-5, 5).to_numpy()
        xn = np.hstack([z, flags]).astype(np.float32)
        xc = np.stack([X[c].cat.codes.to_numpy() + 1 for c in self.cats], axis=1) if self.cats \
            else np.zeros((len(X), 0), dtype=np.int64)
        return torch.tensor(xn), torch.tensor(xc.astype(np.int64))

    def _net(self, n_num, sizes, bias):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(s):
                super().__init__()
                s.emb = nn.ModuleList([nn.Embedding(k + 1, min(16, (k + 2) // 2)) for k in sizes])
                width = n_num + sum(e.embedding_dim for e in s.emb)
                s.body = nn.Sequential(nn.Linear(width, 256), nn.ReLU(), nn.Dropout(0.1),
                                       nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.1), nn.Linear(128, 1))
                nn.init.constant_(s.body[-1].bias, bias)

            def forward(s, xn, xc):
                parts = [xn] + [e(xc[:, i]) for i, e in enumerate(s.emb)]
                return s.body(torch.cat(parts, dim=1)).squeeze(1)
        return Net()

    @staticmethod
    def _loss(f, y, w):
        import torch
        mu1 = torch.exp((1 - P) * f)
        mu2 = torch.exp((2 - P) * f)
        return torch.sum(w * (-y * mu1 / (1 - P) + mu2 / (2 - P))) / torch.sum(w)

    def _epoch(self, net, opt, xn, xc, y, w, g):
        import torch
        net.train()
        idx = torch.randperm(len(y), generator=g)
        for s in range(0, len(y), self.batch):
            b = idx[s:s + self.batch]
            opt.zero_grad()
            loss = self._loss(net(xn[b], xc[b]), y[b], w[b])
            loss.backward()
            opt.step()

    def _score(self, net, xn, xc, y, w):
        import torch
        net.eval()
        with torch.no_grad():
            return float(self._loss(net(xn, xc), y, w))

    def fit(self, tr, feats, n=None, valid=None):
        import torch
        # one thread: on macOS, PyTorch's OpenMP can deadlock next to LightGBM / XGBoost's in one process
        torch.set_num_threads(1)
        torch.manual_seed(SEED)
        g = torch.Generator().manual_seed(SEED)
        xn, xc = self._encode(tr, feats, fit=True)
        y = torch.tensor((tr.target / tr.weight).to_numpy(np.float32))
        w = torch.tensor(tr.weight.to_numpy(np.float32))
        bias = float(np.log(max(tr.target.sum() / tr.weight.sum(), 1e-6)))
        sizes = [len(v) for v in self.cats.values()]
        self.net = self._net(xn.shape[1], sizes, bias)
        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3, weight_decay=1e-5)
        if n is None:
            vn, vc = self._encode(valid, feats)
            vy = torch.tensor((valid.target / valid.weight).to_numpy(np.float32))
            vw = torch.tensor(valid.weight.to_numpy(np.float32))
            best, best_state, best_ep, bad = np.inf, None, 1, 0
            for ep in range(1, self.max_epochs + 1):
                self._epoch(self.net, opt, xn, xc, y, w, g)
                s = self._score(self.net, vn, vc, vy, vw)
                log(f"  mlp epoch {ep}: holdout loss {s:.6f}")
                if s < best - 1e-6:
                    best, best_ep, bad = s, ep, 0
                    best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
            self.net.load_state_dict(best_state)
            self.n = best_ep
        else:
            for ep in range(1, n + 1):
                self._epoch(self.net, opt, xn, xc, y, w, g)
                log(f"  mlp refit epoch {ep} of {n}")
            self.n = n
        self.k = balance(tr, self._raw(tr, feats))
        return self

    def _raw(self, d, feats):
        import torch
        xn, xc = self._encode(d, feats)
        self.net.eval()
        with torch.no_grad():
            return np.exp(self.net(xn, xc).numpy().astype(float))

    def predict(self, d, feats):
        return self._raw(d, feats) * self.k


MODELS = {"lgb": LGB, "cat": CAT, "xgb": XGB, "mlp": MLP}


# --------------------------------------------------------------------------- stacking
def stack_weights(H, y, w, step=0.05):
    """Non-negative weights summing to 1 that maximise D2 on the holdout (coordinate search on a grid)."""
    m = H.shape[1]
    best_w = np.full(m, 1 / m)
    best = d2(y, H @ best_w, w)
    for _ in range(30):
        improved = False
        for i in range(m):
            for j in range(m):
                if i == j or best_w[j] < step - 1e-12:
                    continue
                cand = best_w.copy()
                cand[i] += step
                cand[j] -= step
                s = d2(y, H @ cand, w)
                if s > best + 1e-9:
                    best, best_w, improved = s, cand, True
        if not improved:
            break
    return best_w, best


def fit_stack(tr, feats, models, tag=""):
    """Choose lengths and stack weights on the last training year, then refit every model on all of tr."""
    inner, hold = split(tr)
    hy, hw = (hold.target / hold.weight).to_numpy(), hold.weight.to_numpy()
    H, lengths, single = [], {}, {}
    for name in models:
        t0 = time.time()
        m = MODELS[name]().fit(inner, feats, valid=hold)
        h = m.predict(hold, feats)
        H.append(h)
        n = m.n if name == "mlp" else max(int(m.n * 1.1), 1)    # more data in the refit
        lengths[name] = n
        single[name] = d2(hy, h, hw)
        log(f"{tag}{name}: length {m.n} on {int(hold.year.iloc[0])}, D2 there {single[name]:.4f} "
            f"({time.time() - t0:.0f}s)")
    weights, s = stack_weights(np.column_stack(H), hy, hw)
    log(f"{tag}stack weights " + ", ".join(f"{n} {x:.2f}" for n, x in zip(models, weights)) + f"; D2 {s:.4f}")
    fitted = {}
    for name, wt in zip(models, weights):
        if wt > 1e-9:
            t0 = time.time()
            fitted[name] = MODELS[name]().fit(tr, feats, n=lengths[name])
            log(f"{tag}{name}: refitted on all training years ({time.time() - t0:.0f}s)")
    return {"models": fitted, "weights": dict(zip(models, weights)), "holdout_d2": single}


def predict_stack(st, d, feats):
    parts = {n: m.predict(d, feats) for n, m in st["models"].items()}
    rate = sum(st["weights"][n] * p for n, p in parts.items())
    return rate, parts


# --------------------------------------------------------------------------- runs
def metrics(va, rate):
    r = evaluate(va.target, rate * va.weight.to_numpy(), va.weight, show=False)
    lf = r["lift"]["A/E"]
    return {"D2": r["D2"], "A/E": r["A/E"], "low": lf.iloc[0], "top": lf.iloc[-1]}


def validate(lines, models, data_dir=None, with_v11=True):
    cfg_s, cfg_v = blackbox_config(), copy.deepcopy(PART1)
    if data_dir:
        cfg_s["data_dir"] = cfg_v["data_dir"] = Path(data_dir)
    claims = load_claims(cfg_s["data_dir"])
    rows = []
    for line in lines:
        ds = build_line(line, cfg_s, claims)
        dv = build_line(line, cfg_v, claims) if with_v11 else None
        for vy, tys in cfg_s["folds"]:
            tr, va = ds["tr"][ds["tr"].year.isin(tys)], ds["tr"][ds["tr"].year == vy]
            st = fit_stack(tr, ds["feats"], models, tag=f"{line} {vy} ")
            rate, parts = predict_stack(st, va, ds["feats"])
            rows.append({"line": line, "year": vy, "model": "stack", **metrics(va, rate),
                         "weights": " ".join(f"{n}:{w:.2f}" for n, w in st["weights"].items())})
            for n, p in parts.items():
                rows.append({"line": line, "year": vy, "model": n, **metrics(va, p), "weights": ""})
            if with_v11:
                trv, vav = dv["tr"][dv["tr"].year.isin(tys)], dv["tr"][dv["tr"].year == vy]
                rv, _ = predict_rate(line, cfg_v, trv, vav, dv["feats"])
                rows.append({"line": line, "year": vy, "model": "v11 (ours)", **metrics(vav, rv), "weights": ""})
    r = pd.DataFrame(rows)
    t = r.pivot_table(index=["line", "model"], columns="year", values=["D2", "A/E", "low", "top"])
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    t["D2_avg"] = t[[c for c in t.columns if c.startswith("D2_")]].mean(axis=1)
    print("\nOut-of-time validation (low / top = A/E of the safest / riskiest 10%; below 1 = over-priced)")
    print(t.round(4).to_string())
    print("\nStack weights by fold:")
    print(r[r.model == "stack"][["line", "year", "weights"]].to_string(index=False))
    if with_v11:
        print("\nStack minus v11 (D2 average) and the worst tail distance from 1:")
        tail = lambda x: max(abs(x[c] - 1) for c in x.index if c.startswith(("low_", "top_")))
        for line in lines:
            a, b = t.loc[(line, "v11 (ours)")], t.loc[(line, "stack")]
            print(f"  {line:9s} D2 {b.D2_avg - a.D2_avg:+.4f}   worst tail: v11 {tail(a):.3f} vs stack {tail(b):.3f}")
    return t


def run(out, models, data_dir=None, lines=None):
    cfg = blackbox_config()
    if data_dir:
        cfg["data_dir"] = Path(data_dir)
    claims = load_claims(cfg["data_dir"])
    sample = pd.read_parquet(Path(cfg["data_dir"]) / "sample_submission.parquet")
    id_col, val_col = sample.columns[:2]
    parts = []
    for line in lines or cfg["lines"]:
        t0 = time.time()
        d = build_line(line, cfg, claims)
        st = fit_stack(d["tr"], d["feats"], models, tag=f"{line} ")
        rate, _ = predict_stack(st, d["te"], d["feats"])
        rate, load_info = apply_loading(line, cfg, rate, d["tr"], d, claims)
        expo = d["te"].exposure_clean.to_numpy()
        pred = np.maximum(rate * expo, 0)
        log(f"{line}: stack; {load_info}; total {pred.sum():,.0f} ({time.time() - t0:.0f}s)")
        parts.append(pd.DataFrame({id_col: d["te"].row_id.to_numpy(), val_col: pred}))
    sub = sample[[id_col]].merge(pd.concat(parts), on=id_col, how="left")
    assert len(sub) == len(sample) and sub[val_col].notna().all(), "every sample row needs a prediction"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(out, index=False)
    log(f"saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the stack submission here (experiment only)")
    ap.add_argument("--compare", help="compare with this submission (e.g. submissions/v11.csv)")
    ap.add_argument("--validate", action="store_true", help="out-of-time folds, stack vs v11")
    ap.add_argument("--lines", nargs="+", default=list(PART1["lines"]))
    ap.add_argument("--models", nargs="+", default=ALL_MODELS, choices=ALL_MODELS)
    ap.add_argument("--no-v11", action="store_true", help="skip the v11 rows in validation")
    ap.add_argument("--data", help="data directory (default: the config's)")
    a = ap.parse_args([] if "ipykernel" in sys.modules else None)
    if a.validate:
        validate(a.lines, a.models, a.data, not a.no_v11)
        return
    if not a.out:
        ap.error("give --out or --validate")
    run(a.out, a.models, a.data, a.lines)
    if a.compare:
        compare(a.compare, a.out)


if __name__ == "__main__":
    main()
