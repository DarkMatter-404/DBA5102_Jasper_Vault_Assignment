# Final PP pricing solution (team)

This folder holds the team's final pricing solution. It is a copy of `subham/final/` at commit `461f015`, set up to
run inside `code_final/main` (changes: `../../CHANGES.md`, section 3). The pipeline is in [`../README.md`](../README.md).

The core is Maksim's model: `premium = quantity × fair value × 1.25`, never below the API base price.
The improvement is Chris's order-flow loading. This section was committed **before** any scoring of the loading on
the model's prices. The commit hash of this file is the proof.

**Read first:** [`final_report.html`](final_report.html), a plain-English report with no code. GitHub shows only the
HTML source, so download the file and open it in a browser.

## Result in short

| Item | Result |
|---|---|
| Main price | Maksim's frozen premium for all 4,155 validation orders: total 205,823.94 USDC |
| Submission file | `outputs/final_submission.csv`, column `recommended_premium_USDC` (SHA-256 `810eae3a1c00…`) |
| Order-flow loading | Tested with the rule below. It beats the model, but not a flat raise of the same size, so it is an optional column only |
| Risk rule | Cap of 250,000 USDC open protection per direction (reported, not priced) |

## Adoption rule for the order-flow loading

> This section is unchanged since commit `cd9437f`, when the rule was committed before any scoring. Its paths name the
> original folders: `maksim/results/...` is now `../evidence/fair_value_model/results/...`, and `data/` is the
> repository's `data/` folder.

**Panel.** `maksim/results/walk_forward_orders_priced.parquet`: 7,150 training orders, February to July 2026. Each
month is priced by Maksim's model fitted on earlier data only (`model_premium_USDC`). `row_id` is the row number in
`data/with_base_premium/pp_transactions_training.csv`.

**Strategies.**

| Name | Premium |
|---|---|
| M | Maksim's walk-forward premium |
| M+L | M × loading |
| Flat-M | M × f, with f set so that the total of Flat-M equals the total of M+L in the same period |

- Loading = 1 + 0.3 × max(−s_add, 0) when the open book holds at least 1 BTC, else 1.
- Open book at time t = earlier orders (`createdAt` < t) with `expirationDate` > t. `closedAt` is never used.
- imb = (open call BTC − open put BTC) ÷ (open call BTC + open put BTC). s_add = imb for a call, −imb for a put.
- k = 0.3 and the 1-BTC threshold are fixed in advance (Chris, chosen on February to June). No other value is tried.

**Demand rules.** The reference price A is JV's actual premium. "None": every order is kept.
"Conservative e = 2": an order is kept with weight min((P ÷ A)^−2, 1), so price rises lose orders and price cuts win none.

**Decision.** M+L becomes the main column only if all three conditions hold:

1. July 2026: profit(M+L) − profit(M) > 0 under "none" and under "conservative e = 2".
2. February to June 2026: the same two conditions.
3. July 2026: profit(M+L) ≥ profit(Flat-M) under "conservative e = 2". This shows better allocation, not only a
   higher price level.

If any condition fails, Maksim's frozen premium stays the main column, and M+L becomes an optional column.

Note: the loading never decreases a premium, so the "none" part of conditions 1 and 2 always holds. The informative
tests are "conservative e = 2" and condition 3. The report shows every other demand rule too, including any rule
where the loading loses. Those rules do not change the decision.

## Result of the adoption rule

Scored after the rule above was committed (`final_solution.ipynb`, section C):

| Condition | Result |
|---|---|
| 1. July: M+L − M > 0 under "none" and "conservative e = 2" | Passed: +3,842 and +1,596 USDC |
| 2. February to June: the same | Passed: +3,443 and +1,619 USDC |
| 3. July: M+L ≥ Flat-M under "conservative e = 2" | **Failed**: 16,696 vs 16,812 USDC (difference −116; 90% interval −1,015 to +738) |

So the main column is Maksim's frozen premium. The loading stays in the file as an option:
`premium_frozen_model_USDC × orderflow_loading` (total 211,552.86 USDC, +2.8%).

## Files

| Path | What it is |
|---|---|
| `final_report.html` | The report, without code. Built from `final_report.ipynb` |
| `final_solution.ipynb` | The computation: training evidence, adoption rule, blind-file prices, outputs |
| `solution.py` | Functions: open book from expiry dates, loading, adoption rule, submission, cap, moneyness |
| `outputs/final_submission.csv` | 4,155 rows in the original order of the validation file |
| `outputs/summary.json` | Totals, checks, the decision, SHA-256 of every input and of the submission |
| `outputs/*.csv`, `outputs/figures/` | Every table and chart in the report |
| `tests/` | 42 checks: unit tests, output checks, a `closedAt` invariance test, the submitted file's SHA-256, and the evidence copies |

Columns of `final_submission.csv`:

| Column | Meaning |
|---|---|
| `row` | Row number in the validation file (0-based). The file has no order ID |
| `createdAt`, `optionType`, `productType`, `quantity_BTC`, `strikePrice`, `apiBasePrice_per_BTC_USDC` | Copied from the validation file, so that JV can match rows |
| `recommended_premium_USDC` | **The premium to score** |
| `recommended_multiplier_vs_base` | Premium ÷ (base price × quantity). Blank where there is no base price |
| `fair_value_USDC` | Expected payout from Maksim's model |
| `premium_frozen_model_USDC` | Maksim's frozen premium, unchanged |
| `orderflow_loading` | The optional order-flow factor (≥ 1) |

## How to run

Tested with Python 3.14.3 on Windows. From this folder:

```bash
python -m pip install -r ../requirements.txt
python -m ipykernel install --user --name jv-pricing     # the notebooks use this kernel name
jupyter nbconvert --to notebook --execute --inplace final_solution.ipynb
jupyter nbconvert --to notebook --execute --inplace final_report.ipynb
jupyter nbconvert --to html --no-input final_report.ipynb --output final_report
python -m pytest tests -q                               # 42 checks
```

The code finds the data by searching parent folders for `data/with_base_premium`. If the data is somewhere else, set
the `JV_REPO` environment variable to the folder that holds `data/`.

## Inputs (read only)

| Input | File | SHA-256 (first 12) |
|---|---|---|
| Maksim's walk-forward prices, training | `../evidence/fair_value_model/results/walk_forward_orders_priced.parquet` | `29e04ae3f0fd` |
| Training orders | `data/with_base_premium/pp_transactions_training.csv` | `3f046081325c` |
| Validation orders | `data/validation/pp_transactions_validation.csv` | `fd85444b94f9` |
| Maksim's frozen prices | `../fair_value_engine/outputs/validation_recommendations.csv` | `995844128715` |
| Subham's rebuilt base price (cross-check) | `../evidence/hybrid_base_multiplier/outputs/validation_premiums.csv` | `d70b3bf024ee` |

Code used without change: `../fair_value_engine/src/evaluate.py` (demand rules, intervals, Gini),
`../fair_value_engine/src/model.py` (`fair_value_per_btc`) and `../fair_value_engine/run_extensions.py`
(`exposure_cap`). The open-book code follows `../../experiments/team_audit/combos.py`.

## Key assumptions

- No outcome enters any price. `closedAt` and `realizedProfit_USDC` are dropped on read, and a test changes every
  `closedAt` value and gets the same prices.
- JV's open book counts each protection until its expiry date, because the actual close time is an outcome.
- JV's actual price is never an input. It is unknown for 3,611 of the 4,155 validation orders.
- The demand rules are assumptions. JV's own rule is unknown.
