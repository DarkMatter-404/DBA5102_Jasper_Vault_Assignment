"""Mechanics of the dynamic delta hedge (src/hedge.py) on small hand-made books."""
import numpy as np
import pytest

from src.hedge import band_rebalance, hedge_positions, per_protection_hedge_gain, position_minutes


def test_position_minutes_cover_entry_to_exit():
    idx, k = position_minutes(np.array([3, 10]), np.array([5, 11]))
    assert idx.tolist() == [0, 0, 1]
    assert k.tolist() == [3, 4, 10]


def test_position_minutes_reject_empty_holding():
    with pytest.raises(ValueError):
        position_minutes(np.array([4]), np.array([4]))


def test_delta_signs_and_limits():
    close = np.array([100.0, 150.0, 50.0])
    one = np.ones(1)
    deep_call = hedge_positions(close, np.array([0]), np.array([1]), one * 100, one * 2, np.array([True]), one * 0.001, one * 10)
    deep_put = hedge_positions(close, np.array([0]), np.array([2]), one * 100, one * 2, np.array([False]), one * 0.001, one * 10)
    atm_call = hedge_positions(close, np.array([0]), np.array([0]), one * 100, one, np.array([True]), one * 0.001, one * 10)
    assert deep_call[0] == pytest.approx(2.0)   # long 2 BTC against a sold call far in the money
    assert deep_put[0] == pytest.approx(-2.0)   # short 2 BTC against a sold put far in the money
    assert 0.5 < atm_call[0] < 0.51             # about half at the money


def test_flat_price_earns_nothing_and_pays_fees_only_on_trades():
    px = np.full(6, 100.0)
    target = np.array([0.5, 0.5, 0.5, 0.5, 0.0, 0.0])
    live = np.array([True, True, True, True, False, False])
    event = np.array([True, False, False, False, True, False])
    pnl, fee, held = band_rebalance(target, live, event, px, k0=0, interval_min=1, band_btc=0.1, fee_rate=0.001)
    assert np.allclose(pnl, 0.0)
    assert fee.sum() == pytest.approx(2 * 0.001 * 0.5 * 100)  # one trade in, one flattening trade out
    assert held.tolist() == [0.5, 0.5, 0.5, 0.5, 0.0, 0.0]


def test_band_hedge_offsets_a_trend():
    px = np.array([100.0, 101.0, 102.0, 103.0])
    pnl, _, held = band_rebalance(np.ones(4), np.ones(4, bool), np.r_[True, False, False, False], px, 0, 1, 0.0, 0.0)
    assert pnl.sum() == pytest.approx(3.0)  # long 1 BTC from the first close earns the full rise
    assert held.tolist() == [1.0, 1.0, 1.0, 1.0]


def test_per_protection_gain_sums_rows():
    close = np.array([100.0, 102.0, 101.0])
    gain = per_protection_hedge_gain(close, np.array([0, 0, 1]), np.array([0, 1, 0]), np.array([1.0, 2.0, -1.0]), 2)
    assert gain.tolist() == pytest.approx([1 * 2 + 2 * (-1), -1 * 2])
