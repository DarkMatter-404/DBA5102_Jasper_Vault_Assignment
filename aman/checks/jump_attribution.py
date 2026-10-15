"""Where do the big BTC moves and the big payouts come from? Aman, 16 Oct 2026.
Descriptive check for the LLM/news amendment (not a pricing input).

1. 15-minute bars Feb-Jul: what share of the largest |moves| fall in the hour after a
   scheduled core release (CPI, jobs report, FOMC)?
2. Resolved orders: payout share and loss ratio for orders whose window
   (a) contains a core release, (b) contains a large move that is NOT near a release, (c) neither.
Outcomes are used only to describe, never as features.
"""
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "with_base_premium"
c = pd.read_csv(D / "btc_market_history.csv", usecols=["open_time_utc", "close"])
c["t"] = pd.to_datetime(c.open_time_utc, utc=True)
c = c.set_index("t").sort_index()
c = c[(c.index >= "2026-02-01") & (c.index < "2026-08-01")]
bar = np.log(c.close).resample("15min").last().diff().dropna()      # label L: close(L+15m) vs close(L)
bar = bar.abs().rename("absr").to_frame()
bar["start"] = bar.index                                              # so the move happened over [L, L+15m)

ev = pd.read_csv(REPO / "aman" / "data_external" / "macro_events_2026_checked.csv")
ev = ev[ev.in_core_set.astype(str) == "True"]
rel = pd.to_datetime(ev.ts_utc, utc=True).sort_values().values

def near_release(t0):
    """True if the bar [t0, t0+15m) overlaps the hour after a core release, i.e. a release R in (t0-60m, t0+15m)."""
    t0 = np.asarray(t0, dtype="datetime64[ns]")
    lo = np.searchsorted(rel, t0 - np.timedelta64(60, "m"), side="right")
    hi = np.searchsorted(rel, t0 + np.timedelta64(15, "m"), side="left")
    return hi > lo

bar["near_rel"] = near_release(bar.start.values)
print(f"15-min bars Feb-Jul: {len(bar):,}; share of bars within the hour after a core release: {bar.near_rel.mean():.2%}")
for q in (0.99, 0.999):
    top = bar[bar.absr >= bar.absr.quantile(q)]
    print(f"top {1-q:.1%} bars (|r| >= {bar.absr.quantile(q)*1e4:.0f} bp): {len(top)} bars on {top.index.normalize().nunique()} days;"
          f" near a core release {top.near_rel.mean():.1%}")
big = bar[bar.absr >= bar.absr.quantile(0.995)]
big_unsched = big[~big.near_rel]
print(f"top 0.5% bars: {len(big)}, not near a release: {len(big_unsched)}")

o = pd.read_csv(D / "pp_transactions_training.csv")
for k in ["createdAt", "expirationDate"]:
    o[k] = pd.to_datetime(o[k], utc=True, format="mixed")
r = o[o.realizedProfit_USDC.notna()].copy()
r["month"] = r.createdAt.dt.month
s = r.createdAt.values.astype("datetime64[ns]"); e = r.expirationDate.values.astype("datetime64[ns]")
lo = np.searchsorted(rel, s, side="right"); hi = np.searchsorted(rel, e, side="right")
r["release_in_window"] = hi > lo
u0 = big_unsched.start.values.astype("datetime64[ns]"); u1 = u0 + np.timedelta64(15, "m")
lo = np.searchsorted(u1, s, side="right"); hi = np.searchsorted(u0, e, side="left")   # bars overlapping (s, e)
r["unsched_big_move"] = (hi > lo) & ~r.release_in_window
r["group"] = np.select([r.release_in_window, r.unsched_big_move], ["release in window", "big unscheduled move"], "neither")
r["loss"] = r.realizedProfit_USDC - r.premiumAmount_USDC

def summ(g, tot_p, tot_c):
    return pd.Series({"orders": len(g), "prem_share": g.premiumAmount_USDC.sum() / tot_p,
                      "payout_share": g.realizedProfit_USDC.sum() / tot_c,
                      "loss_ratio": g.realizedProfit_USDC.sum() / g.premiumAmount_USDC.sum()})

print(f"\nresolved orders {len(r):,}; overall loss ratio {r.realizedProfit_USDC.sum()/r.premiumAmount_USDC.sum():.3f}")
for name, g in [("ALL", r), ("June", r[r.month == 6]), ("July", r[r.month == 7]),
                ("ALL ex 10 worst", r.drop(r.nlargest(10, "loss").index))]:
    t = g.groupby("group")[g.columns.drop("group")].apply(summ, g.premiumAmount_USDC.sum(), g.realizedProfit_USDC.sum())
    print(f"\n-- {name} --\n{t.round(3).to_string()}")
