# evidence

Saved results from the experiments that the final notebooks read. Each file is a byte-exact copy of the file with the
same path in `../../experiments/`. A test (`../final_pricing/tests/test_final_solution.py`) checks that they stay
equal.

| File (here) | Copied from | Made by | Read by |
|---|---|---|---|
| `fair_value_model/results/walk_forward_orders_priced.parquet` | `maksim/results/` | `run_backtest.py` | `final_solution.ipynb`: the adoption rule for the loading (7,150 training orders) |
| `fair_value_model/results/walk_forward_monthly.csv` | `maksim/results/` | `run_backtest.py` | `final_report.ipynb` |
| `fair_value_model/results/margin_sensitivity_walk_forward.csv` | `maksim/results/` | `run_backtest.py` | `final_report.ipynb` (margin section) |
| `fair_value_model/results/payout_over_fair_value_walk_forward.csv` | `maksim/results/` | `run_backtest.py` | `final_report.ipynb` (calibration) |
| `fair_value_model/results/extensions/exposure_limits.csv` | `maksim/results/extensions/` | `run_extensions.py` | `final_report.ipynb` (risk and the cap) |
| `fair_value_model/results/sealed_check/summary.json` | `maksim/results/sealed_check/` | `run_sealed_check.py` (run once) | `final_report.ipynb` (validation period) |
| `fair_value_model/results/sealed_check/sealed_check_monthly.csv` | `maksim/results/sealed_check/` | `run_sealed_check.py` (run once) | `final_report.ipynb` |
| `team_audit/same_holdout_scores.csv` | `chris/audit/` | `score_panels.py` | `final_report.ipynb` (all team models on the same orders) |
| `hybrid_base_multiplier/outputs/backtest_summary.csv` | `subham/outputs/` | notebook `04_backtest.ipynb` | `final_report.ipynb` (scorecard) |
| `hybrid_base_multiplier/outputs/validation_premiums.csv` | `subham/outputs/` | notebook `05_validation_submission.ipynb` | `final_solution.ipynb` (rebuilt base price: a cross-check only) |
