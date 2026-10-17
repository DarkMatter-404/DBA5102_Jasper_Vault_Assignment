# Event-to-Loss: standalone PP pricing experiment

> **code_final copy.** Copied from `llm assisted trading/` at commit `461f015`, with no code change. Its input folder
> `data/raw/` was never committed, so it is restored from the repository's own files
> ([`data/raw/README.md`](data/raw/README.md)). Checked from this folder on 18 Oct 2026, with Python 3.12:
>
> ```bash
> python -m pip install -r requirements-tested.txt
> python -m unittest discover -s tests -v                          # 9 of 9 pass
> python scripts/run_study.py --output results/my_reproduction     # about 20 s
> ```
>
> The full study reproduces every saved result in `results/` within 1e-6.

A complete research prototype for the Jasper Vault assignment: conditional historical market paths, an early-close model, and structured event research. The language model supplies evidence classifications; it does **not** invent claim probabilities or set premiums.

Start with **[Event_to_Loss_PP_Report.html](Event_to_Loss_PP_Report.html)** for a nontechnical explanation, the six assignment requirements, measured findings and a suggested video narrative. Open it directly in a browser; it has no external dependencies.

## Main findings

Corrected chronological test: **2,559 July orders**, with model fitting restricted to information available before July. One price policy is selected using 3,222 settled May–June development orders and applied to every arm.

| July comparison | Gross profit, USDC | Interpretation |
|---|---:|---|
| Raw API Base premiums, matched rows | -31,427.90 | Base quote comparator, before extra components in paid prices |
| Actual paid premiums | 4,284.69 | The closer business comparator |
| Market-only engine | 7,617.88 | Assumes every historical order remains accepted |
| Verified-research engine | 7,655.52 | Same policy and orders as market-only |
| Increment from verified research | +37.64 | 90% paired-day interval: -44.48 to +166.10 |

All 2,559 July rows have matched API prices, so these July totals use the same population. Prices increase 3.13% in aggregate versus actual paid premiums. At unchanged demand, a uniform increase giving the same total premium produces identical profit: this alone does not demonstrate better risk selection. With assumed elasticity 2, verified-research gross profit is **-1,639.31 USDC**, versus +7,197.98 for that same-total uniform adjustment. Elasticity is a sensitivity assumption, not estimated demand.

Verified research changes **187 quotes across four macro episodes** and improves the claim-distribution score by about **0.034%** versus market-only. Its uncertainty interval includes no improvement. Expected claims cover only **64.0%** of actual July payouts. This is a testable hypothesis and working implementation, **not an established commercial improvement**.

The later validation file produces **4,155 quotes per arm**: 1,893 with fresh market context, and 2,262 explicitly labelled diagnostic fallbacks because supplied candles stop on 24 August. Every payout is hidden, so later accuracy and profitability cannot be scored.

## Reproduce the study

Python 3.12 is the tested interpreter. From this folder:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-tested.txt
python -m unittest discover -s tests -v
python scripts/run_study.py
python scripts/build_report.py
```

On Windows, activate with `.venv\Scripts\activate` instead. The study is offline and requires no API key, GitHub access, account, or earlier implementation. The initial run took about 21 seconds in the authoring environment; other machines will vary. For stable small-workload performance, set `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` before running. Tiny floating-point differences can occur across dependency/platform versions.

The supplied outputs are already generated. Re-running replaces files in `results/`; use a different `--output` folder to preserve them.

```bash
python scripts/run_study.py --output results/my_reproduction
python scripts/build_report.py --results results/my_reproduction --output my_report.html
```

### Strict receipt-clock check

```bash
python scripts/run_study.py --clock observed --output results/observed_clock
```

No historical news effect is possible in this mode: the corpus was collected in October. The principal experiment uses disclosed publication-time proxies. This is retrospective reconstruction, not evidence of historical live availability. Both modes are included in the package.

### Price one contract

Illustrative historical research quote, assuming ATM protection at the supplied strike:

```bash
python scripts/quote.py --at 2026-07-14T13:00:00Z --strike 65000 --quantity 0.01 --hours 1 --side put --clock publication_proxy
```

This command refits at the requested timestamp; the report uses fixed monthly fits, so the example need not reproduce a report row. Use `--verified-spot` only with a separately verified contract quote-time spot; it changes payoff mechanics, not the fitted early-close behaviour for moneyness. OTM predictive validity is untested.

For new dates, supply a complete updated market CSV with the supplied column schema using `--market PATH`, and processed evidence using `--events PATH`. Default `--clock observed` enforces actual collection/processing availability. Without a fresh completed candle, the command returns `no_quote` and exit code 2. `--allow-diagnostic-fallback` exists only for inspection. No command submits trades.

## Run a genuine prospective research workflow

**What was executed:** two recorded assistant classification/review passes, before forecast scores, replayed from 44 short source cards. The passes share one assistant session. They are not independent external-model agents and do not establish an advantage from agent architecture.

**What is implemented but needs a live integration test:** RSS intake, an API research call, an API verification call, strict JSON validation, audit logs and quote-time evidence filtering. The HTTP adapter supports Chat Completions-compatible JSON responses. It was tested with a clearly identified fixture client; no external API request or measured token cost is claimed.

1. Collect prospective primary-source cards. Change the user-agent to a suitable project/contact identifier where a publisher requires it.

```bash
python scripts/collect_news.py --config data/events/feed_sources.json --output data/events/live_sources.jsonl --user-agent "YourProject contact@example.com"
```

2. Configure `LLM_API_KEY` (or `OPENAI_API_KEY`) and `LLM_MODEL` in your environment. Optional: `LLM_BASE_URL` and a different `LLM_VERIFIER_MODEL`. Do not put keys in files or commits. This step incurs your provider's API charges. Model/API support and access must be checked for your account.

```bash
python scripts/run_agents.py --input data/events/live_sources.jsonl --output data/events/live_reviewed.jsonl --limit 20
```

The command makes at most two research requests per card, records actual provider usage when returned, and never overwrites an existing output. Failed requests or invalid JSON reject the signal. It does not run automatically during reproduction.

3. Review cross-source episode identities before pricing: the collector deduplicates exact URLs; it does not autonomously resolve every syndicated or updated story. Replace per-URL event IDs with a common verified episode ID where appropriate. Retain real first-seen clocks. Short feed excerpts may be insufficient and should then be rejected, not guessed.
4. Feed reviewed records and fresh market data to shadow quotes. The current source configuration covers Fed and SEC feeds. Broader crypto/security feeds require source approval, timestamps and appropriate access; the historical eight crypto cards are a selected sample, not full coverage.
5. Collect settlement outcomes and offered/accepted/rejected quote observations. Evaluate after measured data/research costs under a new fixed protocol before a controlled commercial trial.

To test a newly API-labelled historical corpus, write it to a new file, use `run_study.py --events PATH --output NEW_FOLDER`, and label any `publication_proxy` run as retrospective. Do not present it as a pre-event autonomous experiment.

## Assignment requirements

| Requirement | Evidence and current limit |
|---|---|
| Profitability | Higher fixed-order profit; demand-sensitive improvement not established; news-only uplift small and uncertain. |
| Meaningful factors | Volatility, momentum, volume, duration, covered direction, notional and early closing; event classes and reasons are inspectable. No causal importance claim. |
| Market conditions/moneyness | Conditional market paths and duration/side segments; ATM evaluated, other moneyness only supported mechanically. |
| Reasonable pricing | Development aggregate/p95 price gates passed; July aggregate +3.13%, p95 ratio 1.47×. Demand remains unmeasured. |
| Unseen data | July chronological test, paired day uncertainty; later validation outcome fields hidden. No claim of a virgin holdout or live backtest. |
| Practical deployment | Offline deterministic engine, timestamps, safe stale-market status and API adapter. Fresh data, realistic costs and prospective testing still required. |

## Files and outputs

- `src/etl/`: market preparation, evidence handling, early-close hazard, simulation, pricing evaluation and optional API research.
- `scripts/`: offline study, source-card rebuild, report builder, feed collector, API passes and single-quote command.
- `data/raw/`: supplied assignment inputs and SHA256 manifest. Market CSV is losslessly gzip-compressed.
- `data/events/recorded_events.jsonl`: 44 evidence cards / 42 unique episodes, source URLs, availability clocks, recorded labels and review reasons. The 36 macro cards and eight crypto cards were assembled afresh for this experiment.
- `docs/EXPERIMENT_PROTOCOL.md`: fixed experimental choices, hashed before scores.
- `docs/IMPLEMENTATION_DECISIONS.md`: pre-score implementation details.
- `docs/CORRECTIONS.md`: transparent policy-cutoff correction log.
- `docs/MODEL_CARD.md`: equations, limitations and the prospective success criteria.
- `results/scored_predictions.csv`: May, June and July per-order predictions and scores for all four arms.
- `results/validation_predictions.csv`: 4,155 predictions per arm, without validation settlement or payout inputs.
- `results/metrics.json`, `paired_day_bootstrap.json`, `policy_search.csv`: complete aggregate comparisons and all loading candidates.
- `results/july_segments.csv`, `july_market_segments.csv`, `july_event_quote_changes.csv`: inspectable subgroups and every event-adjusted July quote.
- `results/data_audit.json`, `model_fit_audit.json`, `integrity_checks.json`, `tests.log`, `run_manifest.json`: data checks, fit cutoffs and run evidence.
- `results/observed_clock/`: strict receipt-clock control experiment.
- `SHA256SUMS.txt`: package file checksums.

All premiums are USDC per order unless labelled per BTC. `realizedProfit_USDC` is treated as the **customer payout**, per the supplied dictionary, not the seller's profit. Seller gross profit is premium minus payout.
