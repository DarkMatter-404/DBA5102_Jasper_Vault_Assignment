"""Checks for make_audit_inputs.py (fast parts only; the full run is the reproduction itself)."""
import sys
from pathlib import Path

import nbformat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_audit_inputs as mai  # noqa: E402


def test_work_folder_is_audit_work_or_local_work(monkeypatch, tmp_path):
    monkeypatch.delenv("AUDIT_WORK", raising=False)
    assert mai.work_dir() == Path(mai.__file__).resolve().parent / "work"
    monkeypatch.setenv("AUDIT_WORK", str(tmp_path))
    assert mai.work_dir() == tmp_path


def test_the_dump_cell_is_appended_and_the_original_notebook_is_unchanged():
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("panels = {}")])
    out = mai.with_dump_cell(nb)
    assert len(nb.cells) == 1
    assert len(out.cells) == 2 and out.cells[-1].source == mai.DUMP_CELL
    assert "panels_dump.pkl" in mai.DUMP_CELL and "'panels': panels" in mai.DUMP_CELL


def test_the_data_root_is_the_folder_that_holds_data():
    assert (mai.data_root() / "data" / "with_base_premium" / "pp_transactions_training.csv").is_file()
