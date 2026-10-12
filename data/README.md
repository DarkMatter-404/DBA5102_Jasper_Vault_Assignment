# Jasper Vault data inventory

Both supplied dataset releases are extracted here without changing file contents. Each release retains its own guide, dictionary, and metadata. The original ZIPs are in [materials/archives](../materials/archives/).

## Included files

| File | `with_base_premium/` | `en/` | Purpose |
| --- | ---: | ---: | --- |
| `pp_transactions_training.csv` | 7,204 rows, 13 columns | 7,831 rows, 10 columns | Historical PP orders and observed outcomes |
| `btc_market_history.csv` | 338,917 rows, 13 columns | Same file | One-minute Binance BTCUSDC USD-M perpetual futures candles |
| `data_dictionary.csv` | Included | Included | Field definitions and units |
| `research_dataset_guide.md` | Included | Included | Dataset construction, chronology, and usage notes |
| `pp_research_datasets_metadata.json` | Included | Included | Source information, split details, and enrichment metadata |

Counts above were checked against the extracted CSVs. The identical market-history file is retained in both release folders so each supplied package remains self-contained.

Training order timestamps run from **2026-02-02 01:41:47 UTC** through **2026-07-31 17:11:11 UTC**. The supplied market file's first and last candle opening timestamps are **2026-01-01 00:00:00 UTC** and **2026-08-24 08:36:00 UTC**. These endpoints do not establish that every intervening minute is present.

## Choosing a release

Use [with_base_premium](with_base_premium/) as a starting point for approaches that adjust Jasper Vault's base pricing. It adds:

- `orderPrice_per_BTC_USDC`: recorded order premium divided by BTC quantity.
- `apiBasePrice_per_BTC_USDC`: the matched API base quote per BTC.
- `markup_per_BTC_USDC`: per-BTC order price minus per-BTC API base price.

The supplier excluded 627 training rows with negative effective markup after the original chronological split, leaving 7,204 rows. **1,131 of those rows have no matched API base price.** The supplied guide says unmatched rows were retained. Define and document a fallback or exclusion rule when a method requires a base price.

The [EN release](en/) retains the original 7,831 training rows and 10 order fields. It does not contain the three pricing enrichment columns. Results from the two releases use different row populations unless explicitly aligned.

Refer to the [base-premium guide](with_base_premium/research_dataset_guide.md), [dictionary](with_base_premium/data_dictionary.csv), and [metadata](with_base_premium/pp_research_datasets_metadata.json) for the source definitions. Equivalent documents are available in the EN folder.

## Validation availability

Neither archive contains `pp_transactions_validation.csv`. The source guides describe a later validation period from **2026-07-31 17:11:48 UTC** through **2026-08-24 15:58:54 UTC**, containing 1,958 orders in the EN release or 1,898 after the base-premium release's negative-markup filter.

Those are supplier-documented counts, not locally verified files. The documented blind-validation format hides `closedAt` and `realizedProfit_USDC`. The case calls for a pricing multiplier or premium recommendation for each validation observation.

## Modeling notes

- Order timestamps are UTC. Preserve timezone awareness when joining market observations.
- `productType` is a duration in seconds; `quantity_BTC` is a BTC quantity. The original premium and outcome amounts are in USDC, while the three enrichment fields are per BTC.
- `optionType` is `0 = Call` and `1 = Put`, consistent with `optionType_label`.
- Treat `closedAt` and `realizedProfit_USDC` as outcome information, not quote-time predictors. Confirm the payout sign and accounting convention before calculating provider profit.
- Use only market candles that had finished before an order was created. A candle's opening timestamp alone does not mean its closing price or full volume was already observable.
- The supplier matched base quotes using the nearest timestamp within 120 seconds after aligning UTC and UTC+8. The packaged data does not include individual matched quote timestamps. Audit quote-time availability if using these fields for a strictly causal backtest.
- Effective markup may incorporate moneyness, conversion, subsidies, or execution differences; the guide explicitly says it is not necessarily the configured platform premium.
- Keep development splits chronological and document how orders spanning a split boundary are handled.

Store derived data separately from these source files. Source checksums can be verified from the repository root with `shasum -a 256 -c materials/SHA256SUMS.txt`.
