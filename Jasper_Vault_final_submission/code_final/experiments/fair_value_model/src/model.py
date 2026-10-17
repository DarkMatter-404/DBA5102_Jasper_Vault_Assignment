"""The PP pricing model.

premium = quantity x fair_value_per_BTC x (1 + margin)

1. Expected-move model. For each product length T, a Poisson regression with a log link
   predicts E|log(P[t+T] / P[t])|, the expected size of the BTC move over the protection
   window, from recent volatility and the time of day. It is fitted on market history (one
   window every few minutes), not on orders, so it learns from hundreds of thousands of windows.
2. Scheduled releases. A CPI, jobs report or FOMC decision inside the window adds a fixed
   amount of extra variance, measured from past releases.
3. Fair value. An at-the-money option pays about half the absolute move on average (a call
   pays on up-moves, a put on down-moves). The expected move is converted into a
   Black-Scholes volatility for the window, which also prices strikes away from the money.
4. Margin. One number set by the business: premium = fair value x (1 + margin).
"""
from dataclasses import dataclass, field

import numpy as np
import polars as pl
from scipy.stats import norm
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .market import Market, Seasonality, VolRegimeHMM, features, market_sample

SQRT_PI_2 = np.sqrt(np.pi / 2)
BPS = 1e4

RECENT_VOL = ["log_var_60m", "log_var_240m", "log_var_1440m", "log_var_10080m"]
TIME_OF_DAY = ["log_seas_window", "log_seas_last60"]

# Model variants compared in the backtest, from simplest to richest.
VARIANTS = {
    "average move only": {"features": [], "events": False},
    "recent volatility": {"features": RECENT_VOL, "events": False},
    "+ time of day": {"features": RECENT_VOL + TIME_OF_DAY, "events": False},
    "+ macro releases (final)": {"features": RECENT_VOL + TIME_OF_DAY, "events": True},
    "+ HMM regime": {"features": RECENT_VOL + TIME_OF_DAY + ["hmm_p_turbulent"], "events": True},
}
RANGE_AND_VOLUME = ["log_park_60m", "log_park_240m", "log_rel_volume_60m", "taker_imbalance_60m"]
VARIANTS["+ range and volume (candidate)"] = {"features": RECENT_VOL + TIME_OF_DAY + RANGE_AND_VOLUME, "events": True}
FINAL_VARIANT = "+ macro releases (final)"


@dataclass
class MoveModel:
    """One Poisson regression per product length, on a chosen subset of features."""
    feature_names: list[str]
    models: dict[int, object] = field(default_factory=dict)
    n_windows: dict[int, int] = field(default_factory=dict)

    def fit(self, mkt: Market, seas: Seasonality, k_from: int, k_to: int,
            hmm: VolRegimeHMM | None = None, exclude_release_windows: bool = False) -> "MoveModel":
        for t_s in config.DURATIONS_S:
            t_min = t_s // 60
            k = market_sample(mkt, k_from, k_to, t_min, config.SAMPLE_STEP_MIN)
            if exclude_release_windows:  # diagnostic: keep the release effect out of the baseline entirely
                k = k[mkt.events_in_window(k, np.full(len(k), t_min)) == 0]
            x = self._matrix(mkt, seas, k, np.full(len(k), t_min), hmm)
            y = mkt.forward_abs_return(k, np.full(len(k), t_min)) * BPS
            pipe = make_pipeline(StandardScaler(), PoissonRegressor(alpha=0.0, max_iter=1000))
            self.models[t_s] = pipe.fit(x, y)
            self.n_windows[t_s] = len(k)
        return self

    def _matrix(self, mkt, seas, k, t_min, hmm) -> np.ndarray:
        f = features(mkt, seas, k, t_min, hmm)
        if self.feature_names:
            return np.column_stack([f[n] for n in self.feature_names])
        return np.zeros((len(k), 1))  # no information: the average move for this product length

    def predict_abs_move(self, mkt, seas, k: np.ndarray, t_s: np.ndarray,
                         hmm: VolRegimeHMM | None = None) -> np.ndarray:
        """Expected |log return| over the window without release effects (a fraction, not bps)."""
        out = np.full(len(k), np.nan)
        for t in np.unique(t_s):
            m = t_s == t
            x = self._matrix(mkt, seas, k[m], np.full(m.sum(), t // 60), hmm)
            out[m] = self.models[int(t)].predict(x) / BPS
        return out

    def coefficients(self) -> pl.DataFrame:
        """Coefficients per one standard deviation of each feature, one row per product length.

        exp(coefficient) is the multiplicative change in the expected move when the feature
        rises by one standard deviation.
        """
        rows = []
        for t_s, pipe in self.models.items():
            glm = pipe[-1]
            row = {"productType": t_s, "n_windows": self.n_windows.get(t_s), "intercept": float(glm.intercept_)}
            row.update({n: float(c) for n, c in zip(self.feature_names, glm.coef_)})
            rows.append(row)
        return pl.DataFrame(rows)


def add_event_jump(abs_move: np.ndarray, event_in_window: np.ndarray, jump_var: float) -> np.ndarray:
    """Expected |move| after adding the release variance to windows that contain a release.

    With normal returns, E|R| = s * sqrt(2 / pi). Variances add: s_total^2 = s^2 + jump_var.
    """
    s2 = (abs_move * SQRT_PI_2) ** 2 + jump_var * event_in_window
    return np.sqrt(s2) / SQRT_PI_2


def bs_value_per_btc(spot: np.ndarray, strike: np.ndarray, sigma_window: np.ndarray,
                     option_type: np.ndarray) -> np.ndarray:
    """Black-Scholes value per BTC with zero rates, using the total volatility over the window.

    option_type: 0 = call (protects a short position), 1 = put (protects a long position).
    """
    s = np.maximum(sigma_window, 1e-9)
    d1 = (np.log(spot / strike) + 0.5 * s * s) / s
    d2 = d1 - s
    call = spot * norm.cdf(d1) - strike * norm.cdf(d2)
    put = strike * norm.cdf(-d2) - spot * norm.cdf(-d1)
    return np.where(option_type == 0, call, put)


def fair_value_per_btc(abs_move: np.ndarray, strike: np.ndarray, option_type: np.ndarray,
                       spot: np.ndarray | None = None) -> np.ndarray:
    """Convert an expected absolute move into a premium per BTC.

    The window volatility is s = E|R| * sqrt(pi / 2). PP is sold at the money (strike =
    platform mark price at creation), so by default spot = strike, and the value reduces to
    about strike x E|R| / 2. A different spot, or a deductible that moves the strike, is
    priced through the same Black-Scholes formula (this is how moneyness enters).
    """
    spot = strike if spot is None else spot
    return bs_value_per_btc(spot, strike, abs_move * SQRT_PI_2, option_type)


def margin_from_target_loss_ratio(target: float = config.TARGET_LOSS_RATIO) -> float:
    return 1.0 / target - 1.0
