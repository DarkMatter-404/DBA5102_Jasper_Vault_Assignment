# Event-to-Loss model card

## Intended use
Test whether source-checked LLM event research adds useful information for Bitcoin price-protection pricing. Research and shadow evaluation only. No trade execution, autonomous investment action or live-ready profitability claim.

## Contract and numerical model
The supplied class notes describe ATM, zero-deductible, full-coverage protection. For BTC quantity q, protected price K and settlement price S, the model uses call payout q max(S−K,0) or put payout q max(K−S,0). Market candles provide signed returns and risk state; the unverified difference between an exchange close and a contract strike is not used as contract moneyness.

The market engine selects 128 historical paths with nearest-neighbour state matching and a Gaussian distance kernel. The archive starts every 30 minutes and contains 24 hours of future five-minute steps, all complete before the fitting cutoff. A seven-day warmup, trailing volatility features and past-only standardization prevent future information entering state selection. Paths are rescaled to current volatility, with the ratio clipped to [0.25,4]. There is no neural return forecaster, LLM-generated scenario probability, or risk-neutral no-arbitrage calibration.

Settlement is integrated over a regularized logistic discrete-time early-close hazard. The hazard conditions on the previous interval's signed return, elapsed fraction, duration, direction and notional. Mass that survives to expiry settles then. This approximates early closing on a five-minute grid and is not an optimal-exercise model. The output is a physical-measure empirical payout distribution.

An active event can shift up to 35% of the path weight toward the same category's historical episodes. Its influence decays with a two-hour half-life and stops after six hours. Verified research multiplies this weight by n/(n+10), where n counts distinct earlier event episodes. Evidence quality determines admission, not market probability. Duplicate URLs/episodes do not supply additional independent evidence. New event types with no matching archive fall back to market-only pricing.

Price = (1+m) × expected claim + lambda × (ES95 − expected claim). ES95 is the average of the worst 5% of empirical claims, with fractional mass at the quantile boundary. The selected common policy is m=0.10 and lambda=0.10. It is a business loading, not a replication price, hedge or portfolio capital requirement.

## Experiment and result
The main contrast is verified research minus market-only with identical policy and evaluation rows. May and June are development months; policy uses only outcomes settled before 1 July. July is a retrospective chronological test. Final validation is refit before its first quote. The evaluator never reconstructs validation payouts from candles or conditions a quote on the validation closing time.

July news-only gross-profit change is +37.64 USDC with a 90% paired UTC-day bootstrap interval of −44.48 to +166.10. CRPS changes by −0.01051 USDC/order (lower is better), interval −0.03380 to +0.00283. The test does not reject no improvement at that interval level. Dependence across multi-day shocks may make even day-level intervals optimistic.

The larger gain over actual paid premiums is not attributable to the research layer: +3,370.83 USDC under unchanged acceptance, with aggregate premiums 3.13% higher. A same-total flat repricing gives identical fixed-order profit and performs better in the stated demand scenarios. Moderate assumed price sensitivity makes the model loss-making. Expected claims are substantially undercalibrated, at 64.0% of realized payouts. Per-order intervals can cover about 90.9% of outcomes while aggregate claim cost remains biased: coverage alone is insufficient.

Gross-profit gains exclude operating costs and hedging. The news-only point estimate supports at most about 0.0147 USDC incremental research cost per July order if spread over all orders; uncertainty includes negative benefit. Costs are sensitivities, not observed API bills.

## Evidence provenance and scope
The corpus contains 44 short records: 30 BLS release-calendar occurrences, six Fed statements, and eight selected crypto source records. There are 42 distinct episode IDs. Six records are rejected by review. Calendar data contain occurrence and release time, not forecast surprise or news sentiment. Source facts are short paraphrases with URLs; no full articles are redistributed.

Two classification passes were recorded by the authoring assistant before forecasting scores. They share a session and are not independent provider runs. The external API path is provided separately and has not been exercised with real credentials. The recorded arm therefore tests this particular evidence classification plus weighting design; it does not establish the value of autonomous agents or generalized LLM extraction accuracy.

All four supported July event episodes are macro releases. The dataset does not establish crypto-specific event prediction, social sentiment value, or unprecedented crash probabilities. Admitted primary regulatory records are useful for the schema, but sparse events cannot support reliable event-tail estimation.

Publication-clock replay uses a five-minute delay; date-only US sources wait until the end of the stated Eastern day plus five minutes. This is a proxy. Actual October receipt clocks activate no historical events in the strict control. A current calendar or mutable page is not a historical archive snapshot; later edits and model pretraining may introduce look-ahead bias. True prospective receipt logs are required.

## Data and operational limits
- 7,204 training rows become 7,078 scorable records: 54 unresolved outcomes and 72 impossible closing sequences are excluded. Original inputs remain unchanged.
- The supplied enriched release had already removed orders with negative residual markup; selection limits generalization.
- External BTC candle prices may differ from the product's settlement reference. Investigate source alignment before interpreting aggregate payout underprediction as a single modelling cause.
- Only ATM is evaluated. A separately verified spot affects payoff mechanics, but the fitted closing model is not validated across moneyness.
- Later outcomes are hidden. Of 4,155 validation quotes, 2,262 lack fresh market candles and use a labelled diagnostic fallback. The normal single-quote command refuses a stale-market quote.
- Absolute-USDC scores and gross profits can be dominated by large notionals. Direction/duration/market-state breakdowns are supplied, but no randomized demand data exist.
- Market bands in the report are descriptive July terciles, not thresholds used to train or tune the model.
- Optional feed collection deduplicates URLs; cross-source episode matching needs review. Restricted publisher access and short excerpts may prevent safe classification. Reject uncertain cards.

## Proposed next test
Before collecting the next evaluation period, fix sources, models/prompts, admission policy, costs, simulator and price-loading rules. Log first receipt and processing clocks prospectively. Begin with shadow quotes and matured settlements; do not replace live prices based on this retrospective result. Aim initially for at least 90 days and 50 independent event episodes, then assess effective sample size and power.

The primary test remains incremental value versus the same market-only engine, after measured research/data costs and with paired-day uncertainty. Require calibrated claims, acceptable tail losses and no unacceptable price dispersion. Demand needs offered and rejected quote data and ultimately an authorized controlled commercial trial; shadow simulations alone cannot prove causal business uplift. Do not retune on the final test period.
