# Jasper Vault data inventory

All three supplied packages are extracted here without changing file contents: the two training releases (`with_base_premium/`, `en/`) and the blind validation release (`validation/`). Each training release retains its own guide, dictionary, and metadata. The original ZIPs are in [materials/archives](../materials/archives/).

| Folder | Use it for |
| --- | --- |
| [with_base_premium/](with_base_premium/) | **Training orders** (7,204) with the base price |
| [validation/](validation/) | **Blind validation orders** (4,155) and **the BTC market file to use** (to 14 Oct) — read its [README](validation/README.md) |
| [en/](en/) | The original 7,831-row training release, kept for reference |

## Included files

| File | `with_base_premium/` | `en/` | Purpose |
| --- | ---: | ---: | --- |
| `pp_transactions_training.csv` | 7,204 rows, 13 columns | 7,831 rows, 10 columns | Historical PP orders and observed outcomes |
| `btc_market_history.csv` | 338,917 rows, 13 columns | Same file | One-minute Binance BTCUSDC USD-M perpetual futures candles |
| `data_dictionary.csv` | Included | Included | Field definitions and units |
| `research_dataset_guide.md` | Included | Included | Dataset construction, chronology, and usage notes |
| `pp_research_datasets_metadata.json` | Included | Included | Source information, split details, and enrichment metadata |

Counts above were checked against the extracted CSVs. The identical market-history file is retained in both release folders so each supplied package remains self-contained.

Training order timestamps run from **2026-02-02 01:41:47 UTC** through **2026-07-31 17:11:11 UTC**. The training-release market file's first and last candle opening timestamps are **2026-01-01 00:00:00 UTC** and **2026-08-24 08:36:00 UTC**; that last candle was cut while still open. The validation-release market file (`validation/btc_market_history.csv`) runs to **2026-10-14 03:59 UTC** with no missing or duplicate minutes, and supersedes it.

## Choosing a release

Use [with_base_premium](with_base_premium/) as a starting point for approaches that adjust Jasper Vault's base pricing. It adds:

- `orderPrice_per_BTC_USDC`: recorded order premium divided by BTC quantity.
- `apiBasePrice_per_BTC_USDC`: the matched API base quote per BTC.
- `markup_per_BTC_USDC`: per-BTC order price minus per-BTC API base price.

The supplier excluded 627 training rows with negative effective markup after the original chronological split, leaving 7,204 rows. **1,131 of those rows have no matched API base price.** The supplied guide says unmatched rows were retained. Define and document a fallback or exclusion rule when a method requires a base price.

The [EN release](en/) retains the original 7,831 training rows and 10 order fields. It does not contain the three pricing enrichment columns. Results from the two releases use different row populations unless explicitly aligned.

Refer to the [base-premium guide](with_base_premium/research_dataset_guide.md), [dictionary](with_base_premium/data_dictionary.csv), and [metadata](with_base_premium/pp_research_datasets_metadata.json) for the source definitions. Equivalent documents are available in the EN folder.

## Validation release

The blind validation file arrived separately on 14 October 2026 and is extracted in
[validation/](validation/), with its own [README](validation/README.md). It does **not** match
what the guides above describe (1,898 orders, 31 Jul – 24 Aug, with `closedAt` hidden):

- **4,155 orders, 31 July – 14 October 2026.** The first 1,898 rows are the documented release
  (timestamps cut to the minute); the remaining 2,257 are new.
- **2,195 orders (53%) have no base price**, nearly all in the new rows.
- `premiumAmount_USDC`, `orderPrice_per_BTC_USDC` and `realizedProfit_USDC` are blank;
  **`closedAt` is filled in** and must not be used as a feature.
- It ships with a new `btc_market_history.csv` (412,080 candles to 2026-10-14 03:59 UTC). It
  matches the training-release file on every shared candle except that file's last,
  half-finished minute. **Use the new file for all market features.**

The case calls for a pricing multiplier or premium recommendation for each validation observation.

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
