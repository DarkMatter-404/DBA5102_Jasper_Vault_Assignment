# Validation release (received 14 October 2026)

Jasper Vault's blind validation package, extracted without changes. The original ZIP is kept at
[`materials/archives/JV validation dataset (Blockchain_Assignment_export).zip`](../../materials/archives/).
Both files are byte-identical to the ZIP contents (see `materials/SHA256SUMS.txt`).

| File | Rows | Coverage | SHA-256 (first 12) |
| --- | ---: | --- | --- |
| `pp_transactions_validation.csv` | 4,155 orders, 13 columns | created 2026-07-31 17:11 → 2026-10-14 02:46 UTC | `fd85444b94f9` |
| `btc_market_history.csv` | 412,080 one-minute candles | 2026-01-01 00:00 → 2026-10-14 03:59 UTC | `70cae3c152eb` |

The columns are the same 13 as `data/with_base_premium/pp_transactions_training.csv`. Field
definitions are in [`../with_base_premium/data_dictionary.csv`](../with_base_premium/data_dictionary.csv).

## This is not the release the dataset guide describes

The guide says the validation set is 1,898 orders from 31 July to 24 August. The file we
received has **4,155 orders up to 14 October**. It is two blocks joined together:

| Block | Rows (0-based) | Orders | createdAt | Timestamp format | Base price present |
| --- | --- | ---: | --- | --- | ---: |
| **A** — the documented release | 0–1,897 | 1,898 | 31 Jul 17:11 → 24 Aug 15:58 | `2026/7/31 17:11` — **minute only** (seconds lost, probably saved through Excel) | 1,895 (99.8%) |
| **B** — new orders | 1,898–4,154 | 2,257 | 24 Aug 16:05:59 → 14 Oct 02:46:18 | `2026-08-24 16:05:59` | **65 (2.9%)** |

## What is hidden and what is not

| Column | Status | What to do |
| --- | --- | --- |
| `premiumAmount_USDC`, `orderPrice_per_BTC_USDC` | **Blank in every row** | We cannot see what JV actually charged |
| `realizedProfit_USDC` | Blank in every row | The outcome — this is what JV scores us against |
| `closedAt` | **Filled in every row** | ⚠ This is an outcome (when the protection closed; 50.5% close more than 1 minute before expiry). **Never use it as a feature** |
| `apiBasePrice_per_BTC_USDC` | Present for 1,960 rows, blank for 2,195 | Approach 1 (base × multiplier) only works on these 1,960 rows |
| `markup_per_BTC_USDC` | Present for 544 rows (10–26 Aug) | For those rows base + markup reveals JV's current price per BTC. Coverage is patchy; do not build on it |

## Consequences for the model

1. **We need a price for orders without a base price.** 2,195 of 4,155 orders (53%) have no
   base, almost all of block B. A model that only outputs a multiplier on the base cannot price
   them. Either predict a premium directly (Approach 2 in the case) for every order, or define a
   documented fallback for the no-base rows.
2. **There is no order ID.** Keep the file's row order in the submission, and repeat
   `createdAt, optionType, productType, quantity_BTC, strikePrice` next to our premium so JV can
   match rows.
3. **Join market data strictly before `createdAt`.** For block A, `createdAt` is cut to the
   minute, so the true order time is within the next 59 seconds. Taking the last candle whose
   `close_time_utc` is before the cut `createdAt` is still leak-free. Checked: with
   `merge_asof(..., direction="backward", allow_exact_matches=False)` every validation order
   matches a candle, and the largest gap is 59.0 seconds.
4. **Parse dates with both formats.** `pd.to_datetime(col)` with default settings reads both
   formats in pandas 1.4. In pandas 2.x pass `format="mixed"`.

## The new BTC file replaces the old one

`btc_market_history.csv` here is a superset of the training-release file
(`data/with_base_premium/` and `data/en/`, 338,917 rows ending 2026-08-24 08:36). Every
overlapping candle is identical **except the old file's last row**, which was cut while that
minute was still open (close 77,027.3 and volume 13.451 in the old file; 77,010.4 and 20.327 in
the new one). The new file adds 73,163 candles, has no missing or duplicate minutes, and covers
every validation order and expiry. **Use this file for both training and validation features.**

## Where teammates' code expects these files

- Subham's pipeline reads `data/validation/` directly.
- Maksim's `maksim/src/config.py` points to `data/pp_transactions_validation.csv` and a parquet
  copy of the BTC file; update the path or keep a local copy.
- Jay's commands use `data/en/btc_market_history.csv`, which stops on 24 August.
