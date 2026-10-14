# Perpetual Protect pricing strategy (Maksim)

Pricing strategy for Jasper Vault's Perpetual Protect (PP): analysis, code, backtests, overfitting checks and a recommended premium for every order in the validation file. This folder is a working strategy for the team, not a final submission document.

**Recommended rule.** `premium = quantity x fair value per BTC x 1.25`, never below Jasper Vault's API base price when that quote exists. The fair value is half the expected size of the BTC move over the protection window, forecast from recent volatility, the time of day (US Eastern) and scheduled US releases (CPI, jobs report, FOMC). The model is fitted on BTC market data only; no order outcome is used to fit it.

## Summary

| Question | Answer and evidence |
| --- | --- |
| How profitable is current pricing? | Barely. February to July 2026: premiums 248,089 USDC, payouts 230,652 USDC, loss ratio 0.93. June and July orders with a base quote: loss ratio 1.00. |
| Does the current markup (CTA layer) track risk? | No. Relative to the API base price its ordered Lorenz Gini is 0.01 (90 percent interval minus 0.05 to 0.07): it carries no information about which orders pay out. |
| Does the model track risk? | Yes. On the 3,947 June and July test orders with a base quote, Gini 0.175 against the current price (0.10 to 0.24) and 0.151 against the base price (0.10 to 0.20). Its fair value matches actual payouts (payout / fair value 0.98, interval 0.88 to 1.09, February to July) without being fitted on any payout. |
| Which factors matter? | Recent volatility, and above all the time of day: BTC variance in the half hour after the 09:30 ET US equity open is about 3.8 times its average over the week, and the base price ignores this. Scheduled releases add extra variance, but this estimate is unstable (0 to 57 basis points depending on the fit window). Direction (call or put) does not matter; order size matters only below 1,000 USDC (those orders pay out 0.79 of fair value). |
| Profit in the June and July test | 45,101 USDC against 10,576 for current pricing if users do not react to price; 39,603 if a 10 percent higher price loses 10 percent of orders; 12,280 if every order priced above today's price is lost and cheaper prices win nothing. |
| Is it better pricing or just higher pricing? | Partly higher. Total premium is 16.5 percent above today's. 61 percent of orders get cheaper, but they are small: orders holding 63 percent of today's premium get dearer (large orders plus 17 percent). Against a flat raise of every current price to the same total, the model has smaller losses on bad days (worst day minus 7,636 against minus 8,530) and earns more when users are price-sensitive (elasticity 1: 39,603 against 38,717; elasticity 2: 37,532 against 33,237; strict rule: 12,280 against 0), but less when users accept any rise up to 25 percent (18,463 against 45,101). |
| Main risk | If users are lost as soon as a price exceeds what they paid today and cheaper prices win no extra orders, the model earns less than current pricing over the six-month walk-forward (15,401 against 17,437 USDC). It cuts prices that users already accepted while losing some profitable large orders. |
| Overfitting | Forecast skill 0.208 in sample and 0.187 out of sample; coefficients and the time-of-day profile are stable across refits; the simplest version (recent volatility and time of day, nothing else) gives 95 percent of the final profit. See section 6. |
| Basic extensions (tested on training data after the holdout check, rule fixed in advance) | Delta hedging the net book within a 0.5 BTC band cuts the worst training day from minus 7,636 to minus 4,042 USDC for about 22 percent of profit, but would not have prevented the August loss. Range-based volatility, volume features and a US-holiday calendar all failed the pre-registered adoption rule, so the submitted prices are unchanged. See sections 5.7 and 7. |
| Untouched holdout (validation file, August to October) | Checked once, after the recommendations were frozen and pushed (commit c70c413). The book is profitable but thin: premiums 205,824 USDC, payouts 201,003 USDC, loss ratio 0.98. August lost 12,667 USDC: BTC rose 25 percent and calls paid out 2.0 times fair value, although the size of the moves was forecast correctly (realised / expected move 1.03 for calls, 0.97 for puts). September and October were profitable (loss ratios 0.88 and 0.77). On the August orders with a base quote the model lost less than the base price and than a flat markup at today's average, but its risk ranking did not hold there. See section 6.4. |

![Loss ratio by quintile of model risk](results/figures/loss_ratio_by_model_quintile.png)

## Contents

1. [The product and the data](#1-the-product-and-the-data)
2. [What the data shows](#2-what-the-data-shows)
3. [The model](#3-the-model)
4. [How the model was tested](#4-how-the-model-was-tested)
5. [Results](#5-results)
6. [Overfitting checks](#6-overfitting-checks)
7. [Alternatives tested and not used](#7-alternatives-tested-and-not-used)
8. [Validation recommendations](#8-validation-recommendations)
9. [Data integrity notes](#9-data-integrity-notes)
10. [Limitations and open decisions](#10-limitations-and-open-decisions)
11. [How to reproduce](#11-how-to-reproduce)

## 1. The product and the data

PP is short-dated protection on a perpetual futures position. A trader who is long buys a put (option type 1), a trader who is short buys a call (option type 0). All products in the data are at the money with zero deductible and last 0.5, 1, 2, 4, 8, 12 or 24 hours. The user pays the premium up front; Jasper Vault pays out if the price moves against the position.

**How the payout is computed.** The payout equals `quantity x max(price at close minus strike, 0)` for a call and `quantity x max(strike minus price at close, 0)` for a put, where "close" is when the user closes the protection (67 percent of orders close more than 30 seconds before expiry) or the expiry time. Checked against the one-minute BTC candles (price at a timestamp = close of the minute that contains it): the formula gives 231,193 USDC in total against 230,652 USDC recorded (0.2 percent apart) with a per-BTC correlation of 0.994; among the 46 percent of orders that paid out, the median difference is 16.7 USDC per BTC (8 percent), mostly because the recorded price is not exactly the minute's close. Early closing does not raise payouts: with the same price convention, holding every order to expiry would have paid 237,206 USDC instead of 231,193 USDC.

**Files used.**

| File | Content |
| --- | --- |
| `../data/with_base_premium/pp_transactions_training.csv` | 7,204 orders, 2 February to 31 July 2026, with the API base price per BTC (blank for 1,131 orders) |
| `data/pp_transactions_validation.csv` | 4,155 orders, 31 July to 14 October 2026, outcome hidden (see section 8 for its two blocks) |
| `data/btc_market_history_2026-01-01_to_2026-10-14.parquet` | 412,080 one-minute BTCUSDC perpetual candles. Identical to the supplied file on every overlapping candle except the last one, which was still open when the supplied file was cut |
| `data/nyse_holidays_2026.csv` | NYSE full-day closures in 2026, from nyse.com (used only by the holiday candidate) |
| `data/macro_events_2026.csv` | 38 US releases (CPI, jobs report, FOMC, PCE), January to October 2026, each with an official source URL (BLS, BEA, Federal Reserve), checked by a second independent pass |

## 2. What the data shows

Numbers in this section come from `run_descriptive.py` (`results/descriptive_facts.json`) unless stated otherwise.

1. **Current pricing is close to break-even.** Loss ratio 0.93 overall, and above 1 in some segments: 4-hour products 1.14 over February to July, and the 08:00 to 12:00 UTC window 1.23 in June and July.
2. **The API base price is too low.** Payouts were 1.40 times the base price in total. The base price is a Black-Scholes value; its implied volatility fell from about 50 percent per year in February and March to about 31 percent in July (monthly medians). For 30-minute and 1-hour orders it is below the realised volatility of the hour before the order (medians 36 and 33 percent against 44 and 41 percent); for longer products the two are similar. The main shortfall is that the base price does not change with the time of day, while orders cluster in the most volatile hours.
3. **The CTA markup does not follow risk.** Split into five equal groups by markup, the orders with the lowest markup (mean 1.15 times base) lost money (loss ratio 1.18) and those with the highest markup (mean 2.50 times base) were very profitable (0.56), while the payout per unit of base price was similar in all five groups (1.30 to 1.47).
4. **Time of day is the largest missing factor.** On weekdays, BTC variance in the half hour after 09:30 ET is 3.8 times its average over all minutes of the week (final profile in `outputs/model_card.json`) and stays above average until early afternoon; nights and weekends are calmer. See `results/figures/time_of_day_volatility.png`.
5. **Scheduled releases move BTC.** In the 30 minutes after a release, BTC moved 2.6 times as much as in the same clock window on the preceding release-free weekdays for FOMC decisions (5 releases), 1.8 times for the jobs report (7), 1.4 times for CPI (7) and 0.92 times for PCE (8), so PCE is not used. The counts are small and the effects uncertain.
6. **Direction is not predictable from the training data.** BTC was at 77,626 at the first training order (2 February) and 62,798 at the last (31 July), and puts lost more than calls. Relative to the model's fair value, however, calls paid out 0.90 and puts 1.10, and both 90 percent intervals include 1. A downtrend over six months is not a forecast for the next few hours, so the model prices the size of the move, not its direction.

## 3. The model

```
premium (USDC) = quantity (BTC) x fair value per BTC x (1 + margin), with margin = 25 percent
                 and premium per BTC >= API base price per BTC whenever a base quote exists

fair value per BTC = Black-Scholes value with window volatility s = expected |move| x sqrt(pi / 2)
                   = strike x expected |move| / 2 for an at-the-money option
```

**Step 1. Expected move.** For each product length there is one Poisson regression (log link) that predicts the expected absolute log return of BTC over the protection window from six inputs, all measured before the order is created:

| Input | Meaning |
| --- | --- |
| `log_var_60m`, `log_var_240m`, `log_var_1440m`, `log_var_10080m` | how much BTC moved in the last hour, 4 hours, day and week (log of the average squared one-minute return) |
| `log_seas_window` | typical activity during the protection window, from the time-of-day profile (US Eastern time, weekday or weekend) |
| `log_seas_last60` | typical activity during the last hour, so that a busy last hour that is simply due to the US open is not read as a more volatile market |

The regressions are fitted on market history, one window every 5 minutes (about 41,000 windows per product length in the June development fit and 59,000 in the final fit), not on the 7,204 orders. A Poisson regression with a log link estimates the mean of a non-negative quantity directly, which is what pricing needs.

**Step 2. Scheduled releases.** If a CPI, jobs report or FOMC release falls inside the window, the window variance increases by a fixed amount, estimated from past releases as the extra squared 30-minute move after a release compared with the same UTC clock time on other weekdays (57 basis points of move in the final fit, from 19 releases). Because variances add, this raises a 30-minute price a lot and a 24-hour price only slightly.

**Step 3. Fair value.** The expected move is converted into a volatility for the window and priced with Black-Scholes at zero interest. For the at-the-money strikes in the data this is close to `strike x expected move / 2`; the same formula prices other strikes (for example a deductible), which is how moneyness enters.

**Step 4. Margin and floor.** A margin of 25 percent corresponds to a target loss ratio of 80 percent. It was set as a business target before any test was run at that margin; section 5.4 shows margins from 0 to 50 percent. The premium never goes below the API base price when a base quote exists: the supplied data already excludes every order priced below the base, and payouts averaged 1.4 times the base. The floor applied to 16 percent of June and July test orders with a base quote and added about 400 USDC of profit; it does not apply to orders without a base quote.

**Worked example (a real order).** On 16 June 2026 at 13:39 UTC (09:39 ET, nine minutes after the US equity open) a user bought a 1-hour put on 0.1702 BTC at a strike of 65,994 USDC (notional 11,233 USDC).

- The last hour was active: average squared one-minute return `exp(-14.26)`, about 58 percent per year in volatility terms.
- The window 09:39 to 10:39 ET is the busiest hour of the day: time-of-day factor `exp(1.256) = 3.5` times average.
- Expected move over the hour: 0.66 percent. Fair value per BTC = 65,994 x 0.0066 / 2 = 217.85 USDC.
- Model price per BTC = 217.85 x 1.25 = 272.31 USDC, so the premium is 0.1702 x 272.31 = **46.35 USDC**.
- For comparison: API base price 92.62 per BTC (15.76 USDC), current price 165.88 per BTC (**28.23 USDC**).
- Actual payout: **84.07 USDC**. Both prices lost money on this order, as single orders often do: the current price lost 55.83 USDC and the model price 37.72 USDC. The point is the average over thousands of orders.

## 4. How the model was tested

- **No order outcome is used to fit the model.** Every parameter comes from market data and the release calendar; orders are only used to evaluate it.
- **Chronological split.** Development fit on data before 1 June 2026; test on the 4,841 orders of June and July. Each order uses only candles that had closed before it was created. June and July were also used to compare model variants during development (section 6), so they are not a fully untouched holdout; the validation file is.
- **Walk-forward.** Every month from February to July is priced by a model fitted only on data before that month.
- **Ranking test.** The ordered Lorenz curve and Gini index (Frees, Meyers and Cummings, 2011, a standard tool for comparing insurance premiums) measure whether a premium charges more where payouts turn out larger, independent of the price level. Intervals come from resampling whole days.
- **Conversion rules.** Jasper Vault's conversion rule is not published, so profit is shown under several rules. With elasticity e, an order priced at P instead of today's price A is counted `(P / A) ^ (-e)` times (capped at 3). Under elasticity 1 or less, any uniform price rise raises profit (with elasticity 1 the revenue per order stays at today's price), so these rules cannot tell better pricing from higher pricing. The threshold rules can: an order is kept only if P is at most A (or at most 1.25 A), or at most 1.5 or 2 times the base price, and lower prices win no extra orders.
- **Benchmarks.** Current pricing; the API base price; a flat markup on the base price (1.37, the average markup before June); and flat raises of every current price by 16.5 percent (the model's total premium) and by 25 percent.
- **Risk.** Daily profit and loss of the PP book: worst day, average of the worst 5 percent of days, maximum drawdown, share of losing days.
- 54 training orders have no close time and no payout in the source file and are excluded from every evaluation.

## 5. Results

### 5.1 Out-of-sample test, June and July 2026 (4,841 orders, profit in USDC)

| Conversion rule | Current price | Model | Flat raise x1.165 (same total as model) | Flat raise x1.25 |
| --- | ---: | ---: | ---: | ---: |
| No demand response | 10,576 | 45,101 | 45,101 | 62,925 |
| Elasticity 0.5 | 10,576 | 41,739 | 41,787 | 56,281 |
| Elasticity 1 | 10,576 | 39,603 | 38,717 | 50,340 |
| Elasticity 2 | 10,576 | 37,532 | 33,237 | 40,272 |
| Keep only orders priced at or below today | 10,576 | 12,280 | 0 | 0 |
| Keep only orders at most 25 percent above today | 10,576 | 18,463 | 45,101 | 62,925 |

| Risk, no demand response | Current price | Model | Flat raise x1.165 (same total as model) |
| --- | ---: | ---: | ---: |
| Loss ratio | 0.95 | 0.82 | 0.82 |
| Worst day (USDC) | minus 9,630 | minus 7,636 | minus 8,530 |
| Average of the worst 5 percent of days (USDC) | minus 5,552 | minus 4,342 | minus 4,691 |
| Maximum drawdown (USDC) | 13,031 | 9,673 | 10,817 |
| Share of losing days | 31 percent | 16 percent | 21 percent |

![Cumulative profit](results/figures/cumulative_profit_test_period.png)

On the 3,947 test orders with a base quote, the API base price alone would have lost 53,246 USDC and a flat 1.37 markup on the base would have lost 10,317 USDC; current pricing made 8 USDC and the model 30,732 USDC. Under base-relative acceptance rules (an order is kept only if its price is at most 1.5 or 2 times the base price), the model makes 9,186 and 21,202 USDC against minus 8,766 and minus 7,311 for current pricing.

### 5.2 Where the gain comes from: allocation and price level

**Allocation at today's price level.** Rescaling the model so that it collects the same total premium as today (a diagnostic, since the scale uses test totals) separates better pricing from higher pricing. On all 4,841 test orders, profit is 11,602 against 10,576 at elasticity 1, 12,720 at elasticity 2 and 12,642 if rises up to 25 percent are accepted; the worst day improves from minus 9,630 to minus 6,231 and the maximum drawdown from 13,031 to 7,990. Under the strictest rule, allocation alone loses (4,098 against 10,576), because it cuts prices that users already accepted.

**Price level.** Most of the profit increase comes from the margin. Current pricing keeps about 5 to 7 percent of premium as profit, a thin margin for a book whose daily result swings by thousands of USDC. The model sets the level from a calibrated cost (fair value matches payouts at 0.98) plus a 25 percent margin, and decides where the increase falls: large orders plus 17 percent, medium orders plus 11 percent, small orders minus 6 percent; 4-hour products plus 39 percent and 30-minute products minus 13 percent.

| Segment (June and July) | Current loss ratio | Model loss ratio | Model price change |
| --- | ---: | ---: | ---: |
| 0.5-hour products | 0.62 | 0.70 | minus 13 percent |
| 4-hour products | 1.18 | 0.85 | plus 39 percent |
| 8-hour products | 1.01 | 0.78 | plus 29 percent |
| Orders 00:00 to 04:00 UTC | 0.73 | 0.90 | minus 19 percent |
| Orders 08:00 to 12:00 UTC | 1.23 | 0.92 | plus 34 percent |
| Release in window | 1.53 | 1.22 | plus 25 percent |

### 5.3 Walk-forward, February to July 2026 (profit in USDC)

| Conversion rule | Current price | Model | Months in which the model earns more |
| --- | ---: | ---: | ---: |
| No demand response | 17,437 | 62,879 | 6 of 6 |
| Elasticity 1 | 17,437 | 53,864 | 6 of 6 |
| Keep only orders at most 25 percent above today | 17,437 | 28,911 | 4 of 6 |
| Keep only orders priced at or below today | 17,437 | 15,401 | 3 of 6 |

Under the strictest rule the model earns less in April (1,033 against 2,645), May (2,490 against 4,620) and July (3,715 against 4,319), and more in February, March and June. In April and May current pricing was profitable (loss ratios 0.76 and 0.82); there the model's price cuts give margin away and its price rises lose orders that would have been profitable. This is the main risk of the strategy if Jasper Vault's conversion constraint works this way. See `results/figures/walk_forward_monthly_profit.png` and `results/walk_forward_monthly.csv`.

### 5.4 Margin

| Margin | No demand response | Elasticity 1 | Elasticity 2 | Keep if not dearer | Keep if at most 25 percent dearer |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 percent | minus 1,497 | 729 | 2,558 | minus 2,675 | 5,290 |
| 10 percent | 16,669 | 17,720 | 19,203 | 6,386 | 14,361 |
| 25 percent (chosen) | 45,101 | 39,603 | 37,532 | 12,280 | 18,463 |
| 40 percent | 74,066 | 57,476 | 48,961 | 12,331 | 27,297 |
| Current price | 10,576 | 10,576 | 10,576 | 10,576 | 10,576 |

June and July 2026; full grid in `results/margin_sensitivity_test_period.csv`. Under the strict rule profit is flat from 25 percent upwards. The margin is the main business lever and depends on how price-sensitive users are, which only a live price test can measure.

### 5.5 Which factors carry the ranking power

| Model variant | Forecast error (Poisson deviance, lower is better) | Gini against current price (3,947 orders) | Gini against base price (3,947 orders) |
| --- | ---: | ---: | ---: |
| Average move only | 54.07 | 0.065 | minus 0.025 |
| Recent volatility | 50.35 | 0.061 | 0.010 |
| plus time of day | 47.67 | 0.164 | 0.136 |
| plus scheduled releases (final) | 47.51 | 0.175 | 0.151 |
| plus HMM regime | 47.99 | 0.175 | 0.150 |

Recent volatility alone is about as informative as the base price, which already contains market implied volatility. The time-of-day profile is what makes the model better than the base price.

### 5.6 Risk and proposed limits

The five worst days of the model's book in June and July (`results/worst_days_test_period.csv`) were days of large BTC moves: 24 June (BTC range 7.0 percent, model minus 7,636 against current minus 9,630), 31 July (4.8 percent), 14 July (4.6 percent), 18 June (4.2 percent) and 25 June (6.7 percent). On each of these days the model lost less than current pricing. Suggested limits to accompany the pricing, not tested here:

- a daily loss limit (for example 10,000 USDC) that triggers a review of the margin and of the release-window treatment;
- a cap on open protected notional per direction, tighter during scheduled release windows (which remain underpriced, model loss ratio 1.22) and after a large one-way move;
- monthly monitoring of the loss ratio by product length and hour, with a review if a segment exceeds 1.0 for a month.

### 5.7 Delta hedging

Jasper Vault is short every protection it sells, so its book loses when BTC moves strongly in either direction and also carries a directional exposure (the net delta). A basic risk control for an options seller is to hedge that directional exposure with a BTC perpetual position. `run_extensions.py` tests this without changing any price: each protection's delta (Black-Scholes, with the model's window volatility) is hedged from open to close. Assumed trading cost: 0.04 percent of hedge notional per side. Profit in USDC, February to July walk-forward, model prices, no demand response.

| Hedge | Profit after costs | Hedge cost | Worst day | Maximum drawdown | Standard deviation of daily profit |
| --- | ---: | ---: | ---: | ---: | ---: |
| No hedge | 62,879 | 0 | minus 7,636 | 9,673 | 1,246 |
| Every order hedged on its own | 28,197 | 31,671 | minus 5,653 | 8,991 | 1,000 |
| Net book, rebalanced when off by more than 0.5 BTC | 49,157 | 13,998 | minus 4,042 | 6,523 | 1,025 |
| Net book, rebalanced when off by more than 1 BTC | 52,676 | 5,722 | minus 5,247 | 8,539 | 1,123 |

- Hedging every order on its own costs about half the profit. The book's net delta is small (at most 2.3 BTC, 95th percentile 1.2 BTC), so hedging the net book within a band is much cheaper: with a 0.5 BTC band it costs 22 percent of profit and cuts the worst day by 47 percent and the maximum drawdown by 33 percent. The band hedge was added after the per-order result was seen; the bands are round numbers, not tuned.
- Post hoc on the validation period (frozen prices, payouts recomputed): the 1 BTC band improves the worst day from minus 15,183 to minus 11,386 USDC and the maximum drawdown from 34,184 to 29,550, with profit about unchanged after costs (3,728 against 4,821). The August loss came from large moves on the side that pays out, not from a net directional position, so hedging limits it only partly. Margin and exposure caps per direction remain the main controls for such months.
- Outputs: `results/extensions/hedging_summary.csv`, `hedging_net_book_bands.csv`, `hedging_training_monthly.csv`, `net_exposure.json`.

## 6. Overfitting checks

Two kinds of overfitting are possible here. The first is fitting noise with too many parameters. The second is choosing the design after looking at the test results, so that the test period stops being a fair test. Both were checked with `run_overfitting_checks.py` (outputs in `results/overfitting/`).

### 6.1 Parameters

The model has 7 regressions with 7 coefficients each, a 96-value time-of-day profile and one release parameter, all fitted on market data (41,000 to 59,000 windows per regression, `results/overfitting/move_model_coefficients_by_cutoff.csv`). No parameter is fitted on order payouts, and the margin is a business target.

- *In sample against out of sample.* The move model was refitted at five monthly cut-offs (1 March to 1 July) and scored on the following month. Skill, the reduction in forecast error against a model that only knows the average move, is 0.208 in sample and 0.187 out of sample on average. By product length the gap is small (30 minutes 0.26 against 0.24, 4 hours 0.20 against 0.20) and largest for the rare 12-hour product (0.19 against 0.13). Out of sample the forecasts are slightly too high on average (realised / predicted 0.955), which errs on the safe side for pricing.
- *Stability.* Across six fits, the coefficient on last-hour volatility varies by 0.01 to 0.03 around values of 0.05 to 0.27. The weekday time-of-day profile fitted on January to March correlates 0.93 with the one fitted on April to July (weekend profile 0.55, less stable). The release effect is the least stable parameter: 0, 31, 49, 45, 51 and 57 basis points as more releases enter the fit.
- *Agreement with theory.* The expected absolute move should scale with the square root of variance, so the four volatility coefficients should add up to about 0.5. Averaged over the six fits they add up to 0.50 for 30-minute windows and 0.43 to 0.48 for the other lengths (0.41 to 0.49 in the final fit), without this being imposed.

### 6.2 Design decisions

Several choices were made during development after looking at results that include June and July. The table re-runs the walk-forward test (each month priced by a model fitted on earlier data only) for each step, separately for February to May and June and July. Profit in USDC.

| Variant | Feb to May, no demand response | Feb to May, elasticity 1 | Feb to May, keep if not dearer | Jun and Jul, no demand response | Jun and Jul, elasticity 1 | Jun and Jul, keep if not dearer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current price | 6,861 | 6,861 | 6,861 | 10,576 | 10,576 | 10,576 |
| A. Recent volatility only | 5,500 | 4,202 | minus 313 | minus 2,671 | minus 10,875 | minus 7,104 |
| B. Simplest: recent volatility and time of day, margin 25 percent | 13,354 | 10,966 | 3,131 | 46,525 | 38,362 | 8,642 |
| C. B plus releases (CPI, jobs report, FOMC) | 13,679 | 11,127 | 3,231 | 48,654 | 42,027 | 11,623 |
| D. C plus floor at the base price (final model) | 13,859 | 11,367 | 3,412 | 49,020 | 42,497 | 11,990 |
| E. D with PCE as a fourth release type | 13,871 | 11,362 | 3,428 | 48,775 | 41,963 | 11,224 |
| F. D plus size-tier loading | 16,013 | 11,192 | 1,788 | 29,681 | 27,803 | 10,212 |

- The simplest version B uses two well-known volatility facts (recent volatility persists; US trading hours are more volatile) and a margin fixed in advance. It already earns 95 percent of the final model's profit (59,880 against 62,879 USDC over February to July with no demand response) and beats current pricing in every month with no demand response and at elasticity 1.
- The later choices (releases, floor, leaving out PCE) each add little and point the same way in February to May as in June and July. Size tiers were dropped because they hurt in June and July, and at elasticity 1 and under the strict rule in February to May.
- Under the strict rule every variant earns less than current pricing in February to May (section 5.3). This weakness is not caused by any of the later choices.

### 6.3 Decision log

| Decision | Made after seeing | Re-checked on |
| --- | --- | --- |
| Price the size of the move, not its direction | training data (calls 0.90, puts 1.10 of fair value); the BTC price file to October was also visible, but it is not used for this decision | training data only |
| Add time of day | loss ratio by hour, February to July orders | February to May (table, A to B) |
| Model releases as extra variance; leave out PCE | event study, January to July prices | February to May (table, B to C and D to E) |
| Drop size tiers | June and July test | February to May (table, D to F) |
| Floor at the base price | June and July test, February to July walk-forward | February to May (table, C to D) |
| Margin 25 percent | set before any test at that margin | margin table in section 5.4 |
| Range and volume features, US holidays (not adopted) | proposed after the holdout check; adoption rule committed before the test (commit f8801e8) | training data only (section 7) |
| Delta hedging overlay (no price change) | textbook risk control; band version added after the per-order cost was seen | training data; validation shown post hoc (section 5.7) |

February to May is not a fully untouched period either, because the whole training period was explored at the start. The only data that played no part in any decision are the outcomes of the validation period (August to October 2026).

### 6.4 Untouched holdout: the validation period

The validation file hides payouts, but they can be recomputed from `closedAt` and the BTC prices (on training orders this reconstruction is within 0.23 percent of the recorded total). With the team's agreement this was done once, by `run_sealed_check.py`, after the recommendations were frozen and pushed to GitHub (commit c70c413, 14 October 2026, 18:15 SGT; the script refuses to run on any other version of the file). The model was not changed afterwards. Outputs: `results/sealed_check/`.

| Period | Orders | Model premium | Payout | Profit | Loss ratio | Payout / fair value |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| August (BTC plus 25 percent) | 2,129 | 86,266 | 98,933 | minus 12,667 | 1.15 | 1.45 |
| September (BTC plus 6 percent) | 1,340 | 90,144 | 79,332 | 10,812 | 0.88 | 1.10 |
| October to the 14th (BTC flat) | 568 | 29,365 | 22,687 | 6,679 | 0.77 | 0.97 |
| All 4,155 orders (including 118 on 31 July) | 4,155 | 205,824 | 201,003 | 4,821 | 0.98 | 1.23 |

- **The volatility forecast held.** On August order windows the realised size of the BTC move was 1.03 times the forecast for calls and 0.97 times for puts.
- **The trend did not.** In August calls (protection for short positions) paid out 2.01 times fair value and puts 0.80 times. A price that ignores direction cannot cover a one-way move of 25 percent in a month. Pricing direction from the training data would have made this worse, since the training period favoured charging more for puts.
- **Against the benchmarks** on the 1,960 orders with a base quote (almost all in August), with no demand response: model minus 20,006 USDC (loss ratio 1.34), a flat 1.44 markup on the base (today's average markup) minus 25,844 (1.48), the base price alone minus 42,310 (2.14). With elasticity measured against the base price the model and the flat markup are close (elasticity 1: minus 18,272 against minus 17,918; elasticity 2: minus 15,560 against minus 12,423); keeping only orders priced at most 1.5 times the base: minus 19,486 against minus 25,844.
- **Ranking.** On these orders the model's Gini against the base price is minus 0.085: the risk ranking that held in training (0.15) did not hold in a month driven by direction rather than volatility.
- **Against actual prices.** On the 544 validation orders where the actual price can be recovered (base plus recorded markup), actual pricing lost 26,119 USDC and the model 27,684 USDC.

The lesson for the strategy is risk control rather than a different model: a cap on open protected notional per direction (section 5.6) is the tool that limits a one-way month like August, because no direction-neutral price can.

## 7. Alternatives tested and not used

- **Hidden Markov model of market regimes.** A two-state Gaussian HMM on hourly realised variance, using the forward (filtering) probabilities only, so that no future hour is used. It did not improve the forecast (deviance 47.99 against 47.51) or the ranking (Gini 0.175 in both cases), because recent realised volatility already measures the current regime.
- **News sentiment (NLP).** No timestamped news archive was supplied; paid feeds are hard to align to the minute without look-ahead, and six months of orders are too few to learn a reliable mapping from sentiment to payouts. The release calendar captures the predictable part of news risk and is known in advance.
- **Size tiers.** A loading by order size is unstable over time: in the walk-forward, large orders paid out 0.84 of fair value in February to May and 1.01 in June and July (`results/payout_over_fair_value_walk_forward.csv`). With the time-of-day model in place, payouts per unit of fair value are 0.98 for medium and 0.99 for large orders; only orders under 1,000 USDC pay out less (0.79), and they hold about 1 percent of premium.
- **Charging by direction.** Calls 0.90 and puts 1.10 of fair value over February to July; both 90 percent intervals include 1.
- **Range-based volatility and trading activity.** One-hour and four-hour Parkinson (high-low) variance, last-hour volume relative to the weekly average, and last-hour taker buy/sell imbalance. Tested after the holdout check under a rule committed beforehand (commit f8801e8): adopt only if out-of-sample forecast skill improves by at least 0.005 for at least 5 of 7 product lengths and the walk-forward Gini against current pricing does not fall. Skill improved slightly for 30-minute to 2-hour products (0.001 to 0.002) and fell for longer ones (down to minus 0.011); 0 of 7 lengths reached 0.005. Not adopted (`results/extensions/decision.json`).
- **US market holidays.** On NYSE holidays (for example Juneteenth or Labor Day) there is no 09:30 opening spike, so treating them like weekend days is a calendar fact (dates from nyse.com, `data/nyse_holidays_2026.csv`). In the walk-forward it raised profit from 62,879 to 65,105 USDC and the Gini from 0.188 to 0.190, but with only 7 holiday weekdays in the training period the forecast skill gain is small (0.002 on average, 1 of 7 lengths above 0.005), so under the pre-registered rule it is not adopted for the submission. It is a reasonable change for production.
- **Blending with the base price.** Once the model is known, the base price adds no ranking information (Gini of the base price against the model minus 0.004, interval minus 0.05 to 0.05, on the 3,947 test orders), and it is missing for 53 percent of validation orders. It is used only as a price floor.

## 8. Validation recommendations

`outputs/validation_recommendations.csv` keeps the 13 original columns of the validation file unchanged (same text, same row order, same CRLF line endings) and adds:

| Column | Meaning |
| --- | --- |
| `recommended_premium_USDC` | the recommended premium for the order; this is the recommendation for every row |
| `recommended_price_per_BTC_USDC` | the same per BTC |
| `recommended_multiplier_vs_base` | recommended price / API base price, informational (blank when the base is blank) |
| `fair_value_per_BTC_USDC` | model fair value before margin |
| `expected_abs_move_bps` | expected size of the BTC move over the window, in basis points |
| `macro_release_in_window` | 1 if a CPI, jobs report or FOMC release falls in the window |
| `floor_at_base_applied` | 1 if the premium was raised to the API base price |

The model was fitted on candles up to the end of the training period (31 July 2026, 17:11:12 UTC) and then frozen. The file has two blocks with different characteristics:

| | Rows 1 to 1,898 | Rows 1,899 to 4,155 |
| --- | --- | --- |
| What it is | the validation set described in the dataset guide (31 July 17:11 to 24 August 15:58 UTC) | a later extension (24 August 16:05 to 14 October 02:46 UTC) |
| Rows with an API base price | 1,895 | 65 |
| Rows at the base-price floor | 702 | 2 |
| Median order size | 0.0027 BTC | 0.089 BTC |
| Recommended premium | 53,709 USDC | 152,115 USDC |
| Multiplier against base (5th, 50th, 95th percentile) | 1.00, 1.17, 2.16 | 1.04, 1.44, 2.39 (65 rows) |
| Premium-weighted multiplier against base | 1.56 | 2.07 (65 rows) |

Over all 1,960 rows with a base quote, the premium-weighted multiplier is 1.60, against 1.44 for today's actual prices over the training period: the model is cheaper than current pricing for the median order and dearer for the large ones. `outputs/model_card.json` lists every fitted parameter, these block summaries and the SHA-256 of the validation file, the candle file and the release calendar; `outputs/FROZEN.json` holds the SHA-256 of the recommendation file.

## 9. Data integrity notes

- **The validation file reveals its own outcomes.** `closedAt` is still filled in (the dataset guide says it would be blank), and the BTC history runs to 14 October 2026. Together these allow the hidden payout of every validation order to be recomputed. The pricing code drops `closedAt` before pricing and uses only candles that closed before each order (`tests/test_no_lookahead.py` checks this: altering every candle after each order leaves the premiums of 150 validation orders exactly unchanged, while altering the hour before them changes the premiums). Jasper Vault may want to know about this.
- **Quote time.** Features use the last candle that closed before `createdAt`, as the dataset guide prescribes. `expirationDate` minus the product length is a median 18 seconds earlier than `createdAt` in the June and July test orders, so for some orders the last candle used closes a few seconds after the implied contract start; re-pricing all test orders at the implied start changes total premium by 0.05 percent (`results/summary.json`). The API base quote was matched within 120 seconds of the order (dataset guide) and is treated as available at the order, as the guide states.
- 54 training orders have no close time and no payout (some have an expiry before their creation time); they are excluded.
- 1,131 training orders and 2,195 validation orders have no API base price. The model does not need it; the floor is not applied to those orders.
- Order times are UTC. The time-of-day profile uses US Eastern time (including the daylight saving change on 8 March 2026), since the main volatility events are tied to US trading hours.
- Validation timestamps mix two formats (`2026/8/10 7:54` and `2026-08-26 14:55:09`); both are parsed. The minute-only timestamps are truncated, so the last fully closed candle before that minute is always before the order.

## 10. Limitations and open decisions

- **Conversion rule.** User demand is not observed. The strategy is clearly better if users respond smoothly to price or if acceptance is judged against the base price, and worse over the full walk-forward if any price above today's loses the order (section 5.3).
- **Margin.** 25 percent is a business target, not an optimum; section 5.4 shows the trade-off.
- **Release windows** were still underpriced in the June and July test (payout / fair value 1.53 on 192 orders), and the release effect is estimated from few events.
- **Remaining mispriced segments.** 24-hour products (payout / fair value 0.40 on 96 test orders) and orders between 16:00 and 24:00 UTC (0.75 to 0.77) are overpriced by the model; orders under 1,000 USDC pay out 0.79 of fair value.
- **The validation extension** (rows 1,899 to 4,155) has much larger orders than the training data and almost no base quotes, so the floor does not protect it.
- **Trend risk.** The model prices the size of the move, not its direction. In a strongly trending month (August 2026, BTC plus 25 percent) protection on the losing side pays out far more than its fair value (section 6.4). This needs an exposure limit, not a pricing change.
- **Holidays and hedging for production.** The US-holiday calendar (section 7) and net-book delta hedging within a band (section 5.7) are recommended for live use but are not part of the submitted prices.
- The model treats every at-the-money product the same way; deductibles other than zero are priced by the formula but were not in the data.

## 11. How to reproduce

```bash
cd maksim
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_descriptive.py          # results/descriptive_facts.json (sections 1 and 2)
.venv/bin/python run_backtest.py             # results/*.csv
.venv/bin/python run_overfitting_checks.py   # results/overfitting/*.csv
.venv/bin/python run_validation.py           # outputs/validation_recommendations.csv
.venv/bin/python run_extensions.py           # results/extensions/* (hedging, candidate features)
.venv/bin/python make_figures.py             # results/figures/*.png
.venv/bin/python -m pytest tests -q          # no-look-ahead test
```

| Path | Content |
| --- | --- |
| `src/data.py` | loading, timestamp parsing, size tiers, release calendar |
| `src/market.py` | candle features, time-of-day profile, release effect, HMM filter |
| `src/model.py` | expected-move regressions, fair value, model variants |
| `src/pipeline.py` | fitting the full pricer at a cut-off date and pricing orders |
| `src/evaluate.py` | profit, conversion rules, daily risk, ordered Lorenz curve and Gini |
| `run_descriptive.py` | descriptive facts quoted in sections 1 and 2 |
| `run_backtest.py` | June and July test, walk-forward, benchmarks, segments, margin grid, worst days |
| `run_overfitting_checks.py` | in-sample against out-of-sample skill, parameter stability, design decisions by sub-period |
| `run_validation.py` | final fit and validation recommendations |
| `run_extensions.py` | delta hedging overlay and candidate features (range, volume, US holidays) with the pre-registered adoption rule |
| `run_sealed_check.py` | one-time check of the frozen recommendations against August to October outcomes (runs only on the committed, frozen file; outputs in `results/sealed_check/`) |
| `make_figures.py` | figures in `results/figures/` |
| `tests/test_no_lookahead.py` | checks that a price depends only on candles closed before the order |
| `results/` | every table behind the numbers above |

Reference: Frees, E. W., Meyers, G. and Cummings, A. D. (2011). Summarizing insurance scores using a Gini index. Journal of the American Statistical Association, 106(495), 1085 to 1098. https://doi.org/10.1198/jasa.2011.tm10506
