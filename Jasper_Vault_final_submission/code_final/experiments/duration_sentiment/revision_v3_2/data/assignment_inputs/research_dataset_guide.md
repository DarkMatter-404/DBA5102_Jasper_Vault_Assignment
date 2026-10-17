# Jasper Vault PP Pricing Research: Dataset Guide

## 1. pp_transactions_training.csv

The training dataset is taken directly from the `Options` sheet in the supplied merged options-order workbook. The original order columns and their order are preserved. Three pricing fields are appended: `orderPrice_per_BTC_USDC`, `apiBasePrice_per_BTC_USDC`, and `markup_per_BTC_USDC`.

- Orders: 7,204
- Date range: 2026-02-02 01:41:47 UTC to 2026-07-31 17:11:11 UTC
- Sampling method: sort by `createdAt` in ascending order and select the earliest 80%
- `closedAt` and `realizedProfit_USDC` retain their actual values for model training and backtesting

## 2. pp_transactions_validation.csv

The validation dataset uses the same 13 columns as the training dataset. The three appended pricing fields are observable at order creation and therefore remain available for validation.

- Orders: 1,898
- Date range: 2026-07-31 17:11:48 UTC to 2026-08-24 15:58:54 UTC
- Sampling method: sort by `createdAt` in ascending order and select the latest 20%
- For blind validation, the `closedAt` and `realizedProfit_USDC` columns are retained but their values are blank
- All other fields retain their original source values

## 3. btc_market_history.csv

This file is unchanged. It contains one-minute Binance BTCUSDC USD-M perpetual futures candles. Researchers may join it to orders by `createdAt` and independently derive pre-trade returns, realized volatility, volume, price-range, or other market features.

## Negative Markup Filter

Rows where `markup_per_BTC_USDC < 0` are excluded from both datasets. This rule removed 627 training rows and 60 validation rows. Rows with a blank markup are retained because no matched API Base price is available to evaluate them.

## Why the 80/20 Split Is Chronological Rather Than Random

Option risk and pricing behavior change across market regimes. A random split can place orders from the same day or adjacent periods in both training and validation data. This allows the model to indirectly observe the validation period's market conditions and may overstate out-of-sample performance.

This dataset therefore uses a deployment-like chronological split:

1. Sort all orders by `createdAt`, from earliest to latest.
2. Use the earliest 80% for training.
3. Use the latest 20% for validation.
4. Ensure that the training period ends before the validation period begins.

This test is stricter, but it provides a more realistic measure of whether the model can price future orders.

## Field Definitions

See `data_dictionary.csv` for detailed field definitions. The first 10 fields come from the source order workbook. The final three fields normalize the order premium to one BTC, add the contemporaneous API Base price, and calculate the effective markup.

## API Base Matching and Markup Calculation

- Order timestamps in `createdAt` are UTC. They are shifted by eight hours to match the UTC+8 timestamps in the 0DTE quote files.
- Quotes are matched on the same `optionType` and `productType`, using the nearest timestamp within 120 seconds.
- `orderPrice_per_BTC_USDC = premiumAmount_USDC / quantity_BTC`.
- `markup_per_BTC_USDC = orderPrice_per_BTC_USDC - apiBasePrice_per_BTC_USDC`.
- `markup_per_BTC_USDC` is an effective residual. It may include moneyness, PP conversion, subsidies, or other execution differences, so it is not necessarily equal to the configured `platform_premium` in a 0DTE quote file.
- A blank API Base or markup value means that no valid quote was available within the matching tolerance.

