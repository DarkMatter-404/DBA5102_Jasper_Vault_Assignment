"""Profit under demand scenarios, error measures and bootstrap confidence intervals."""
import numpy as np
import pandas as pd

from .rules import K_SCENARIOS, conversion


def expected_profit(P, R, y, qty, k):
    """Per-order expected profit in USD: kept share * (premium - payout) * size."""
    a = conversion(P, R, k)
    return a * (np.asarray(P) - np.asarray(y)) * np.asarray(qty)


def summarize(P, df: pd.DataFrame) -> dict:
    """Totals for one price vector. df needs paid (R), post_payout (y), qty."""
    R, y, q = df["paid"].to_numpy(), df["post_payout"].to_numpy(), df["qty"].to_numpy()
    out = {}
    for name, k in K_SCENARIOS.items():
        out[f"profit_{name}"] = expected_profit(P, R, y, q, k).sum()
    a = conversion(P, R, K_SCENARIOS["moderate"])
    out["loss_ratio_moderate"] = (a * y * q).sum() / (a * np.asarray(P) * q).sum()
    ratio = np.asarray(P) / R
    out["median_price_vs_paid"] = np.median(ratio)
    out["share_above_1.5x_paid"] = (ratio > 1.5).mean()
    out["share_below_paid"] = (ratio < 1).mean()
    return out


def poisson_deviance(y, mu, w):
    """Weighted Poisson deviance of payout predictions (lower is better)."""
    y, mu, w = (np.asarray(v, dtype=float) for v in (y, mu, w))
    mu = np.maximum(mu, 1e-9)
    ylogy = np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0.0)
    return 2 * np.sum(w * (ylogy - (y - mu))) / np.sum(w)


def calibration_table(mu, y, qty, bins=10) -> pd.DataFrame:
    """Predicted vs real payout (USD) by decile of predicted payout per BTC."""
    d = pd.DataFrame({"mu": mu, "y": y, "q": qty})
    d["bin"] = pd.qcut(d["mu"].rank(method="first"), bins, labels=False)
    g = d.groupby("bin").apply(lambda t: pd.Series({
        "orders": len(t), "predicted_usd": (t.mu * t.q).sum(), "real_usd": (t.y * t.q).sum()}), include_groups=False)
    g["real/predicted"] = g["real_usd"] / g["predicted_usd"]
    return g


def bootstrap_gain(profit_new, profit_ref, days, n=2000, seed=0, level=0.90):
    """CI of total(new - ref), resampling whole days (orders on the same day move together)."""
    diff = pd.Series(np.asarray(profit_new) - np.asarray(profit_ref)).groupby(np.asarray(days)).sum().to_numpy()
    rng = np.random.default_rng(seed)
    sims = diff[rng.integers(0, len(diff), (n, len(diff)))].sum(axis=1)
    lo, hi = np.quantile(sims, [(1 - level) / 2, 1 - (1 - level) / 2])
    return diff.sum(), lo, hi, (sims > 0).mean()
