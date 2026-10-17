# code_final: the team's code, by idea

DBA5102 Blockchain group assignment, Option 2: pricing Jasper Vault's Perpetual Protect (PP). Group 23.

- **`main/`** holds the final solution: the code that makes every submitted price. **Start with
  [`main/README.md`](main/README.md).**
- **`experiments/`** holds each idea that the team tested, one folder per idea.
- The deck and the video are next to this folder, in `Jasper_Vault_final_submission/`.

## Map

| Folder | Idea | Copied from | By | Status |
|---|---|---|---|---|
| [`main/`](main/) | Fair value × 1.25, never below JV's API base price; one submission file; order-flow loading tested; exposure cap; report | `subham/final/` + parts of `maksim/` | Team | **Submitted** |
| [`experiments/fair_value_model/`](experiments/fair_value_model/) | Forecast the BTC move from recent volatility, time of day and US releases; Black-Scholes fair value; 25% margin; full research and risk tests | `maksim/` | Maksim | Core of `main` |
| [`experiments/hybrid_base_multiplier/`](experiments/hybrid_base_multiplier/) | JV's base price × a multiplier learned from payouts (higher in US release windows), plus a margin | `subham/` (without `final/`) | Subham | Not adopted; its rebuilt base price is a cross-check in `main` |
| [`experiments/jv_reference_f1/`](experiments/jv_reference_f1/) | F1, θ = 0: an estimate of JV's current price × a fair-value shape kept within 0.8–1.2 | `aman/` | Aman | Not adopted |
| [`experiments/order_flow_book/`](experiments/order_flow_book/) | JV as a market maker: orders against the crowded side of the open book pay out more; a contrarian loading | `chris/` (steps 00–06) | Chris | Loading tested in `main`; kept as an optional column |
| [`experiments/team_audit/`](experiments/team_audit/) | Independent audit: every team model scored on the same orders | `chris/audit/`, `chris/holdout_all.py` | Chris | Evidence for `main` |
| [`experiments/duration_sentiment/`](experiments/duration_sentiment/) | A bounded multiplier from product length, market state, news NLP and X sentiment (versions 1 to 3.2) | `jay/` + `revision_v2/` | Jay | Not adopted |
| [`experiments/llm_event_research/`](experiments/llm_event_research/) | Event-to-Loss: market paths, an early-close model and LLM-classified events | `llm assisted trading/` | Jay | Not adopted |

Each experiment README starts with a short "code_final copy" block: what was copied, and the commands checked from
that folder. The rest of each README is the author's text. It names the original folders (`maksim/`, `jay/`, ...);
the table above maps them to the new ones.

## Data

The data is not copied. It stays in `data/` at the repository root. Every script finds it by walking up to the nearest
folder that holds `data/with_base_premium`. In the zip for Canvas, `data/` sits at the top, next to
`Jasper_Vault_final_submission/`, so the same paths work.

## Environments

Each folder installs its own requirements file. The "code_final copy" block in each README names it.

| Python | Folders | Requirements file |
|---|---|---|
| 3.14.3 | `main` | `main/requirements.txt` |
| 3.14.3 | `fair_value_model`, `hybrid_base_multiplier`, `order_flow_book` | `requirements.txt` in the folder |
| 3.14.3 or 3.12 | `jv_reference_f1`, `team_audit` (it runs Aman's notebook) | `experiments/jv_reference_f1/requirements.txt` |
| 3.12 | `duration_sentiment` | `revision_v3_2/requirements.txt` in the folder |
| 3.12 | `llm_event_research` | `requirements-tested.txt` in the folder |

On Windows, set `PYTHONUTF8=1` for Jay's two folders (his scripts read UTF-8 text with the system default encoding).

## Checks run for code_final

Run on 18 Oct 2026 from the unzipped package (code and data only, with no member folders next to it), on Windows 11.

| Folder | Check | Result |
|---|---|---|
| `main/final_pricing` | both notebooks, the HTML report, `pytest tests` | 43 of 43 pass. `final_submission.csv` is byte-identical to the submitted file (SHA-256 `810eae3a…`). All 498 numbers in the report are unchanged. |
| `main/fair_value_engine` | `pytest tests`; `run_validation.py` | 9 of 10 pass (see Known limits). The rebuilt prices equal the frozen file, except 6 of 4,155 premiums that differ by 0.000001 USDC. |
| `fair_value_model` | `pytest tests`; `run_validation.py` | The same as `main/fair_value_engine`. |
| `hybrid_base_multiplier` | `pytest tests` | 14 of 14 pass. |
| `jv_reference_f1` | the whole notebook (it stops at the first failed check) | Runs to the end; every built-in check passes. 4 of 4,155 premiums differ from the committed file by 0.000001 USDC (Python 3.14 and 3.12 give the same result). |
| `order_flow_book` | `run_all.sh` | The 6 console outputs are identical. 3 result tables differ only in the last digit. |
| `team_audit` | `make_audit_inputs.py`, then the 5 audit scripts | Reproduced for the first time: the 3 saved tables match within 0.00000002 USDC. |
| `duration_sentiment` | v1, v2 and v3.2 verify scripts | See [`experiments/duration_sentiment/README.md`](experiments/duration_sentiment/README.md). |
| `llm_event_research` | `unittest`; the full study (about 20 s) | 9 of 9 pass. Every saved result is reproduced within 1e-6. |

## How this folder was made

1. **Exact copies.** `tools/make_copies.py` put 495 files into code_final with the same git blob IDs as their sources at
   commit `461f015` (commit `9e3fcd1` holds only these copies).
2. **Path fixes.** 37 edits in 24 files, each listed in [`CHANGES.md`](CHANGES.md). Only lines that find files changed.
3. **main.** The final pricing code reads the engine and the evidence inside `main/` (tests first; `CHANGES.md`,
   section 3). The notebooks were re-run.
4. **Manifest.** [`MANIFEST.csv`](MANIFEST.csv) lists every file with its source, its SHA-256 and its status:
   `identical`, `path-edited`, `regenerated` or `new`. `python tools/verify_manifest.py` checks the files on disk.

## Known limits

- **Rounding across computers.** Rerun on Windows, Maksim's `run_validation.py` and Aman's notebook give the committed
  numbers, except a few values that differ in the 6th decimal (0.000001 USDC). The committed files are the submitted
  ones.
- **One of Maksim's tests fails in his original folder too.** `test_no_lookahead.py` for the variant
  `+ range and volume (candidate)` requires exact equality, and one price differs by 0.000000000009 USDC. The final model
  does not use that variant, and its own test passes.
- **LLM study inputs.** `data/raw/` was never committed. Three files are restored byte for byte. The candle file has
  the same content but different gzip bytes. See
  [`experiments/llm_event_research/data/raw/README.md`](experiments/llm_event_research/data/raw/README.md).
- **Third-party documents.** 10 links inside the Instrumetriq source documents
  (`experiments/duration_sentiment/revision_v3_2/data/instrumetriq/*_source.md`) point to files of that external
  project. They were broken in `jay/` too.
- **Not copied.** `keerthi/` holds only a README. Maksim's open PR #7 is a research note with no code, and it was not
  merged.
