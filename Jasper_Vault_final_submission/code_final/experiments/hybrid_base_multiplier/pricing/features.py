"""Features known at the moment an order is created.

Market features are computed for every BTC minute from that minute and earlier minutes only
(trailing windows), then read at the last complete minute before the order (data.info_minute).
"""
import numpy as np
import pandas as pd

from .data import MINUTES_PER_YEAR, info_minute

RV_WINDOWS = {"rv15": 15, "rv60": 60, "rv240": 240, "rv1440": 1440, "rv10080": 10080}
RET_WINDOWS = {"ret15": 15, "ret60": 60, "ret240": 240, "ret1440": 1440}


def _spaced(series: pd.Series, step: int, count: int) -> pd.DataFrame:
    """Columns = series shifted by 0, step, 2*step, ... (count columns). Trailing values only."""
    return pd.concat({k: series.shift(k * step) for k in range(count)}, axis=1)


def market_features(btc: pd.DataFrame) -> pd.DataFrame:
    """One row per BTC minute. Each row uses that minute's close and earlier data only."""
    c = btc["close"]
    r = np.log(c).diff()
    r2 = r ** 2
    f = pd.DataFrame(index=btc.index)
    f["spot"] = c

    # Realized volatility (annualized) from 1-minute returns.
    for name, w in RV_WINDOWS.items():
        f[name] = np.sqrt(r2.rolling(w, min_periods=int(w * 0.8)).sum() * MINUTES_PER_YEAR / w)

    # Parkinson range volatility (uses highs and lows, more robust to noise).
    hl2 = np.log(btc["high"] / btc["low"]) ** 2
    for name, w in {"pk60": 60, "pk1440": 1440}.items():
        f[name] = np.sqrt(hl2.rolling(w, min_periods=int(w * 0.8)).mean() / (4 * np.log(2)) * MINUTES_PER_YEAR)

    # Price change over recent windows.
    for name, w in RET_WINDOWS.items():
        f[name] = np.log(c / c.shift(w))

    # Activity: last hour vs the average hour of the last 7 days.
    v60 = btc["volume"].rolling(60).sum()
    f["volume_ratio"] = np.log(v60 / (btc["volume"].rolling(10080).sum() / 168))
    f["trades_ratio"] = np.log(btc["trades"].rolling(60).sum() / (btc["trades"].rolling(10080).sum() / 168))
    f["taker_ratio"] = btc["taker_buy"].rolling(60).sum() / v60

    # RSI(14) and Bollinger %b(20, 2) on closes spaced 15 minutes apart (trailing).
    d = c - c.shift(15)
    gains = _spaced(d.clip(lower=0), 15, 14).mean(axis=1, skipna=False)
    losses = _spaced((-d).clip(lower=0), 15, 14).mean(axis=1, skipna=False)
    f["rsi"] = 100 - 100 / (1 + gains / losses.replace(0, np.nan))
    closes = _spaced(c, 15, 20)
    mid, sd = closes.mean(axis=1, skipna=False), closes.std(axis=1, skipna=False)
    f["bb_pctb"] = (c - (mid - 2 * sd)) / (4 * sd)
    return f


def order_features(orders: pd.DataFrame, mkt: pd.DataFrame) -> pd.DataFrame:
    """Market features at the info minute plus order features. Index = orders.index."""
    minute = info_minute(orders["created"])
    X = mkt.reindex(minute.to_numpy()).set_axis(orders.index)
    X["info_minute"] = minute
    X["duration_s"] = orders["duration_s"]
    X["T"] = orders["duration_s"] / (365 * 24 * 3600)
    X["duration_h"] = orders["duration_s"] / 3600
    X["is_put"] = orders["is_put"].astype(int)
    X["log_qty"] = np.log(orders["qty"])
    S, K = X["spot"], orders["strike"]
    X["strike"] = K
    # Signed moneyness: + = protection already pays (in the money).
    X["mny"] = np.where(orders["is_put"], np.log(K / S), np.log(S / K))
    X["strike_calc"] = orders["strike_calc"].astype(int)
    # Recent price move in the direction that makes the protection pay.
    for name in RET_WINDOWS:
        if name in X:
            X["dir_" + name] = np.where(orders["is_put"], -X[name], X[name])
    X["hour"] = orders["created"].dt.hour
    X["weekday"] = orders["created"].dt.weekday
    X["weekend"] = (X["weekday"] >= 5).astype(int)
    return X
