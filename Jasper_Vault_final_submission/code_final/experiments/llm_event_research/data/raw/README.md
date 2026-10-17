# data/raw (restored for code_final)

The study reads its inputs from this folder, but the folder was never committed to the repository. code_final
restores it from files that are already in the repository. `../../SHA256SUMS.txt` lists the SHA-256 that the study
expects.

| File | Copied from | SHA-256 matches `SHA256SUMS.txt` |
|---|---|---|
| `pp_transactions_training.csv` | `data/with_base_premium/pp_transactions_training.csv` | Yes (`3f046081…`) |
| `pp_transactions_validation.csv` | `data/validation/pp_transactions_validation.csv` | Yes (`fd85444b…`) |
| `classnotes.md` | `jay/docs/classnotes.md` | Yes (`4669ff0f…`) |
| `btc_market_history.csv.gz` | `jay/revision_v3_2/data/assignment_inputs/btc_market_history.csv.gz` | No: `5dbfb026…`, not `5d0a2c6a…` |

The candle file decompresses to exactly the supplied training candles (`data/with_base_premium/btc_market_history.csv`,
SHA-256 `64ac0e48…`), which end on 24 August 2026, as the study's README says. Only the gzip bytes differ. With these
four files, the full study (`scripts/run_study.py`) reproduces every saved result in `../../results/` within 1e-6.

Not restored, because no code reads them: `data_dictionary.csv`, `research_dataset_guide.md` and `manifest.json`.
The supplied versions are in the repository's `data/` folder.
