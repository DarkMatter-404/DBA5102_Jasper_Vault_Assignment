"""Evidence for notes/JV-03 (paper ideas). Aman, 15 Oct 2026.

Run from the repo root or anywhere:
    python aman/checks/jv03_evidence.py            # uses data/with_base_premium/
    python aman/checks/jv03_evidence.py <folder>   # any folder with the two CSVs

Rules: outcomes (closedAt, realizedProfit_USDC) are used ONLY to evaluate, never as inputs to a price.
Market data is joined from 1-min bars that CLOSED before createdAt.

Simple maths used throughout (all orders are ATM, so strike K = BTC price at purchase):
    ATM premium per order  ~=  0.3989 * q * K * sigma * sqrt(T)          (Black-Scholes, short T)
    => any USDC amount A on a group of orders 'implies' a volatility
       sigma(A) = sum(A) / sum(0.3989 * q * K * sqrt(T))
    base vol    = sigma(base premium)      what the Black-Scholes base charges
    charged vol = sigma(premium paid)      what JV actually charged
    needed vol  = sigma(payouts)           the break-even volatility (premium = payouts)
"""
import sys
from math import pi, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

pd.set_option("display.width", 200)
REPO = Path(__file__).resolve().parents[2]
D = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "with_base_premium"
YEAR_S = 365 * 24 * 3600
Q5 = ["Q1", "Q2", "Q3", "Q4", "Q5"]

o = pd.read_csv(D / "pp_transactions_training.csv")
for c in ["createdAt", "closedAt", "expirationDate"]:
    o[c] = pd.to_datetime(o[c], utc=True)
r = o[o.realizedProfit_USDC.notna()].copy().sort_values("createdAt")
r["month"] = r.createdAt.dt.month
r["N"] = r.quantity_BTC * r.strikePrice                                   # notional, USDC
r["unit"] = r.N * np.sqrt(r.productType / YEAR_S) / sqrt(2 * pi)          # USDC per 1.00 of sigma
r["base"] = r.quantity_BTC * r.apiBasePrice_per_BTC_USDC
r["loss"] = r.realizedProfit_USDC - r.premiumAmount_USDC
r["size_q"] = pd.qcut(r.N, 5, labels=Q5)
r["early"] = (r.expirationDate - r.closedAt).dt.total_seconds() > 60


def lr(g):
    return g.realizedProfit_USDC.sum() / g.premiumAmount_USDC.sum()


def needed(g, col="realizedProfit_USDC"):
    return g[col].sum() / g.unit.sum()


def ladder(g):
    return pd.Series({"orders": len(g), "base": g.base.sum() / g.unit.sum(),
                      "charged": g.premiumAmount_USDC.sum() / g.unit.sum(), "needed": needed(g)})


def drop_worst(g, k=10):
    return g.drop(g.nlargest(k, "loss").index)


print("== 1. Volatility ladder by duration (rows with a base price; same sample for all columns) ==")
b = r[r.apiBasePrice_per_BTC_USDC.notna()]
t = b.groupby("productType").apply(ladder)
t.loc["ALL"] = ladder(b)
t["needed_mult"] = t.needed / t.base          # multiplier on base that breaks even
t["current_mult"] = t.charged / t.base        # what JV charges over base today
t["needed_Jun"] = b.groupby("productType").apply(lambda g: needed(g[g.month == 6]) if (g.month == 6).any() else np.nan)
t["needed_Jul"] = b.groupby("productType").apply(lambda g: needed(g[g.month == 7]))
t["needed_ex_worst10"] = b.groupby("productType").apply(lambda g: needed(drop_worst(g)))
t.loc["ALL", ["needed_Jun", "needed_Jul", "needed_ex_worst10"]] = [needed(b[b.month == 6]), needed(b[b.month == 7]), np.nan]
print(t.round(3).to_string())
print(f"Loss ratio if JV charged Base x 1.00: {b.realizedProfit_USDC.sum() / b.base.sum():.3f}")

print("\n== 2. Fat tails: share of payouts from the biggest moves vs a normal model with fixed vol ==")
r["x"] = r.realizedProfit_USDC / r.N / np.sqrt(r.productType / YEAR_S)   # scale-free move size


def top_share(s, p):
    s = s.sort_values(ascending=False)
    return s.iloc[:max(1, round(p * len(s)))].sum() / s.sum()


for p in (0.01, 0.05):
    print(f"top {p:.0%} of orders by move: normal {norm.pdf(norm.ppf(1 - p)) / norm.pdf(0):.1%} | ours {top_share(r.x, p):.1%}"
          f" | Jun {top_share(r[r.month == 6].x, p):.1%} | Jul {top_share(r[r.month == 7].x, p):.1%}")
for p in (0.01, 0.05):
    print(f"top {p:.0%} of orders by USDC payout carry {top_share(r.realizedProfit_USDC, p):.1%} of all USDC paid out")

print("\n== 3. Order size (notional quintiles, Q5 = largest) ==")
m = pd.read_csv(D / "btc_market_history.csv", usecols=["close_time_utc", "close"])
m["t"] = pd.to_datetime(m.close_time_utc, utc=True)
m = m.sort_values("t")
ret = np.log(m.close).diff()
m["rv60"] = np.sqrt((ret ** 2).rolling(60).sum() * 365 * 24)              # annualised, last 60 closed bars
j = pd.merge_asof(r[["createdAt"]].reset_index(), m[["t", "rv60", "close"]], left_on="createdAt", right_on="t",
                  direction="backward", allow_exact_matches=False).set_index("index")
r["rv60"], r["S0"] = j.rv60, j.close
print(f"max gap order -> last closed bar: {(r.createdAt - j.t).dt.total_seconds().max():.0f}s")


def px(col):
    y = pd.merge_asof(r[[col]].reset_index().sort_values(col), m[["t", "close"]], left_on=col, right_on="t",
                      direction="backward")
    return y.set_index("index")["close"]


r["ST"], r["Sc"] = px("expirationDate"), px("closedAt")                   # evaluation only
d = np.where(r.optionType == 0, 1, -1)
r["held_rel"] = np.maximum(d * (r.ST / r.S0 - 1), 0)                      # payout if held to expiry, per 1 notional
r["actual_rel"] = r.realizedProfit_USDC / r.N


def size_row(g):
    w = g.unit
    return pd.Series({"orders": len(g), "prem_share": g.premiumAmount_USDC.sum() / r.premiumAmount_USDC.sum(),
                      "LR": lr(g), "LR_Jun": lr(g[g.month == 6]), "LR_Jul": lr(g[g.month == 7]),
                      "LR_ex_worst10": lr(drop_worst(g)),
                      "charged_vol": g.premiumAmount_USDC.sum() / w.sum(), "needed_vol": needed(g),
                      "pretrade_vol60": np.average(g.rv60, weights=w),
                      "early_close": g.early.mean(),
                      "paid/if_held": (g.actual_rel * g.N).sum() / (g.held_rel * g.N).sum(),
                      "needed_if_held": (g.held_rel * g.N).sum() / w.sum(),
                      "needed_if_held_Jun": (g[g.month == 6].held_rel * g[g.month == 6].N).sum() / g[g.month == 6].unit.sum(),
                      "needed_if_held_Jul": (g[g.month == 7].held_rel * g[g.month == 7].N).sum() / g[g.month == 7].unit.sum()})


print(r.groupby("size_q", observed=True).apply(size_row).round(3).T.to_string())
r["vol_t"] = pd.qcut(r.rv60, 3, labels=["calm", "mid", "volatile"])
print("\nneeded vol by pre-trade vol tercile (rows) x size quintile (cols):")
print(r.groupby(["vol_t", "size_q"], observed=True).apply(needed).unstack().round(3).to_string())
r["close_rel"] = np.maximum(d * (r.Sc / r.S0 - 1), 0)                    # intrinsic value at the actual close
print(f"\nALL orders: early-closed {r.early.mean():.1%} | paid / if-held {(r.actual_rel * r.N).sum() / (r.held_rel * r.N).sum():.3f}"
      f" | intrinsic-at-close / paid {(r.close_rel * r.N).sum() / (r.actual_rel * r.N).sum():.3f}")

print("\n== 4. 'Cheap and good': what a discount costs ==")
for label, g in [("30-min orders", r[r.productType == 1800]), ("whole book", r)]:
    P, C = g.premiumAmount_USDC.sum(), g.realizedProfit_USDC.sum()
    print(f"{label}: premium {P:,.0f} payout {C:,.0f} profit {P - C:,.0f} ({len(g)} orders)")
    for x in (0.01, 0.05, 0.10):
        new = (1 - x) * P - C
        need = f"volume must rise x{(P - C) / new:.2f}" if new > 0 else "loss-making at any volume"
        print(f"   cut {x:.0%}: profit at same volume {new:,.0f} -> {need}")
