# Report explanation — pricing Jasper Vault's Perpetual Protect

**Status: final.** At the 16 Oct regroup the team chose model F1, theta_level = 0 and the 0.8-1.2 band. The
specification was locked at 2026-10-16 04:46 SGT, and only then was our reference checked against the 544 JV prices that
the blind file reveals (section 9).

This note is for an MSBA classmate without a finance background. It explains what we built, what every number means,
how to read each table, what we found and how sure we are, and what we must not claim. Money is in USDC. Unless a
line says otherwise, results are for May + June together under the central demand scenario, with 90% intervals.

## 1. The problem in one paragraph

Jasper Vault (JV) sells short-term price protection on bitcoin (BTC). A buyer pays a premium now. If BTC moves against
them before the protection ends (30 minutes to 24 hours later), JV pays the difference. Between February and July JV
collected 248,089 USDC of premium on 7,150 settled orders and paid out 230,652, so it kept only 7.0%. JV asked for a
price per order that is **better, not just higher**: charge risky orders more and safe orders less.

## 2. The metrics, in plain words

| Term | Meaning |
|---|---|
| **Loss ratio** | Payouts / premium. 0.93 means JV paid out 93 cents of every dollar it collected. Above 1 means a loss |
| **Margin** | 1 - loss ratio. JV's margin was 7.0% |
| **Expected move** | How far BTC is expected to move (up or down) during the protection window, as a fraction of its price. Our move model predicts it from recent volatility and the time of day |
| **Fair value (FV)** | The expected payout of an order: notional x expected move / 2. Selling below it loses money on average |
| **Reference price (P_ref)** | Our estimate of what JV would charge today for the order. It sets our overall price level |
| **Shape** | How much riskier an order is than the reference assumes: FV / P_ref, rescaled by n and kept between 0.8 and 1.2. Our price = P_ref x shape |
| **Cost floor** | Our price is never below fair value. This is the Lerner-rule lower bound: price at least marginal cost |
| **Multiplier vs base** | Our premium / JV's base price for the order. The base is missing for many orders, so the multiplier is often blank |
| **Conversion (demand) scenario** | An assumption about how many buyers stay when the price changes. If r = our price / JV's price, "conservative, e = 2" keeps a share min(r^-2, 1) of each order: cheaper orders do not gain volume, dearer ones lose some. We did **not** estimate demand; we test 12 scenarios |
| **Gini** | Does a model raise prices on the orders that really pay out more? Sort orders from "we charge much less than JV" to "much more", and compare the cumulative share of JV's premium with the cumulative share of payouts. 0 = no better than JV's own pricing; higher = better ranking of risk (Frees, Meyers & Cummings, 2011) |
| **C2 (same-total flat change)** | JV's own prices scaled up or down by one factor so that their total equals the model's total. Beating C2 means the gain comes from *where* the model charges, not from charging more overall |
| **Worst day** | The single worst day's profit (orders grouped by the UTC day they were sold). It shows risk, not just average |
| **Worst 5% of days** | The average profit of the worst 5% of days (3 days in May + June). A steadier version of the worst day, often called expected shortfall |
| **Maximum drawdown** | Add up profit day by day. The drawdown is how far the running total has fallen below its best level so far; the maximum drawdown is the deepest such fall. It is the loss a treasury would have to sit through |
| **Daily standard deviation** | How much daily profit swings around its average |
| **Exposure cap** | A risk rule, not a price: stop selling protection in one direction (calls or puts) while the total size (q x K) of open protections in that direction would go above a limit |
| **Placebo power check** | Shuffle F1's shape at random among similar orders 200 times and see how much profit gain pure chance produces. That spread is the noise floor |
| **CORP terms** | A score of how well price tracks payouts, split into three parts (Gneiting & Resin, 2023): **MCB** = calibration error (level and shape wrong; lower is better), **DSC** = ranking power (higher is better), **UNC** = how noisy the outcomes are (the same for every model) |
| **Regret table** | If our reference level were wrong by -20% to +20%, how much profit would each price-level choice lose against the best choice for that error? The choice with the smallest worst-case loss is the "minimax regret" choice (Bergemann & Schlag, 2011) |
| **90% interval** | We resample whole trading days 2,000 times. If the interval for a difference is entirely above zero, the gain is unlikely to be luck; if it straddles zero, we cannot tell |

## 3. What we built

1. **Move model (our teammate Maksim's design).** For each product length, a Poisson regression predicts the size of
   the BTC move from realised volatility over the last hour, 4 hours, day and week, plus the time of day in New York.
   We rebuilt it and matched his results exactly (mean deviance 47.5130). Our one change: the extra variance added for
   a scheduled CPI, jobs-report or FOMC release is shrunk when few releases have been seen.
2. **Reference price.** JV's charged volatility relative to the last day's realised volatility, by product length (or a
   ridge regression), with its level corrected over the last three training months. It passed its audit: bias -1.6% in
   May and +7.1% in June; weighted error 21.4% and 25.5% (limits 15% and 30%).
3. **Price (F1).** Price = reference x shape, shape kept within 0.8-1.2, never below fair value. One constant n makes
   the training total equal the reference total, so F1 moves prices between orders without changing the overall level.

## 4. Results by model (May + June, central scenario)

| Model | What it is | Price vs JV | Profit | vs JV's price | vs own flat change (C2) | Gini | Worst day | July vs JV |
|---|---|---:|---:|---|---|---|---:|---|
| C0 | JV's actual price | 1.000 | 10,876 | — | — | 0 | -9,630 | — |
| R0 | our estimate of JV's price | 1.054 | 8,336 | -2,540 [-8,915, +4,599] | -7,628 [-11,725, -3,564] | 0.076 [-0.001, 0.149] | -9,608 | -14,588 [-17,698, -11,370] |
| F0 | fair value scaled to JV's total | 1.014 | 12,647 | +1,770 [-9,600, +14,689] | +844 [-7,301, +11,079] | 0.243 [0.149, 0.317] | -3,880 | -1,023 [-5,906, +3,904] |
| **F1** | **selected and locked** | **1.045** | **16,594** | **+5,717 [-4,742, +17,739]** | **+1,402 [-5,596, +9,381]** | **0.235 [0.146, 0.303]** | **-4,228** | **-2,883 [-6,830, +1,081]** |
| F1nf | F1 without the floor (diagnostic) | 1.005 | 12,093 | +1,216 [-7,497, +10,529] | +742 [-4,754, +7,503] | 0.213 | -6,653 | -8,845 [-12,006, -5,595] |
| M | Maksim (FV x 1.25, base floor) | 1.169 | 23,656 | +12,779 [+296, +27,441] | +161 [-6,747, +7,704] | 0.246 [0.153, 0.319] | -2,504 | +10,782 [+3,268, +18,660] |
| S | Subham (selected config) | 1.178 | 20,622 | +9,746 [+1,493, +18,697] | -3,110 [-5,835, +192] | 0.125 [0.036, 0.213] | -5,816 | +10,200 [+4,626, +16,634] |
| C3 | payout-fitted ladder (JV-03) | 0.791 | -20,592 | -31,468 [-40,528, -22,704] | -2,743 [-4,077, -1,558] | 0.103 | -11,261 | +2,420 [-2,372, +6,746] |

**How to read it.** "Price vs JV" is the model's total quote over JV's total (1.045 = 4.5% dearer). "Profit" is
premium kept minus payouts under the central scenario. The bracket is the 90% interval. F1h (a softer F1) is
**infeasible**: the cost floor alone pushes its total 0.15%, 2.61% and 4.97% above the reference total in the three
folds. Jay's model has no row-level history on this data release, so it is not scored.

**What it says.**
- **F1 ranks risk well and stays near JV's price level.** Its Gini is 0.235 [0.146, 0.303], far above R0's 0.076, and
  CORP agrees: ranking power DSC 0.0992 against R0's 0.0279, with lower calibration error (MCB 0.0356 against 0.0428).
- **F1 is selected, but not on profit.** It passed all four pre-registered tests (ranking, calibration, profit not
  worse than R0: +8,258 [+583, +18,608], and no clear harm against JV's price in any scenario). Its gain over JV's
  price (+5,717) and over its own flat change (+1,402) both have intervals that include zero.
- **The ranking comes from Maksim's fair value.** F0, M and raw fair value have almost the same Gini each month
  (0.143 / 0.143 / 0.143 in May, 0.268 / 0.271 / 0.268 in June, 0.097 / 0.097 / 0.097 in July). Our addition is level
  discipline: F1 is 4.5% above JV where M and S are 17-18% above.
- **M and S beat JV by charging more.** Against their own flat change of the same size they show no gain (M +161
  [-6,747, +7,704]; S -3,110 [-5,835, +192]).
- **The cost floor does much of F1's profit work.** F1 beats F1 without the floor by +4,501 in May + June and +5,961 in
  July, mostly by raising the average price (+4.0% and +8.4%).

## 5. How sure we are

| Check | Result |
|---|---|
| May, June, July separately (F1 Gini) | 0.099 [-0.000, 0.193], 0.269 [0.162, 0.349], 0.101 [0.048, 0.154]: positive every month; May's lower bound touches zero |
| F1 profit vs JV by month | May 4,154 vs 4,620; June 12,440 vs 6,257; July 1,436 vs 4,319 (July is retrospective) |
| Without the top 1% of orders by size | F1 vs R0 +8,470 (with them +8,258); F1 vs JV +5,304 (with them +5,717) |
| Placebo noise floor | Shuffled shapes gain 9,580 to 11,174 over R0, and F1's real gain (+8,258) is inside that range |
| Calm, middle and volatile markets | F1 vs JV +3,678, +1,108, +932 (May + June terciles of 1-hour volatility) |

**Reading the placebo.** As declared, each shuffle keeps F1's cost floor. A post-hoc diagnostic (not part of the
selection rule) shows why the shuffles look so good: a random shape often sets a risky order below its fair value, so
the floor lifts 34.7% of orders (F1: 15.4%), raising the total price to 1.059 times R0's (F1: 0.992). Without the
floor the shuffles lose 5,927 on average while F1 still gains 3,756. So the noise floor mostly measures the floor's
price-level effect, and **F1's profit over R0 is not evidence of better allocation**. Its selection rests on the Gini
and calibration tests.

**What we must not claim.**
- We did not estimate demand. The 12 scenarios are assumptions, so scenario profits are not proven commercial gains.
- July was seen by the team before, so it is a retrospective check, not a clean test.
- The reference price is our estimate of JV's price, not JV's real formula. It quoted 0.98x, 1.07x and 0.88x JV's
  actual total in May, June and July, and ran 7.6% below the 544 JV prices revealed in August (section 9). F1
  inherits any level error.
- The blind orders cannot be filtered the way JV filtered training (627 below-base orders removed), because 2,195
  blind orders have no base. We do not know the size or direction of any bias this causes.

## 6. Other tables, and how to read them

**Band and floor (`clipping_and_floor.csv`).** F1's 0.8-1.2 band binds for 58.2%, 70.8% and 74.8% of orders in May,
June and July (mostly the lower bound in June and July: 53.1% and 54.9%). The floor raises 17.0%, 14.8% and 18.8%. So
many quotes sit at a limit, and a better forecast moves few final prices. A wider band would have been a new, unscored
variant; the team kept 0.8-1.2.

**Price-level frontier (`theta_frontier.csv`).** theta_level shifts all of F1's prices. Under the central scenario
profit rises from 13,336 (theta -0.05) to 16,594 (0), 19,938 (+0.05), 23,266 (+0.10) and 30,322 (+0.25), while the
share of orders kept falls from 86.9% to 84.8%, 82.4%, 79.6% and 70.4%. Under the strict rule "the buyer stays only if
we are no dearer than JV today", profit peaks at +0.05 (12,805) and falls after. **Reading:** with a 7% margin, losing
some orders costs little while each kept order earns more, so the conservative scenarios always favour a higher price.
That is the "just charge more" answer JV ruled out, so the team kept theta_level = 0.

**Regret table (`level_regret.csv`).** The worst-case regret falls from 13,848 at theta 0 to 0 at +0.25. That is the
top of the grid, not an optimum, and it inherits the same demand assumption.

**Volume sanity table (notebook section 9.8).** To keep today's May + June profit after a price cut, JV would need
1.13 times the orders after a 1% cut and 2.40 times after a 5% cut; after a 10% cut no volume is enough, because the
price would fall below cost. On the whole Feb-Jul book: 1.17 and 3.46 times.

**Where the payouts come from (`payout_attribution.csv`, descriptive only).** Orders whose window contained a
scheduled release hold 5.7% of premium and 8.5% of payouts over Feb-Jul (loss ratio 1.39). Orders whose window held
one of the largest unscheduled 15-minute moves hold 4.5% and 8.8% (loss ratio 1.81). In June, big unscheduled moves
carried 9.8% of JV's premium but 19.2% of payouts (loss ratio 1.84 at JV's price, 1.68 at F1's). In July, release
windows carried 8.6% of premium and 14.7% of payouts (1.64 at JV's price, 1.57 at F1's; 1.11 without the 10 largest
losses). Not every month: in May both groups made money at JV's price (loss ratios 0.59 and 0.89) and at F1's (0.52
and 0.63). None of the 18 largest 15-minute moves fell
within an hour after a release. **Reading:** the biggest moves are unscheduled and lumpy, so no quote-time model
foresees them. That is the case for a risk layer, not for a bigger pricing model. The groups are defined with hindsight,
so a loss ratio above 1 here is expected and is not a pricing error.

## 7. Extensions we tested (Phase 4)

We tested a closed list of 15 ideas, written down before any run, including the macro and sentiment data JV suggested.
A move-model feature had to improve forecast skill by at least 0.005 in at least 5 of 7 product lengths, beat at least
18 of 20 copies of itself shifted by whole weeks (a placebo), and then keep F1's Gini and earn more than F1 with an
interval above zero.

| ID | Idea | Lengths with gain >= 0.005 (of 7) | Mean gain | What happened |
|---|---|---:|---:|---|
| 4a-1 to 4a-3 | VIX, US 10-year yield, S&P 500 (FRED) | — | — | not run: the data source did not answer |
| 4a-4 | Binance funding rate | 0 | -0.0022 | no forecast gain |
| 4a-5 | Deribit DVOL (BTC implied volatility) | 5 | +0.0088 | better forecasts and beats 18 of 20 shifted copies, but slightly lower Gini than F1 (0.234 vs 0.235) and less profit (-1,553 [-2,487, -771]) |
| 4a-6 | Crypto Fear & Greed | 0 | -0.0005 | no forecast gain |
| 4a-7 | Fed dollar index | — | — | not run: the series is revised and no vintage was available |
| 4b1-1, 4b1-2 | GDELT news attention | — | — | not run: the data source did not answer |
| 4b2 | LLM headline score | — | — | not run (needed Aman's OK and a passing 4b1) |
| 4c-1 | Jump share of last-hour variance | 0 | +0.0010 | too small |
| 4c-2 | Volatility of volatility | 4 | +0.0042 | close, but 4 of 7 lengths (rule: 5) |
| 4c-3 | PCE releases | 0 | -0.0000 | no gain |
| 4c-4 | DVOL in the reference price | — | — | better on the calibration months, but many shifted copies also helped, the audit failed (June bias -20.7%) and profit fell (-6,745 [-9,911, -3,922]) |
| 4d | Payout calibration by length | — | — | lower Gini (0.222) and no profit gain (-336 [-2,189, +1,097]) |

**Reading.** Nothing was adopted: "JV's suggested macro and sentiment data tested; none adopted" (the FRED macro series and the GDELT news series could not be downloaded, so they were not run). The one feature that passed the forecast test, BTC implied volatility (DVOL), separates level from allocation: at 1.022 times JV's total it charges about 2% less than F1 (1.045), and its gain over its own flat change (+1,952 [-4,804, +10,010]) is no more certain than F1's (+1,402 [-5,596, +9,381]). With 58-75% of F1's quotes at a band limit, a better forecast moves few final prices.

## 8. The blind-file prices (Phase 5, final)

The final model is F1 at theta_level = 0 with the 0.8-1.2 band, refitted once on 7,132 orders created and settled
before 31 Jul 17:11 UTC. It priced all 4,155 blind orders (total 177,986 USDC, `validation_predictions.csv`). 74.9% of
the quotes sit at a band limit and the cost floor lifts 12.4%. On the 1,960 orders with a base, our median price is
1.484 times the base, close to JV's own median in training (1.505). By product length, F1 charges 0.88 times our
estimate of JV's price for 30-minute orders, 0.80 for 12- and 24-hour orders, and 1.03-1.08 for 2-8 hour orders
(1.02 overall).

**Locking.** "Locking" means freezing every choice before looking at any check that uses validation prices, so the check
cannot steer the model. The lock time and a fingerprint (SHA-256) of the predictions file are stored in
`model_params.json`. A rerun of the notebook rebuilds exactly the same file.

## 9. Checking our estimate of JV's price on 544 blind orders (after the lock)

For 544 blind orders, all from August, the file shows JV's base and markup per BTC, so JV's price can be recovered as
q x (base + markup). We first confirmed this rule on all 6,073 training orders that show both (it holds exactly), and
that the blind numbers are in the same units. Then we compared our locked reference price with these JV prices. We
report only bias and error: no payout is rebuilt and nothing in the model was changed.

| Orders | Count | Bias | Weighted error |
|---|---:|---:|---:|
| All revealed orders | 544 | -7.6% | 13.4% |
| Rows 0-1,897 (the documented release) | 479 | -5.5% | 12.7% |
| Rows 1,898-4,154 (newer orders) | 65 | -21.7% | 19.6% |
| 30-minute orders | 106 | -20.7% | 18.4% |
| 4-hour orders | 243 | -4.3% | 12.0% |

**How to read it.** Bias -7.6% means our reference totals 7.6% less than JV's actual prices on these orders. The
weighted error, 13.4%, is the typical size of the miss on one order, weighted by order size. Overall this is inside the
limits we set for the May and June audit (bias within 15%, error within 30%), and the reference runs low as it did in
the July check (-12.4%). It runs about 20% low on 30-minute orders and on the newer rows. Cautions: these are August
orders only, they need not look like the 2,195 orders without a base, and the team had looked at the blind inputs
before, so this is not untouched data.

## 10. Risk: bad days, drawdowns and an exposure cap (report-only)

These tables change no price. They use the May-July training orders (July retrospective), with each order's profit on
the day it was sold.

| May + June | Profit | Worst day | Worst 5% of days | Max drawdown | Daily sd |
|---|---:|---:|---:|---:|---:|
| JV's price (C0) | 10,876 | -9,630 | -5,348 | 12,829 | 1,782 |
| F1, no demand response | 16,587 | -8,620 | -4,372 | 11,021 | 1,535 |
| F1, central scenario | 16,594 | -4,228 | -1,881 | 4,653 | 937 |

**How to read it.** With no demand response (every buyer stays), F1 is a little less risky than JV's price: its worst
day is about 1,000 better and its deepest drawdown about 1,800 smaller. Under the central scenario F1 looks much safer,
but that comes from the assumption that buyers of orders F1 prices above JV partly leave; it is not measured. In July
(retrospective) F1 and JV are close (worst day -4,796 vs -5,073 with no demand response).

**The exposure cap.** We reused Maksim's rule (`maksim/run_extensions.py`, commit 65daf8c): stop selling in a direction
while open protections in that direction would exceed 250,000 USDC of notional. Without a cap, open notional reached
518,362 USDC in calls and 503,814 in puts. On F1's May + June orders with no demand response, the cap declines 60 orders
and keeps 95.0% of premium. Profit goes from 16,587 to 16,493, the worst day from -8,620 to -6,513, and the maximum
drawdown from 11,021 to 9,274. In July it declines 196 orders (premium kept 73.6%) and improves profit (3,785 to 4,546),
the worst day (-4,796 to -2,244) and the drawdown (4,796 to 2,641). Under the central scenario it rarely binds in May +
June (18 orders) and makes the worst day slightly worse (-4,228 to -4,369). The cap trades a little revenue for smaller
bad days; it does not touch prices.

## 11. Recommendation for JV

1. **Use F1 as the per-order price, at today's level (theta_level = 0).** It keeps JV's overall level and moves price
   toward the risky orders. Its gain is in ranking and calibration; the profit gain is not proven.
2. **Why ranking matters even when backtest profit is flat.** Our scenarios hold the payouts fixed. In reality, when
   prices rise, the lowest-risk buyers leave first (adverse selection). A flat price rise keeps the riskiest buyers,
   while risk-based pricing charges them more (Einav, Finkelstein & Cullen, 2010).
3. **Add a risk layer.** On F1's own May + June orders, a 250,000 USDC cap per direction cut the worst day from -8,620
   to -6,513 and kept 95% of premium (no demand response; section 10). In Maksim's saved result (his prices, training
   months, payouts booked on the closing day), the same cap plus a 0.5 BTC hedge band cut the worst day from -8,399 to
   -3,976, at the cost of about 30% of profit.
4. **Run an A/B price test to learn willingness to pay.** Randomly raise or cut prices for some orders and measure the
   **elasticity** = change in log orders / change in log price. Under its assumptions (a constant elasticity e and a
   known cost), the Lerner rule then gives the margin: (price - cost) / price = 1 / e. Run it as a bandit experiment
   that shifts traffic toward better prices while it learns, to limit lost profit (Misra, Schwartz & Abernethy, 2019),
   and use fair value as a pre-test covariate to cut the sample needed (CUPED; Deng et al., 2013).
5. **Watch the level every day.** Compare JV's price with our reference inside a band that widens after misses and
   narrows after hits (adaptive conformal inference; Gibbs & Candès, 2021). A breach is an alarm to recalibrate the level.

**Risks.** The level depends on our estimate of JV's price; many quotes sit at the band's limits; demand is unknown;
large unscheduled moves will still cause losses.

## 12. Why we did not build an LLM trader or an LLM pricer

Most work on LLM trading predicts the **direction** of prices, but the cost of selling at-the-money protection depends
on the **size** of the move. In a small benchmark, standard LLM trading agents lost 15-22 percentage points of alpha
after their training period (Benhenda, 2026). LLM pricing agents reached supracompetitive prices and were sensitive to
small changes in wording (Fish, Gonczarowski & Shorrer, 2024). So there is no language model anywhere in our quote path.
We allowed news only as a tested input to the volatility forecast: an hourly GDELT news-attention feature, tested like any other feature. GDELT did not answer, so it was not run. The planned headline score from a language model trained before 2026 (4b2) needed a passing 4b1 and Aman's OK, so it was not run either. Of the market series JV suggested, the funding rate, DVOL and Fear & Greed were tested and none was adopted; the FRED series could not be downloaded (section 7).
