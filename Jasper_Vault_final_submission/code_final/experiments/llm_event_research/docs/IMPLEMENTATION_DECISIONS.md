# Decisions fixed before forecast scores

The original protocol hash is recorded in `results/run_manifest.json`. The following fills in implementation details before scores, without selecting settings based on test results.

- Current volatility is the square root of the average of trailing 60-minute and 1,440-minute return variances. Historical observations use the same estimator. No forward filling across missing quote-time candles.
- Log relative volume is trailing 60-minute mean volume divided by trailing 1,440-minute mean volume. Similarity bandwidth is the median neighbour distance (minimum 0.25 in standardized units).
- The five-minute close hazard includes observations up to the close interval. Settlement less than five minutes before nominal expiry is treated as expiry settlement. Gain is signed for the covered direction. L2 logistic regularization C=0.1 is fixed, with no test tuning.
- Where market data are missing, use a deterministic 128-point stratified sample across the past archive and its median volatility. Disable event overlays for those rows. This is a diagnostic fallback, never an executable commercial quote.
- Latest eligible event is the single active context. Verified event duplicates are admitted at their earliest eligible source clock, so syndication does not extend the event window. The single-pass and keyword comparators expose duplicate-clock sensitivity.
- The curated research sample includes BLS inflation/employment release occurrences, six Federal Reserve statements and eight crypto source records. Calendar entries are release-clock proxies, not pre-release forecasts or surprise measurements. Selected rejection examples exercise source checking; this is not a representative accuracy benchmark for LLMs.
- All classification labels were recorded in this assistant session. The research and review passes share a model/session and are not statistically independent agents. The reviewed arm changes both admission and sparse-event shrinkage; its difference from the single-pass arm does not isolate review quality alone.
- Retention scenarios are capped at the historically observed order count: retention = min(1, price_ratio^(-elasticity)). Lower quotes do not manufacture new customers. There is no fitted demand curve.
- In a missing-outcomes validation file, quote coverage and stability are measurable; profitability, calibration and predictive superiority are not.
- Source-card assembly completed 16 October 2026. Publication replay is an explicitly optimistic availability proxy. Observed-clock mode cannot activate any of these cards for February–October 14 historical quotes.
