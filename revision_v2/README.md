# Jasper PP pricing — revision 2

**Recommended research candidate: duration credibility with an analytic price cap.** It makes small, explainable markups and markdowns around the recorded premium. July scenario gross margin improves from **4,042.04 to 4,542.88 USDC** at assumed elasticity 4, with **98.28% assumed order retention**. This is retrospective scenario evidence, not a proven improvement over Jasper's live pricing. The candidate has no established advantage over matched uniform-price comparators, and its July payout RMSE is slightly worse than the calibrated reference.

Read [findings.md](findings.md) for the assignment argument, equations, all important negative results, limitations and proposed submission. The original `jay/pp_pricing.py` study is retained as version 1; its default adjustment remains disabled.

## Run from the repository root

Use Python 3.12. The checked environment used Python 3.12.14 and the pinned packages in `jay/requirements.txt`.

```bash
python3.12 -m venv jay/.venv
source jay/.venv/bin/activate
python -m pip install -r jay/requirements.txt

python jay/revision_v2/pricing.py analyze \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --outdir jay/output/v2

python jay/revision_v2/verify.py
python jay/revision_v2/build_figures.py
```

Windows: use `py -3.12 -m venv jay/.venv`, activate with `jay\.venv\Scripts\Activate.ps1`, and put multiline commands on one line. No API keys or network access are needed after installing dependencies and obtaining the repository inputs.

`analyze` uses **only the original EN release**. It imports the existing audited feature pipeline from `jay/pp_pricing.py`. Keep that file when uploading this folder. Do not swap in `data/with_base_premium/` and interpret the result as an API-base model: the separate research runner below explicitly implements that experiment.

## Expected outputs

| Output under `jay/output/v2/` | Meaning |
| --- | --- |
| `cost_metrics.csv` | April–July cost accuracy, calibrated reference versus duration credibility |
| `commercial_scenarios.csv` | All four elasticity scenarios, monthly results and uniform comparators |
| `conditional_bootstrap.json` | July paired-day intervals, conditional on the fitted models and demand scenarios |
| `creation_cohort_margins.csv` | Eventual margin grouped by order creation date; not settlement cashflow |
| `frozen_tenor_rates.csv` | Seven duration adjustments for the pre-July fit |
| `frozen_july_model.json` | Parameters fitted using 4,975 labels available before July 1 |
| `preblind_research_model.json` | Same specification refitted on 7,585 labels before July 31, 17:11:48 UTC |
| `july_recommendations.csv` | The 2,625 evaluated July rows, with row IDs and candidate prices |
| `verification_report.json` | Chronology, outcome independence, price-bound and reproduction checks |
| `figures/` | PNG/SVG charts for an updated presentation |

Compact reference tables and both model JSONs are in `reference_results/`. Large row-level outputs and research logs are regenerated locally and ignored by Git. The model JSONs are research candidates; they are not live deployment approval.

## Reproduce every alternative tested

This additionally requires `data/with_base_premium/pp_transactions_training.csv`, which is already part of the shared repository, and scikit-learn for the four shallow-tree challengers.

```bash
python -m pip install -r jay/revision_v2/requirements_research.txt
python jay/revision_v2/research/run_all.py
```

The runner executes eight stages and writes tables/logs to `jay/output/v2/research/`: seven EN cost specifications; their calibration and pricing diagnostics; a daily-batch neutral diagnostic; a four-weight pricing study; nine API/paid-anchor specifications; four shallow-tree specifications; and nine nonzero cost-plus pricing policies plus unchanged pricing. All failures are retained. The analytic final cap is reproduced by the main `analyze` command, not selected by the alternative grids.

`research/base_study.py` and `research/tree_study.py` operate on the **same 5,887 matched, valid enriched rows**, of which 2,539 are in July. Their absolute scores must not be compared directly with the original EN sample's 2,625 July rows. The enriched release's filtering and quote-timestamp caveats are recorded in the findings.

## Train or generate recommendations

```bash
python jay/revision_v2/pricing.py train \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --cutoff 2026-07-31T17:11:48Z \
  --rho 0.95 --emax 4 \
  --model-out jay/output/v2/preblind_research_model.json
```

Both `createdAt` and `closedAt` must be strictly before the cutoff. Parameters `rho` and `emax` are explicit demand-scenario assumptions. Changing them changes the price bound and invalidates the published commercial comparison.

This executable example checks the output format on training rows; it is **not** a new performance test:

```bash
python jay/revision_v2/pricing.py predict \
  --orders data/en/pp_transactions_training.csv \
  --market data/en/btc_market_history.csv \
  --model jay/output/v2/preblind_research_model.json \
  --output jay/output/v2/training_schema_example.csv
```

For the separate blind file, replace `--orders` with its actual path and provide market data through the entire quote period. The blind order file is not available in the supplied repository. The supplied candle history also ends about **7 hours 22 minutes before** the documented end of validation.

Required order columns are `createdAt`, `expirationDate`, `optionType`, `productType`, `quantity_BTC`, `strikePrice`, and `premiumAmount_USDC`. `closedAt` and `realizedProfit_USDC` may be missing. At inference, `premiumAmount_USDC` must mean an observable reference quote. Historical paid prices do not by themselves establish that live availability.

Output retains every input row in original order. `source_row` is the zero-based file position, not an exchange order ID. `recommended_multiplier` is relative to the **recorded-premium reference**, not the API base. Use the absolute `recommended_premium_USDC` field if the partner's submission schema accepts premiums, and confirm the reference semantics before submitting a multiplier.

Invalid contracts or references receive blank candidate prices. Valid contracts with stale market coverage or ambiguous timing receive an explicitly labelled reference fallback for offline row continuity; those rows require a new quote before any live use. Rows dated before the model's cutoff are labelled historical diagnostics because that model can contain later labels. They are never an out-of-sample test.

## Interpretation boundary

The final multiplier is between **0.987094 and 1.012906**. Within the assumed demand family `q = min(1, multiplier**(-elasticity))`, this gives at least 95% retention for each quote when elasticity is between 0 and 4. It does **not** guarantee actual retention, profit or capital safety.

July had already been inspected before this revision. The cost specification is chosen using April–June folds, but the revised policy design remains retrospective. A separate outcome-blind assessment and Jasper's actual conversion rule are still required. The previous PowerPoint describes version 1; use this folder's findings and regenerated figures when updating the presentation.
