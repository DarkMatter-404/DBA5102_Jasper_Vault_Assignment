# Jasper Vault PP Pricing Research: Dataset Guide

## 1. pp_transactions_training.csv

The training dataset is taken directly from the `Options` sheet in the supplied merged options-order workbook. The original column names, column order, and field meanings are preserved. No 0DTE quote-matching columns, Binance market columns, or other derived features have been added.

- Orders: 7,831
- Date range: 2026-02-02 01:41:47 UTC to 2026-07-31 17:11:11 UTC
- Sampling method: sort by `createdAt` in ascending order and select the earliest 80%
- `closedAt` and `realizedProfit_USDC` retain their actual values for model training and backtesting

## 2. pp_transactions_validation.csv

The validation dataset uses exactly the same 10 columns, in the same order, as the training dataset. No additional fields have been introduced.

- Orders: 1,958
- Date range: 2026-07-31 17:11:48 UTC to 2026-08-24 15:58:54 UTC
- Sampling method: sort by `createdAt` in ascending order and select the latest 20%
- For blind validation, the `closedAt` and `realizedProfit_USDC` columns are retained but their values are blank
- All other fields retain their original source values

## 3. btc_market_history.csv

This file is unchanged. It contains one-minute Binance BTCUSDC USD-M perpetual futures candles. Researchers may join it to orders by `createdAt` and independently derive pre-trade returns, realized volatility, volume, price-range, or other market features.

## Why the 80/20 Split Is Chronological Rather Than Random

Option risk and pricing behavior change across market regimes. A random split can place orders from the same day or adjacent periods in both training and validation data. This allows the model to indirectly observe the validation period's market conditions and may overstate out-of-sample performance.

This dataset therefore uses a deployment-like chronological split:

1. Sort all orders by `createdAt`, from earliest to latest.
2. Use the earliest 80% for training.
3. Use the latest 20% for validation.
4. Ensure that the training period ends before the validation period begins.

This test is stricter, but it provides a more realistic measure of whether the model can price future orders.

## Field Definitions

See `data_dictionary.csv` for detailed field definitions. The two order datasets contain only the 10 fields from the source workbook and do not include quote-matching or market-derived fields.
