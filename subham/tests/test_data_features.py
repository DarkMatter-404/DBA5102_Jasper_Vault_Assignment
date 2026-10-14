import numpy as np
import pandas as pd
import pytest

from pricing.data import VALID_FILE, info_minute, load_btc, load_orders, parse_time
from pricing.features import market_features, order_features


def test_parse_both_date_formats():
    t, minute_only = parse_time(pd.Series(["2026-02-04 09:22:02", "2026/7/31 17:11"]))
    assert t.tolist() == [pd.Timestamp("2026-02-04 09:22:02"), pd.Timestamp("2026-07-31 17:11:00")]
    assert minute_only.tolist() == [False, True]


def test_info_minute_is_last_complete_minute():
    t, _ = parse_time(pd.Series(["2026-02-04 09:22:02", "2026/7/31 17:11", "2026-02-04 09:22:00"]))
    assert info_minute(t).tolist() == [
        pd.Timestamp("2026-02-04 09:21"), pd.Timestamp("2026-07-31 17:10"), pd.Timestamp("2026-02-04 09:21")]


@pytest.fixture(scope="module")
def btc_slice():
    return load_btc().loc["2026-03-01":"2026-03-12"]


def _orders(times, is_put):
    created, minute_only = parse_time(pd.Series(times))
    return pd.DataFrame({"created": created, "created_minute_only": minute_only, "duration_s": 1800,
                         "is_put": is_put, "qty": 0.01, "strike": 90000.0, "strike_calc": False})


def test_features_do_not_use_future_prices(btc_slice):
    times = ["2026-03-10 09:22:02", "2026/3/11 17:11", "2026-03-12 00:00:59"]
    orders = _orders(times, [True, False, True])
    base = order_features(orders, market_features(btc_slice))
    rng = np.random.default_rng(0)
    for i in range(len(orders)):
        cut = info_minute(orders["created"]).iloc[i]
        changed = btc_slice.copy()
        after = changed.index > cut
        for col in ["open", "high", "low", "close"]:
            changed.loc[after, col] *= rng.uniform(0.9, 1.1, after.sum())
        changed.loc[after, ["volume", "trades", "taker_buy"]] *= 3
        again = order_features(orders, market_features(changed))
        pd.testing.assert_series_equal(base.iloc[i], again.iloc[i], check_names=False)


def test_features_change_when_past_prices_change(btc_slice):
    # Guard against a test that passes because nothing is computed.
    orders = _orders(["2026-03-10 09:22:02"], [True])
    base = order_features(orders, market_features(btc_slice))
    changed = btc_slice.copy()
    before = changed.index <= info_minute(orders["created"]).iloc[0]
    changed.loc[before, "close"] *= np.random.default_rng(1).uniform(0.99, 1.01, before.sum())
    again = order_features(orders, market_features(changed))
    assert not np.isclose(base["rv1440"].iloc[0], again["rv1440"].iloc[0])


def test_moneyness_sign():
    btc = pd.DataFrame({"spot": [100.0]}, index=[pd.Timestamp("2026-03-10 09:21")])
    orders = _orders(["2026-03-10 09:22:02", "2026-03-10 09:22:02"], [True, False])
    orders["strike"] = [110.0, 110.0]
    X = order_features(orders, btc)
    assert X["mny"].iloc[0] > 0  # Put with strike above the price: in the money
    assert X["mny"].iloc[1] < 0  # Call with strike above the price: out of the money


def test_order_files_load():
    tr = load_orders("train")
    assert len(tr) == 7204 and tr["created"].notna().all()


@pytest.mark.skipif(not VALID_FILE.exists(), reason="validation files not found (see README)")
def test_validation_file_loads():
    va = load_orders("valid")
    assert len(va) == 4155 and va["created"].notna().all()
    assert va["post_payout_usd"].isna().all()
    assert va["created_minute_only"].sum() == 1898
