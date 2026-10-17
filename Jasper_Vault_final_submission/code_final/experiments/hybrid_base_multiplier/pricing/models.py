"""Model parts of the hybrid pricer.

(A) Fair value: Black-Scholes with a HAR volatility forecast for the PP duration.
(B) Anchor: Jasper's base price; BaseModel rebuilds it where it is missing.
(C) Risk multiplier g(x) = expected payout / anchor, learned from real payouts.
    With no features it is one calibration constant (the selected setup, see notebook 04).
(D) ReferenceModel: the price customers pay today, relative to the anchor.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor

from .data import MINUTES_PER_YEAR

DURATIONS_S = (1800, 3600, 7200, 14400, 28800, 43200, 86400)
HAR_COLS = ["rv15", "rv60", "rv240", "rv1440", "rv10080"]
ATM = 1 / np.sqrt(2 * np.pi)  # Black-Scholes at the money: price ~ ATM * S * sigma * sqrt(T)


# ---------------------------------------------------------------- (A) fair value
def black_scholes(S, K, T, sigma, is_put):
    """Price per 1 BTC of a European put or call, interest rate 0."""
    S, K, T = (np.asarray(v, dtype=float) for v in (S, K, T))
    sd = np.maximum(np.asarray(sigma, dtype=float), 1e-4) * np.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * sd ** 2) / sd
    d2 = d1 - sd
    call = S * norm.cdf(d1) - K * norm.cdf(d2)
    put = K * norm.cdf(-d2) - S * norm.cdf(-d1)
    return np.where(np.asarray(is_put, dtype=bool), put, call)


class HarVol:
    """Annualized volatility forecast for the next h minutes, one regression per PP duration.

    log(realized variance over the next h minutes) = a + sum_j b_j * log(rv_j^2), fitted on BTC
    minutes (every `step` minutes) whose forecast window ends before `cutoff`.
    The mean forecast uses the log-normal correction exp(s^2 / 2).
    """

    def __init__(self, step: int = 15):
        self.step = step
        self.coef = {}

    def fit(self, btc: pd.DataFrame, mkt: pd.DataFrame, cutoff: pd.Timestamp) -> "HarVol":
        r2 = np.log(btc["close"]).diff().pow(2).fillna(0.0)
        csum = r2.cumsum()
        logx = np.log(mkt[HAR_COLS].clip(lower=1e-6) ** 2)
        grid = mkt.index[:: self.step]
        for d in DURATIONS_S:
            h = d // 60
            future = (csum.shift(-h) - csum) * MINUTES_PER_YEAR / h
            t = grid[grid + pd.Timedelta(minutes=h) <= cutoff]
            X = logx.loc[t]
            y = np.log(future.loc[t].clip(lower=1e-8))
            ok = X.notna().all(axis=1) & y.notna()
            A = np.column_stack([np.ones(ok.sum()), X[ok].to_numpy()])
            b, *_ = np.linalg.lstsq(A, y[ok].to_numpy(), rcond=None)
            resid = y[ok].to_numpy() - A @ b
            self.coef[d] = (b, float(resid.var()), int(ok.sum()))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        out = np.full(len(X), np.nan)
        logx = np.log(X[HAR_COLS].clip(lower=1e-6).to_numpy() ** 2)
        dur = X["duration_s"].to_numpy()
        for d, (b, s2, _) in self.coef.items():
            m = dur == d
            if m.any():
                out[m] = np.sqrt(np.exp(b[0] + logx[m] @ b[1:] + s2 / 2))
        return out


# ---------------------------------------------------------------- (B) anchor
class BaseModel:
    """Rebuild Jasper's base price per BTC where it is missing.

    Target: log(base / (ATM * S * sqrt(T))) = log of the volatility implied by the base price.
    The base price is an at-the-money quote matched on type and duration, so the strike is not used.
    """

    FEATS = ["log_sigma", "log_rv60", "log_rv240", "log_rv1440", "log_rv10080", "log_pk1440",
             "duration_h", "is_put", "hour", "weekday"]

    def fit(self, X: pd.DataFrame, base: pd.Series) -> "BaseModel":
        y = np.log(base / (ATM * X["spot"] * np.sqrt(X["T"])))
        self.model = HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05, max_iter=300,
                                                   min_samples_leaf=50, l2_regularization=1.0,
                                                   random_state=0).fit(X[self.FEATS], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.exp(self.model.predict(X[self.FEATS])) * ATM * X["spot"].to_numpy() * np.sqrt(X["T"].to_numpy())


# ---------------------------------------------------------------- (C) risk multiplier
RISK_INPUTS = ("dur", "size", "put", "mny_sd", "vol_gap", "rv_trend", "dir_move", "strike_calc", "rebuilt", "weekend")


class RiskMultiplier:
    """g(x) = expected payout per BTC / anchor.

    Poisson loss on target y / anchor with weight qty * anchor equals a Poisson model of the payout
    with offset log(anchor). The weight of the largest orders is capped (weight_cap quantile of qty).

    features = ()   -> one constant: total payout / total anchor (dollar-weighted).
    kind = "glm"    -> Poisson GLM with L2 penalty `alpha` on the chosen inputs (RISK_INPUTS or
                       extra numeric columns). The size effect is capped to `size_cap`.
    kind = "gbm"    -> gradient boosting (Poisson) on the numeric inputs; for comparison only.
    """

    def __init__(self, features=(), kind="glm", alpha=0.1, size_cap=(0.8, 1.5), g_clip=(0.3, 4.0), weight_cap=0.9):
        self.features, self.kind, self.alpha = list(features), kind, alpha
        self.size_cap, self.g_clip, self.weight_cap = size_cap, g_clip, weight_cap

    def _inputs(self, X: pd.DataFrame) -> pd.DataFrame:
        sdT = X["sigma"] * np.sqrt(X["T"])
        f = pd.DataFrame(index=X.index)
        for c in self.features:
            if c == "dur":
                for d in DURATIONS_S[1:]:
                    f[f"dur_{d}"] = (X["duration_s"] == d).astype(float)
            elif c == "size":
                b = np.digitize(X["log_qty"].to_numpy(), self.size_edges)
                for k in (0, 1, 3, 4):
                    f[f"size_{k}"] = (b == k).astype(float)
            elif c == "put":
                f["put"] = X["is_put"].astype(float)
            elif c == "mny_sd":
                f[c] = (X["mny"] / sdT).clip(-3, 3)
            elif c == "vol_gap":
                f[c] = np.log(X["sigma"] / X["iv_anchor"]).clip(-1, 1)
            elif c == "rv_trend":
                f[c] = np.log(X["rv60"] / X["rv1440"]).clip(-2, 2)
            elif c == "dir_move":
                f[c] = (X["dir_ret60"] / (X["rv60"] * np.sqrt(60 / MINUTES_PER_YEAR))).clip(-3, 3)
            elif c == "rebuilt":
                f[c] = X["anchor_rebuilt"].astype(float)
            else:
                f[c] = X[c].astype(float)
        return f.fillna(0.0)

    def fit(self, X, y, qty, anchor) -> "RiskMultiplier":
        qty, anchor, y = np.asarray(qty, float), np.asarray(anchor, float), np.asarray(y, float)
        w = np.minimum(qty, np.quantile(qty, self.weight_cap)) * anchor
        self.const = float(np.sum(y * qty) / np.sum(anchor * qty))
        self.size_rel = np.ones(5)
        if not self.features:
            return self
        self.size_edges = np.quantile(X["log_qty"], [0.2, 0.4, 0.6, 0.8])
        D = self._inputs(X)
        self.cols = list(D.columns)
        self.center, self.scale = D.mean(), D.std().replace(0, 1)
        Z = (D - self.center) / self.scale
        if self.kind == "glm":
            self.model = PoissonRegressor(alpha=self.alpha, max_iter=3000).fit(Z, y / anchor, sample_weight=w)
            coef = dict(zip(self.cols, self.model.coef_ / self.scale.to_numpy()))
            raw = np.array([np.exp(coef.get(f"size_{k}", 0.0)) for k in range(5)])
            self.size_rel = np.clip(raw, *self.size_cap)
        else:
            self.model = HistGradientBoostingRegressor(loss="poisson", max_depth=2, learning_rate=0.03, max_iter=100,
                                                       min_samples_leaf=800, l2_regularization=5.0, random_state=0)
            self.model.fit(Z, y / anchor, sample_weight=w)
        # Re-level so the dollar-weighted average multiplier equals the training ratio.
        g = self._raw(X)
        self.level = float(np.sum(y * qty) / np.sum(anchor * g * qty))
        return self

    def _raw(self, X):
        Z = (self._inputs(X)[self.cols] - self.center) / self.scale
        if self.kind == "glm":
            coef = pd.Series(self.model.coef_, index=self.cols)
            size_cols = [c for c in self.cols if c.startswith("size_")]
            eta = self.model.intercept_ + Z.drop(columns=size_cols).to_numpy() @ coef.drop(size_cols).to_numpy()
            s = self.size_rel[np.digitize(X["log_qty"].to_numpy(), self.size_edges)] if size_cols else 1.0
            return np.exp(eta) * s
        return self.model.predict(Z)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.features:
            return np.full(len(X), self.const)
        return np.clip(self.level * self._raw(X), *self.g_clip)

    def factors(self) -> pd.Series:
        """GLM factors as multipliers per unit of input (size bins already capped)."""
        if not self.features or self.kind != "glm":
            return pd.Series({"constant": self.const})
        f = pd.Series(np.exp(self.model.coef_ / self.scale.to_numpy()), index=self.cols)
        for k in (0, 1, 3, 4):
            if f"size_{k}" in f:
                f[f"size_{k}"] = self.size_rel[k]
        return f


# ---------------------------------------------------------------- (D) reference price
class ReferenceModel:
    """Price customers pay today, as a factor on the anchor: R_hat = anchor * exp(f(x)).

    Fitted on rows with Jasper's real base price and real paid price. Uses no outcomes.
    kind = "const" uses one average markup factor instead of a model.
    """

    FEATS = ["duration_h", "is_put", "log_qty", "mny", "hour", "weekday", "rsi", "bb_pctb",
             "log_rv60", "log_rv1440", "dir_ret60", "dir_ret240", "strike_calc"]

    def __init__(self, kind: str = "model"):
        self.kind = kind

    def fit(self, X: pd.DataFrame, paid: pd.Series, base: pd.Series) -> "ReferenceModel":
        y = np.log(paid / base)
        self.const = float(np.exp(y.mean()))
        if self.kind == "model":
            self.model = HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05, max_iter=300,
                                                       min_samples_leaf=50, l2_regularization=1.0,
                                                       random_state=0).fit(X[self.FEATS], y)
        return self

    def predict(self, X: pd.DataFrame, anchor) -> np.ndarray:
        if self.kind == "const":
            return np.asarray(anchor) * self.const
        return np.asarray(anchor) * np.exp(self.model.predict(X[self.FEATS]))
