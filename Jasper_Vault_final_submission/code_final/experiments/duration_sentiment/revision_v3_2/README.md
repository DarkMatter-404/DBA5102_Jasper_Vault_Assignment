# V3.2 — reproduce the combined pricing experiment

The assignment findings and six evaluation criteria are in [jay/README.md](../README.md). This release makes the **combined news/social sentiment variant the main research experiment**. Duration, market/news and activity variants are ablations. The original July-1 component model is preserved byte-for-byte; its older recommendation flags are provenance, while `framework.py` explicitly selects the combined experiment. No deployment approval is inferred.

## Offline reproduction

Use Python 3.12 and run from the repository root:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux alternative: source .venv/bin/activate
python -m pip install -r jay/revision_v3_2/requirements.txt
python jay/revision_v3_2/build_data.py
python jay/revision_v3_2/framework.py
python jay/revision_v3_2/verify.py
python jay/revision_v3_2/make_figure.py
```

The inputs and frozen model are bundled. No network, paid API, API key or transformer download is required. `build_data.py` verifies the 11 new raw social files against pinned Git blob hashes and rebuilds the combined BTC/headline datasets. `download_samples.py` optionally retrieves missing pinned CSVs; existing files are verified without network access. Dependencies on previous versions are included in the ZIP as unchanged source files.

`framework.py` defaults to the bundled market and training `.csv.gz` files and the exact new validation upload. It parses mixed dates, strips payouts and actual closing times before validation inference, then retains every source row. To preserve bundled results, add `--outdir your_results_directory`.

Custom inputs:

```bash
python jay/revision_v3_2/framework.py --validation path/to/orders.csv --market path/to/complete_market.csv --outdir custom_results
```

The validation adapter is deliberately for withheld-outcome data. If outcomes arrive, it stops and requests a separate scoring-only evaluation instead of accidentally refitting. Seven supplied rows fail the existing nominal-duration/time guard and have blank multipliers. No missing paid premium or markup is treated as zero.

## Technical model

Let `B` be the compatible reference PP premium, `r_T` the pooled duration claim-to-premium estimate, `x` the standardized market/news features, and `s` the standardized social features. The frozen expected-payout model is:

```text
news_cost_ratio = r_T × exp(clip(beta · x, −log(2), log(2)))
social_factor  = exp(clip(gamma · s, −log(1.10), log(1.10)))
expected_payout = B × news_cost_ratio × social_factor
```

The social factor is exactly one for missing/stale observations. The resulting price rule is:

```text
raw = clip(a × sqrt(cost_ratio / pooled_claim_ratio), 0.85, 1.15)
multiplier = 1 + 0.0860393 × (raw − 1)
experimental_premium = B × multiplier
```

`a`, the pooling parameters, transforms and coefficients are frozen from the original training run. `a` normalized the news component on its training set; adding social does not guarantee aggregate premium neutrality. The final bound is 0.987094–1.012906. Because `B` cancels from the ratio, the multiplier can be computed without inventing a missing premium. Applying it still requires a reference with compatible semantics. This is a statistical expected-claim model and bounded allocation rule, not a risk-neutral option valuation or a proven optimizer of real customer demand.

News features are train-only TF-IDF bigrams/unigrams, three SVD components, exponentially weighted four-hour text/event features and four-/24-hour counts. Market features are volatility ratio, absolute 60-minute momentum, UTC time/weekend and option direction. The social overlay uses activity, score availability, silence, direction-adjusted sentiment and sentiment magnitude. Our two residual models are regularized log-link quasi-Poisson regressions with fixed predicted-payout offsets. Instrumetriq's precomputed NLP score is external; our runtime does not run its BERTweet/DistilBERT models.

The model is calibrated on purchased orders and recorded premiums. It does not identify price elasticity or demand causally. Class notes limit this assignment to ATM contracts, so no independent moneyness coefficient is estimated.

## Time and fallback rules

| Situation | Action |
|---|---|
| Research replay with fresh market data | Apply market/news and, when fresh, social adjustments |
| Social missing/stale | Social increment is exactly zero; retain market/news component |
| Market missing/stale | Use duration component and report explicit fallback |
| Contract/nominal-time invalid or quote before cutoff | Preserve row, withhold multiplier |
| Reference missing | Output relative factor only; no invented USDC premium |
| Historical observed clock lacks receipts or news-feed health | Duration fallback; no backdating |

Research replay is limited to this study window, February 1–October 14. Headline availability is strictly earlier than the quote, using the later displayed publication/update time plus five minutes for the new collection. Social availability is after the later of session expiry or start-plus-duration, plus processing delay; age is measured from session start and capped at four hours. Actual historical availability and headline version are not established by these proxies.

The supplied candles stop on August 24. September/October news and social features are constructed and audited, but the complete pricing component cannot activate on those months without later market inputs. A zero news count describes the sampled corpus, not the universe of news.

## Outputs

| File under `results/` | Purpose |
|---|---|
| `summary.json`, `checks.json` | Coverage, frozen identity and executed invariants |
| `validation_predictions.csv` | Every original row; four component factors, cost ratios, conditional prices and status |
| `assignment_recommendations.csv` | Compact row-aligned experimental recommendations; includes seven abstentions and reference flags |
| `component_comparison.csv` | Same-row quote comparisons; includes separate full-market and fallback-inclusive populations |
| `monthly_coverage.csv` | News/social availability and actual layer activation by month |
| `collection_extension_effect.csv` | Same model with original versus extended input corpus; input-effect diagnostic only |
| `quote_time_features.csv`, `learned_factors.csv` | Inputs and saved coefficients for explanation |
| `latency_sensitivity.csv` | Fixed-model replay under five-minute, one-hour and one-day delays |
| `historical_july_cost_metrics.csv` | July retrospective cost errors; no validation labels involved |
| `historical_july_commercial_scenarios.csv` | July assumed conversion scenarios for elasticity 0, 1, 2, 4 |
| `demo_joint_signals.json` | Earliest actual row with fresh social and a four-hour headline; relative quote because reference is missing |
| `demo_result.json` | Earliest eligible social example with a conditional absolute reference |
| `observed_clock_diagnostic.json` | Why reconstructed historical data cannot masquerade as observed receipt |
| `framework_results.png` | Figure for the presentation |

`source_row` is zero-based in the exact upload. `csv_line` includes the header. No order ID was supplied. Keep this mapping when Jasper returns scores. Price totals are not profits. The 544 conditional references require confirmation of the earlier dictionary's identity on this new export.

## Collect future information

The scripts below run once. Schedule them on a machine with permitted network access if continuous collection is needed; this package does not create a scheduled job.

```bash
# Poll configured publisher feeds; save headline-only text, actual receipt and health.
python jay/revision_v3_2/collect_forward.py --user-agent "Your project name and contact" --outdir runtime_news

# Ingest an actually received, timely provider Tier-1 CSV.
python jay/revision_v3_1/collect_social.py --input path/to/fresh_provider_export.csv --journal runtime_social.jsonl

# Strict observed-clock shadow pricing with current market data and input quote rows.
python jay/revision_v3_2/framework.py --validation path/to/new_quotes.csv --market path/to/current_market.csv --news runtime_news/observed_news.jsonl --social runtime_social.jsonl --clock observed --news-health runtime_news/feed_health.json --skip-historical --outdir observed_results
```

The news collector records healthy/error runs and the inference adapter accepts a healthy receipt report for at most 600 seconds after its recorded time. Missing social remains a fallback. The public weekly exports are research samples, not a timely provider API; a suitable licensed feed/export is required for sustained use. RSS reachability and production feed reliability are not established by the offline tests. No historical receipt override is offered.

## Verification and scope

`verify.py` checks source/model identities, training cutoffs, future-record exclusion, observed-clock fallback, inference without fitting, outcome removal and missing-market handling. The runner additionally verifies row preservation, past-only joins, freshness, exact equivalence to the original relative formula, price limits and immutable inputs. Package verification reruns the bundle from a clean extraction.

This package updates the assignment experiment. It does not claim validated profitability, automatic live deployment, full news coverage or a completed official scoring submission.
