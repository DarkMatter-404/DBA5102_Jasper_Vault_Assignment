# V3.2 combined framework: protocol fixed before the extended run

This release makes the news + social sentiment model the assignment's experimental framework. It studies whether information beyond contract duration can improve PP pricing. It does not assert that enabling a layer proves an economic improvement.

- Retain the frozen July-1 V3.1 model, its training vocabulary, coefficients, normalizer, and limits. No validation labels, future text, or newly collected social records enter fitting.
- Extend the same Instrumetriq public Tier-1 source with every available weekly CSV from August 2 through October 11, 2026. Verify source byte counts and Git blob hashes. Preserve provider methodology and four-hour freshness rules.
- Extend the headline corpus by systematic date/topic searches covering August through October 14. Include dated, non-live CoinDesk market articles with an identifiable headline and publisher clock; exclude live blogs, undated pages, duplicates, and after-period articles. Selection is not based on PP payouts, price impact, or model output. This remains a convenience sample, not a census of news.
- Use the later of publication and displayed update clocks plus five minutes for new historical headlines. Historical text versions and actual historical receipt remain unverified. Keep reconstructed-clock research separate from observed-receipt inference.
- Run four ablations using one calibration: duration foundation; market + news; market + news + social activity; market + news + social sentiment. The combined sentiment variant is the main assignment experiment regardless of ranking.
- Keep all validation rows, remove closing time and payouts before inference, and preserve original quote timestamps as conservative lower bounds. Retain contract and timing guards. Do not pretend stale market candles are fresh.
- Produce relative factors without imputing missing premiums. Absolute quotes require a verified premium or a clearly labelled API-plus-markup reconstruction. These factors are calibrated to a recorded-premium-compatible reference, not automatically to raw API prices.
- Where market data is unavailable, the combined framework uses its duration component and explicitly records that fallback. Where social data is missing or stale, use the news component with zero incremental social effect. Missing inputs are not evidence of neutral sentiment.
- Evaluate newly collected information through coverage, component effects, limits, timing checks, and comparison with the same model using the original corpus. Validation profit and accuracy remain unmeasurable until Jasper supplies outcomes or scoring.
- Report earlier July retrospective evidence for context, retaining all component results. Do not describe it as an untouched holdout or use it to claim August–October performance.
- Include both the research replay and an observed-clock mode. The latter cannot backdate newly collected historical records and will fall back when historical receipt logs are absent.

Collection scope and fallback rules are fixed before inspecting extended-model outputs. No thresholds are tuned to the new validation population.

## Coverage-driven collection addition

The first replay revealed that the new headlines mostly fell on weekdays while the free social observations were Sunday samples; there were no quotes jointly exposed to a four-hour headline and fresh social record. A second, documented search pass therefore covers August 2, 9, 16 and 23 and includes dated crypto market, policy, security and infrastructure headlines. This expands acquisition based on a coverage gap, not outcomes (which remain hidden), predicted returns or coefficient selection. All eligible non-live results from that search pass are included regardless of direction. The frozen model, five-minute clock proxy, four-hour freshness, pricing cap and all evaluation rules stay fixed. The package preserves the first-run coverage finding here; final results use the extended collection.
