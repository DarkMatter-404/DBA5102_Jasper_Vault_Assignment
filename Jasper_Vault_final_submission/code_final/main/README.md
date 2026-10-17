# main: the final solution

For each of the 4,155 validation orders, the price is Maksim's fair-value premium: **fair value × 1.25, never below
JV's API base price**. One file holds all the prices:

| | |
|---|---|
| File | `final_pricing/outputs/final_submission.csv` |
| Column to score | `recommended_premium_USDC` |
| Total | 205,823.94 USDC |
| SHA-256 | `810eae3a1c007c9443616afc97e7f11c7c8fcf60d3e79807e571a4c717110dcf` |

Report without code: [`final_pricing/final_report.html`](final_pricing/final_report.html). GitHub shows only the
HTML source, so download the file and open it in a browser.

## The pipeline

1. **`fair_value_engine/`** (Maksim). It fits the move model on BTC candles up to 31 July 2026, 17:11 UTC, and prices
   every validation order. Output: `outputs/validation_recommendations.csv`, frozen (its SHA-256 is in
   `outputs/FROZEN.json`).
2. **`final_pricing/`** (Subham). It builds the submission file from the frozen prices. It tests Chris's order-flow
   loading with a rule committed before scoring; the loading failed one condition, so it is an optional column only.
   It counts Maksim's 250,000 USDC cap on the validation orders and writes the report.
3. **`evidence/`**. The saved experiment results that the notebooks read. Each file equals its copy in
   `../experiments/` (a test checks this). See [`evidence/README.md`](evidence/README.md).

Nothing in `final_pricing/` fits a model. No outcome (`closedAt`, `realizedProfit_USDC`) enters a price: a test
changes every `closedAt` in the validation file and gets the same prices.

## Run

From the repository root, or from the top of the unzipped package:

```bash
python -m pip install -r Jasper_Vault_final_submission/code_final/main/requirements.txt
python -m ipykernel install --user --name jv-pricing      # the notebooks use this kernel name
cd Jasper_Vault_final_submission/code_final/main/final_pricing
jupyter nbconvert --to notebook --execute --inplace final_solution.ipynb
jupyter nbconvert --to notebook --execute --inplace final_report.ipynb
jupyter nbconvert --to html --no-input final_report.ipynb --output final_report
python -m pytest tests -q                                 # 42 checks
cd ../fair_value_engine
python -m pytest tests -q                                 # 9 of 10 pass: see below
```

Optional: `python run_validation.py` in `fair_value_engine/` rebuilds the frozen prices. It overwrites `outputs/`, so
keep a copy first. On Windows, the rebuild matches the frozen file except 6 of 4,155 premiums, which differ by
0.000001 USDC (rounding across computers). The submitted prices are the committed file.

## Checks (Windows 11, Python 3.14.3, 18 Oct 2026, from the unzipped package)

- `final_pricing`: 42 of 42 checks pass. After the re-run, `final_submission.csv` is byte-identical to the submitted
  file, and all 498 numbers in the report are the same as in the report that the deck used.
- `fair_value_engine`: 9 of 10 checks pass. The failing one also fails in Maksim's original folder: it requires exact
  equality for the variant `+ range and volume (candidate)`, and one price differs by 0.000000000009 USDC. The final
  model does not use that variant, and its own no-look-ahead test passes.
