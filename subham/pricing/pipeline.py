"""HybridPricer: connects the model parts, and a rolling backtest."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import ATM, BaseModel, HarVol, ReferenceModel, RiskMultiplier, black_scholes
from .rules import CAP_HI, CAP_LO, K_MODERATE, conversion, optimal_price

LOG_COLS = ["rv60", "rv240", "rv1440", "rv10080", "pk1440"]


@dataclass
class Config:
    k: float = K_MODERATE           # demand sensitivity used by the pricing rule
    cap_lo: float = CAP_LO          # premium >= cap_lo * reference price
    cap_hi: float = CAP_HI          # premium <= cap_hi * reference price
    risk_features: tuple = ()       # () = one calibration constant (selected); see RISK_INPUTS
    risk_kind: str = "glm"          # glm or gbm, used only when risk_features is not empty
    risk_alpha: float = 0.1
    size_cap: tuple = (0.8, 1.5)
    ref_kind: str = "model"         # model or const


def best_constant(price_basis, orders, k=K_MODERATE, grid=np.arange(0.5, 4.001, 0.02)):
    """Constant c that maximizes expected profit of the price c * price_basis on the given orders."""
    B = np.asarray(price_basis, dtype=float)
    R, y, q = orders["paid"].to_numpy(), orders["post_payout"].to_numpy(), orders["qty"].to_numpy()
    profits = [np.sum(conversion(c * B, R, k) * (c * B - y) * q) for c in grid]
    return float(grid[int(np.argmax(profits))])


class HybridPricer:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()

    def _enrich(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        X["sigma"] = self.har.predict(X)
        X["log_sigma"] = np.log(X["sigma"])
        for c in LOG_COLS:
            X["log_" + c] = np.log(X[c].clip(lower=1e-6))
        X["fv"] = black_scholes(X["spot"], X["strike"], X["T"], X["sigma"], X["is_put"])
        return X

    def _add_anchor(self, orders: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
        rebuilt = pd.Series(self.base_model.predict(X), index=X.index)
        X["anchor"] = orders["base"].fillna(rebuilt)
        X["anchor_rebuilt"] = orders["base"].isna()
        X["base_rebuilt_value"] = rebuilt
        X["iv_anchor"] = X["anchor"] / (ATM * X["spot"] * np.sqrt(X["T"]))
        return X

    def fit(self, orders, X, btc, mkt, cutoff, extra_base=None) -> "HybridPricer":
        """orders, X: training rows with outcomes. extra_base: optional (orders, X) whose base price
        (an input, not an outcome) may also be used to fit the base-price rebuild."""
        cfg = self.cfg
        self.har = HarVol().fit(btc, mkt, cutoff)
        Xe = self._enrich(X)
        has_base = orders["base"].notna()
        bx, by = Xe[has_base], orders.loc[has_base, "base"]
        if extra_base is not None:
            eo, ex = extra_base
            ex = self._enrich(ex)
            m = eo["base"].notna()
            bx, by = pd.concat([bx, ex[m]]), pd.concat([by, eo.loc[m, "base"]])
        self.base_model = BaseModel().fit(bx, by)
        Xe = self._add_anchor(orders, Xe)
        self.risk = RiskMultiplier(cfg.risk_features, cfg.risk_kind, cfg.risk_alpha, cfg.size_cap).fit(
            Xe, orders["post_payout"], orders["qty"], Xe["anchor"])
        self.ref = ReferenceModel(cfg.ref_kind).fit(Xe[has_base], orders.loc[has_base, "paid"], orders.loc[has_base, "base"])
        self.c_base = best_constant(Xe["anchor"], orders, cfg.k)
        self.c_fv = best_constant(Xe["fv"], orders, cfg.k)
        return self

    def predict(self, orders, X) -> pd.DataFrame:
        cfg = self.cfg
        Xe = self._add_anchor(orders, self._enrich(X))
        out = pd.DataFrame(index=orders.index)
        out["sigma_forecast"] = Xe["sigma"]
        out["fair_value_per_BTC"] = Xe["fv"]
        out["anchor_per_BTC"] = Xe["anchor"]
        out["anchor_source"] = np.where(Xe["anchor_rebuilt"], "rebuilt", "jasper")
        out["base_rebuilt_per_BTC"] = Xe["base_rebuilt_value"]
        out["risk_multiplier"] = self.risk.predict(Xe)
        out["expected_payout_per_BTC"] = Xe["anchor"] * out["risk_multiplier"]
        out["reference_price_per_BTC"] = self.ref.predict(Xe, Xe["anchor"])
        out["premium_per_BTC"] = optimal_price(out["expected_payout_per_BTC"], out["reference_price_per_BTC"],
                                               cfg.k, cfg.cap_lo, cfg.cap_hi)
        out["premiumAmount_USDC"] = out["premium_per_BTC"] * orders["qty"]
        # Multiplier on the anchor: Jasper's base price where it exists, else the rebuilt base price.
        out["pricing_multiplier"] = out["premium_per_BTC"] / Xe["anchor"]
        out["bench_base_x1"] = Xe["anchor"]
        out["bench_base_x_c"] = self.c_base * Xe["anchor"]
        out["bench_fv_x_c"] = self.c_fv * Xe["fv"]
        return out


def backtest(orders, X, btc, mkt, test_months, configs: dict) -> pd.DataFrame:
    """Rolling-origin backtest. For each test month, fit on all earlier months, price that month.

    Training rows must have ended (expiry) before the test month starts, so no outcome is used
    before it is known.
    """
    parts = []
    for month in test_months:
        start = pd.Timestamp(month)
        end = start + pd.offsets.MonthBegin(1)
        train = orders[(orders["created"] < start) & orders["has_outcome"] & (orders["expiry"] <= start)]
        test = orders[(orders["created"] >= start) & (orders["created"] < end) & orders["has_outcome"]]
        for name, cfg in configs.items():
            pricer = HybridPricer(cfg).fit(train, X.loc[train.index], btc, mkt, cutoff=start)
            out = pricer.predict(test, X.loc[test.index])
            out["fold"], out["config"] = start.strftime("%Y-%m"), name
            parts.append(out)
    return pd.concat(parts)
