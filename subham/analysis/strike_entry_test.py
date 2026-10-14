"""Test: is the PP strike the market price at order creation, or an earlier price (the trader's entry price)?

The data has no entry-price column, so the test is indirect:
  1. Is the strike inside the BTC price range at the creation minute? If yes for almost all orders,
     the strike is the market price at the moment the protection was bought.
  2. If not, when did BTC last trade at the strike before the order? A short look-back time
     with a consistent pattern is what an entry price would produce.
  3. Signed moneyness at creation: for a Put, strike above the market means the protection
     is already in the money (the trader's position is at a loss).
"""
import sys
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
base = sys.argv[1]
d = pd.read_csv(base + "/pp_transactions_training.csv")
b = pd.read_csv(base + "/btc_market_history.csv", usecols=["open_time_utc", "high", "low", "close"])
b["t"] = pd.to_datetime(b.open_time_utc, utc=True).dt.tz_localize(None)
b = b.set_index("t").sort_index()
d["createdAt"] = pd.to_datetime(d.createdAt)
m = d.createdAt.dt.floor("min")
put = d.optionType == 1

# 1. strike inside the creation-minute range (that minute, and +/- 1 minute)
lo0, hi0 = b.low.reindex(m).values, b.high.reindex(m).values
lo1 = np.fmin.reduce([b.low.reindex(m + pd.Timedelta(minutes=k)).values for k in (-1, 0, 1)])
hi1 = np.fmax.reduce([b.high.reindex(m + pd.Timedelta(minutes=k)).values for k in (-1, 0, 1)])
K = d.strikePrice.values
close0 = b.close.reindex(m).values
inside0 = (K >= lo0) & (K <= hi0)
inside1 = (K >= lo1) & (K <= hi1)
gap1 = np.where(K < lo1, lo1 - K, np.where(K > hi1, K - hi1, 0.0))
print("orders:", len(d))
print("strike inside the creation-minute range:          %.1f%%" % (100 * inside0.mean()))
print("strike inside the range, creation minute +/- 1:   %.1f%%" % (100 * inside1.mean()))
print("distance outside the +/-1 minute range (USD): median %.1f, p75 %.1f, p95 %.1f, max %.1f" % tuple(
    np.percentile(gap1[~inside1], [50, 75, 95, 100])) if (~inside1).any() else "")
rel = (K - close0) / close0 * 100
print("strike vs close of creation minute (%%): median %.3f, mean |diff| %.3f, p95 |diff| %.3f" % (
    np.median(rel), np.mean(np.abs(rel)), np.percentile(np.abs(rel), 95)))

# 3. signed moneyness at creation (positive = in the money)
itm = np.where(put, K - close0, close0 - K)
print("\nsigned distance at creation, strike vs price (USD, + = protection already in the money):")
for lab, mask in (("Put", put.values), ("Call", ~put.values)):
    x = itm[mask]
    print("  %-4s n=%d  in the money %.1f%%  out of the money %.1f%%  median %.1f  p5 %.1f  p95 %.1f" % (
        lab, mask.sum(), 100 * (x > 1).mean(), 100 * (x < -1).mean(), np.median(x), np.percentile(x, 5), np.percentile(x, 95)))

# 2. look-back: minutes since BTC last traded at the strike (search up to 7 days back)
lows, highs, idx = b.low.values, b.high.values, b.index
pos0 = idx.get_indexer(m)
lag = np.full(len(d), np.nan)
for i in range(len(d)):
    p = pos0[i]
    if p < 0:
        continue
    start = max(0, p - 7 * 1440)
    hit = np.where((lows[start:p + 1] <= K[i]) & (highs[start:p + 1] >= K[i]))[0]
    if len(hit):
        lag[i] = p - (start + hit[-1])
d["lag_min"] = lag
print("\nminutes since BTC last traded at the strike (0 = the creation minute):")
print(pd.Series(lag).describe(percentiles=[.5, .75, .9, .95, .99]).round(1).to_string())
print("not found in 7 days:", int(np.isnan(lag).sum()))
bins = [-0.5, 0.5, 1.5, 5.5, 30.5, 240.5, 1440.5, 1e9]
labels = ["0", "1", "2-5", "6-30", "31-240", "241-1440", ">1 day"]
print(pd.cut(pd.Series(lag), bins, labels=labels).value_counts().reindex(labels).to_string())

# decimals pattern of the strike (a computed price vs a quoted price)
dec = d.strikePrice.astype(str).str.split(".").str[1].fillna("").str.len()
print("\nstrike decimal places:", dec.value_counts().sort_index().to_dict())
d["dec"] = dec
print("lag by decimal places (median minutes):", d.groupby(pd.cut(d.dec, [-1, 1, 2, 20], labels=["0-1", "2", "3+"]), observed=True).lag_min.median().to_dict())
print("in-range by decimal places (+/-1 min):", pd.Series(inside1).groupby(pd.cut(d.dec, [-1, 1, 2, 20], labels=["0-1", "2", "3+"]).values, observed=True).mean().round(3).to_dict())

# same quantity + strike repeated across orders (one position protected several times?)
key = d.strikePrice.round(4).astype(str) + "_" + d.optionType.astype(str)
rep = key.map(key.value_counts())
print("\norders whose (strike, type) appears in more than one order: %.1f%%" % (100 * (rep > 1).mean()))
g = d.assign(key=key)[rep > 1].groupby("key").createdAt.agg(["count", "min", "max"])
g["span_h"] = (g["max"] - g["min"]).dt.total_seconds() / 3600
print("groups:", len(g), " median orders per group:", g["count"].median(), " median span (hours):", round(g.span_h.median(), 2))
