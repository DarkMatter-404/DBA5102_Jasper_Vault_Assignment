# Changes in code_final

Every file in code_final started as an exact copy of a team file at commit `461f015` (the same git blob ID, made by
`tools/make_copies.py`). `MANIFEST.csv` lists every file with its source. This file lists every line that changed
after the copy.

**Why anything changed.** In the repository, each member folder (`maksim/`, `jay/`, ...) sits next to `data/`. In
code_final the copies sit three or four folders deeper. So a line that meant "the folder next to mine holds `data/`"
now looks for the nearest parent folder that holds `data/with_base_premium`. When there is no such folder, it falls
back to the old expression. No model, parameter, price or output changed.

## 1. Path fixes in the teammates' copies (37 edits in 24 files)

Applied once by `tools/path_edits.py`. The tool refuses an edit unless its old text appears exactly once in the file.
"↵" marks a line break inside one edit.

| File (inside code_final) | Before | After | Why |
|---|---|---|---|
| `main/fair_value_engine/src/config.py` | `REPO = ROOT.parent` | `REPO = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/fair_value_model/src/config.py` | `REPO = ROOT.parent` | `REPO = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/hybrid_base_multiplier/pricing/data.py` | `TRAIN_FILE = _first_existing(` ↵ `    ROOT.parent / "data" / "with_base_premium" / "pp_transactions_training.csv",` | `DATA_ROOT = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)  # code_final path fix` ↵ `TRAIN_FILE = _first_existing(` ↵ `    DATA_ROOT / "data" / "with_base_premium" / "pp_transactions_training.csv",` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/hybrid_base_multiplier/pricing/data.py` | `VALID_DIR = _first_existing(ROOT.parent / "data" / "validation", ROOT / "JV validation dataset")` | `VALID_DIR = _first_existing(DATA_ROOT / "data" / "validation", ROOT / "JV validation dataset")` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/jv_reference_f1/pp_pricing.ipynb` | `"REPO = AMAN.parent\n"` | `"REPO = next((p for p in AMAN.resolve().parents if (p / 'data' / 'with_base_premium').is_dir()), AMAN.parent)  # code_final path fix\n"` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) (notebook cell 2) |
| `experiments/jv_reference_f1/checks/reproduce_checks.py` | `REPO = Path(__file__).resolve().parents[2]` | `_UP = Path(__file__).resolve().parents  # code_final path fix: nearest folder with data/` ↵ `REPO = next((p for p in _UP if (p / "data" / "with_base_premium").is_dir()), _UP[2])` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/jv_reference_f1/checks/jv03_evidence.py` | `REPO = Path(__file__).resolve().parents[2]` | `_UP = Path(__file__).resolve().parents  # code_final path fix: nearest folder with data/` ↵ `REPO = next((p for p in _UP if (p / "data" / "with_base_premium").is_dir()), _UP[2])` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/jv_reference_f1/checks/jump_attribution.py` | `REPO = Path(__file__).resolve().parents[2]` | `_UP = Path(__file__).resolve().parents  # code_final path fix: nearest folder with data/` ↵ `REPO = next((p for p in _UP if (p / "data" / "with_base_premium").is_dir()), _UP[2])` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/jv_reference_f1/checks/jump_attribution.py` | `REPO / "aman" / "data_external" / "macro_events_2026_checked.csv"` | `Path(__file__).resolve().parents[1] / "data_external" / "macro_events_2026_checked.csv"` | Aman's folder is now experiments/jv_reference_f1 |
| `experiments/order_flow_book/run_all.sh` | `DATA=../data/with_base_premium` | `DATA=../../../../data/with_base_premium  # code_final: the repository root is four levels up` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/team_audit/score_panels.py` | `SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'` | `import os; from pathlib import Path  # code_final path fix: work folder set at run time` ↵ `SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work')) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/bootstrap_diffs.py` | `SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'` | `import os; from pathlib import Path  # code_final path fix: work folder set at run time` ↵ `SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work')) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/combos.py` | `SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'` | `import os; from pathlib import Path  # code_final path fix: work folder set at run time` ↵ `SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work')) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/combos.py` | `R = '/home/claude/dba5102_jasper_vault_assignment/'` | `R = str(next(p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir())) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/book_proxy_check.py` | `SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'` | `import os; from pathlib import Path  # code_final path fix: work folder set at run time` ↵ `SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work')) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/book_proxy_check.py` | `R = '/home/claude/dba5102_jasper_vault_assignment/'` | `R = str(next(p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir())) + '/'` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/team_audit/holdout_all.py` | `SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad'` | `import os; from pathlib import Path  # code_final path fix: work folder set at run time` ↵ `SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work'))` | The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root |
| `experiments/duration_sentiment/verify_pricing.py` | `ROOT=Path(__file__).resolve().parent` | `ROOT=Path(__file__).resolve().parent` ↵ `DATA_ROOT=next((p for p in ROOT.parents if (p/'data'/'with_base_premium').is_dir()),ROOT.parent)  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/verify_pricing.py` | `default=ROOT.parent/'data/en/pp_transactions_training.csv'` | `default=DATA_ROOT/'data/en/pp_transactions_training.csv'` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/verify_pricing.py` | `default=ROOT.parent/'data/en/btc_market_history.csv'` | `default=DATA_ROOT/'data/en/btc_market_history.csv'` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/revision_v2/verify.py` | `REPO=ROOT.parents[1]` | `REPO=next((p for p in ROOT.parents if (p/'data'/'with_base_premium').is_dir()),ROOT.parents[1])  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/revision_v2/verify.py` | `OUT=REPO/'jay/output/v2'` | `OUT=ROOT.parent/'output/v2'  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/run_all.py` | `REPO=HERE.parents[2]` | `REPO=next((p for p in HERE.parents if (p/'data'/'with_base_premium').is_dir()),HERE.parents[2])  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/revision_v2/research/run_all.py` | `sys.path.insert(0,str(REPO/'jay'))` | `sys.path.insert(0,str(HERE.parents[1]))  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/run_all.py` | `OUT=REPO/'jay/output/v2/research'` | `OUT=HERE.parents[1]/'output/v2/research'` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/base_study.py` | `sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'jay'))` | `sys.path.insert(0,str(Path(__file__).resolve().parents[2]))  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/base_study.py` | `OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/base_study'` | `OUT=Path(__file__).resolve().parents[2]/'output/v2/research/base_study'` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/tree_study.py` | `sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'jay'))` | `sys.path.insert(0,str(Path(__file__).resolve().parents[2]))  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/tree_study.py` | `OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/tree_study'` | `OUT=Path(__file__).resolve().parents[2]/'output/v2/research/tree_study'` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/decision_study.py` | `OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/decision_study'` | `OUT=Path(__file__).resolve().parents[2]/'output/v2/research/decision_study'` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/study.py` | `ROOT = Path(__file__).resolve().parents[4]` | `ROOT = next((p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir()), Path(__file__).resolve().parents[4])  # code_final path fix` | Repository root = nearest parent with data/ (the copy is deeper than the original folder) |
| `experiments/duration_sentiment/revision_v2/research/cost_family/study.py` | `sys.path.insert(0, str(ROOT / 'jay'))` | `sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/study.py` | `OUT = ROOT / 'jay/output/v2/research/cost_family'` | `OUT = Path(__file__).resolve().parents[3] / 'output/v2/research/cost_family'` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/blend_tradeoff.py` | `OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'` | `OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/budget_neutral_study.py` | `OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'` | `OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/commercial.py` | `OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'` | `OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |
| `experiments/duration_sentiment/revision_v2/research/cost_family/diagnostics.py` | `OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'` | `OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder` | Jay's folder is now experiments/duration_sentiment, two or three levels up |

## 2. Not changed on purpose

| File | Why it stays as it was |
|---|---|
| `experiments/duration_sentiment/revision_v3_2/package_update.py` | It zips the original `jay/` folder for Jay's own upload. No result depends on it. |
| `experiments/jv_reference_f1/fetch_external.py` | It reads teammates' files from git history at fixed commits (`git show <commit>:maksim/...`). That still works anywhere inside the repository. It needs internet and git. |
| `experiments/fair_value_model/run_sealed_check.py`, `run_dynamic_hedge.py` | One-time checks of the validation period, already run. They compare files with git `HEAD`, and they are not re-run. |
| Paths in the text of copied READMEs, docstrings and notebook text | They name the original folders. The table in `README.md` maps each old folder to its new place. |

## 3. main/final_pricing (Subham's own code; tests written first)

| File (inside code_final) | Change |
|---|---|
| `main/final_pricing/solution.py` | `find_repo_root()` looked for `maksim/src`. It is now `find_data_root()`, which looks for `data/with_base_premium` (the `JV_REPO` variable still works). New constants `MAIN`, `ENGINE` (= `main/fair_value_engine`) and `EVIDENCE` (= `main/evidence`). `_use_maksim_code()` is now `_use_engine_code()`. `price_blind_file` reads the frozen prices from `fair_value_engine/outputs/`. No pricing logic changed. |
| `main/final_pricing/tests/conftest.py` | The import path is `fair_value_engine/` instead of `maksim/`. |
| `main/final_pricing/tests/test_final_solution.py` | The 2 tests for the old root finder are replaced by 4 location tests (the engine code must be imported from `main`, never from a member folder). 11 new tests: `evidence/` holds 10 files, and each one equals its copy in `experiments/`. |
| `main/final_pricing/tests/test_final_submission.py` | New paths. New test: `final_submission.csv` is byte-identical to the submitted file (SHA-256 `810eae3a…`). |
| `main/final_pricing/final_solution.ipynb`, `final_report.ipynb` | Input paths now point to `fair_value_engine/`, `evidence/` and the data root. 3 text mentions of old folders now use the new names. Both notebooks were re-run. |
| `main/final_pricing/final_report.html` | Rebuilt. All 3,166 words and all 498 numbers are the same as in the report the deck used. The only text change is `chris/audit/` → `experiments/team_audit/`. |
| `main/final_pricing/outputs/` | From the re-run. `final_submission.csv` is byte-identical (SHA-256 `810eae3a…`). In `summary.json`, only `repo_commit_at_run` changed. `training_scores.csv` and `training_intervals.csv` differ only by float rounding (below 1e-9 relative). |

## 4. Documentation

| File (inside code_final) | Change |
|---|---|
| `experiments/fair_value_model/README.md` | A "code_final copy" block under the title: what was copied, and the commands checked from this folder. |
| `experiments/hybrid_base_multiplier/README.md` | The pointer to `final/` is replaced by the "code_final copy" block; the link to `data/` now goes 4 levels up. |
| `experiments/jv_reference_f1/README.md` | The "code_final copy" block; the links to the project README and to `data/README.md` now go 4 levels up. |
| `experiments/order_flow_book/README.md` | The "code_final copy" block. |
| `experiments/duration_sentiment/README.md` | The "code_final copy" block. |
| `experiments/duration_sentiment/docs/findings_and_submission.md` | 6 links to `materials/` and `data/` now go 5 levels up. |
| `experiments/llm_event_research/README.md` | The "code_final copy" block. |
| `main/final_pricing/README.md` | Paths and run steps for `main/`; 42 checks; a note on the pre-registered rule, whose text is unchanged. |

New files (status `new` in `MANIFEST.csv`): every other README in code_final, `experiments/team_audit/README.md`,
`experiments/team_audit/make_audit_inputs.py` and its test, `experiments/llm_event_research/data/raw/README.md`,
this file, `.gitattributes`, `MANIFEST.csv` and `tools/`.
