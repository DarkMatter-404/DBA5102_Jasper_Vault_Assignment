"""Dynamic delta hedge of the PP book (a risk overlay; it never changes a price).

Jasper Vault is short every protection it sells, so a one-way BTC move is its main risk. It can
offset that exposure with BTC perpetual futures. Unlike the opening-delta hedge in
run_extensions.py, the hedge here is recomputed as the price and the time left change.

Timing follows the payout convention used everywhere else. A protection enters the book at the
close of the last one-minute candle before its order and leaves it at the close of the candle
that contains closedAt (the payout price). At the close of every candle k in between, its
Black-Scholes delta is recomputed from the price at that close, the time left to expiry and the
window volatility the model forecast at the sale (fixed per protection, so nothing observed after
the order enters the hedge except prices as they arrive).
"""
import numpy as np
from scipy.stats import norm

MIN_TAU_MIN = 1e-6  # time left (minutes) below which the delta is the payout's: 1 in the money, 0 out


def position_minutes(entry_k: np.ndarray, exit_k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One row per protection and candle close at which it is in the book.

    Protection i is held from the close of candle entry_k[i] to the close of exit_k[i], so its rows
    are k = entry_k[i], ..., exit_k[i] - 1 (the hedge set at close k earns the move to close k + 1).
    Returns (protection index, candle index)."""
    lens = exit_k - entry_k
    if (lens < 1).any():
        raise ValueError("every protection must stay in the book for at least one minute")
    idx = np.repeat(np.arange(len(entry_k)), lens)
    start = np.repeat(np.cumsum(lens) - lens, lens)
    k = np.repeat(entry_k, lens) + (np.arange(lens.sum()) - start)
    return idx, k


def hedge_positions(close: np.ndarray, idx: np.ndarray, k: np.ndarray, strike: np.ndarray, qty: np.ndarray,
                    is_call: np.ndarray, sigma_per_min: np.ndarray, expiry_min: np.ndarray) -> np.ndarray:
    """BTC position that offsets each (protection, minute) row: quantity x Black-Scholes delta.

    Long BTC against a call Jasper Vault has sold, short BTC against a put. expiry_min is the expiry
    in minutes after the first candle's open; the close of candle k is at k + 1."""
    s = close[k]
    tau = np.maximum(expiry_min[idx] - (k + 1), MIN_TAU_MIN)
    vol = sigma_per_min[idx] * np.sqrt(tau)
    d1 = (np.log(s / strike[idx]) + 0.5 * vol ** 2) / vol
    delta = norm.cdf(d1) - np.where(is_call[idx], 0.0, 1.0)
    return qty[idx] * delta


def per_protection_hedge_gain(close: np.ndarray, idx: np.ndarray, k: np.ndarray, hedge: np.ndarray, n: int) -> np.ndarray:
    """Profit of hedging each protection on its own, re-hedged every minute, before fees."""
    return np.bincount(idx, weights=hedge * (close[k + 1] - close[k]), minlength=n)


def band_rebalance(target: np.ndarray, live: np.ndarray, event: np.ndarray, px: np.ndarray, k0: int,
                   interval_min: int, band_btc: float, fee_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Hedge the whole book's net delta, trading only when needed.

    Arrays run over consecutive candle closes k0, k0 + 1, ... At each close the hedge earns
    hedge x (price change since the previous close). The hedge is then checked when an order
    opens or closes, or every interval_min minutes; if it differs from the book's target by more
    than band_btc it is traded to the target. It is flattened whenever the book is empty. Each
    trade pays fee_rate x traded notional. Returns (hedge profit per close, fee per close, hedge
    held after each close in BTC)."""
    h = 0.0
    pnl, fee, held = np.zeros(len(px)), np.zeros(len(px)), np.zeros(len(px))
    for i in range(len(px)):
        if i:
            pnl[i] = h * (px[i] - px[i - 1])
        if not live[i]:
            if h != 0.0:
                fee[i], h = fee_rate * abs(h) * px[i], 0.0
        elif (event[i] or (k0 + i) % interval_min == 0) and abs(target[i] - h) > band_btc:
            fee[i], h = fee_rate * abs(target[i] - h) * px[i], target[i]
        held[i] = h
    return pnl, fee, held
