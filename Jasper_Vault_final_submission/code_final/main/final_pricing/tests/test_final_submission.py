"""Checks on the final submission file and the blind-file pipeline (run final_solution.ipynb first)."""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

import solution as s

DATA = s.find_data_root()
OUT = s.MAIN / "final_pricing" / "outputs"
VALID_CSV = DATA / "data" / "validation" / "pp_transactions_validation.csv"
FROZEN_CSV = s.ENGINE / "outputs" / "validation_recommendations.csv"
SUBMITTED_SHA256 = "810eae3a1c007c9443616afc97e7f11c7c8fcf60d3e79807e571a4c717110dcf"  # the file the team submitted


def outputs():
    sub_path, summary_path = OUT / "final_submission.csv", OUT / "summary.json"
    assert sub_path.exists() and summary_path.exists(), "run main/final_pricing/final_solution.ipynb first"
    return pd.read_csv(sub_path), json.loads(summary_path.read_text()), sub_path


def test_submission_file_is_byte_identical_to_the_submitted_file():
    _, summary, sub_path = outputs()
    assert hashlib.sha256(sub_path.read_bytes()).hexdigest() == SUBMITTED_SHA256
    assert summary["submission_sha256"] == SUBMITTED_SHA256


def test_one_row_per_validation_order_in_the_original_order():
    sub, _, _ = outputs()
    raw = pd.read_csv(VALID_CSV)
    assert len(sub) == len(raw) == 4155
    assert list(sub.columns) == s.SUBMISSION_COLUMNS
    assert sub["row"].tolist() == list(range(4155))
    assert (pd.to_datetime(sub["createdAt"]) == pd.to_datetime(raw["createdAt"], format="mixed")).all()


def test_every_order_has_a_positive_premium_and_no_outcome_column():
    sub, _, _ = outputs()
    p = sub["recommended_premium_USDC"]
    assert p.notna().all() and (p > 0).all()
    assert not set(s.OUTCOME_COLUMNS) & set(sub.columns)


def test_frozen_column_is_maksims_file_unchanged():
    sub, summary, _ = outputs()
    frozen = pd.read_csv(FROZEN_CSV)
    assert np.array_equal(sub["premium_frozen_model_USDC"].to_numpy(), frozen["recommended_premium_USDC"].to_numpy())
    assert summary["frozen_sha256_matches"] is True


def test_main_column_follows_the_adoption_decision():
    sub, summary, _ = outputs()
    assert (sub["orderflow_loading"] >= 1.0).all()
    expected = sub["premium_frozen_model_USDC"] * (sub["orderflow_loading"] if summary["adopted"] else 1.0)
    assert np.allclose(sub["recommended_premium_USDC"], expected, rtol=0, atol=1e-6)  # rounded to USDC's 6 decimals
    assert summary["adopted"] == summary["decision"]["adopt"]


def test_multiplier_is_blank_exactly_where_the_base_price_is_blank():
    sub, _, _ = outputs()
    no_base = sub["apiBasePrice_per_BTC_USDC"].isna()
    assert sub.loc[no_base, "recommended_multiplier_vs_base"].isna().all()
    assert sub.loc[~no_base, "recommended_multiplier_vs_base"].notna().all()


def test_summary_records_the_file_hash_and_every_key():
    _, summary, sub_path = outputs()
    assert set(s.SUMMARY_KEYS) <= set(summary)
    assert summary["submission_sha256"] == hashlib.sha256(sub_path.read_bytes()).hexdigest()


def test_loading_reproduces_the_audit_on_the_blind_file():
    # experiments/team_audit/AUDIT_MEMO.md: the expiry-proxy loading loads 25-26% of blind orders by +7.7% on average and
    # raises the blind premium total by 2.7-2.8%. Bands allow for small differences in the book's start.
    _, summary, _ = outputs()
    assert 0.22 <= summary["loaded_share"] <= 0.30
    assert 0.06 <= summary["mean_load_on_loaded"] - 1 <= 0.095
    change = summary["premium_total_with_loading"] / summary["premium_total_frozen"] - 1
    assert 0.022 <= change <= 0.033


def test_blind_pricing_ignores_closedAt(tmp_path):
    raw = pd.read_csv(VALID_CSV, dtype=str, keep_default_na=False)
    raw["closedAt"] = "2030-01-01 00:00:00"  # any value: the pipeline must not read it
    changed = tmp_path / "valid_changed_closedAt.csv"
    raw.to_csv(changed, index=False)
    a, _ = s.price_blind_file(DATA, adopted=True)
    b, _ = s.price_blind_file(DATA, adopted=True, valid_path=changed)
    pd.testing.assert_frame_equal(a, b)
