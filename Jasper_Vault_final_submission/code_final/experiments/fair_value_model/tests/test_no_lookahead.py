"""No look-ahead: a price may depend only on candles that closed before the order.

Run from the maksim folder: .venv/bin/python -m pytest tests -q
"""
import dataclasses
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.data import load_candles, load_events, load_orders  # noqa: E402
from src.market import build_market  # noqa: E402
from src.pipeline import fit_pricer  # noqa: E402

N_ORDERS = 150


@pytest.fixture(scope="module", params=["+ macro releases (final)", "+ range and volume (candidate)"])
def setup(request):
    mkt = build_market(load_candles(), load_events())
    pricer = fit_pricer(mkt, config.TRAIN_END, request.param)
    orders = load_orders(config.VALID_CSV)
    idx = np.linspace(0, orders.height - 1, N_ORDERS).astype(int)
    return mkt, pricer, orders[idx]


def perturbed(mkt, mask: np.ndarray, seed: int):
    """Copy of the market with every price-derived series altered on the minutes in `mask`:
    close prices, high-low ranges, volume and taker volume."""
    rng = np.random.default_rng(seed)
    logp = mkt.logp + np.where(mask, rng.normal(0, 0.02, len(mkt.logp)), 0.0)
    r = np.diff(logp, prepend=logp[0])
    prefix = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    scale = lambda cum: prefix(np.diff(cum) * np.where(mask, rng.uniform(0.2, 5.0, len(mask)), 1.0))
    return dataclasses.replace(mkt, logp=logp, cum_r2=prefix(r * r), cum_park=scale(mkt.cum_park),
                               cum_vol=scale(mkt.cum_vol), cum_taker=scale(mkt.cum_taker))


def test_later_candles_do_not_change_prices(setup):
    mkt, pricer, orders = setup
    base = pricer.price(mkt, orders)["model_premium_USDC"].to_numpy()
    k = mkt.last_closed_index(orders["createdAt"].to_numpy())
    for i in range(orders.height):  # perturb everything after each order's last closed candle
        m2 = perturbed(mkt, np.arange(mkt.n) > k[i], seed=i)
        p = pricer.price(m2, orders[i:i + 1])["model_premium_USDC"][0]
        assert p == pytest.approx(base[i], rel=0, abs=0), f"order {i} changed"


def test_earlier_candles_do_change_prices(setup):
    """The test above has power: perturbing the hour before the orders moves the prices."""
    mkt, pricer, orders = setup
    base = pricer.price(mkt, orders)["model_premium_USDC"].to_numpy()
    k = mkt.last_closed_index(orders["createdAt"].to_numpy())
    mask = np.zeros(mkt.n, dtype=bool)
    for ki in k:
        mask[ki - 59: ki + 1] = True
    p = pricer.price(perturbed(mkt, mask, seed=1), orders)["model_premium_USDC"].to_numpy()
    assert (np.abs(p / base - 1) > 1e-6).mean() > 0.9
