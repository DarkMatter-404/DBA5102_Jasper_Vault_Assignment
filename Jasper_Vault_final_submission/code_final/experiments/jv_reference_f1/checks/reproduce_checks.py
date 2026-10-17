"""Reproducibility checks for the Jasper Vault PP project (Aman, 14 Oct 2026).

Run from anywhere:  python aman/checks/reproduce_checks.py
Data: data/with_base_premium/ (default) or pass a folder containing pp_transactions_training.csv.

Outcomes (closedAt, realizedProfit_USDC) are used ONLY to evaluate, never as features.
Prints:
  1. JV-01 headline numbers (expect 7,150 resolved / LR 0.930 / margin 7.0%)
  2. Base-only economics: loss ratio if JV charged Base x 1.0, by month
  3. Duration loss ratios with and without each duration's 10 largest single-order losses,
     plus June vs July
"""
import sys
from pathlib import Path

import pandas as pd

_UP = Path(__file__).resolve().parents  # code_final path fix: nearest folder with data/
REPO = next((p for p in _UP if (p / "data" / "with_base_premium").is_dir()), _UP[2])
D = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "with_base_premium"

o = pd.read_csv(D / "pp_transactions_training.csv")
for c in ["createdAt", "closedAt"]:
    o[c] = pd.to_datetime(o[c], utc=True, errors="coerce")
r = o[o.realizedProfit_USDC.notna() & o.closedAt.notna()].copy()
r["month"] = r.createdAt.dt.month
r["loss"] = r.realizedProfit_USDC - r.premiumAmount_USDC  # JV loss per order at the price charged

# 1. Headline numbers
prem, pay = r.premiumAmount_USDC.sum(), r.realizedProfit_USDC.sum()
print("== 1. JV-01 headline check ==")
print(f"rows {len(o):,} | resolved {len(r):,} | unresolved {len(o) - len(r)}")
print(f"premium {prem:,.0f} | payout {pay:,.0f} | profit {prem - pay:,.0f} | "
      f"loss ratio {pay / prem:.3f} | margin {(prem - pay) / prem:.1%} | paid out {(r.realizedProfit_USDC > 0).mean():.1%}")

# 2. Base-only economics (rows with a matched base)
if "apiBasePrice_per_BTC_USDC" in r:
    b = r[r.apiBasePrice_per_BTC_USDC.notna()].copy()
    b["base_prem"] = b.quantity_BTC * b.apiBasePrice_per_BTC_USDC
    t = b.groupby("month").agg(n=("base_prem", "size"), charged=("premiumAmount_USDC", "sum"),
                               base=("base_prem", "sum"), payout=("realizedProfit_USDC", "sum"))
    t.loc["all"] = t.sum()
    t["LR_charged"] = t.payout / t.charged
    t["LR_base_x1"] = t.payout / t.base
    t["charged_over_base"] = t.charged / t.base
    jj = b[b.month >= 6]
    print("\n== 2. Base-only economics (rows with a matched base) ==")
    print(f"{len(b):,} of {len(r):,} resolved rows have a base; "
          f"no-base rows carry {1 - b.premiumAmount_USDC.sum() / prem:.1%} of premium")
    print(t.round(3).to_string())
    print(f"Break-even uniform multiplier on base, Jun-Jul: {jj.realizedProfit_USDC.sum() / jj.base_prem.sum():.3f}")

# 3. Duration robustness
rows = []
for d, g in r.groupby("productType"):
    rest = g.drop(g.nlargest(10, "loss").index)
    lr = lambda x: x.realizedProfit_USDC.sum() / x.premiumAmount_USDC.sum() if len(x) else float("nan")
    rows.append(dict(hours=d / 3600, n=len(g), LR=lr(g), profit=-g.loss.sum(),
                     worst10_profit=-g.nlargest(10, "loss").loss.sum(), LR_ex_worst10=lr(rest),
                     LR_Jun=lr(g[g.month == 6]), LR_Jul=lr(g[g.month == 7])))
print("\n== 3. Loss ratio by duration: all orders vs without its 10 largest losses ==")
print(pd.DataFrame(rows).round(3).to_string(index=False))
