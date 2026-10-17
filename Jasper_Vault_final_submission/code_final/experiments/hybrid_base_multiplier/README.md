# Subham: hybrid pricing model for Perpetual Protect

> **code_final copy.** Copied from `subham/` (without `final/`) at commit `461f015`. `pricing/data.py` changed so that
> it finds `data/` ([`../../CHANGES.md`](../../CHANGES.md)). The team's final solution is in
> [`../../main/final_pricing/`](../../main/final_pricing/) (report:
> [`final_report.html`](../../main/final_pricing/final_report.html)). Checked from this folder on 18 Oct 2026:
>
> ```bash
> python -m pip install -r requirements.txt
> python -m pytest tests -q     # 14 of 14 pass
> ```
>
> The notebooks were not re-run for code_final. Notebook 02 needs internet.

This folder has my pricing model for Jasper Vault's Perpetual Protect (PP). The model starts from Jasper Vault's base price. It corrects that price with the payouts in the training data. Then it adds a margin that keeps the price near what customers pay today.

For each of the 4,155 validation orders, the model gives **both** outputs:

- a premium in USDC, and
- a pricing multiplier, so that `Final Premium = Base Premium × Pricing Multiplier`.

**Read first:** [`reports/pricing_report.html`](reports/pricing_report.html). It is a plain-language report with no code. GitHub shows only the HTML source, so download the file and open it in a browser.

## Main results

Backtest on May–July 2026. Each month is priced with a model fitted only on earlier months. "Expected profit" assumes moderate price sensitivity (see Key assumptions).

| | Our model | Jasper Vault today |
| --- | ---: | ---: |
| Expected profit, May–July (USDC) | 34,124 | 15,195 |
| Gain (90% interval) | 18,928 (6,482 to 33,832) | – |

- With high price sensitivity, the gain is 13,019 USDC, but its interval includes zero.
- Our price is lower than today's price for 30% of orders, and more than 1.5 × today's price for 13%.
- Validation file (31 Jul – 14 Oct 2026): total premium 216,764 USDC, expected payout 160,251 USDC.

## The model in five steps

All prices are per 1 BTC until the last step.

1. **Anchor.** Use Jasper Vault's base price. Where it is missing (all of September and October, and part of August), use our rebuilt base price.
2. **Expected payout = anchor × risk multiplier.** The multiplier is learned from real payouts. It is about 1.32 for a normal order and about 1.72 when a scheduled US economic release (CPI, jobs report, Fed decision, PPI, PCE, GDP) falls inside the protection window.
3. **Reference price = anchor × reference factor.** This estimates what customers pay today for this type of order.
4. **Premium = expected payout + reference price ÷ 3.** This margin gives the highest expected profit under moderate price sensitivity.
5. **Caps.** The premium stays between 0.85 and 1.6 × the reference price, and never goes below the expected payout.

Premium for the order = premium per BTC × order size. Multiplier = premium per BTC ÷ anchor.

The report (sections 3.1 and 3.2) shows these steps with two real orders.

## Folder layout

```text
subham/
├── README.md
├── requirements.txt
├── pricing/         # Model code, used by the notebooks
├── notebooks/       # 01–05 and report.ipynb; run in this order
├── tests/           # pytest checks: no look-ahead, payout rule, caps, submission file
├── analysis/        # Two early checks: payout formula and strike type
├── data/external/   # Saved outside data: US release calendar, Crypto Fear & Greed index
├── outputs/         # Features, backtest results, validation_premiums.csv
└── reports/         # pricing_report.html, made from notebooks/report.ipynb
```

## Data

- **Training data:** [`../data/with_base_premium/`](../../../../data/with_base_premium/), unchanged. These files are identical to the supplied release (check with `materials/SHA256SUMS.txt`).
- **Validation data:** not in this repository. Put the two validation files in `data/validation/` at the repository root. The version I used:

  | File | Content | SHA256 |
  | --- | --- | --- |
  | `pp_transactions_validation.csv` | 4,155 orders, 31 Jul – 14 Oct 2026 | `fd85444b94f91cf212ddecbc2a16681e9f4a196cc45b7d42cdbddba03ff72d07` |
  | `btc_market_history.csv` | 1-minute BTC candles, 1 Jan – 14 Oct 2026 | `70cae3c152eb7279fdfd838b4a483b1800fd2f3950ce21cbbfb03ed502cbee88` |

  This release has more orders than the supplied guides describe (1,898 orders up to 24 August).
- **Without the validation files**, you can still run notebooks 03, 04 and the report. Notebooks 01, 02 and 05 need them. The code then uses the training copy of the BTC file, which covers the training months.
- The code also finds the data in the original export folders, if you put them in this folder: `JV validation dataset/` and `Jasper Vault Options Pricing Optimisation(Included Base Premium)/`.

## How to run

Tested with Python 3.14.3 on Windows. Run these commands from the repository root.

```bash
python -m venv .venv
.venv\Scripts\activate                  # macOS/Linux: source .venv/bin/activate
pip install -r subham/requirements.txt
python -m ipykernel install --user --name jv-pricing   # the notebooks use this kernel name

cd subham/notebooks
jupyter nbconvert --to notebook --execute --inplace 01_data_features.ipynb 02_external_data.ipynb 03_models.ipynb 04_backtest.ipynb 05_validation_submission.ipynb report.ipynb
jupyter nbconvert --to html --no-input report.ipynb --output-dir ../reports --output pricing_report

cd ..
python -m pytest tests                  # 14 tests; 2 skip without the validation files
```

- Notebook 02 needs internet. It downloads the Crypto Fear & Greed index (alternative.me) and tries the GDELT news service, which refused our requests. The US release dates are in `pricing/external.py`, taken from the official 2026 schedules.
- The two scripts in `analysis/` take the data folder as an argument, for example `python analysis/payout_formula_test.py ../data/with_base_premium`.

## Output file

`outputs/validation_premiums.csv` has one row for each validation order, in the same order as the input file.

| Column | Meaning |
| --- | --- |
| `premiumAmount_USDC` | Premium for the order |
| `pricingMultiplier` | Premium per BTC ÷ anchor |
| `anchor_source` | `jasper` = Jasper Vault's base price, `rebuilt` = our rebuilt base price |
| `anchor_per_BTC_USDC` | The anchor (step 1) |
| `expected_payout_per_BTC_USDC` | Step 2 |
| `reference_price_per_BTC_USDC` | Step 3 |
| `premium_per_BTC_USDC` | Steps 4 and 5 |

The other columns are copied from the input file.

## Key assumptions

- **Price sensitivity is moderate:** a 10% higher price gives about 26% fewer orders. Jasper Vault did not give its scoring rule, so the report also shows low and high sensitivity.
- **Payout rule:** a Put pays (strike − BTC price at close) × size, and a Call pays the opposite. The trader can close early.
- **No look-ahead:** each order uses only the last complete minute of BTC data before it was created. The `closedAt` column in the validation file is never used.
- **Missing base prices are rebuilt by a model.** On August orders, the median error was 9%.
- **Order size does not change the price per BTC.** Size helped in the training months but failed on new months.

The limits of the model are in section 8 of the report.
