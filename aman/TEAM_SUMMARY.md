# Team summary — Jasper Vault PP pricing (final)

Aman's converged model (plan: `aman/PLAN.md`; code: `aman/pp_pricing.ipynb`; all tables: `aman/team_scorecard/`).
**Status: final.** Team decision at the 16 Oct regroup: model **F1**, theta_level = 0, band 0.8-1.2. The specification
was **locked at 2026-10-16 04:46 SGT** (`model_params.json`: `spec_locked: true`, the lock time, and the SHA-256 of
`validation_predictions.csv`, `0a733667...`). The 544-row reference check was first run after the lock, in a run
started at 04:47 SGT.
Money in USDC. Unless marked July, results are May + June under the central demand scenario (conservative, e = 2), with
paired 90% day-bootstrap intervals. July is a retrospective check: the team has looked at it before, so it chose nothing.

## The eight things to know

1. **F1 is selected on ranking and calibration, not on profit.** It passed all four pre-registered tests, but there is
   no demonstrated profit gain over JV's price (May + June +5,717 [-4,742, +17,739]; July -2,883 [-6,830, +1,081]) or
   over its own flat raise (+1,402 [-5,596, +9,381]).
2. **F1's ranking comes from Maksim's fair value.** F0, M and raw fair value have almost identical Gini by month
   (0.143 / 0.143 / 0.143 in May, 0.268 / 0.271 / 0.268 in June, 0.097 / 0.097 / 0.097 in July). Our addition is level
   discipline: F1 charges 4.5% above JV against 17-18% for M and S, and its worst day is -4,228 against -9,630 at JV's price.
3. **The cost floor does most of F1's profit work.** F1 beats F1 without the floor by +4,501 in May + June and +5,961
   in July, mostly by raising the average price: +4.0% in May + June and +8.4% in July.
4. **Ranking is positive in every month and survives the biggest orders.** F1 Gini: May 0.099 [-0.000, 0.193] (the
   lower bound touches zero), June 0.269 [0.162, 0.349], July 0.101 [0.048, 0.154]. Profit vs R0 is unchanged without
   the top 1% of orders (+8,258 with them, +8,470 without).
5. **The reference level is the weak point.** Our estimate of JV's price, R0, quoted 0.98x, 1.07x and 0.88x JV's actual
   total in May, June and July, and 7.6% below JV's revealed prices on the 544 August blind orders (see below). F1
   inherits this level: an error here moves every price.
6. **M and S beat JV by charging 17-18% more.** Against their own flat raise of the same size they show no gain
   (M +161 [-6,747, +7,704]; S -3,110 [-5,835, +192]).
7. **The level frontier favours charging more under our demand scenarios.** Under the central scenario, profit rises
   all the way to theta_level = +0.25 (16,594 at 0, 30,322 at +0.25); under "keep the order only if it is no dearer than
   today" it peaks at +0.05. We keep theta_level = 0: JV ruled out "just charge more", and we have not estimated demand.
8. **Big unscheduled moves and release windows lose money at every model's price** (pooled May-July: loss ratios
   1.35-2.91 and 1.12-1.87). Not every month: in May their loss ratios were only 0.51-1.00 and 0.39-0.68. The biggest
   moves are unscheduled and lumpy (June), so no quote-time model foresees them. That is the case for the risk layer.

## Scorecard

| Model | Role | Price vs JV | Profit | vs JV's price (C0) | vs own flat raise (C2) | Gini | Worst day | July vs C0 |
|---|---|---:|---:|---|---|---|---:|---|
| C0 | JV's actual price | 1.000 | 10,876 | — | — | 0 | -9,630 | — |
| R0 | our estimate of JV's price (fallback) | 1.054 | 8,336 | -2,540 [-8,915, +4,599] | -7,628 [-11,725, -3,564] | 0.076 [-0.001, 0.149] | -9,608 | -14,588 [-17,698, -11,370] |
| F0 | fair value scaled to JV's total | 1.014 | 12,647 | +1,770 [-9,600, +14,689] | +844 [-7,301, +11,079] | 0.243 [0.149, 0.317] | -3,880 | -1,023 [-5,906, +3,904] |
| **F1** | **selected and locked** | **1.045** | **16,594** | **+5,717 [-4,742, +17,739]** | **+1,402 [-5,596, +9,381]** | **0.235 [0.146, 0.303]** | **-4,228** | **-2,883 [-6,830, +1,081]** |
| F1nf | F1 without the floor (diagnostic) | 1.005 | 12,093 | +1,216 [-7,497, +10,529] | +742 [-4,754, +7,503] | 0.213 | -6,653 | -8,845 [-12,006, -5,595] |
| M | Maksim (FV x 1.25, base floor) | 1.169 | 23,656 | +12,779 [+296, +27,441] | +161 [-6,747, +7,704] | 0.246 [0.153, 0.319] | -2,504 | +10,782 [+3,268, +18,660] |
| S | Subham (selected config) | 1.178 | 20,622 | +9,746 [+1,493, +18,697] | -3,110 [-5,835, +192] | 0.125 [0.036, 0.213] | -5,816 | +10,200 [+4,626, +16,634] |

Not in the table: F1h is **infeasible** (with a +/-10% band, the cost floor alone puts the total 0.15-4.97% over the
reference); C3, the payout-fitted duration ladder, charges 21% below JV and loses 31,468 against it; Jay's model has no
row-level history on this data release (N/A).

## Phase 4: extensions from a closed registry (16 Oct)

**JV's suggested macro and sentiment data tested; none adopted.** F1 stays as it is. The FRED macro series (VIX,
10-year yield, S&P 500) and the GDELT news series could not be downloaded, so they were not run. Rule for a move-model
feature: skill gain >= 0.005 in at least 5 of 7 lengths (May-June mean), then beat at least 18 of 20
whole-week-shifted copies, then keep F1's Gini and beat F1's profit with an interval above zero. Every run is in
`phase4_trials.csv` (71 runs).

| ID | Candidate | Lengths >= 0.005 | Mean gain | Outcome |
|---|---|---:|---:|---|
| 4a-1 | VIX level | — | — | not run: data unavailable (FRED did not answer; retried once with a 180 s timeout) |
| 4a-2 | US 10-year yield shock | — | — | not run: data unavailable (FRED did not answer; retried once with a 180 s timeout) |
| 4a-3 | S&P 500 absolute return | — | — | not run: data unavailable (FRED did not answer; retried once with a 180 s timeout) |
| 4a-4 | Binance funding rate (absolute) | 0 | -0.0022 | fails the skill rule |
| 4a-5 | Deribit DVOL (implied volatility) | 5 | +0.0088 | passes skill and placebo (18 of 20; no shifted copy passes), then fails "Gini not below F1" (0.234 vs 0.235); profit vs F1 -1,553 [-2,487, -771] -> keeps F1 |
| 4a-6 | Fear & Greed, distance from neutral | 0 | -0.0005 | fails the skill rule |
| 4a-7 | Fed broad dollar index | — | — | not run: revised series, no vintage in time |
| 4b1-1, 4b1-2 | GDELT news attention (last hour; last 24 hours) | — | — | not run: data unavailable (GDELT did not answer: 6 tries, 03:20-03:43 SGT 16 Oct) |
| 4b2 | LLM headline score | — | — | not run without Aman's OK (and 4b1 could not run) |
| 4c-1 | Jump share of last-hour variance | 0 | +0.0010 | fails the skill rule |
| 4c-2 | Vol-of-vol (realised kurtosis) | 4 | +0.0042 | fails the skill rule (4 of 7) |
| 4c-3 | PCE added to the release set | 0 | -0.0000 | fails the skill rule |
| 4c-4 | log(DVOL / RV_1d) in the reference | — | — | improves the reference by 2.66 and 1.12 points (June, July folds) and beats 18 of 20 placebos, but 10 shifted copies also improve; fails the audit (June bias -20.7%) and the guards; profit vs F1 -6,745 [-9,911, -3,922] -> keeps F1 |
| 4d | F1d per-length payout calibration | — | — | Gini 0.222 vs 0.235; profit vs F1 -336 [-2,189, +1,097] -> keeps F1 |

**Level vs allocation.** F1: quoted / JV 1.045, profit vs its own flat raise +1,402 [-5,596, +9,381]. 4a-5 (DVOL):
1.022 and +1,952 [-4,804, +10,010]. DVOL moves prices between orders slightly better but charges about 2% less overall,
and the lower level is what loses profit against F1. Neither allocation gain is distinguishable from zero. This does not
change the decision.

## Phase 5: final prices for the blind file

- **Final fit.** F1 at theta_level = 0 with the July fold's choices (release shrinkage k_event = 0; ridge reference,
  alpha 100), refitted once on 7,132 labels created and settled before 31 Jul 17:11 UTC (left out: 17 settled after
  the cutoff, 1 created at or after it, 54 never resolved). n = 0.9933; reference level factor 1.0248 over May-July;
  release term 57.3 bps from 19 releases.
- **Blind prices** (`validation_predictions.csv`, status "final"): 4,155 orders, total 177,986 USDC. Shape clipped for
  74.9% of orders; the cost floor binds for 12.4%; a release falls inside the window for 3.5%. Median multiplier vs base
  1.484 on the 1,960 orders with a base (JV's own median in training: 1.505). Computed columns are rounded to 6
  decimals (the precision of USDC), so a rerun writes the same file byte for byte.
- **Checks.** 25/25 pass: the 15 from Phases 1-3, 8 for Phase 5 (7 on `price_orders` with a mock blind file and 1 on
  the final fit's cutoff), and 2 for the risk sections (the risk measures and the exposure cap).

### Where F1 moves price

| Length | Blind-file orders | F1 quote / estimated JV price | JV loss ratio, Feb-Jul | May | June | July |
|---|---:|---:|---:|---:|---:|---:|
| 30 min | 1,865 | 0.88 | 0.65 | 0.73 | 0.52 | 0.85 |
| 1 h | 484 | 0.99 | 0.96 | — | 1.03 | 0.88 |
| 2 h | 727 | 1.08 | 0.88 | 0.80 | 0.95 | 0.84 |
| 4 h | 704 | 1.07 | 1.14 | 0.97 | 1.18 | 1.18 |
| 8 h | 301 | 1.03 | 1.00 | 0.48 | 1.31 | 0.89 |
| 12 h | 22 | 0.80 | 0.81 | — | — | 0.81 |
| 24 h | 52 | 0.80 | 0.37 | 0.76 | 0.50 | 0.19 |
| **All** | 4,155 | 1.02 | 0.93 | 0.82 | 0.94 | 0.96 |

F1 quote / estimated JV price is a ratio of totals over the blind-file prices (`validation_predictions.csv`). JV's loss
ratio is payouts / JV's premium on settled training orders, by month created; — means no orders that month. Small
samples: 1-hour orders start in June, 12-hour orders exist only in July (46), and 24-hour months have 14-82 orders.

**Note:** 30-minute orders had loss ratios of 1.42 in February and 1.07 in March (205 orders each). The low Feb-Jul
figure (0.65) comes from April to July (0.52-0.85).

## The 544-row reference check (after the lock)

Our **locked** reference price against the JV prices that can be recovered from the blind file,
P_revealed = q x (base per BTC + markup per BTC). Bias and error only: no payout is rebuilt and no validation profit is
computed. Nothing was refitted or changed because of it.

- **Identity and units: confirmed.** The identity holds on all 6,073 training rows that have a base and a markup
  (largest relative gap 4e-16). On the revealed blind rows, markup / base quartiles are 0.43 / 0.51 / 0.97 against
  0.35 / 0.51 / 0.98 in training.
- **Coverage:** 544 of 4,155 blind orders, all created in August (479 in rows 0-1,897 and 65 in the newer rows).

| Rows | Orders | Bias | Weighted error |
|---|---:|---:|---:|
| **All revealed rows** | **544** | **-7.6%** | **13.4%** |
| Rows 0-1,897 (documented release) | 479 | -5.5% | 12.7% |
| Rows 1,898-4,154 (newer orders) | 65 | -21.7% | 19.6% |
| 30 min | 106 | -20.7% | 18.4% |
| 1 h | 16 | -20.0% | 16.4% |
| 2 h | 112 | -13.2% | 19.5% |
| 4 h | 243 | -4.3% | 12.0% |
| 8 h | 65 | -8.2% | 10.7% |
| 12 h | 2 | +41.7% | 42.5% |

Bias = sum(P_ref - P_revealed) / sum(P_revealed), so negative means our reference is **below** JV's price; weighted
error = sum(q x K x |P_ref / P_revealed - 1|) / sum(q x K). **Reading:** overall the reference is inside the audit
limits we set for May and June (bias within 15%, error within 30%), and runs low as it did in the retrospective July
audit (-12.4%). It runs about 20% low on 30-minute and 1-hour orders and on the newer rows. Cautions: these are August
orders with a revealed markup only, they need not represent the 2,195 orders without a base, and the blind inputs were
profiled before (14-15 Oct), so this is not untouched data.

**F1 and fair value against the revealed JV prices** (added on request after the check; prices only, no payouts or
profit):

| Length | Orders | F1 quote / JV revealed price | Fair value / JV revealed price |
|---|---:|---:|---:|
| **All revealed rows** | **544** | **0.86** | **0.75** |
| 30 min | 106 | 0.65 | 0.54 |
| 1 h | 16 | 0.88 | 0.85 |
| 2 h | 112 | 0.86 | 0.81 |
| 4 h | 243 | 0.86 | 0.72 |
| 8 h | 65 | 0.92 | 0.85 |
| 12 h | 2 | 1.15 | 0.98 |

Ratios of totals, from the locked `validation_predictions.csv` and the blind file's base and markup. **Note:** on these
orders F1 is about 14% below JV's price overall (0.86) and 35% below on 30-minute orders (0.65), and never below fair
value (the cost floor binds on 46 of the 544).

## Risk (report-only, training orders, no price changed)

Daily P&L of JV's price (C0) and F1 on the May-July orders, booked on each order's UTC creation day as in the
scorecard. Measures as in Maksim's `daily_risk`: worst day, mean of the worst 5% of days (3 days in May + June, 2 in
July), maximum drawdown of cumulative P&L, and daily standard deviation. C0 keeps every order in both demand scenarios,
so it has one row per period.

| Period | Demand | Model | Profit | Worst day | Worst 5% of days | Max drawdown | Daily sd |
|---|---|---|---:|---:|---:|---:|---:|
| May + June | either | C0 | 10,876 | -9,630 | -5,348 | 12,829 | 1,782 |
| May + June | no response | F1 | 16,587 | -8,620 | -4,372 | 11,021 | 1,535 |
| May + June | central | F1 | 16,594 | -4,228 | -1,881 | 4,653 | 937 |
| July (retrospective) | either | C0 | 4,319 | -5,073 | -4,683 | 5,073 | 1,835 |
| July (retrospective) | no response | F1 | 3,785 | -4,796 | -4,680 | 4,796 | 1,809 |
| July (retrospective) | central | F1 | 1,436 | -4,938 | -4,712 | 4,938 | 1,656 |

**Reading:** with no demand response, F1 is a little less risky than JV's price in May + June (worst day -8,620 vs
-9,630; drawdown 11,021 vs 12,829) and about the same in July. Under the central scenario the gap is much larger
(-4,228 and 4,653), but most of that comes from the assumed loss of orders that F1 prices above JV, so it is not a
measured effect. Monthly rows are in `team_scorecard/risk_daily_pnl.csv`.

### Exposure cap on F1's orders (report-only overlay)

Maksim's rule (`exposure_cap` in `maksim/run_extensions.py`, commit 65daf8c), reimplemented: decline a new order if
the open notional (q x K) in its direction (calls or puts) would go above **250,000 USDC**; a protection stops counting
once it has closed. No hedge, and no quote or `price_orders` changes. Under the central scenario each order counts with
its expected volume. Without a cap, open notional peaked at 518,362 USDC in calls and 503,814 in puts.

| Demand | Period | Orders declined | Premium kept | Profit: no cap -> cap | Worst day: no cap -> cap | Max drawdown: no cap -> cap |
|---|---|---:|---:|---|---|---|
| no response | May + June | 60 | 95.0% | 16,587 -> 16,493 | -8,620 -> -6,513 | 11,021 -> 9,274 |
| no response | July (retrospective) | 196 | 73.6% | 3,785 -> 4,546 | -4,796 -> -2,244 | 4,796 -> 2,641 |
| central | May + June | 18 | 98.4% | 16,594 -> 15,948 | -4,228 -> -4,369 | 4,653 -> 4,794 |
| central | July (retrospective) | 134 | 82.2% | 1,436 -> 2,619 | -4,938 -> -3,313 | 4,938 -> 3,499 |

**Reading:** with no demand response, the cap cuts the worst May + June day by about 2,100 and the drawdown by about
1,750, keeping 95% of premium and almost all the profit. In July it declines more (26% of premium) and improves all
three. Under the central scenario it rarely binds in May + June (18 orders) and makes the worst day and drawdown
slightly worse. These are not comparable with Maksim's saved -8,399 -> -3,976: that used his prices, payouts booked on
the closing day, and the cap plus a hedge.

## Caveats for the deck

- F1's band binds often: 58%, 71% and 75% of quotes are clipped in May, June and July (and 74.9% of blind
  orders). A wider band would have been a new post-hoc variant; the team kept 0.8-1.2.
- The placebo check is reported as declared. A post-hoc diagnostic (not part of the selection rule) shows that its
  noise floor mostly measures the cost floor's price-level effect, so F1's profit gain over R0 is not evidence of better
  allocation. Its selection rests on the Gini and calibration tests.
- External data: FRED (VIX, 10-year yield, S&P 500) and GDELT did not answer from our connection, even after a retry
  with longer waits, so 4a-1 to 4a-3 and 4b1 were not run. No other source was substituted.
- The 544-row check covers only August orders with a revealed markup; it is a level check, not an outcome test.
- Not claimed: demand was not estimated; scenario profits and the risk tables' central-scenario rows are not proven
  commercial effects; R0 is an estimate of JV's price; July is retrospective. The 544 revealed JV prices are not used
  for pricing (team decision, 15 Oct).

## Decisions (16 Oct regroup)

1. Model F1, theta_level = 0, band 0.8-1.2: **locked at 04:46 SGT**.
2. The 544-row reference check ran after the lock; bias and error only, nothing changed because of it.
3. Open: whether JV should run the exposure cap (report-only here), and whether to send `questions_for_jv.md` (not sent).
