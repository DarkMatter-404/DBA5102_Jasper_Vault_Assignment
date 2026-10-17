import sys
import numpy as np
import pandas as pd

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
base = sys.argv[1]
d = pd.read_csv(base + "/pp_transactions_training.csv")
b = pd.read_csv(base + "/btc_market_history.csv", usecols=["open_time_utc", "high", "low", "close"])
b["t"] = pd.to_datetime(b.open_time_utc, utc=True).dt.tz_localize(None)
b = b.set_index("t").sort_index()
full = pd.date_range(b.index.min(), b.index.max(), freq="1min")
print("BTC minutes", len(b), "expected", len(full), "missing", len(full) - len(b))
b = b.reindex(full)

for c in ["createdAt", "closedAt", "expirationDate"]:
    d[c] = pd.to_datetime(d[c])
n_all = len(d)
d = d[d.realizedProfit_USDC.notna() & d.closedAt.notna()].copy()
print("orders", n_all, "with a known result", len(d))

d["per_btc"] = d.realizedProfit_USDC / d.quantity_BTC
put = d.optionType == 1
d["implied"] = np.where(put, d.strikePrice - d.per_btc, d.strikePrice + d.per_btc)
d["late_s"] = (d.closedAt - d.expirationDate).dt.total_seconds()
print("\nclosedAt minus expirationDate (seconds):")
print(d.late_s.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).round(1))
d["early"] = d.late_s < -60
print("closed more than 60 s before expiry:", int(d.early.sum()), "of", len(d), "= %.1f%%" % (100 * d.early.mean()))

def window(ts, w):
    m = ts.dt.floor("min")
    lo = pd.concat([b.low.reindex(m + pd.Timedelta(minutes=k)).reset_index(drop=True) for k in range(-w, w + 1)], axis=1).min(axis=1)
    hi = pd.concat([b.high.reindex(m + pd.Timedelta(minutes=k)).reset_index(drop=True) for k in range(-w, w + 1)], axis=1).max(axis=1)
    return lo.values, hi.values

def gap(x, lo, hi):
    return np.where(x < lo, lo - x, np.where(x > hi, x - hi, 0.0))

res = {}
for name, col in [("closedAt", "closedAt"), ("expirationDate", "expirationDate")]:
    for w in (0, 1):
        lo, hi = window(d[col], w)
        d["lo_%s_%d" % (name, w)] = lo; d["hi_%s_%d" % (name, w)] = hi
        d["gap_%s_%d" % (name, w)] = gap(d.implied.values, lo, hi)

pos = d[d.realizedProfit_USDC > 0]
zero = d[d.realizedProfit_USDC == 0]
print("\norders with a payout:", len(pos), " orders with zero payout:", len(zero))

def rep(df, label):
    print("\n--- %s (n=%d) ---" % (label, len(df)))
    rows = []
    for name in ("closedAt", "expirationDate"):
        for w in (0, 1):
            g = df["gap_%s_%d" % (name, w)]
            ok = g.notna()
            rows.append({"price taken at": name, "window": "that minute" if w == 0 else "+/- 1 minute",
                         "inside range %": round(100 * (g[ok] == 0).mean(), 1), "within 10 USD %": round(100 * (g[ok] <= 10).mean(), 1),
                         "within 50 USD %": round(100 * (g[ok] <= 50).mean(), 1), "median gap": round(g[ok].median(), 2),
                         "p95 gap": round(g[ok].quantile(.95), 1), "no BTC data": int((~ok).sum())})
    print(pd.DataFrame(rows).to_string(index=False))

rep(pos, "PAYOUT > 0: is the implied end price inside the real BTC range?")
rep(pos[~pos.early], "PAYOUT > 0, closed at expiry")
rep(pos[pos.early], "PAYOUT > 0, closed early")
rep(pos[pos.optionType == 1], "PAYOUT > 0, Puts")
rep(pos[pos.optionType == 0], "PAYOUT > 0, Calls")

# zero payout: the price at the end must be on the non-paying side of the strike
print("\n--- ZERO PAYOUT: was the price on the non-paying side of the strike? ---")
for name in ("closedAt", "expirationDate"):
    for w in (0, 1):
        lo = zero["lo_%s_%d" % (name, w)]; hi = zero["hi_%s_%d" % (name, w)]
        ok = np.where(zero.optionType == 1, hi >= zero.strikePrice, lo <= zero.strikePrice)
        # how far on the paying side, when not consistent
        miss = np.where(zero.optionType == 1, zero.strikePrice - hi, lo - zero.strikePrice)
        bad = miss[~ok]
        print("%-15s %-12s consistent %.1f%%   not consistent: %d (median distance %.1f USD)" % (
            name, "that minute" if w == 0 else "+/- 1 minute", 100 * ok.mean(), (~ok).sum(), np.median(bad) if len(bad) else 0))

# reverse check: when the formula says a payout was due, was one paid?
print("\n--- REVERSE CHECK at closedAt (+/- 1 minute): whole range on the paying side ---")
lo = d.lo_closedAt_1; hi = d.hi_closedAt_1
must_pay = np.where(d.optionType == 1, hi < d.strikePrice, lo > d.strikePrice)
mp = d[must_pay]
print("orders where every price in the window was on the paying side:", len(mp), " of these with payout > 0: %.1f%%" % (100 * (mp.realizedProfit_USDC > 0).mean()))

# size of typical numbers, for context
print("\npayout per 1 BTC (payout > 0):", pos.per_btc.describe(percentiles=[.5, .95]).round(1).to_dict())
worst = pos.sort_values("gap_closedAt_1", ascending=False).head(8)[["createdAt", "closedAt", "expirationDate", "optionType_label", "productType", "strikePrice", "per_btc", "implied", "lo_closedAt_1", "hi_closedAt_1", "gap_closedAt_1", "early"]]
print("\nlargest misses:\n", worst.round(1).to_string(index=False))
big = pos[pos.gap_closedAt_1 > 50]
print("\nmisses > 50 USD: %d; share early-closed among them: %.1f%%; by duration:" % (len(big), 100 * big.early.mean() if len(big) else 0))
print(big.groupby("productType").size().to_string())
