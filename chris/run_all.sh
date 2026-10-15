#!/usr/bin/env bash
# Reproduce every table in README.md from the supplied files. Run from this folder. Takes a few minutes.
set -e
mkdir -p work results
DATA=../data/with_base_premium
python3 00_prepare_features.py $DATA/pp_transactions_training.csv $DATA/btc_market_history.csv work/orders.pkl
python3 01_build_book.py        work/orders.pkl work/book.pkl                 | tee results/console_01_book.txt
python3 02_test_imbalance.py    work/book.pkl   work/orders.pkl               | tee results/console_02_imbalance.txt
python3 03_robustness.py        work/book.pkl   work/orders.pkl               | tee results/console_03_robustness.txt
python3 04_backtest_skew.py     work/book.pkl                                 | tee results/console_04_backtest.txt
python3 05_targeted_vs_flat.py  work/book.pkl                                 | tee results/console_05_targeted_vs_flat.txt
python3 06_crowd_right_days.py  work/book.pkl                                 | tee results/console_06_crowd_right_days.txt
