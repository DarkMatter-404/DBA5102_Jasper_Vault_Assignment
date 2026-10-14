"""Profit, stability and conversion metrics for a set of recommended premiums.

Conversion assumption. The data only contains orders that were bought at the current price
A. If a strategy charges P instead, the expected number of such orders is scaled by
w = (P / A) ** (-elasticity). Elasticity 0 means users ignore price (every order is still
bought); elasticity 1 means a 10 percent higher price loses about 10 percent of orders.
Jasper Vault's own conversion rule is not published, so results are shown for a range.

A second, stricter rule is also reported: an order is kept only if P <= (1 + tolerance) x A
and lower prices win no extra orders.
"""
import numpy as np
import polars as pl

DAYS_PER_YEAR = 365.0
MAX_WEIGHT = 3.0  # cap on the volume multiplier when a price is cut sharply


def conversion_weight(price: np.ndarray, reference: np.ndarray, elasticity: float) -> np.ndarray:
    ratio = np.maximum(price, 1e-12) / np.maximum(reference, 1e-12)
    return np.minimum(ratio ** (-elasticity), MAX_WEIGHT)


def threshold_weight(price: np.ndarray, reference: np.ndarray, tolerance: float) -> np.ndarray:
    return (price <= (1.0 + tolerance) * reference).astype(float)


def daily_risk(day: np.ndarray, pnl: np.ndarray) -> dict[str, float]:
    """Stability of the daily P&L of the PP book."""
    df = pl.DataFrame({"day": day, "pnl": pnl}).group_by("day").agg(pl.col("pnl").sum()).sort("day")
    d = df["pnl"].to_numpy()
    cum = np.cumsum(d)
    drawdown = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:] - cum
    worst5 = np.sort(d)[: max(1, int(np.ceil(0.05 * len(d))))]
    return {
        "days": len(d),
        "mean_daily_pnl": float(d.mean()),
        "sd_daily_pnl": float(d.std(ddof=1)),
        "sharpe_annualised": float(d.mean() / d.std(ddof=1) * np.sqrt(DAYS_PER_YEAR)) if d.std() > 0 else np.nan,
        "share_losing_days": float((d < 0).mean()),
        "worst_day": float(d.min()),
        "cvar5_daily": float(worst5.mean()),
        "max_drawdown": float(drawdown.max()),
    }


def evaluate(name: str, price: np.ndarray, payout: np.ndarray, reference: np.ndarray,
             day: np.ndarray, weight: np.ndarray | None = None, scenario: str = "") -> dict:
    """All metrics for one strategy under one conversion weight vector."""
    w = np.ones_like(price) if weight is None else weight
    revenue = float((w * price).sum())
    paid = float((w * payout).sum())
    pnl = w * (price - payout)
    out = {
        "strategy": name,
        "scenario": scenario,
        "expected_orders": float(w.sum()),
        "premium": revenue,
        "payout": paid,
        "profit": revenue - paid,
        "loss_ratio": paid / revenue if revenue > 0 else np.nan,
        "margin_on_premium": (revenue - paid) / revenue if revenue > 0 else np.nan,
        "median_price_vs_current": float(np.median(price / reference)),
        "share_cheaper_than_current": float((price < reference).mean()),
    }
    out.update(daily_risk(day, pnl))
    return out


def evaluate_scenarios(strategies: dict[str, np.ndarray], payout: np.ndarray, reference: np.ndarray,
                       day: np.ndarray, elasticities, tolerances=(0.0, 0.25), base: np.ndarray | None = None,
                       base_caps=()) -> pl.DataFrame:
    """Metrics per strategy and conversion rule.

    Note: under elasticity e <= 1 any uniform price rise raises profit (with e = 1 the revenue per
    order stays at today's price whatever the price), so these scenarios cannot tell better pricing
    from higher pricing. The threshold rules (keep_if_within_*) and the base-relative rules
    (keep_if_at_most_*x_base) can, because a higher price there loses the order.
    """
    rows = []
    for name, price in strategies.items():
        for e in elasticities:
            w = conversion_weight(price, reference, e)
            rows.append(evaluate(name, price, payout, reference, day, w, f"elasticity={e:g}"))
        for tol in tolerances:
            w = threshold_weight(price, reference, tol)
            rows.append(evaluate(name, price, payout, reference, day, w, f"keep_if_within_{int(tol * 100)}pct"))
        for cap in base_caps:
            w = (price <= cap * base + 1e-9).astype(float)
            rows.append(evaluate(name, price, payout, reference, day, w, f"keep_if_at_most_{cap:g}x_base"))
    return pl.DataFrame(rows)


def move_forecast_scores(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Out-of-sample quality of an expected-absolute-move forecast."""
    y_pred = np.maximum(y_pred, 1e-12)
    dev = 2 * (np.where(y_true > 0, y_true * np.log(np.maximum(y_true, 1e-300) / y_pred), 0.0) - (y_true - y_pred))
    return {
        "mean_poisson_deviance": float(dev.mean()),
        "calibration_actual_over_pred": float(y_true.sum() / y_pred.sum()),
        "spearman": float(pl.DataFrame({"a": y_true, "b": y_pred}).select(pl.corr("a", "b", method="spearman")).item()),
    }


def ordered_lorenz(reference: np.ndarray, candidate: np.ndarray, payout: np.ndarray):
    """Ordered Lorenz curve and Gini index (Frees, Meyers and Cummings, 2011).

    Orders are sorted by the relativity candidate / reference (how much more the candidate
    premium charges than the reference premium). The curve plots the cumulative share of
    reference premium (x) against the cumulative share of payouts (y). If the candidate has no
    information beyond the reference, the curve follows the diagonal and the Gini is 0. A
    positive Gini means the orders the candidate marks up are the ones the reference
    underprices. Returns (x, y, gini).
    """
    order = np.argsort(candidate / reference, kind="stable")
    x = np.concatenate([[0.0], np.cumsum(reference[order]) / reference.sum()])
    y = np.concatenate([[0.0], np.cumsum(payout[order]) / payout.sum()])
    return x, y, float(2.0 * np.trapezoid(x - y, x))


def gini_with_interval(reference: np.ndarray, candidate: np.ndarray, payout: np.ndarray, day: np.ndarray,
                       n_boot: int = 1000, seed: int = 0) -> dict[str, float]:
    """Gini with a 90 percent interval from resampling whole days."""
    g = ordered_lorenz(reference, candidate, payout)[2]
    days = np.unique(day)
    by_day = [np.where(day == d)[0] for d in days]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = np.concatenate([by_day[i] for i in rng.integers(0, len(days), len(days))])
        boots.append(ordered_lorenz(reference[idx], candidate[idx], payout[idx])[2])
    lo, hi = np.percentile(boots, [5, 95])
    return {"gini": g, "gini_ci05": float(lo), "gini_ci95": float(hi), "share_boot_positive": float(np.mean(np.array(boots) > 0))}
