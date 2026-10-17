# Event-to-Loss: protocol fixed before this study's scores

Recorded 16 October 2026. This is a standalone implementation using only supplied assignment inputs and a newly assembled evidence corpus. No existing pricing implementation, parameter file or result is imported.

## Question
Does structured, source-checked event research improve a PP claim distribution and its pricing decisions beyond the same simulator using market information alone?

## Four fixed arms
1. Market only: conditional historical simulation.
2. Simple event rules: a fixed keyword taxonomy on the same source records.
3. Single research pass: recorded LLM-assisted event classifications.
4. Verified research: a second source/time/relevance review of those classifications, with sparse-event shrinkage.

All arms share historical paths, early-close model, price loading and evaluation rows. No free-form LLM probability enters a premium. Interactive assistant labels are explicitly distinguished from autonomous API agent runs. No external model API key is available for the initial study. The shipped recorded labels permit an offline research replay; the optional API workflow is separately executable.

## Data and clocks
Primary order population: the supplied enriched 7,204-row training release. Retain original raw inputs. Exclude unresolved outcomes and impossible quote/settlement chronology from outcome scoring, reporting the exact counts. Use nominal product duration. Label availability requires both creation and actual settlement strictly before each fit cutoff. API base is a comparator only, never a required input to our price. Market features use only completed candles strictly before quote time. Source article clocks are conservative publication/update proxies plus a 5-minute processing delay; date-only sources are admitted at the end of the stated day plus that delay. Never backdate a current receipt. Strict observed-clock replay uses the actual collected/processed timestamps and must therefore have no historical event effect. An event's schedule is not presumed known in advance without a dated calendar snapshot.

The class notes specify ATM, zero deductible and full coverage. Base simulation starts at the protected strike. External exchange spot is used to measure returns and volatility, not to manufacture verified moneyness. The pricing API also accepts a separately verified spot for payoff mechanics tests; OTM predictive performance is not established.

## Fixed numerical specification
Five-minute simulation steps. Analogue starts on a 30-minute grid with at least one week of history and with a full 24-hour future path ending before the fitting cutoff. Neighbours use log recent volatility, the fast/slow volatility ratio, signed 1h/4h returns scaled by volatility, and relative trading activity. Feature scales are fit only on the training archive. Use 128 market neighbours; candidate event neighbours are selected from the same past archive. Similarity uses a Gaussian distance kernel and 90-day recency half-life. Paths are rescaled by the ratio of current to historical pre-trade volatility, clipped to [0.25, 4] and reported when binding. A common signed-return path preserves call/put asymmetry.

Early closing: regularized discrete-time logistic hazard on completed training contracts, with elapsed fraction, elapsed fraction squared, log duration, side, standardized gain/loss and log notional. Probability mass surviving to expiry closes there. Five-minute discretisation is an approximation and settlement calibration is reported. A pooled hazard is the fallback if a fit has insufficient early exits. Do not use actual future holding time as a prediction input.

Event memories are active for six hours with a two-hour half-life. The single-pass/rule arms can place up to 35% of scenario weight on matched episodes. The verified arm scales that weight by n/(n+10), where n is the number of distinct matching historical event IDs; same-event duplicates do not increase n. If no supported matching history exists, use the market distribution. Source confidence controls admission; it is not a forecast probability.

## Price and policy choice
Premium = (1 + m) * mean claim + lambda * (95% expected shortfall - mean claim). Report research/operating costs separately with per-order cost sensitivities rather than inventing observed API costs. Development grid m in {0.10, 0.25, 0.50}; lambda in {0, 0.025, 0.05, 0.10}. Choose one policy on the MARKET-ONLY May/June predictions: highest minimum profit gain over current prices across no demand response and conservative elasticity 2 and 4. Feasibility: quoted-total/current-total within [0.80,1.20] and 95th percentile price ratio <=2. If none passes, retain the declared m=0.25, lambda=0.05 diagnostic default and report the failed gate. Apply exactly the same policy to every arm. No policy is retuned on July or validation.

## Chronology and tests
May: train before 1 May. June: train before 1 June. July: train before 1 July. July is a retrospective chronological test, not a claim that no participant ever saw that month. Final validation: refit with outcomes available before its first creation timestamp; do not reconstruct hidden payouts or use validation closedAt. One premium per valid input row, including a clearly labelled unconditional-history fallback where current candles are unavailable. Those fallbacks are diagnostic prices and need fresh market data before operational use.

Primary hypothesis comparison: verified research minus market only, using identical policy and rows. Report mean-claim error/calibration, payout probability Brier score, CRPS, gross profit under demand scenarios, daily tail losses, quote distribution, effect versus same-total flat repricing, and 90% paired day-bootstrap intervals. Demand is not estimated from accepted orders. Overlapping events are not independent evidence. Report event coverage, unique events, changed quotes and forecast intervals. Compare raw API prices only on their matched rows; distinguish API prices from actual paid prices. Report operating-cost break-even and stale-data behaviour. Run timestamp, outcome-independence, payoff, probability-mass and source-admission checks. Publish unfavourable results without changing the frozen experiment.

## Limits fixed in advance
Sparse, retrospectively collected sources and LLM pretraining may contaminate historical interpretation. Recorded classifications are source extraction and review, not independent model-provider experiments. The archive is a purposive research sample, not exhaustive news coverage. Source clocks without historical receipt records are proxies. Historical simulation cannot give probability to unprecedented shocks absent a separate stress exercise. Per-order tail loading is not a complete portfolio capital model. No superiority claim is justified by responsiveness or a higher price alone.
