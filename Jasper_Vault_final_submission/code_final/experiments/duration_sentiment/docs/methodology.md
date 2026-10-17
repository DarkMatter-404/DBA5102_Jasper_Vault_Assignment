# Detailed model specification and evaluation

This document describes the **original EN dataset** experiment. See [findings_and_submission.md](findings_and_submission.md) for the repository base-premium release and submission plan.

## What is being estimated

Per the supplied class notes, `realizedProfit_USDC` is the gross payout from Jasper Vault to its user. The target is the expected gross payout **conditional on the historical mix of people who bought and their early-close behaviour**. It is not a risk-neutral option fair value. Early settlement, exercise rules, refunds, oracle basis, hedge costs, fees, funding, inventory and capital are not fully specified in the files.

The dataset field `premiumAmount_USDC` is the actual recorded paid premium. The EN release has no separate internal Base Premium field. The repository also contains a different, enriched release with API base quotes; this experiment does not use it. Every price-relative comparison in this package is against that recorded-price proxy. If Jasper provides the true base quote, confirm its semantics and revalidate the relationship rather than silently replacing the reference.

All contracts are ATM according to the class notes. The code does not label observed Binance/strike discrepancies as OTM contracts or claim to validate an OTM model. It uses `optionType = 0` for call payoff direction and `1` for put payoff direction, without inferring which underlying perp position was protected.

## Data controls

The guide describes the records as direct extracts from the source workbook's Options sheet, not a synthetic dataset; the files alone do not independently establish transaction provenance.

- 7,831 source orders; 7,767 nonmissing outcomes; 64 missing outcomes with missing closes.
- 86 closes precede creation; 67 expirations precede creation; 181 nominal-duration gaps exceed 120 seconds. These flags overlap.
- Main analysis retains 7,603 orders and excludes 228 unique rows. It requires a positive premium/notional, known tenor and side, finite features, expiration after creation, a nominal-time discrepancy between 0 and 120 seconds, nonnegative observed payout, and settlement at or after creation.
- Quote validity is separate from label validity. Unknown outcomes never cause a blind quote to be excluded. Missing, nonfinite or nonpositive reference premiums produce `no_quote_invalid_reference`; impossible expiry, invalid side/tenor or nonpositive quantity/strike produce `no_quote_invalid_contract`. Both have blank recommended/challenger quotes and multipliers. Otherwise valid reference/contract rows with ambiguous nominal timing or stale/missing market data receive separately labelled recorded-price fallbacks for assignment continuity. In a live system, stale or ambiguous quotes should be blocked and requoted. Of the supplied 7,831 rows, 67 impossible-expiry records have no quote, 114 have timing fallbacks and 7,650 have valid quote features.
- Market features use only one-minute candles whose **close timestamp** is at or before the quote timestamp. The partially formed order-time candle is excluded. A completed candle more than 60 seconds old fails the quote-quality rule.
- `createdAt` is the main quote-time proxy. Expiration minus product duration is often about 19 seconds earlier, so it may reflect an ingestion delay. A fixed-spec sensitivity instead uses the earlier of those timestamps. The negative July result persists.
- Market history contains 338,917 continuous one-minute rows, January 1 to August 24 08:36:59.999 UTC. The guide's validation orders extend to August 24 15:58:54 UTC. Additional market candles are needed for the final roughly 7 hours 22 minutes of those orders.
- `closedAt` is used only for label availability, exclusion and diagnostics. Actual holding time and future returns never enter quote features. Settlement timestamp is only a proxy for when a label became available to the system.

## Exact model

Let `N = quantity_BTC × strikePrice`, `T = productType / 60` minutes, and `r` be completed-candle one-minute log returns. Let `v60` and `v1440` be the means of squared returns over the preceding 60 and 1,440 minutes. The fixed 50/50 volatility blend is a benchmark assumption, not a fitted HAR-RV volatility forecast.

The all-ATM Black/Black-Scholes-shaped scale anchor is:

```text
z = sqrt(T × (0.5 v60 + 0.5 v1440))
anchor_USDC = N × [2 Φ(z/2) − 1]
anchor_bps = 10,000 × anchor_USDC / N
```

It uses zero carry and S=K solely as a financially motivated scale. Empirical calibration adapts it to observed PP payouts; it does not establish European settlement mechanics for PP.

Define the four candidate adjustment features:

```text
x1 = log(T / 120)
x2 = 1{put}
x3 = clip(0.5 log(v60 / v1440), −2.5, 2.5)
x4 = clip((1 − 2 × 1{put}) × log(S_t / S_(t−60)) / sqrt(60 v60), −4, 4)
```

Features are centered and scaled using the fit sample. The expected-payout rate and amount are:

```text
mu_bps = anchor_bps × exp(beta0 + sum_j beta_j × standardized(x_j))
expected_payout_USDC = N × mu_bps / 10,000
```

The model minimizes notional-weighted quasi-Poisson loss plus ridge penalty on slopes (not the intercept). Noninteger payout rates and many zero payouts are allowed. The weights are `N / sum(N)`. This targets conditional means; it does not assume literal Poisson-distributed USDC payouts or provide Poisson confidence intervals. The paired day bootstrap is used for comparative prediction uncertainty.

Candidate models, fixed before July evaluation, use either recorded-price rate or the financial anchor as an offset, with (a) intercept only, (b) tenor and side, or (c) all four features. Ridge strengths for b/c are 0.1, 1 and 10. There are 14 candidates. June notional-weighted Poisson deviance selects the financial-anchor/state model with ridge 0.1. July does not change that choice.

The frozen July model's exact parameters are in `frozen_july_model.json`:

| Term | Coefficient |
|---|---:|
| Intercept | 0.0138438896 |
| Standardized log tenor | −0.0282535198 |
| Standardized put indicator | 0.3343520800 |
| Standardized fast/slow log-volatility ratio | −0.1313713602 |
| Standardized signed 60-minute momentum | −0.1414172910 |

Centers are `[-0.3055571475, 0.4590954774, -0.0014815553, 0.2086506840]`; scales are `[1.1329141185, 0.4983240111, 0.4187625856, 1.0048985396]`. These are predictive coefficients with no causal interpretation.

## Pricing wrapper and gate

Let `B` be recorded premium, `C_hat` the expected payout, and `kappa = sum(training payouts)/sum(training premiums)`. The experimental pricing wrapper is:

```text
M = clip(c × sqrt(max(C_hat / (kappa × B), 0.000001)), 0.85, 1.15)
recommended_premium = B × [1 + w × (M − 1)]
```

`c` is fitted once so the training-sample weighted total of `B × M` equals total `B`. For frozen July evaluation, `kappa = 0.9170461006` and `c = 1.0668864483`. The 15% bounds and square-root smoothing are commercial design assumptions, not Jasper's yet-unspecified evaluation rule or an estimated demand curve. The normalizer is never refitted using holdout payouts or future rows.

For the same all-filled trades and unchanged payouts, exact premium neutrality leaves total gross margin unchanged. Changes in July fixed-volume gross margin come from distribution drift in a **previously frozen** price mapping, not a counterfactual proof of demand or profitability improvement.

The deployment gate uses `w = 0` because the selected challenger failed July. A future activation rule should be prespecified with Jasper and evaluated on new data: lower proper expected-cost prediction loss than the calibrated reference, acceptable calibration and correlated tail loss, and a positive result under the partner's actual conversion/fee/capital scoring rule. The July test has now been inspected and cannot serve as a fresh test for a revised model.

## Results and interpretation

Training before June: 2,650 settled eligible orders. June development: 2,322 orders whose labels were available by July 1. The July model refits on 4,975 eligible labels settled before July 1. July holdout: 2,625 eligible orders, with final outcomes through August 1. Overlapping labels are purged at fitting cutoffs; the latest evaluation outcomes are allowed to arrive after the order month.

| July model | MAE, USDC | RMSE, USDC | Predicted / actual payouts | Weighted Poisson deviance |
|---|---:|---:|---:|---:|
| Calibrated recorded-price reference | 44.81 | 135.09 | 95.35% | 66.70 |
| Calibrated financial anchor | 43.50 | 137.55 | 80.26% | 71.17 |
| June-selected state challenger | 46.34 | 144.82 | 82.91% | 79.15 |
| Recorded-price state model, secondary diagnostic | 49.21 | 145.76 | 106.11% | 75.98 |

The selected challenger improved June deviance to 68.39 from the calibrated recorded-price reference's 72.36, then failed in July. The conditional paired UTC-day bootstrap gives a 95% interval of **+2.78 to +16.21 USDC** for challenger RMSE minus calibrated-reference RMSE. This preserves within-day dependence but does not fully account for cross-day serial dependence or model-selection uncertainty. A lower MAE for a different baseline does not establish better expected-claim pricing; zero-heavy outcomes can reward underprediction on absolute loss.

July actual payouts were 101,796.82 USDC. Recorded premiums were 105,838.86; gross margin before any other costs was 4,042.04 USDC. The experimental frozen wrapper would collect 102,541.67 at unchanged fills and produce only 744.84 gross margin. Under **assumed** retained-buyer weights `min(1, M^(−epsilon))`, epsilon 1, 2 and 4 produces gross margins −1,248.60, −2,988.22 and −5,831.08. These are scenario calculations, not estimated conversion or causal profit effects. They assume price-dependent thinning of historical buyers, unchanged payoffs/holding behaviour among retained buyers, and no extra buyers from markdowns.

When premiums and eventual payouts are assigned to each order's **creation-date cohort**, recorded-price July has nine negative cohorts and a worst daily cohort gross margin of −5,056.73 USDC. These are not daily settlement cashflows, mark-to-market portfolio P&L or live inventory-risk measures. Increasing all recorded payouts by 25%, holding premiums fixed, gives −21,407.17 cohort gross margin in total. Such stresses are scenarios, not probabilities or guaranteed risk limits. Without vault capital and hedge information, insolvency probabilities or risk-adjusted returns are not identifiable.

The main new research direction is an explicit validation-and-risk gate around a financially interpretable payout model, with better quote-time provenance, early-close modelling, event-aware volatility and inventory limits as next data-driven extensions. The present evidence supports continued controlled testing and **rejecting the current overlay**, not announcing a more profitable model.

## Verification and deliverables

`verify_pricing.py` checks that blanking all outcomes and closes leaves every quote unchanged, recomputing features from market history truncated at three quote timestamps gives identical features, serialized model predictions reproduce the saved July results, and the default gate returns multiplier one only for valid references/contracts. Adversarial cases with missing, negative, zero and infinite premiums, negative quantity/strike, invalid side and impossible expiry confirm that no quote is emitted; separate stale-market and ambiguous-time cases receive explicit fallback statuses. It also runs the fixed-spec nominal-start timing sensitivity (RMSE 144.84 versus reference 135.09).

The main numeric deliverables are `data_audit.json`, `analysis_summary.json`, `june_model_selection.csv`, `july_holdout_metrics.csv`, `july_holdout_predictions.csv`, `july_bootstrap.json`, `monthly_summary.csv`, `duration_summary.csv`, `side_and_tenor_diagnostics.csv`, `july_assumed_retention_scenarios.csv`, `payout_stress.csv`, the two model JSONs, and `verification_report.json`. Figures are provided for presentation construction. All source records are identified by input position because the supplied orders do not contain unique transaction IDs.
