"""Fit the full pricer on data before a cut-off and apply it to any set of orders."""
from dataclasses import dataclass

import numpy as np
import polars as pl

from . import config
from .data import minute_index, size_tier
from .market import (Market, Seasonality, VolRegimeHMM, features, fit_event_jump_var, fit_hmm,
                     fit_seasonality)
from .model import (FINAL_VARIANT, VARIANTS, MoveModel, add_event_jump, fair_value_per_btc,
                    margin_from_target_loss_ratio)


@dataclass
class Pricer:
    variant: str
    seas: Seasonality
    hmm: VolRegimeHMM | None
    move: MoveModel
    event_jump_var: float
    n_events_fitted: int
    margin: float
    fit_end: str

    def fair_value(self, mkt: Market, orders: pl.DataFrame) -> pl.DataFrame:
        """Add pre-trade features, the expected move and the fair value per BTC to `orders`."""
        k = mkt.last_closed_index(orders["createdAt"].to_numpy())
        if (k < max(config.TRAILING_WINDOWS_MIN)).any():
            raise ValueError("an order is too early for the one-week trailing window")
        t_s = orders["productType"].to_numpy()
        feats: dict[str, np.ndarray] = {}
        for t in np.unique(t_s):
            sel = t_s == t
            for name, vals in features(mkt, self.seas, k[sel], np.full(sel.sum(), t // 60), self.hmm).items():
                feats.setdefault(name, np.full(len(k), np.nan))[sel] = vals
        move = self.move.predict_abs_move(mkt, self.seas, k, t_s, self.hmm)
        move = add_event_jump(move, feats["event_in_window"], self.event_jump_var)
        fv = fair_value_per_btc(move, orders["strikePrice"].to_numpy(), orders["optionType"].to_numpy())
        return orders.with_columns(
            last_closed_minute=pl.Series(k),
            expected_abs_move=pl.Series(move),
            fair_value_per_btc=pl.Series(fv),
            fair_value_USDC=pl.Series(fv) * pl.col("quantity_BTC"),
            tier=size_tier(pl.col("notional_USDC")),
            **{n: pl.Series(v) for n, v in feats.items()},
        )

    def price(self, mkt: Market, orders: pl.DataFrame, margin: float | None = None,
              floor_at_base: bool = config.FLOOR_AT_BASE) -> pl.DataFrame:
        """Fair value plus margin, floored at the API base price when that quote exists."""
        m = self.margin if margin is None else margin
        raw = pl.col("fair_value_per_btc") * (1.0 + m)
        base = pl.col("apiBasePrice_per_BTC_USDC")
        floored = pl.max_horizontal(raw, base) if floor_at_base else raw  # max ignores a missing base
        return self.fair_value(mkt, orders).with_columns(
            price_per_btc=floored,
            floor_applied=(base.is_not_null() & (base > raw)) if floor_at_base else pl.lit(False),
        ).with_columns(
            model_premium_USDC=pl.col("price_per_btc") * pl.col("quantity_BTC"),
        )


def fit_pricer(mkt: Market, fit_end: str, variant: str = FINAL_VARIANT, margin: float | None = None) -> Pricer:
    """Fit every component on candles that closed before `fit_end` (a UTC timestamp string).

    The time-of-day profile, the regime HMM, the release jump variance and the move model all
    use candles before fit_end only, and the move model's targets are windows that end before
    fit_end. No order outcome is used: the model is fitted on market data alone, and the
    margin comes from the target loss ratio.
    """
    spec = VARIANTS[variant]
    k_end = int(minute_index(np.array([np.datetime64(fit_end)]), mkt.t0)[0]) - 1
    seas = fit_seasonality(mkt, k_end)
    hmm = fit_hmm(mkt, k_end) if "hmm_p_turbulent" in spec["features"] else None
    move = MoveModel(feature_names=spec["features"]).fit(mkt, seas, 0, k_end, hmm)
    jump_var, n_ev = fit_event_jump_var(mkt, k_end) if spec["events"] else (0.0, 0)
    m = margin_from_target_loss_ratio() if margin is None else margin
    return Pricer(variant, seas, hmm, move, jump_var, n_ev, m, fit_end)
