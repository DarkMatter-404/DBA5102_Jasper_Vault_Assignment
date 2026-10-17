# fair_value_engine (Maksim)

The parts of Maksim's model that make the submitted prices. They are copied from `maksim/` at commit `461f015`. The
only change is the `REPO` line in `src/config.py` (see `../../CHANGES.md`). The full research, with backtests, risk
tests and figures, is in [`../../experiments/fair_value_model/`](../../experiments/fair_value_model/).

| Path | What it is | Used by main |
|---|---|---|
| `src/` | Data loading, market features, the move model, the pricer, the evaluation helpers | `model.fair_value_per_btc` (moneyness table); `evaluate.*` (demand rules, intervals, Gini) |
| `run_validation.py` | The final fit, and the price of every validation order | Made `outputs/` |
| `run_extensions.py` | Risk policy and candidate features | `exposure_cap` (the 250,000 USDC cap) |
| `outputs/validation_recommendations.csv` | The frozen prices: fair value × 1.25, never below the API base price | The main column of the submission |
| `outputs/FROZEN.json`, `outputs/model_card.json` | SHA-256 of the frozen file; the fitted parameters | Checked before every run |
| `data/` | BTC candles to 14 Oct 2026, the US release calendar, NYSE holidays, a copy of the validation orders | Read by `src/` |
| `tests/` | No look-ahead; hedge mechanics | Run them with `python -m pytest tests -q` |

The method is in section 3 of [the full README](../../experiments/fair_value_model/README.md).
