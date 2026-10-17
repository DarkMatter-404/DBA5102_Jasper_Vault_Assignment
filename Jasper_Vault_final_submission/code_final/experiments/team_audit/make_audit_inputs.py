"""Rebuild the two inputs that the audit scripts read, in the way the auditor made them (added for code_final).

1. Aman's notebook runs on a copy of experiments/jv_reference_f1 in <work>/amanrun/aman/, with one extra last cell
   that saves its per-order panels to panels_dump.pkl (the step written at the top of holdout_all.py).
2. Chris's open book (order_flow_book steps 00 and 01) is written to <work>/data/book.pkl.

<work> is the AUDIT_WORK environment variable, or ./work next to this file. After this, run score_panels.py,
bootstrap_diffs.py, combos.py, book_proxy_check.py and holdout_all.py. Takes about a minute.
"""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
DUMP_CELL = "import pickle; pickle.dump({'panels': panels}, open('panels_dump.pkl', 'wb'))"


def work_dir() -> Path:
    env = os.environ.get("AUDIT_WORK")
    return Path(env) if env else HERE / "work"


def data_root() -> Path:
    """The nearest parent folder that holds data/with_base_premium."""
    return next(p for p in HERE.parents if (p / "data" / "with_base_premium").is_dir())


def with_dump_cell(nb):
    """A copy of the notebook with the dump cell at the end. The notebook passed in is not changed."""
    out = copy.deepcopy(nb)
    out.cells.append(nbformat.v4.new_code_cell(DUMP_CELL))
    return out


def run_aman_notebook(work: Path) -> Path:
    from nbclient import NotebookClient

    aman = work / "amanrun" / "aman"
    if aman.exists():
        shutil.rmtree(aman)
    shutil.copytree(EXPERIMENTS / "jv_reference_f1", aman,
                    ignore=shutil.ignore_patterns(".ipynb_checkpoints", "__pycache__", ".venv"))
    nb = with_dump_cell(nbformat.read(aman / "pp_pricing.ipynb", as_version=4))
    NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(aman)}}).execute()
    dump = aman / "panels_dump.pkl"
    if not dump.is_file():
        raise SystemExit("The notebook ran, but panels_dump.pkl was not written.")
    return dump


def build_book(work: Path) -> Path:
    data, flow, src = work / "data", EXPERIMENTS / "order_flow_book", data_root() / "data" / "with_base_premium"
    data.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(flow / "00_prepare_features.py"), str(src / "pp_transactions_training.csv"),
                    str(src / "btc_market_history.csv"), str(data / "orders.pkl")], check=True)
    subprocess.run([sys.executable, str(flow / "01_build_book.py"), str(data / "orders.pkl"), str(data / "book.pkl")],
                   check=True)
    return data / "book.pkl"


def main() -> None:
    work = work_dir()
    (work / "audit").mkdir(parents=True, exist_ok=True)  # the audit scripts write here
    print("panels:", run_aman_notebook(work))
    print("book:  ", build_book(work))


if __name__ == "__main__":
    sys.exit(main())
