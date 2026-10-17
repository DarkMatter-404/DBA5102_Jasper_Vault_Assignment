"""Checks for the tools that build code_final: where each source file lands, and how the manifest labels it."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_manifest as bm  # noqa: E402
import make_copies as mc  # noqa: E402
import verify_manifest as vm  # noqa: E402

D = mc.DEST + "/"
EXP = D + "experiments/"


@pytest.mark.parametrize("src, expected", [
    ("maksim/src/model.py", {EXP + "fair_value_model/src/model.py", D + "main/fair_value_engine/src/model.py"}),
    ("maksim/run_backtest.py", {EXP + "fair_value_model/run_backtest.py"}),
    ("maksim/run_extensions.py", {EXP + "fair_value_model/run_extensions.py",
                                  D + "main/fair_value_engine/run_extensions.py"}),
    ("maksim/outputs/FROZEN.json", {EXP + "fair_value_model/outputs/FROZEN.json",
                                    D + "main/fair_value_engine/outputs/FROZEN.json"}),
    ("maksim/results/walk_forward_orders_priced.parquet",
     {EXP + "fair_value_model/results/walk_forward_orders_priced.parquet",
      D + "main/evidence/fair_value_model/results/walk_forward_orders_priced.parquet"}),
    ("maksim/results/sealed_check/summary.json",
     {EXP + "fair_value_model/results/sealed_check/summary.json",
      D + "main/evidence/fair_value_model/results/sealed_check/summary.json"}),
    ("subham/final/solution.py", {D + "main/final_pricing/solution.py"}),
    ("subham/final/requirements.txt", {D + "main/final_pricing/requirements.txt", D + "main/requirements.txt"}),
    ("subham/pricing/data.py", {EXP + "hybrid_base_multiplier/pricing/data.py"}),
    ("subham/outputs/validation_premiums.csv",
     {EXP + "hybrid_base_multiplier/outputs/validation_premiums.csv",
      D + "main/evidence/hybrid_base_multiplier/outputs/validation_premiums.csv"}),
    ("aman/pp_pricing.ipynb", {EXP + "jv_reference_f1/pp_pricing.ipynb"}),
    ("chris/audit/combos.py", {EXP + "team_audit/combos.py"}),
    ("chris/audit/same_holdout_scores.csv", {EXP + "team_audit/same_holdout_scores.csv",
                                             D + "main/evidence/team_audit/same_holdout_scores.csv"}),
    ("chris/holdout_all.py", {EXP + "team_audit/holdout_all.py"}),
    ("chris/TEAM_SAME_HOLDOUT_CHECK.md", {EXP + "team_audit/TEAM_SAME_HOLDOUT_CHECK.md"}),
    ("chris/04_backtest_skew.py", {EXP + "order_flow_book/04_backtest_skew.py"}),
    ("chris/results/console_01_book.txt", {EXP + "order_flow_book/results/console_01_book.txt"}),
    ("chris/requirements.txt", {EXP + "order_flow_book/requirements.txt", EXP + "team_audit/requirements.txt"}),
    ("chris/.gitignore", {EXP + "order_flow_book/.gitignore", EXP + "team_audit/.gitignore"}),
    ("jay/pp_pricing.py", {EXP + "duration_sentiment/pp_pricing.py"}),
    ("jay/revision_v2/pricing.py", {EXP + "duration_sentiment/revision_v2/pricing.py"}),
    ("revision_v2/pricing.py", {EXP + "duration_sentiment/revision_v2/pricing.py"}),
    ("revision_v2/research/run_all.py", {EXP + "duration_sentiment/revision_v2/research/run_all.py"}),
    ("jay/docs/classnotes.md", {EXP + "duration_sentiment/docs/classnotes.md",
                                EXP + "llm_event_research/data/raw/classnotes.md"}),
    ("jay/revision_v3_2/data/assignment_inputs/btc_market_history.csv.gz",
     {EXP + "duration_sentiment/revision_v3_2/data/assignment_inputs/btc_market_history.csv.gz",
      EXP + "llm_event_research/data/raw/btc_market_history.csv.gz"}),
    ("llm assisted trading/src/etl/data.py", {EXP + "llm_event_research/src/etl/data.py"}),
    ("data/with_base_premium/pp_transactions_training.csv",
     {EXP + "llm_event_research/data/raw/pp_transactions_training.csv"}),
    ("data/validation/pp_transactions_validation.csv",
     {EXP + "llm_event_research/data/raw/pp_transactions_validation.csv"}),
    ("data/en/pp_transactions_training.csv", set()),
    ("data/validation/btc_market_history.csv", set()),
    ("keerthi/README.md", set()),
    ("materials/guides/project-guide.md", set()),
    ("README.md", set()),
    ("Jasper_Vault_final_submission/Pricing Perpetual Protect.pptx", set()),
])
def test_each_source_file_lands_where_the_plan_says(src, expected):
    assert set(mc.destinations(src)) == expected


def test_engine_gets_only_the_files_that_make_the_frozen_prices():
    engine = D + "main/fair_value_engine/"
    for src in ("maksim/run_backtest.py", "maksim/run_sealed_check.py", "maksim/make_figures.py", "maksim/README.md",
                "maksim/results/walk_forward_monthly.csv"):
        assert not any(d.startswith(engine) for d in mc.destinations(src)), src


def test_two_sources_with_the_same_blob_merge_into_one_copy():
    entries = [("100644", "aaa", "jay/revision_v2/pricing.py"), ("100644", "aaa", "revision_v2/pricing.py")]
    plan = mc.plan_copies(entries)
    assert len(plan) == 1
    dst, mode, blob, sources = plan[0]
    assert dst == EXP + "duration_sentiment/revision_v2/pricing.py" and blob == "aaa"
    assert sources == ["jay/revision_v2/pricing.py", "revision_v2/pricing.py"]


def test_two_sources_with_different_blobs_at_one_copy_path_stop_the_copy():
    entries = [("100644", "aaa", "jay/revision_v2/pricing.py"), ("100644", "bbb", "revision_v2/pricing.py")]
    with pytest.raises(ValueError, match="different content"):
        mc.plan_copies(entries)


def test_index_info_records_are_nul_terminated_and_keep_spaces_in_paths():
    rec = mc.index_info([(EXP + "llm_event_research/README.md", "100644", "abc", ["llm assisted trading/README.md"])])
    assert rec == f"100644 abc\t{EXP}llm_event_research/README.md\0".encode()


@pytest.mark.parametrize("dst, head_blob, src_blob, expected", [
    (EXP + "fair_value_model/src/model.py", "aaa", "aaa", "identical"),
    (EXP + "fair_value_model/src/config.py", "bbb", "aaa", "path-edited"),
    (D + "main/final_pricing/solution.py", "bbb", "aaa", "path-edited"),
    (D + "main/final_pricing/final_solution.ipynb", "bbb", "aaa", "regenerated"),
    (D + "main/final_pricing/final_report.html", "bbb", "aaa", "regenerated"),
    (D + "main/final_pricing/outputs/summary.json", "bbb", "aaa", "regenerated"),
    (D + "main/README.md", "ccc", None, "new"),
])
def test_manifest_status(dst, head_blob, src_blob, expected):
    assert bm.status(dst, head_blob, src_blob) == expected


def test_every_path_edited_file_must_be_named_in_changes_md():
    rows = [{"copy_path": EXP + "fair_value_model/src/config.py", "status": "path-edited"},
            {"copy_path": EXP + "hybrid_base_multiplier/pricing/data.py", "status": "path-edited"},
            {"copy_path": EXP + "fair_value_model/src/model.py", "status": "identical"}]
    changes = "| `experiments/fair_value_model/src/config.py` | REPO line |"
    assert bm.undocumented_edits(rows, changes) == [EXP + "hybrid_base_multiplier/pricing/data.py"]


def test_verify_accepts_the_same_bytes_and_crlf_checkouts_but_not_other_content(tmp_path):
    lf = b"a,b\n1,2\n"
    expected = hashlib.sha256(lf).hexdigest()
    same, crlf, other = tmp_path / "same.csv", tmp_path / "crlf.csv", tmp_path / "other.csv"
    same.write_bytes(lf)
    crlf.write_bytes(lf.replace(b"\n", b"\r\n"))
    other.write_bytes(b"a,b\n1,3\n")
    assert vm.file_matches(same, expected) == "ok"
    assert vm.file_matches(crlf, expected) == "ok (CRLF line endings)"
    assert vm.file_matches(other, expected) == "DIFFERENT"
