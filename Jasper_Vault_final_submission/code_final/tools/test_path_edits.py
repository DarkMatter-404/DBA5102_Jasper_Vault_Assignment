"""Checks for path_edits.py: each edit must hit exactly one place, and CHANGES.md must list every edit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import path_edits as pe  # noqa: E402


def test_an_edit_replaces_its_text_and_keeps_crlf_line_endings(tmp_path):
    f = tmp_path / "config.py"
    f.write_bytes(b"ROOT = 1\r\nREPO = ROOT.parent\r\nX = 2\r\n")
    pe.apply_one(tmp_path, ("config.py", "REPO = ROOT.parent", "REPO = 3", "why"))
    assert f.read_bytes() == b"ROOT = 1\r\nREPO = 3\r\nX = 2\r\n"


def test_an_edit_whose_text_is_missing_stops(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match="found 0 times"):
        pe.apply_one(tmp_path, ("a.py", "REPO = ROOT.parent", "REPO = 3", "why"))


def test_an_edit_whose_text_appears_twice_stops(tmp_path):
    (tmp_path / "a.py").write_text("p = 1\np = 1\n")
    with pytest.raises(ValueError, match="found 2 times"):
        pe.apply_one(tmp_path, ("a.py", "p = 1", "p = 2", "why"))


def test_every_edit_is_unique_and_lands_in_a_copied_teammate_file():
    keys = [(f, old) for f, old, _, _ in pe.EDITS]
    assert len(keys) == len(set(keys))
    assert all(f.startswith(("experiments/", "main/fair_value_engine/")) for f, _, _, _ in pe.EDITS)


def test_changes_table_names_each_edited_file_with_before_and_after():
    table = pe.changes_table([("experiments/x/a.py", "REPO = ROOT.parent", "REPO = up()", "data root")])
    assert "| `experiments/x/a.py` | `REPO = ROOT.parent` | `REPO = up()` | data root |" in table
