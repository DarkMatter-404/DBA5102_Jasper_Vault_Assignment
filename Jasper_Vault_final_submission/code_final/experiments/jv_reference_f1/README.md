# Aman — pricing Jasper Vault's Perpetual Protect

> **code_final copy.** Copied from `aman/` at commit `461f015`. Path lines changed in `pp_pricing.ipynb` (cell 2) and
> in `checks/` ([`../../CHANGES.md`](../../CHANGES.md)). Checked from this folder on 18 Oct 2026:
>
> ```bash
> python -m pip install -r requirements.txt
> jupyter nbconvert --to notebook --execute --inplace pp_pricing.ipynb --ExecutePreprocessor.timeout=1800
> ```
>
> The notebook runs to the end, and every built-in check passes (about 30 s). On Windows, 4 of 4,155 premiums in
> `validation_predictions.csv` differ from the committed file by 0.000001 USDC, with Python 3.14 and 3.12 alike.

**Status: final.** Team decision at the 16 Oct regroup: model **F1**, theta_level = 0, band 0.8-1.2. The
specification was locked at 2026-10-16 04:46 SGT, and the 544-row reference check was run after the lock.

F1 prices each order as our estimate of JV's current price (the reference) times a fair-value shape kept within
0.8-1.2, and never below fair value (the expected payout). The fair-value engine follows Maksim's design.

## Read first

1. [`TEAM_SUMMARY.md`](TEAM_SUMMARY.md): one-page results, decisions, the lock, the 544-row check and the risk tables.
2. [`REPORT_EXPLANATION.md`](REPORT_EXPLANATION.md): what every metric means and what we can and cannot claim, in plain English.
3. [`CODE_EXPLANATION.md`](CODE_EXPLANATION.md): every notebook section and function, the data sources and what each check proves.

## What is here

| Path | What it is |
|---|---|
| `pp_pricing.ipynb` | The whole model, top to bottom (sections 1-14, then the checks and phase summaries) |
| `validation_predictions.csv` | Final prices for the 4,155 blind orders (SHA-256 `0a733667c06394c24188041646e6e204783afa6130bf4615ac63e3d75eb4f221`) |
| `model_params.json` | Every fitted parameter, `spec_locked: true`, the lock time and the predictions' SHA-256 |
| `team_scorecard/` | Every saved table (scorecard, Phase 4 registry and trials, risk, exposure cap, 544-row check) |
| `checks/test_pricing.py` | 25 checks, run once by the notebook; `checks/jump_attribution.py` is the payout-attribution script |
| `data_external/` | Offline snapshots (release calendar, teammates' saved outputs, Phase 4 series); `sources.md` says where each comes from |
| `fetch_external.py` | Rebuilds the snapshots (optional: needs internet and the git history) |
| `PLAN.md` | The converged build plan (JV-05, amended 16 Oct) |
| `questions_for_jv.md` | Questions for JV, not sent; the team decides whether to send them |
| `requirements.txt` | Exact package versions (Python 3.12.14) |

## How to run

From the repository root:

```
uv venv --python 3.12 aman/.venv
uv pip install --python aman/.venv/bin/python -r aman/requirements.txt
aman/.venv/bin/jupyter nbconvert --to notebook --execute --inplace aman/pp_pricing.ipynb --ExecutePreprocessor.timeout=1800
```

It takes about one minute (55 s on a laptop) and needs no internet. It stops at the first failed check. A rerun writes
the same `validation_predictions.csv` byte for byte: computed columns are rounded to 6 decimals, the precision of USDC.

## Credits

- **Maksim**: the fair-value engine design (a Poisson move model on realised variance over four horizons, the
  96-slot time-of-day profile and the release variance), the release calendar, and the exposure-cap rule reused in
  section 13 (`maksim/` at commit `65daf8c`).
- **Subham**: the independent release list (`subham/pricing/external.py` at commit `d717f99`) that cross-checked the
  calendar; all 27 core releases agree.
- **Jay**: the 2026 news collection and its coverage check (`jay/revision_v3_2/` at commit `d717f99`). Headlines were
  too sparse for intraday features (CoinDesk headlines by month, February to July: 2, 15, 5, 14, 3, 13), which is why
  Phase 4 tested hourly GDELT news attention instead.

Teammates' work is read from saved outputs at fixed commits (see `data_external/teammates/inventory.json`); no branch
was checked out. Project-wide context: the [project README](../../../../README.md) and the [data inventory](../../../../data/README.md).
