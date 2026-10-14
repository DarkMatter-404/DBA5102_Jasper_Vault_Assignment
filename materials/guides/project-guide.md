# Project guide — Jasper Vault PP pricing

A shared starting point for the team: what we are pricing, what the data shows, what the blind
validation file needs, and the rules we all follow. **Every number below was computed from the
files in `data/`**, so use the reference table in section 4 to check your own pipeline.

**Due Sunday 18 October 2026, 23:59, on Canvas** (the folder closes automatically).
Deliverables: PowerPoint deck · 10-minute presentation video · code · any other material.

---

## 1. What Perpetual Protect (PP) is

PP is short-term protection for someone holding a leveraged BTC position (a perpetual future).

| Trader holds | Afraid that BTC… | PP pays if BTC ends… | In option terms |
| --- | --- | --- | --- |
| Long | falls | below the strike | put (`optionType = 1`) |
| Short | rises | above the strike | call (`optionType = 0`) |

Durations are 30 minutes to 24 hours. The user pays a premium upfront; Jasper Vault (JV) pays
out if the protection is triggered. **JV is the seller, so its profit per order is
premium − payout.** In the data the payout is `realizedProfit_USDC` (the user's profit is JV's
cost).

Example: a trader is long 0.1 BTC at $100,000 and buys 2-hour protection at strike $100,000.
The base premium is $300 per BTC, so $30; JV charges 1.5×, so $45.

| BTC when the PP closes | JV pays | JV result |
| --- | --- | --- |
| $100,500 | 0 | +$45 |
| $99,600 | (100,000 − 99,600) × 0.1 = $40 | +$5 |
| $99,000 | $100 | **−$55** |

JV's gain is capped at the premium; its loss is not.

## 2. How the payout is computed (checked on the training data)

    payout = quantity × max(0, price − strike)   for a call
    payout = quantity × max(0, strike − price)   for a put

where "price" is the BTC price **at the moment the protection closes** (`closedAt`). 64.8% of
orders (71% of premium) close more than one minute before expiry. For those orders, using the
price at `closedAt` matches whether the order paid out in 97.9% of cases; using the price at
expiry matches only 86.5%. Maksim's workspace reaches the same formula independently
(`maksim/README.md`, section 1).

The data does not say who triggers an early close (the user closing their position, or a rule).
For modelling it does not matter: we predict the payout from information available when the
order is placed, early closes included. `closedAt` itself is an outcome.

## 3. The whole problem in one formula

The lecturer's slide for this assignment (Blockchain Lecture 7, slide 30 — see
[`../lectures/`](../lectures/)):

> **Choose price P to maximise  a(P, x) × [ P − μ(x) − c(x) ]**

| Piece | Meaning | Where it comes from |
| --- | --- | --- |
| x | What we know when the order is placed: duration, strike distance, recent market, size | Pre-trade data |
| μ(x) | Expected payout | **A prediction problem** — this is what our models estimate |
| a(P, x) | Probability the user buys at price P | **JV's conversion constraint.** Our data only has orders that were bought, and JV's past prices reacted to market conditions, so we cannot estimate it ourselves |
| c(x) | Cost per sale | Not given; zero unless JV says otherwise |
| choose P | The pricing decision | An optimisation over a grid of prices or multipliers |

The slide's example (100 quotes, expected payout $60, cost $5):

| Price | Conversion | Profit |
| --- | --- | --- |
| $80 | 80% | $1,200 |
| **$100** | **50%** | **$1,750** |
| $140 | 10% | $750 |

This is why "raise every price" fails: past a point, the sales we lose cost more than the margin
we gain.

## 4. What the training data shows

### Reference numbers — reproduce these first

`data/with_base_premium/pp_transactions_training.csv`:

| Quantity | Value |
| --- | --- |
| Orders / with an outcome | 7,204 / **7,150** (54 have no outcome — drop them) |
| Premium collected | **248,089 USDC** |
| Payouts | **230,652 USDC** |
| JV profit · loss ratio · margin | **17,437 · 0.930 · 7.0%** |
| Orders that paid out | 46.0% |
| Orders with no base price | **1,131** |
| JV's current multiplier (price ÷ base) | median **1.51**, IQR 1.35–1.98, premium-weighted **1.44** |
| **Break-even multiplier** (Σ payout ÷ Σ base premium) | **1.40** |
| Top 10% of orders by premium | **55.5%** of all premium |
| June + July | **84.4%** of all premium |

**Break-even multiplier** answers: "in this group of orders, how many times the base premium did
JV end up paying out?" Charge above it and the group is profitable. Overall JV charges 1.44
against a break-even of 1.40 — that is the whole 7% margin.

### By duration (orders that have a base price)

| Duration | JV charges | Break-even | Profit (USDC) | Share of premium |
| --- | ---: | ---: | ---: | ---: |
| 30 min | 1.94× | 1.45× | +8,135 | 16% |
| 1 h | 1.60× | 1.52× | +1,784 | 17% |
| 2 h | 1.40× | 1.23× | +4,142 | 17% |
| 4 h | 1.32× | 1.55× | −8,936 | 27% |
| 8 h | 1.28× | 1.29× | −554 | 22% |
| 12 h / 24 h | | | +941 | 1% |

JV marks up 30-minute protection heavily and 4h/8h protection very little.

### Findings that do not survive a check — don't build on them

- **"4-hour protection is underpriced."** The 4h loss (−8,682 USDC over all 1,240 orders) comes
  from ten orders: the worst 10 lost 13,833; the other 1,230 made +5,150.
- **"Puts are underpriced."** Which side loses flips with BTC's direction month to month.
- **"Calm markets lose money"** — only partly true. Loss ratio by volatility in the 60 minutes
  before the order (quintiles):

  | | Q1 calm | Q2 | Q3 | Q4 | Q5 volatile |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | All orders | **1.116** | 0.986 | 0.846 | 0.920 | 0.792 |
  | Jun–Jul | **1.199** | 1.019 | 0.831 | 0.932 | 0.794 |
  | Feb–May | 0.807 | 0.717 | 0.910 | 0.862 | 0.774 |
  | 30-min orders | **0.351** | 0.930 | 0.589 | 0.761 | 0.600 |
  | 2h+ orders | 1.127 | 1.016 | 0.965 | 1.023 | 0.735 |

  The calm-market loss holds in June–July and for 2h+ orders, reverses in Feb–May, and is the
  *most* profitable bucket for 30-minute orders. Duration and recent volatility act together.

## 5. The blind validation file

Full details: [`data/validation/README.md`](../../data/validation/README.md). In short:

- **4,155 orders, 31 July – 14 October 2026**, not the 1,898 the dataset guide describes. Rows
  0–1,897 are the documented block (timestamps cut to the minute); rows 1,898–4,154 are new.
- **2,195 orders (53%) have no base price**, nearly all in the new block. A base × multiplier
  model cannot price them on its own — **we need a premium for every row.**
- Premium, order price and payout are blank. **`closedAt` is filled in — it is an outcome; never
  use it.**
- **No order ID.** Keep the original row order.
- Use `data/validation/btc_market_history.csv` (to 14 Oct) for training *and* validation
  features; it is identical to the old file except the old file's last, half-finished candle.

Proposed submission columns, one row per validation order in the original order:
`row, createdAt, optionType, productType, quantity_BTC, strikePrice, apiBasePrice_per_BTC_USDC,
recommended_premium_USDC, recommended_multiplier` (multiplier blank where there is no base).

## 6. Rules we all follow

1. **Outcomes are never features:** `closedAt`, `realizedProfit_USDC`. Also do not use
   `premiumAmount_USDC`, `orderPrice_per_BTC_USDC` or `markup_per_BTC_USDC` as features — they
   are blank or patchy in the validation file.
2. **Market features only from candles that closed before `createdAt`**:
   `pd.merge_asof(orders, candles, left_on="createdAt", right_on="close_time",
   direction="backward", allow_exact_matches=False)`. Compute rolling features on the candle
   series before joining. The largest gap should be under 60 seconds.
3. **Chronological validation only** — no random cross-validation. JV split the data by time
   because random splits leak market regimes. Default: fit on Feb–Jun, test on July.
4. **Weight by money.** Report totals and premium- or notional-weighted metrics, not per-order
   averages.
5. **Decide candidate models before looking at July results**, and keep the number small.
   Choosing the best of many on one test month mostly selects luck.
6. **Freeze, refit on Feb–Jul, then price the blind file once.**

## 7. Comparing our models fairly (proposal)

Jay, Maksim and Subham currently each use a different conversion assumption (see each workspace
README). For the deck we need one comparison on the same basis:

- **Test period:** July (fit on Feb–Jun).
- **Benchmarks:** current JV pricing; base × 1 where a base exists; a flat multiplier at the
  break-even level (the simplest model).
- **Conversion scenarios:** no response · a moderate smooth response · a strict rule (order lost
  if priced above current). Same formulas for every model.
- **Metrics:** profit after conversion · loss ratio · average price versus current (proves
  "better, not higher") · daily P&L standard deviation and worst day · share of loss from the
  top 1% of orders · result in each half of July · how many orders were priced without a base.

## 8. Course ideas worth naming in the deck

| Course | Idea | Where it shows up |
| --- | --- | --- |
| DBA5106 | Same randomness — recent data is closest to the future | June–July carry 84% of premium and sit next to the validation period |
| DBA5106 | Change the target | Predict payout ÷ base premium (or per BTC), not payout in USDC |
| DBA5106 | Data leakage | `closedAt`; candles after the order |
| DBA5106 | Weighted loss; L2 gives the mean | Big orders dominate; pricing needs the *expected* payout. L1/median is wrong here: 54% of orders pay nothing, so the median payout is often 0 |
| DBA5106 | Asymmetric loss (newsvendor) | Underpricing loses on each sale and attracts more buyers; overpricing only loses some sales |
| DBA5106 | Benchmarks | Must beat current pricing and a flat multiplier |
| DBA5106 | Constraints / Ridge / LASSO; optimizer's curse | Pull small segments toward the average; the 4h "finding" is ten orders |
| DBA5101 | Third-degree price discrimination; inverse elasticity rule | A different multiplier per observable group; higher markup where buyers are less price-sensitive |
| DBA5101 | Endogeneity and selection | Why we cannot estimate demand from purchase-only data |
| DBA5101 | Randomised controlled trial | How JV should learn its real conversion curve: test multipliers on a random share of quotes |
| DBA5103 | Formulation; price grid (markdown case); sensitivity and robust choice | Choose a multiplier per segment from a grid; check it holds across conversion scenarios |
| BT5110 | Joins with conditions; NULL handling | The as-of join; 53% missing base prices in validation |
| DBA5102 L6–L7 | Off-chain model, oracle, caps and limits | Deployment slide (see `materials/lectures/`) |

## 9. Open questions — ask Jasper Vault or the lecturer

1. The exact conversion / scoring rule, and whether it is applied to our premium or our multiplier.
2. How orders without a base price are scored, and whether a premium-only submission is fine.
3. The submission file format and how rows are matched (there is no order ID).
4. Whether all 4,155 orders are scored, or only the documented 1,898.
5. What closes a PP before expiry.

## 10. Before we submit

- [ ] Model frozen; refit on Feb–Jul
- [ ] Every validation row has a premium; row order kept; file checked against 4,155 rows
- [ ] Code runs from the repo root with written instructions and data paths
- [ ] Deck and 10-minute video
- [ ] Module code reads **DBA5102** in submitted material (this repo is named DBA5106)
- [ ] Submitted on Canvas before 23:59, Sunday 18 October
