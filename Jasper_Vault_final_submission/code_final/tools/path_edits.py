"""The path fixes in the teammates' copies, applied once, and the table in CHANGES.md.

Only lines that find files change. In the repository a member folder (maksim/, jay/, ...) sat next to data/.
In code_final the copies sit three or four levels deeper, so "the parent of my folder" no longer holds data/.
Each fix looks for the nearest parent folder that holds data/with_base_premium, and keeps the old expression as the
fallback. No logic, parameter or output changes.

Each edit must match exactly one place in its file, or nothing is written.
"""
from __future__ import annotations

import sys
from pathlib import Path

CODE_FINAL = Path(__file__).resolve().parents[1]
FIX = "  # code_final path fix"
JAY = "  # code_final: Jay's folder"

_SP_OLD = "SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad"
_SP_NEW = ("import os; from pathlib import Path  # code_final path fix: work folder set at run time\n"
           "SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work'))")
_R_OLD = "R = '/home/claude/dba5102_jasper_vault_assignment/'"
_R_NEW = "R = str(next(p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir())) + '/'"
_CHECKS_OLD = "REPO = Path(__file__).resolve().parents[2]"
_CHECKS_NEW = ('_UP = Path(__file__).resolve().parents  # code_final path fix: nearest folder with data/\n'
               'REPO = next((p for p in _UP if (p / "data" / "with_base_premium").is_dir()), _UP[2])')
_MAKSIM_OLD = "REPO = ROOT.parent"
_MAKSIM_NEW = 'REPO = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)' + FIX
_V2 = "experiments/duration_sentiment/revision_v2/"
_CF = _V2 + "research/cost_family/"
_CF_OUT_OLD = "OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'"
_CF_OUT_NEW = "OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'" + JAY
_SYS_OLD = "sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'jay'))"
_SYS_NEW = "sys.path.insert(0,str(Path(__file__).resolve().parents[2]))" + JAY

WHY_ROOT = "Repository root = nearest parent with data/ (the copy is deeper than the original folder)"
WHY_JAY = "Jay's folder is now experiments/duration_sentiment, two or three levels up"
WHY_AUDIT = "The auditor's own computer paths; now a work folder (AUDIT_WORK or ./work) and the repository root"

# (file inside code_final, old text, new text, reason)
EDITS = [
    ("main/fair_value_engine/src/config.py", _MAKSIM_OLD, _MAKSIM_NEW, WHY_ROOT),
    ("experiments/fair_value_model/src/config.py", _MAKSIM_OLD, _MAKSIM_NEW, WHY_ROOT),
    ("experiments/hybrid_base_multiplier/pricing/data.py",
     'TRAIN_FILE = _first_existing(\n    ROOT.parent / "data" / "with_base_premium" / "pp_transactions_training.csv",',
     'DATA_ROOT = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)' + FIX
     + '\nTRAIN_FILE = _first_existing(\n    DATA_ROOT / "data" / "with_base_premium" / "pp_transactions_training.csv",',
     WHY_ROOT),
    ("experiments/hybrid_base_multiplier/pricing/data.py",
     'VALID_DIR = _first_existing(ROOT.parent / "data" / "validation", ROOT / "JV validation dataset")',
     'VALID_DIR = _first_existing(DATA_ROOT / "data" / "validation", ROOT / "JV validation dataset")', WHY_ROOT),
    ("experiments/jv_reference_f1/pp_pricing.ipynb", '"REPO = AMAN.parent\\n"',
     "\"REPO = next((p for p in AMAN.resolve().parents if (p / 'data' / 'with_base_premium').is_dir()), AMAN.parent)"
     + FIX + '\\n"', WHY_ROOT + " (notebook cell 2)"),
    ("experiments/jv_reference_f1/checks/reproduce_checks.py", _CHECKS_OLD, _CHECKS_NEW, WHY_ROOT),
    ("experiments/jv_reference_f1/checks/jv03_evidence.py", _CHECKS_OLD, _CHECKS_NEW, WHY_ROOT),
    ("experiments/jv_reference_f1/checks/jump_attribution.py", _CHECKS_OLD, _CHECKS_NEW, WHY_ROOT),
    ("experiments/jv_reference_f1/checks/jump_attribution.py",
     'REPO / "aman" / "data_external" / "macro_events_2026_checked.csv"',
     'Path(__file__).resolve().parents[1] / "data_external" / "macro_events_2026_checked.csv"',
     "Aman's folder is now experiments/jv_reference_f1"),
    ("experiments/order_flow_book/run_all.sh", "DATA=../data/with_base_premium",
     "DATA=../../../../data/with_base_premium  # code_final: the repository root is four levels up", WHY_ROOT),
    ("experiments/team_audit/score_panels.py", _SP_OLD + "/'", _SP_NEW + " + '/'", WHY_AUDIT),
    ("experiments/team_audit/bootstrap_diffs.py", _SP_OLD + "/'", _SP_NEW + " + '/'", WHY_AUDIT),
    ("experiments/team_audit/combos.py", _SP_OLD + "/'", _SP_NEW + " + '/'", WHY_AUDIT),
    ("experiments/team_audit/combos.py", _R_OLD, _R_NEW, WHY_AUDIT),
    ("experiments/team_audit/book_proxy_check.py", _SP_OLD + "/'", _SP_NEW + " + '/'", WHY_AUDIT),
    ("experiments/team_audit/book_proxy_check.py", _R_OLD, _R_NEW, WHY_AUDIT),
    ("experiments/team_audit/holdout_all.py", _SP_OLD + "'", _SP_NEW, WHY_AUDIT),
    ("experiments/duration_sentiment/verify_pricing.py", "ROOT=Path(__file__).resolve().parent",
     "ROOT=Path(__file__).resolve().parent\n"
     "DATA_ROOT=next((p for p in ROOT.parents if (p/'data'/'with_base_premium').is_dir()),ROOT.parent)" + FIX,
     WHY_ROOT),
    ("experiments/duration_sentiment/verify_pricing.py", "default=ROOT.parent/'data/en/pp_transactions_training.csv'",
     "default=DATA_ROOT/'data/en/pp_transactions_training.csv'", WHY_ROOT),
    ("experiments/duration_sentiment/verify_pricing.py", "default=ROOT.parent/'data/en/btc_market_history.csv'",
     "default=DATA_ROOT/'data/en/btc_market_history.csv'", WHY_ROOT),
    (_V2 + "verify.py", "REPO=ROOT.parents[1]",
     "REPO=next((p for p in ROOT.parents if (p/'data'/'with_base_premium').is_dir()),ROOT.parents[1])" + FIX, WHY_ROOT),
    (_V2 + "verify.py", "OUT=REPO/'jay/output/v2'", "OUT=ROOT.parent/'output/v2'" + JAY, WHY_JAY),
    (_V2 + "research/run_all.py", "REPO=HERE.parents[2]",
     "REPO=next((p for p in HERE.parents if (p/'data'/'with_base_premium').is_dir()),HERE.parents[2])" + FIX, WHY_ROOT),
    (_V2 + "research/run_all.py", "sys.path.insert(0,str(REPO/'jay'))", "sys.path.insert(0,str(HERE.parents[1]))" + JAY,
     WHY_JAY),
    (_V2 + "research/run_all.py", "OUT=REPO/'jay/output/v2/research'", "OUT=HERE.parents[1]/'output/v2/research'",
     WHY_JAY),
    (_V2 + "research/base_study.py", _SYS_OLD, _SYS_NEW, WHY_JAY),
    (_V2 + "research/base_study.py", "OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/base_study'",
     "OUT=Path(__file__).resolve().parents[2]/'output/v2/research/base_study'", WHY_JAY),
    (_V2 + "research/tree_study.py", _SYS_OLD, _SYS_NEW, WHY_JAY),
    (_V2 + "research/tree_study.py", "OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/tree_study'",
     "OUT=Path(__file__).resolve().parents[2]/'output/v2/research/tree_study'", WHY_JAY),
    (_V2 + "research/decision_study.py",
     "OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/decision_study'",
     "OUT=Path(__file__).resolve().parents[2]/'output/v2/research/decision_study'", WHY_JAY),
    (_CF + "study.py", "ROOT = Path(__file__).resolve().parents[4]",
     "ROOT = next((p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir()), "
     "Path(__file__).resolve().parents[4])" + FIX, WHY_ROOT),
    (_CF + "study.py", "sys.path.insert(0, str(ROOT / 'jay'))",
     "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))" + JAY, WHY_JAY),
    (_CF + "study.py", "OUT = ROOT / 'jay/output/v2/research/cost_family'",
     "OUT = Path(__file__).resolve().parents[3] / 'output/v2/research/cost_family'", WHY_JAY),
    (_CF + "blend_tradeoff.py", _CF_OUT_OLD, _CF_OUT_NEW, WHY_JAY),
    (_CF + "budget_neutral_study.py", _CF_OUT_OLD, _CF_OUT_NEW, WHY_JAY),
    (_CF + "commercial.py", _CF_OUT_OLD, _CF_OUT_NEW, WHY_JAY),
    (_CF + "diagnostics.py", _CF_OUT_OLD, _CF_OUT_NEW, WHY_JAY),
]


def apply_one(base: Path, edit) -> None:
    """Replace the old text with the new text. The old text must appear exactly once. CRLF files stay CRLF."""
    rel, old, new, _ = edit
    path = Path(base) / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    n = text.count(old)
    if n != 1:
        raise ValueError(f"{rel}: text found {n} times: {old!r}")
    text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def _cell(s: str) -> str:
    return "`" + s.replace("\n", "` ↵ `") + "`"


def changes_table(edits) -> str:
    rows = ["| File (inside code_final) | Before | After | Why |", "|---|---|---|---|"]
    rows += [f"| `{rel}` | {_cell(old)} | {_cell(new)} | {why} |" for rel, old, new, why in edits]
    return "\n".join(rows)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--table"]:  # print the CHANGES.md table only
        print(changes_table(EDITS))
        return
    for edit in EDITS:  # check every edit first, so that nothing is written when one of them fails
        rel, old, _, _ = edit
        text = (CODE_FINAL / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            raise SystemExit(f"{rel}: text found {text.count(old)} times: {old!r}")
    for edit in EDITS:
        apply_one(CODE_FINAL, edit)
    print(f"{len(EDITS)} edits in {len({e[0] for e in EDITS})} files. Table: python path_edits.py --table")


if __name__ == "__main__":
    sys.exit(main())
