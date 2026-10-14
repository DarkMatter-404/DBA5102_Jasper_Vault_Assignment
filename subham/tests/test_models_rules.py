import numpy as np
import pandas as pd
import pytest

from pricing.data import load_btc, load_orders
from pricing.external import calendar_features, fear_greed_features
from pricing.models import black_scholes
from pricing.rules import conversion, optimal_price


def test_black_scholes_known_value_and_parity():
    call = black_scholes(100, 100, 1.0, 0.2, False)
    put = black_scholes(100, 100, 1.0, 0.2, True)
    assert call == pytest.approx(7.9656, abs=1e-3)
    assert call - put == pytest.approx(0.0, abs=1e-9)          # parity with r = 0, S = K
    assert black_scholes(100, 90, 0.5, 0.3, False) - black_scholes(100, 90, 0.5, 0.3, True) == pytest.approx(10.0)


def test_conversion_rules():
    assert conversion([120.0], [100.0], 0).tolist() == [1.0]
    assert conversion([100.0], [100.0], 3)[0] == pytest.approx(1.0)
    assert conversion([110.0], [100.0], 3)[0] == pytest.approx(np.exp(-0.3))
    assert conversion([10.0], [100.0], 3)[0] == pytest.approx(1.5)  # uplift cap
    p = np.linspace(50, 200, 50)
    assert np.all(np.diff(conversion(p, np.full(50, 100.0), 3)) <= 0)


def test_optimal_price_caps_and_floor():
    R = np.array([100.0, 100.0, 100.0, 100.0])
    mu = np.array([40.0, 60.0, 100.0, 200.0])
    p = optimal_price(mu, R, k=3, cap_lo=0.85, cap_hi=1.6)
    assert p[0] == pytest.approx(85.0)            # 73.3 raised to the lower cap
    assert p[1] == pytest.approx(93.3333, rel=1e-4)  # mu + R / k
    assert p[2] == pytest.approx(133.3333, rel=1e-4)
    assert p[3] == pytest.approx(200.0)           # never below expected payout, even above the cap


def test_calendar_features_use_window_correctly():
    cal = pd.DataFrame({"time_utc": pd.to_datetime(["2026-03-11 12:30", "2026-03-18 18:00"])})
    orders = pd.DataFrame({"created": pd.to_datetime(["2026-03-11 12:00", "2026-03-11 12:31", "2026-03-11 11:00"]),
                           "duration_s": [3600, 3600, 1800]})
    f = calendar_features(orders, cal)
    assert f["event_in_window"].tolist() == [1, 0, 0]
    assert f["hours_to_event"].iloc[0] == pytest.approx(0.5)
    assert f["hours_since_event"].iloc[1] == pytest.approx(1 / 60)


def test_fear_greed_uses_previous_day():
    fng = pd.DataFrame({"date": pd.to_datetime(["2026-03-09", "2026-03-10", "2026-03-11"]), "fng": [20.0, 40.0, 90.0]})
    orders = pd.DataFrame({"created": pd.to_datetime(["2026-03-11 23:59"])})
    assert fear_greed_features(orders, fng)["fng"].iloc[0] == pytest.approx(0.40)


def test_payout_rule_matches_training_data():
    """Put pays (strike - price at close) * size, Call the opposite; checked against BTC prices at the close."""
    tr = load_orders("train")
    d = tr[tr["has_outcome"]]
    b = load_btc()
    m = d["post_closed"].dt.floor("min")
    lo = np.fmin.reduce([b["low"].reindex(m + pd.Timedelta(minutes=k)).to_numpy() for k in (-1, 0, 1)])
    hi = np.fmax.reduce([b["high"].reindex(m + pd.Timedelta(minutes=k)).to_numpy() for k in (-1, 0, 1)])
    K, y, put = d["strike"].to_numpy(), d["post_payout"].to_numpy(), d["is_put"].to_numpy()
    implied = np.where(put, K - y, K + y)
    paid = y > 0
    gap = np.where(implied < lo, lo - implied, np.where(implied > hi, implied - hi, 0.0))
    assert (gap[paid] <= 50).mean() >= 0.99
    zero_ok = np.where(put, hi >= K, lo <= K)[~paid]
    assert zero_ok.mean() >= 0.99
