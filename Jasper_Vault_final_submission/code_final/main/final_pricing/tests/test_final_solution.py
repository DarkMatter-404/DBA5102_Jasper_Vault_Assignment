"""Unit tests for solution.py: the open book, the loading, the adoption rule and the submission builder."""
import numpy as np
import pandas as pd
import pytest

import solution as s


def ts(x):
    return pd.Timestamp(f"2026-08-01 {x}")


def orders(rows):
    return pd.DataFrame(rows, columns=["createdAt", "expirationDate", "optionType", "quantity_BTC"])


# --- repo root -------------------------------------------------------------------------------------------------

def test_find_repo_root_walks_up_to_the_folder_with_maksim_src():
    root = s.find_repo_root()
    assert (root / "maksim" / "src").is_dir() and (root / "subham" / "final").is_dir()


def test_find_repo_root_falls_back_to_jv_repo_env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "maksim" / "src").mkdir(parents=True)
    monkeypatch.setenv("JV_REPO", str(repo))
    assert s.find_repo_root(tmp_path / "elsewhere") == repo


# --- reading orders --------------------------------------------------------------------------------------------

def test_read_orders_parses_both_date_formats_and_keeps_row_order(tmp_path):
    f = tmp_path / "v.csv"
    f.write_text("createdAt,expirationDate,optionType,quantity_BTC,closedAt\n"
                 "2026/7/31 17:11,2026/7/31 18:11,1,0.5,2026-07-31 18:11:29\n"
                 "2026-08-24 16:05:59,2026-08-24 16:35:59,0,0.2,2026-08-24 16:30:00\n")
    d = s.read_orders(f)
    assert list(d["row"]) == [0, 1]
    assert d.loc[0, "createdAt"] == pd.Timestamp("2026-07-31 17:11:00")
    assert d.loc[1, "expirationDate"] == pd.Timestamp("2026-08-24 16:35:59")
    assert "closedAt" not in d.columns  # an outcome: dropped on read


# --- open book -------------------------------------------------------------------------------------------------

BOOK = orders([
    (ts("10:00"), ts("11:00"), 0, 2.0),   # A: call, open 10:00-11:00
    (ts("10:10"), ts("10:40"), 1, 1.0),   # B: put, open 10:10-10:40
])


def test_book_state_counts_orders_created_before_and_expiring_after():
    new = orders([(ts("10:30"), ts("11:30"), 0, 0.1)])  # call while A and B are open
    b = s.book_state(BOOK, new)
    assert b.loc[0, "open_call_btc"] == 2.0 and b.loc[0, "open_put_btc"] == 1.0
    assert b.loc[0, "book_btc"] == 3.0
    assert b.loc[0, "s_add"] == pytest.approx(1 / 3)  # a call joins the call-heavy side


def test_book_state_drops_expired_orders_and_signs_s_add_for_puts():
    new = orders([(ts("10:45"), ts("11:15"), 1, 0.1)])  # put after B expired: only A (call) is open
    b = s.book_state(BOOK, new)
    assert b.loc[0, "open_put_btc"] == 0.0
    assert b.loc[0, "s_add"] == pytest.approx(-1.0)  # a put against an all-call book opposes the crowd


def test_book_state_is_empty_and_neutral_when_nothing_is_open():
    new = orders([(ts("11:30"), ts("12:00"), 1, 0.1)])
    b = s.book_state(BOOK, new)
    assert b.loc[0, "book_btc"] == 0.0 and b.loc[0, "s_add"] == 0.0


def test_book_state_excludes_the_order_itself_and_same_time_orders():
    b = s.book_state(BOOK, BOOK)  # the training case: new orders are also in the book
    assert b.loc[0, "book_btc"] == 0.0  # A sees nothing before itself
    assert b.loc[1, "open_call_btc"] == 2.0 and b.loc[1, "open_put_btc"] == 0.0


# --- loading ---------------------------------------------------------------------------------------------------

def test_loading_charges_only_orders_against_the_crowd_on_books_of_at_least_one_btc():
    load = s.orderflow_loading(s_add=np.array([1 / 3, -1.0, 0.0, -0.5]), book_btc=np.array([3.0, 2.0, 0.0, 0.5]))
    assert load == pytest.approx([1.0, 1.3, 1.0, 1.0])


def test_loading_never_decreases_a_price():
    rng = np.random.default_rng(0)
    load = s.orderflow_loading(rng.uniform(-1, 1, 1000), rng.uniform(0, 5, 1000))
    assert (load >= 1.0).all() and (load <= 1.0 + s.K_LOADING + 1e-12).all()


# --- flat raise and adoption rule -------------------------------------------------------------------------------

def test_flat_factor_matches_a_target_total():
    assert s.flat_factor(110.0, np.array([50.0, 50.0])) == pytest.approx(1.1)


def profits(jul_none=(10.0, 12.0), jul_e2=(8.0, 9.0), fj_none=(20.0, 23.0), fj_e2=(15.0, 16.0), jul_flat_e2=8.5):
    return {
        "Jul": {"none": {"M": jul_none[0], "M+L": jul_none[1]},
                "cons_e2": {"M": jul_e2[0], "M+L": jul_e2[1], "Flat-M": jul_flat_e2}},
        "Feb-Jun": {"none": {"M": fj_none[0], "M+L": fj_none[1]},
                    "cons_e2": {"M": fj_e2[0], "M+L": fj_e2[1]}},
    }


def test_adoption_passes_when_all_three_conditions_hold():
    d = s.adoption_decision(profits())
    assert d["c1_july_gain"] and d["c2_febjun_gain"] and d["c3_july_beats_flat"] and d["adopt"]


def test_adoption_fails_when_july_conservative_gain_is_negative():
    d = s.adoption_decision(profits(jul_e2=(8.0, 7.9)))
    assert not d["c1_july_gain"] and not d["adopt"]


def test_adoption_fails_when_a_flat_raise_of_the_same_size_does_better():
    d = s.adoption_decision(profits(jul_flat_e2=9.5))
    assert not d["c3_july_beats_flat"] and not d["adopt"]


# --- submission ------------------------------------------------------------------------------------------------

def frozen_and_valid():
    valid = pd.DataFrame({
        "row": [0, 1, 2],
        "createdAt": pd.to_datetime(["2026-08-01 10:00", "2026-08-01 10:05", "2026-08-01 10:09"]),
        "optionType": [0, 1, 1], "productType": [1800, 3600, 7200],
        "quantity_BTC": [0.5, 1.0, 2.0], "strikePrice": [60000.0, 60010.0, 60020.0],
        "apiBasePrice_per_BTC_USDC": [100.0, np.nan, 150.0],
    })
    frozen = valid[["createdAt", "quantity_BTC"]].assign(
        recommended_premium_USDC=[60.0, 300.0, 400.0], fair_value_per_BTC_USDC=[96.0, 240.0, 160.0])
    return valid, frozen


def test_build_submission_uses_the_loaded_premium_when_adopted():
    valid, frozen = frozen_and_valid()
    sub = s.build_submission(valid, frozen, np.array([1.0, 1.3, 1.1]), adopted=True)
    assert list(sub.columns) == s.SUBMISSION_COLUMNS
    assert sub["recommended_premium_USDC"].tolist() == pytest.approx([60.0, 390.0, 440.0])
    assert sub["premium_frozen_model_USDC"].tolist() == pytest.approx([60.0, 300.0, 400.0])
    assert sub["fair_value_USDC"].tolist() == pytest.approx([48.0, 240.0, 320.0])
    m = sub["recommended_multiplier_vs_base"]
    assert m[0] == pytest.approx(60.0 / 50.0) and np.isnan(m[1]) and m[2] == pytest.approx(440.0 / 300.0)


def test_build_submission_keeps_the_frozen_premium_when_not_adopted():
    valid, frozen = frozen_and_valid()
    sub = s.build_submission(valid, frozen, np.array([1.0, 1.3, 1.1]), adopted=False)
    assert sub["recommended_premium_USDC"].tolist() == pytest.approx([60.0, 300.0, 400.0])
    assert sub["orderflow_loading"].tolist() == pytest.approx([1.0, 1.3, 1.1])


def test_build_submission_rounds_money_to_usdc_precision():
    valid, frozen = frozen_and_valid()
    frozen["fair_value_per_BTC_USDC"] = [96.1234567, 240.0, 160.0]
    sub = s.build_submission(valid, frozen, np.array([1.0, 1.0000001234, 1.0]), adopted=True)
    assert sub.loc[1, "recommended_premium_USDC"] == round(300.0 * 1.0000001234, 6)  # 300.00003702 -> 300.000037
    assert sub.loc[0, "fair_value_USDC"] == round(96.1234567 * 0.5, 6)


def test_build_submission_refuses_rows_that_do_not_line_up():
    valid, frozen = frozen_and_valid()
    frozen.loc[1, "createdAt"] = pd.Timestamp("2026-08-01 11:00")
    with pytest.raises(ValueError):
        s.build_submission(valid, frozen, np.ones(3), adopted=True)


# --- exposure cap, moneyness, revealed-price check --------------------------------------------------------------

def test_exposure_cap_pauses_a_direction_until_earlier_protections_expire():
    o = pd.DataFrame({
        "createdAt": [ts("10:00"), ts("10:10"), ts("10:10"), ts("11:30")],
        "expirationDate": [ts("11:00"), ts("10:40"), ts("10:40"), ts("12:00")],
        "optionType": [0, 0, 1, 0],
        "notional_USDC": [60.0, 50.0, 80.0, 50.0],
    })
    assert s.exposure_cap_accepts(o, cap=100.0).tolist() == [True, False, True, True]


def test_moneyness_table_prices_out_of_the_money_strikes_lower():
    t = s.moneyness_table(abs_move=0.005, spot=100_000.0, distances=[0.0, 0.0025, 0.005, 0.01])
    put = t[t["side"] == "put"].sort_values("otm_distance")
    assert put["fair_value_per_btc"].iloc[0] == pytest.approx(250.0, rel=1e-3)  # at the money: spot x |move| / 2
    assert put["fair_value_per_btc"].is_monotonic_decreasing
    assert np.allclose(t["premium_per_btc"], t["fair_value_per_btc"] * (1 + s.MARGIN))


def test_revealed_price_ratio_uses_only_rows_with_a_markup():
    v = pd.DataFrame({"quantity_BTC": [1.0, 2.0, 1.0],
                      "apiBasePrice_per_BTC_USDC": [100.0, 50.0, 80.0],
                      "markup_per_BTC_USDC": [20.0, np.nan, 40.0]})
    r = s.revealed_price_ratio(v, premium=np.array([108.0, 999.0, 132.0]))
    assert r["rows"] == 2
    assert r["ratio"] == pytest.approx((108.0 + 132.0) / (120.0 + 120.0))
