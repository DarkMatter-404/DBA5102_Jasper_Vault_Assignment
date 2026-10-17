"""Pricing rule and demand assumption.

Demand: share of orders kept a(P) = exp(-k * (P / R - 1)), capped at UPLIFT_CAP, where R is the
price customers paid. The expected profit a(P) * (P - mu) is largest at P = mu + R / k.
"""
import numpy as np

K_MODERATE = 3.0
K_SCENARIOS = {"none": 0.0, "low": 1.5, "moderate": 3.0, "high": 6.0}
UPLIFT_CAP = 1.5
CAP_LO, CAP_HI = 0.85, 1.6


def conversion(P, R, k, uplift_cap=UPLIFT_CAP):
    """Expected share of orders kept at price P when customers paid R (k = 0: all kept)."""
    P, R = np.asarray(P, dtype=float), np.asarray(R, dtype=float)
    if k == 0:
        return np.ones_like(P)
    return np.minimum(np.exp(-k * (P / R - 1.0)), uplift_cap)


def optimal_price(mu, R_hat, k=K_MODERATE, cap_lo=CAP_LO, cap_hi=CAP_HI):
    """Premium per BTC: mu + R_hat / k, kept within [cap_lo, cap_hi] * R_hat, never below mu."""
    mu, R_hat = np.asarray(mu, dtype=float), np.asarray(R_hat, dtype=float)
    p = np.clip(mu + R_hat / k, cap_lo * R_hat, cap_hi * R_hat)
    return np.maximum(p, mu)
