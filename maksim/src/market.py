"""Market features built from one-minute BTC candles.

Every feature for an order created at time t uses only candles that had fully closed
before t. The function `last_closed_index` enforces this, and every feature is computed
from that index backwards. Forward-looking quantities (the realised move over the
protection window) are only used as training targets for the volatility model.
"""
from dataclasses import dataclass

import numpy as np
import polars as pl
from scipy.stats import norm

from . import config
from .data import minute_index

EPS_VAR = 1e-12  # floor for per-minute variance, avoids log(0) on flat minutes


@dataclass(frozen=True)
class Market:
    t0: np.datetime64          # open time of the first candle
    logp: np.ndarray           # log close price per minute
    cum_r2: np.ndarray         # cum_r2[k + 1] = sum of squared one-minute log returns up to minute k
    minute_et_bucket: np.ndarray  # 0..95: 30-minute bucket of the US Eastern day (48) x weekend flag (2)
    event_cum: np.ndarray      # event_cum[k + 1] = number of macro events in minutes 0..k
    event_idx: np.ndarray      # minute index of every scheduled release
    cum_park: np.ndarray       # prefix sums of the Parkinson (high-low) variance per minute
    cum_vol: np.ndarray        # prefix sums of traded volume (BTC)
    cum_taker: np.ndarray      # prefix sums of taker-buy volume (BTC)

    @property
    def n(self) -> int:
        """Number of candles (the calendar arrays are longer)."""
        return len(self.logp)

    def last_closed_index(self, ts: np.ndarray) -> np.ndarray:
        """Index of the last candle whose close time is before `ts`.

        A candle with open time m covers [m, m + 60 s). At time ts the candle containing ts
        is still open, so the last closed one is the previous candle.
        """
        return minute_index(ts, self.t0) - 1

    def trailing_var(self, k: np.ndarray, h: int) -> np.ndarray:
        """Average squared one-minute return over the h minutes ending at minute k (inclusive)."""
        return np.maximum((self.cum_r2[k + 1] - self.cum_r2[k + 1 - h]) / h, EPS_VAR)

    def forward_abs_return(self, k: np.ndarray, t_min: np.ndarray) -> np.ndarray:
        """|log(P[k + T] / P[k])|: the size of the move over the next T minutes (a TARGET, not a feature)."""
        return np.abs(self.logp[k + t_min] - self.logp[k])

    def events_in_window(self, k: np.ndarray, t_min: np.ndarray) -> np.ndarray:
        """1 if a scheduled macro release falls in minutes k + 1 .. k + T. Calendar dates are known in advance."""
        return ((self.event_cum[k + t_min + 1] - self.event_cum[k + 1]) > 0).astype(float)


CALENDAR_HORIZON_MIN = 2 * 1440  # calendar arrays run two days past the last candle, so a 24-hour
                                 # window that starts at the latest candle can still be priced


def build_market(candles: pl.DataFrame, events: pl.DataFrame, holidays: list | None = None) -> Market:
    """Arrays used by the features. `holidays` (US Eastern dates) are treated like weekend days in
    the time-of-day profile; None keeps the original calendar (weekdays and weekends only)."""
    ts = candles["ts"].to_numpy()
    t0 = ts[0]
    logp = np.log(candles["close"].to_numpy())
    r = np.diff(logp, prepend=logp[0])
    cum_r2 = np.concatenate([[0.0], np.cumsum(r * r)])

    # Calendar-only arrays (time-of-day bucket, release flags) need no price, so they extend past
    # the last candle; price-based arrays (logp, cum_r2) stop at the last candle.
    n_cal = len(logp) + CALENDAR_HORIZON_MIN
    minutes = pl.Series("ts", t0 + np.arange(n_cal).astype("timedelta64[m]"))
    et = minutes.dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    bucket30 = (et.dt.hour().to_numpy().astype(int) * 2 + et.dt.minute().to_numpy().astype(int) // 30)
    weekend = (et.dt.weekday().to_numpy() >= 6).astype(int)  # polars: Monday=1 .. Sunday=7
    if holidays:
        weekend = np.maximum(weekend, et.dt.date().is_in(holidays).to_numpy().astype(int))
    minute_et_bucket = bucket30 + 48 * weekend

    flags = np.zeros(n_cal)
    idx = np.array([], dtype=np.int64)
    if events.height:
        idx = minute_index(events["ts_utc"].to_numpy(), t0)
        idx = idx[(idx >= 0) & (idx < n_cal)]
        flags[idx] = 1.0
    event_cum = np.concatenate([[0.0], np.cumsum(flags)])
    n = len(logp)
    if {"high", "low"} <= set(candles.columns):
        hl = np.log(candles["high"].to_numpy() / candles["low"].to_numpy())
        park = hl * hl / (4.0 * np.log(2.0))
    else:  # close-only price files (long-history test): range features unavailable
        park = np.zeros(n)
    vol = candles["volume"].to_numpy() if "volume" in candles.columns else np.zeros(n)
    taker = candles["taker_buy_base_asset_volume"].to_numpy() if "taker_buy_base_asset_volume" in candles.columns else np.zeros(n)
    prefix = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    return Market(t0=t0, logp=logp, cum_r2=cum_r2, minute_et_bucket=minute_et_bucket, event_cum=event_cum,
                  event_idx=idx, cum_park=prefix(park), cum_vol=prefix(vol), cum_taker=prefix(taker))


@dataclass(frozen=True)
class Seasonality:
    """Average squared one-minute return by half-hour of the US Eastern day, weekday vs weekend.

    Normalised so the average over the fitting period is 1. A value of 1.6 for the 08:30 to
    09:00 bucket means BTC typically moves 1.6 times as much (in variance) then as on average.
    """
    profile: np.ndarray        # length 96
    cum_by_minute: np.ndarray  # prefix sums of the profile mapped onto every minute

    def window_mean(self, k_start: np.ndarray, k_end: np.ndarray) -> np.ndarray:
        """Mean profile value over minutes k_start .. k_end inclusive."""
        return (self.cum_by_minute[k_end + 1] - self.cum_by_minute[k_start]) / (k_end - k_start + 1)


def fit_seasonality(mkt: Market, fit_end_idx: int, fit_start_idx: int = 0) -> Seasonality:
    """Fitted on minutes fit_start_idx .. fit_end_idx, leaving out the 30 minutes after each
    release so that release days are handled by the event term and not counted twice."""
    keep = np.ones(fit_end_idx + 1, dtype=bool)
    keep[:fit_start_idx] = False
    for e in mkt.event_idx[mkt.event_idx <= fit_end_idx]:
        keep[e: e + config.EVENT_WINDOW_MIN] = False
    r2 = np.diff(mkt.cum_r2)[: fit_end_idx + 1][keep]
    buckets = mkt.minute_et_bucket[: fit_end_idx + 1][keep]
    sums = np.bincount(buckets, weights=r2, minlength=96)
    counts = np.bincount(buckets, minlength=96)
    profile = (sums / np.maximum(counts, 1)) / r2.mean()
    per_minute = profile[mkt.minute_et_bucket]
    return Seasonality(profile=profile, cum_by_minute=np.concatenate([[0.0], np.cumsum(per_minute)]))


def fit_event_jump_var(mkt: Market, fit_end_idx: int, control_days: int = 28) -> tuple[float, int]:
    """Extra variance that a scheduled release adds to any window containing it.

    For each release before fit_end_idx: the squared log move over the 30 minutes starting at
    the last closed minute before the release, minus the average squared move over the same UTC
    clock window on the preceding release-free weekdays (controls that straddle the 8 March
    daylight-saving change sit one Eastern hour off; this moves the estimate by under 0.2 bps).
    Returns (jump variance, n releases).
    """
    w = config.EVENT_WINDOW_MIN
    ev = mkt.event_idx[mkt.event_idx + w <= fit_end_idx]
    if len(ev) == 0:
        return 0.0, 0
    move2 = lambda k: (mkt.logp[k + w] - mkt.logp[k]) ** 2
    excess = []
    for e in ev:
        k = e - 1
        ctrl = []
        for d in range(1, control_days + 1):
            kc = k - 1440 * d
            if kc < 0:
                break
            weekday = int(((mkt.t0 + np.timedelta64(int(kc), "m")).astype("datetime64[D]").view("int64") - 4) % 7)  # 0 = Monday
            if weekday < 5 and mkt.event_cum[kc + w + 1] - mkt.event_cum[kc + 1] == 0:
                ctrl.append(kc)
        excess.append(move2(k) - move2(np.array(ctrl)).mean())
    return max(float(np.mean(excess)), 0.0), len(ev)


@dataclass(frozen=True)
class VolRegimeHMM:
    """Two-state Gaussian HMM on hourly log realised variance (calm vs turbulent).

    Only the forward (filtering) recursion is used, so the regime probability at hour h
    depends on hours up to h only. The usual `predict_proba` in hmmlearn runs the
    forward-backward smoother, which uses future hours and would leak information.
    """
    means: np.ndarray
    sds: np.ndarray
    transmat: np.ndarray
    startprob: np.ndarray
    high_state: int
    hour_prob: np.ndarray  # filtered P(turbulent) for every complete hour of the series


def _hourly_log_var(mkt: Market) -> np.ndarray:
    n_hours = mkt.n // 60
    ends = np.arange(1, n_hours + 1) * 60
    return np.log(np.maximum((mkt.cum_r2[ends] - mkt.cum_r2[ends - 60]) / 60, EPS_VAR))


def fit_hmm(mkt: Market, fit_end_idx: int, seed: int = 0) -> VolRegimeHMM:
    from hmmlearn.hmm import GaussianHMM

    x = _hourly_log_var(mkt)
    n_fit = (fit_end_idx + 1) // 60
    hmm = GaussianHMM(n_components=2, covariance_type="diag", n_iter=200, random_state=seed)
    hmm.fit(x[:n_fit, None])
    means = hmm.means_.ravel()
    sds = np.sqrt(hmm.covars_.reshape(2, -1)[:, 0])
    high = int(np.argmax(means))
    log_b = norm.logpdf(x[:, None], means[None, :], sds[None, :])
    probs = np.empty(len(x))
    alpha = hmm.startprob_.copy()
    for h in range(len(x)):
        pred = alpha if h == 0 else alpha @ hmm.transmat_
        a = pred * np.exp(log_b[h] - log_b[h].max())
        alpha = a / a.sum()
        probs[h] = alpha[high]
    return VolRegimeHMM(means, sds, hmm.transmat_, hmm.startprob_, high, probs)


def features(mkt: Market, seas: Seasonality, k: np.ndarray, t_min: np.ndarray,
             hmm: VolRegimeHMM | None = None) -> dict[str, np.ndarray]:
    """Pre-trade features at last-closed minute k for a protection window of t_min minutes."""
    out = {f"log_var_{h}m": np.log(mkt.trailing_var(k, h)) for h in config.TRAILING_WINDOWS_MIN}
    window_sum = lambda cum, h: cum[k + 1] - cum[k + 1 - h]
    out["log_park_60m"] = np.log(np.maximum(window_sum(mkt.cum_park, 60) / 60, EPS_VAR))
    out["log_park_240m"] = np.log(np.maximum(window_sum(mkt.cum_park, 240) / 240, EPS_VAR))
    vol60, vol_week = window_sum(mkt.cum_vol, 60), window_sum(mkt.cum_vol, 10080)
    out["log_rel_volume_60m"] = np.log(np.maximum(vol60 / 60, 1e-9) / np.maximum(vol_week / 10080, 1e-9))
    out["taker_imbalance_60m"] = np.abs(2.0 * window_sum(mkt.cum_taker, 60) / np.maximum(vol60, 1e-9) - 1.0)
    out["log_seas_window"] = np.log(seas.window_mean(k + 1, k + t_min))
    out["log_seas_last60"] = np.log(seas.window_mean(k - 59, k))
    out["event_in_window"] = mkt.events_in_window(k, t_min)
    if hmm is not None:
        last_full_hour = (k + 1) // 60 - 1  # hour h covers minutes 60h .. 60h + 59
        p = hmm.hour_prob[np.clip(last_full_hour, 0, len(hmm.hour_prob) - 1)]
        out["hmm_p_turbulent"] = p
    return out


def market_sample(mkt: Market, k_from: int, k_to: int, t_min: int, step: int) -> np.ndarray:
    """Sample of minute indices whose whole protection window ends by k_to."""
    first = max(k_from, max(config.TRAILING_WINDOWS_MIN))
    return np.arange(first, k_to - t_min + 1, step, dtype=np.int64)
