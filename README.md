# Jay's Jasper Vault PP pricing study

**Latest work: [revision 2 — duration credibility with an analytic price cap](revision_v2/README.md).** It replaces the original research proposal with smaller, explainable adjustments. July scenario margin is 4,542.88 versus 4,042.04 USDC at assumed elasticity 4, with 98.28% assumed retention. This is retrospective evidence; superiority over uniform pricing and the actual Jasper base remains unproven. Read the [revised findings and submission argument](revision_v2/findings.md) and run the commands in the v2 README.

The sections below document **version 1**, retained as the historical baseline and shared data-audit implementation. Its negative result and disabled default adjustment are unchanged. The earlier presentation also describes version 1; update it using the v2 findings and figure generator before presenting the revised model.

This workspace contains the pricing code, reproducible findings and submission plan for the original **7,831-order EN dataset**. The proposal combines an interpretable expected-payout model, a bounded premium adjustment and a validation gate.

**The June-selected challenger failed the July holdout.** July payout RMSE was **144.82 USDC**, compared with **135.09 USDC** for the calibrated recorded-premium reference. The default deployment configuration therefore leaves the adjustment disabled. This is a working research model with a documented negative result; improved profitability has not been established.

Start with the [findings and submission summary](docs/findings_and_submission.md). The [detailed methodology](docs/methodology.md) records the equations, assumptions and diagnostics. The [project README](../README.md) and [data inventory](../data/README.md) describe the assignment and shared inputs.

## Reproduce the analysis

Use **Python 3.12**. Run these commands from the **repository root**, the directory containing `jay/` and `data/`:

```bash
python3.12 -m venv jay/.venv
source jay/.venv/bin/activate
python -m pip install -r jay/requirements.txt

python jay/pp_pricing.py analyze \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --outdir jay/output/data

python jay/verify_pricing.py

python jay/build_figures.py
```

On Windows, create the environment with `py -3.12 -m venv jay/.venv` and activate it with `jay\.venv\Scripts\Activate.ps1` in PowerShell. Enter the analysis command on one line instead of using Bash's `\` continuations.

The analysis and verification require no API keys or network calls once dependencies and input files are present. Python package versions are pinned in `requirements.txt`; Python 3.12.14 was used for the checked results. The verification script fails on a mismatched or truncated source CSV and compares the regenerated July metrics, selected model and chronological splits with the committed reference results. Floating-point comparisons use a tolerance; image bytes need not be identical across systems.

`build_figures.py` creates PNG/SVG presentation figures and equation PNGs in `jay/output/figures/`. Its labels describe this fixed EN experiment. It checks a headline result before generating figures; review labels and assumptions before adapting it to a revised model or another release.

## What is included

| Path | Purpose |
| --- | --- |
| `pp_pricing.py` | Data audit, past-only market features, model selection, July evaluation, training and prediction CLI |
| `verify_pricing.py` | Input checksums, outcome-blinding, future-market truncation, invalid-input checks, gate checks, serialization and reference-result comparison |
| `build_figures.py` | Presentation-chart and equation-image generator |
| `docs/findings_and_submission.md` | Findings, assignment approach, recommendation, next research and timed slide plan |
| `docs/methodology.md` | Detailed model and evaluation specification |
| `docs/classnotes.md` | Supplied session notes used to interpret ATM scope and payouts |
| `reference_results/` | Compact model JSONs, audited results and verification evidence from the original EN study |
| `figures/` | Ready-to-use SVG figures for the presentation |
| `output/` | Local regenerated results, row-level CSVs and chart assets; ignored by Git |

Raw datasets stay in the shared `data/` folder. All code, derived outputs and documentation for this contribution stay under `jay/`.

## Expected headline outputs

| Check | Expected value |
| --- | ---: |
| Source orders / market candles | 7,831 / 338,917 |
| Audited orders / excluded union | 7,603 / 228 |
| Initial fit / June selection / July holdout | 2,650 / 2,322 / 2,625 |
| Pre-July refit labels | 4,975 |
| Selected model | `anchor_bps_state_ridge0.1` |
| July calibrated recorded-premium RMSE | 135.0931 USDC |
| July selected challenger RMSE | 144.8236 USDC |
| July recorded-price gross margin | 4,042.04 USDC |
| July experimental adjustment gross margin at unchanged fills | 744.84 USDC |
| Default deployment adjustment weight | 0 |

Gross margin means premium minus gross payout, before fees, funding, hedging and capital costs. The calibrated recorded-premium **cost benchmark** differs from the actual paid-price **commercial benchmark**.

`analyze` produces the audit, exclusions, monthly/tenor tables, June selection, July metrics and row predictions, conditional day bootstrap, assumed-retention scenarios, cohort stresses, charts and two model files. `verify_pricing.py` adds timing sensitivity, side/tenor diagnostics, a training-row output-schema example and `verification_report.json`. Compact copies are committed in `reference_results/`; large row-level outputs are regenerated locally.

## Predict on a supplied file

This runnable example demonstrates the schema on the training rows. It is **not** an out-of-sample submission or a performance estimate for the later refit:

```bash
python jay/pp_pricing.py predict \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --model jay/output/data/deployment_model.json \
  --output jay/output/data/training_recommendations.csv
```

When the blind EN validation file is supplied, put it under `jay/output/inputs/` and use its path with `--orders`. Also supply market candles covering its entire quote period with `--market`. The described validation ends at 24 August 2026 15:58:54 UTC, while the supplied market file ends at 08:36:59.999 UTC that day. The blind order CSV is not currently included in the repository.

Prediction does not require `closedAt` or `realizedProfit_USDC`. Required order columns are `createdAt`, `expirationDate`, `optionType`, `productType`, `quantity_BTC`, `strikePrice` and `premiumAmount_USDC`. For quote-time use, the last field must represent an observable reference quote; historical paid premiums alone do not establish its live availability.

The output preserves input row order. `source_row` is a zero-based file position, not an exchange order ID. Output includes expected payout, challenger multiplier/premium, gated multiplier/recommended premium, and status. With `deployment_model.json`, the default weight is zero. Use `--experimental-overlay` only to inspect the failed experimental adjustment; it explicitly sets the weight to one.

Invalid references or contracts return blank prices and multipliers. Other valid contracts with ambiguous timing or stale/missing candles receive explicitly labelled recorded-price fallbacks for offline row continuity. A live quote service should block and requote those rows. Do not silently submit them as fully supported model prices.

## Refit a frozen specification

```bash
python jay/pp_pricing.py train \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --template-model jay/output/data/deployment_model.json \
  --cutoff 2026-07-31T17:11:48Z \
  --model-out jay/output/data/refitted_model.json
```

Both creation and settlement must precede the cutoff. This refit uses 7,585 eligible settled labels; 18 otherwise eligible labels were not yet available. Refitting keeps the adjustment disabled. `frozen_july_model.json` is a separate pre-July experimental artifact with weight one; July metrics describe that frozen fit, not `deployment_model.json`.

To use different local input/output locations for the **same EN reproduction**, pass `--orders`, `--market`, `--outdir` and optionally `--reference-dir` to `verify_pricing.py`. The figure builder supports `--data-dir` and `--output-dir`. Create output parent directories before `train` or `predict`.

## Dataset boundary

This implementation uses `premiumAmount_USDC` as a **recorded-price proxy**, not `apiBasePrice_per_BTC_USDC`. The repository's `data/with_base_premium/` release has 7,204 orders, removes 627 negative-markup records and retains 1,131 unmatched base quotes. Its rows and reference-price meaning differ from this experiment.

The current CLI will ignore extra enrichment columns; merely switching paths does **not** implement an API-base pricing model. The verification command intentionally accepts only the original EN input hashes. See the [separate base-premium evaluation plan](docs/findings_and_submission.md#next-study-using-the-base-premium-release) before designing a new experiment.

## Submission status

The code, evidence, model narrative and a ten-minute slide plan are ready for team review. The PowerPoint deck, recorded presentation, missing blind predictions and partner scoring remain to be completed. The brief specifies 18 October 2026 at 11:59 p.m. via Canvas; confirm the displayed timezone there.
