# Order flow and the state of Jasper Vault's book (Cris)

Angle: treat Jasper Vault as a market maker. At the moment each PP order arrives, JV already holds a book of open
protections. Does the state of that book (how one-sided it is, and whether the new order joins or opposes the crowd)
tell us anything about the order's expected payout, about daily losses, and about how to price or limit it?
No other workspace in the team uses the order flow itself as a state variable.

Training orders only (February to July 2026). The validation file is not touched: its `closedAt` column reveals
outcomes, so any use of it would not be a blind test.

## What was done

0. `00_prepare_features.py` builds the per-order table from the supplied files: spot and trailing volatility from the
   one-minute candles, and a direction-neutral fair value (Black-Scholes with a HAR-style volatility forecast fitted
   on February to June orders, scaled to their payouts). `run_all.sh` runs every step and writes `results/`.
1. `01_build_book.py` reconstructs the open book before every order: open call and put notional (orders created
   earlier and not yet closed), imbalance `imb = (call - put) / (call + put)` in [-1, 1], JV's net delta, and the
   net flow of the last 4 and 24 hours. Whether an earlier protection is still open is known at quote time; no
   payout information is used. `s_add = imb` for a call and `-imb` for a put: positive means the new order adds to
   the dominant side.
2. `02_test_imbalance.py` compares payouts of orders that add to the crowd with those that oppose it, with
   day-resampled 90 percent intervals; checks whether the imbalance predicts the direction of the move; daily P&L
   against one-sidedness.
3. `03_robustness.py` rules out three alternative explanations (early-close forfeits, size, single days) and
   documents the mechanism.
4. `04_backtest_skew.py`, `05_targeted_vs_flat.py` test a pricing layer `multiplier = 1 + k * max(-s_add, 0)`
   (parameters chosen on February to June, reported on July) against a flat raise of the same total.
5. `06_crowd_right_days.py` measures how often the crowd was right and what those days cost.

Fair value per order is direction-neutral by construction (it depends on volatility, duration and strike, not on
whether the order is a call or a put), which is what a payout / fair value ratio needs.

## Findings

**1. The crowded side pays little; the contrarian side pays a lot.** Orders placed when the book held at least
1 BTC of open protection (3,241 orders, 67 percent of premium):

| Order relative to the open book | Orders | Premium | Loss ratio | Payout / fair value (90 pct interval) |
| --- | ---: | ---: | ---: | ---: |
| strongly opposes the crowd (s_add < -0.5) | 265 | 14,512 | 1.23 | 1.42 (1.01 to 1.85) |
| opposes | 518 | 31,140 | 1.17 | 1.24 (0.90 to 1.58) |
| neutral | 1,385 | 63,048 | 1.13 | 1.21 (0.97 to 1.48) |
| joins the crowd | 636 | 32,027 | 0.93 | 0.97 (0.71 to 1.26) |
| strongly joins (s_add > 0.5) | 437 | 24,972 | 0.48 | 0.61 (0.46 to 0.76) |

The direction is the same in every product length, in May, June and July separately (July alone: joins 0.80,
opposes 1.25), on the European counterfactual (intrinsic value at expiry: joins 0.90, opposes 1.30, so it is not
an early-close artefact), after dropping the largest day of each month (0.83 against 1.35), and in the large size
tiers that carry the premium. Equal-weighted per order the gap is smaller (mean ratio 0.84 against 1.05): the
contrarian orders do not pay more often (46 against 44 percent), they pay more when they pay.

**2. Mechanism: users herd into protection after the move, and the move partly reverts.** After BTC rose more
than 2 percent in the previous 24 hours the book leans to calls (mean imbalance +0.26: shorts buying protection);
after a fall of more than 2 percent it leans to puts (-0.10). When the book is call-heavy, BTC's return to expiry
averages -21 basis points and is positive only 39 percent of the time; put-heavy, +0.5 basis points and 54 percent.
Spearman correlation of past 24-hour return with imbalance: 0.36. The crowd protects against continuation and on
average gets reversal.

**3. One-sided days were JV's best days, but the exceptions carried the losses.** Splitting training days by whether
the crowded side paid out more than its premium:

| | Days | Premium | P&L | Worst day | Loss ratio, crowd orders | Loss ratio, contrarian orders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| crowd wrong (76 percent of days) | 38 | 147,272 | +24,266 | | 0.42 | 1.33 |
| crowd right (24 percent of days) | 12 | 50,866 | -20,450 | -9,630 | 1.57 | 0.91 |

Twelve days gave back almost everything the other 38 earned. The worst day (24 June, -9,630) was a crowd-right day.
A trend filter (|24h return| > 2 percent) does not flag these days in advance (3 of 15 flagged days against 9 of 35
unflagged). August 2026 in the validation period, with BTC up 25 percent, was a month of such days (Maksim's sealed
check, section 6 of his README).

**4. As a pricing layer the effect is real but modest.** Loading only the contrarian orders
(`multiplier = 1 + k * max(-s_add, 0)`, k = 0.3) on top of today's prices:

| | Actual | Contrarian loading k=0.3 | Flat raise, same total (x1.019 / x1.037) |
| --- | ---: | ---: | ---: |
| Feb to Jun, conservative demand e=1 | 13,120 | 16,292 | 15,448 |
| Feb to Jun, conservative e=2 | 13,120 | 16,790 | 15,165 |
| Feb to Jun, strict (lose order if > 25 pct dearer) | 13,120 | 16,660 | 15,736 |
| July, conservative e=1 | 4,319 | 8,141 | 7,998 |
| July, conservative e=2 | 4,319 | 8,002 | 7,714 |
| July, strict > 25 pct | 4,319 | 9,486 | 8,294 |

The layer beats an equal flat raise by 500 to 1,600 USDC per period under smooth demand and keeps 1 to 3 points
more orders; in July under smooth demand the two are within 150 USDC. k = 0.5 is worse than flat in July under
strict rules (large targeted rises get rejected). Ranking quality (Spearman of price against payout) is unchanged,
because the layer touches 30 percent of orders. Discounting the crowded side was tested too (k_crowd up to 0.2) and
reduces profit under every demand rule with elasticity up to 2: a segment with a 20 percent margin cannot pay for
a 10 to 20 percent price cut unless elasticity is above roughly 2.5. It would also sell more of the side that
produces the crowd-right losses.

## What this means for the submission

- The book state is a **risk signal first and a pricing signal second**. The business as priced today is a
  mean-reversion bet: it earns on three days in four and gives it back on the fourth, and those days cannot be
  told apart in advance. "Long-term, stable, sustainable returns" therefore need an exposure control on the
  crowded side, not a price. This gives Maksim's cap-per-direction policy a rationale from the order flow, and
  explains the August validation loss.
- A small contrarian loading (k about 0.3, on books of at least 1 BTC) is a defensible add-on to any base model
  (Maksim's fair value or Subham's corrected base): about +3,000 USDC a month in training, roughly +1,000 over a
  flat raise, applied to the 30 percent of orders that go against the crowd, with no price cut anywhere.
- The herding result (users buy protection after the move hurt them, and the move then reverts) is worth one
  slide on its own: it is the behavioural reason the crowded side is cheap to insure, and it is why a pure
  volatility model (which ignores direction) left money on the table on the contrarian side and over-charged the
  crowd.

## Files

| File | Output |
| --- | --- |
| `run_all.sh` | runs everything below from `../data/with_base_premium/` (a few minutes) |
| `00_prepare_features.py` | `work/orders.pkl`: per-order features and fair value |
| `01_build_book.py` | `work/book.pkl`: book state per order; `results/console_01_book.txt` |
| `02_test_imbalance.py` | tables in findings 1 and 3; `results/console_02_imbalance.txt` |
| `03_robustness.py` | robustness and mechanism tables; `results/console_03_robustness.txt` |
| `04_backtest_skew.py` | `results/grid_febjun.csv`, `results/july_policies.csv`, `results/july_skew_orders.csv` |
| `05_targeted_vs_flat.py` | `results/targeted_vs_flat.csv` |
| `06_crowd_right_days.py` | `results/crowd_right_days.csv` |

Inputs: `../data/with_base_premium/pp_transactions_training.csv` and `btc_market_history.csv`, unchanged. 7,123 of the
7,204 training orders are used: 54 have no recorded outcome and 27 have an expiry earlier than creation or a duration
far from the product length. Requirements: pandas, numpy, scipy, scikit-learn (`requirements.txt`).
