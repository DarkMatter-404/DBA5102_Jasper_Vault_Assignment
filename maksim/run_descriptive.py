"""Descriptive facts quoted in README sections 1 and 2, computed from the training data.

Output: results/descriptive_facts.json. The BTC price at a timestamp is the close of the
one-minute candle that contains it; with this convention the payout rule reproduces the recorded
payout total to within 0.3 percent.
"""
import json

import numpy as np
import polars as pl

from src import config
from src.data import load_candles, load_events, load_orders, minute_index
from src.market import build_market

QUINTILES = 5


def price_at(candles: pl.DataFrame, ts: np.ndarray) -> np.ndarray:
    return candles["close"].to_numpy()[minute_index(ts, candles["ts"].to_numpy()[0])]


def intrinsic(o: pl.DataFrame, px: np.ndarray) -> np.ndarray:
    sign = np.where(o["optionType"].to_numpy() == 0, 1.0, -1.0)
    return o["quantity_BTC"].to_numpy() * np.maximum(sign * (px - o["strikePrice"].to_numpy()), 0.0)


def payout_rule(o: pl.DataFrame, candles: pl.DataFrame) -> dict:
    rec = intrinsic(o, price_at(candles, o["closedAt"].to_numpy()))
    hold = intrinsic(o, price_at(candles, o["expirationDate"].to_numpy()))
    act = o["realizedProfit_USDC"].to_numpy()
    q = o["quantity_BTC"].to_numpy()
    paid = act > 0
    err = np.abs(rec - act) / q
    early = o.select(pl.col("closedAt") < pl.col("expirationDate") - pl.duration(seconds=30)).to_series().to_numpy()
    return {
        "orders": o.height, "share_with_payout": float(paid.mean()), "share_closed_early": float(early.mean()),
        "paid_orders_median_abs_error_usdc_per_btc": float(np.median(err[paid])),
        "paid_orders_median_relative_error": float(np.median(err[paid] / (act[paid] / q[paid]))),
        "correlation_per_btc": float(np.corrcoef(rec / q, act / q)[0, 1]),
        "total_recorded": float(act.sum()), "total_rule_at_close": float(rec.sum()), "total_rule_at_expiry": float(hold.sum()),
    }


def release_effects(mkt, events: pl.DataFrame, end_idx: int, window: int = 30, control_days: int = 28) -> dict:
    """Mean |30-minute move| after each release type over the same clock window on release-free weekdays."""
    out = {}
    for typ in ["CPI", "NFP", "FOMC", "PCE"]:
        idx = minute_index(events.filter(pl.col("event_type") == typ)["ts_utc"].to_numpy(), mkt.t0)
        idx = idx[idx + window <= end_idx]
        ev, ctrl = [], []
        for e in idx:
            k = e - 1
            ev.append(abs(mkt.logp[k + window] - mkt.logp[k]))
            for d in range(1, control_days + 1):
                kc = k - 1440 * d
                weekday = int(((mkt.t0 + np.timedelta64(int(kc), "m")).astype("datetime64[D]").view("int64") - 4) % 7)
                if kc > 0 and weekday < 5 and mkt.event_cum[kc + window + 1] - mkt.event_cum[kc + 1] == 0:
                    ctrl.append(abs(mkt.logp[kc + window] - mkt.logp[kc]))
        out[typ] = {"releases": len(idx), "move_bps": float(np.mean(ev) * 1e4), "control_move_bps": float(np.mean(ctrl) * 1e4),
                    "ratio": float(np.mean(ev) / np.mean(ctrl))}
    return out


def markup_groups(o: pl.DataFrame) -> dict:
    m = o.filter(pl.col("base_premium_USDC").is_not_null()).with_columns(mult=pl.col("orderPrice_per_BTC_USDC") / pl.col("apiBasePrice_per_BTC_USDC"))
    m = m.with_columns(q=(pl.col("mult").rank("ordinal") / pl.len() * QUINTILES).ceil().cast(pl.Int32))
    g = m.group_by("q").agg(mean_multiplier=pl.col("mult").mean(), loss_ratio=pl.col("realizedProfit_USDC").sum() / pl.col("premiumAmount_USDC").sum(),
                            payout_over_base=pl.col("realizedProfit_USDC").sum() / pl.col("base_premium_USDC").sum()).sort("q")
    return {"quintiles_of_markup": g.to_dicts(),
            "payout_over_base_total": float(m["realizedProfit_USDC"].sum() / m["base_premium_USDC"].sum())}


def implied_vs_realised(o: pl.DataFrame, mkt) -> dict:
    """Volatility implied by the base price (at the money: base = 0.3989 x strike x sigma x sqrt(T)) and trailing realised volatility."""
    m = o.filter(pl.col("apiBasePrice_per_BTC_USDC").is_not_null())
    t_years = m["productType"].to_numpy() / (365 * 86400)
    iv = m["apiBasePrice_per_BTC_USDC"].to_numpy() / (0.398942 * m["strikePrice"].to_numpy() * np.sqrt(t_years))
    k = mkt.last_closed_index(m["createdAt"].to_numpy())
    rv = np.sqrt(mkt.trailing_var(k, 60) * 525600)
    df = pl.DataFrame({"productType": m["productType"], "month": m["createdAt"].dt.strftime("%Y-%m"), "iv": iv, "rv_last_hour": rv})
    g = df.group_by("productType").agg(pl.col("iv").median(), pl.col("rv_last_hour").median()).sort("productType")
    mo = df.group_by("month").agg(pl.col("iv").median(), pl.col("rv_last_hour").median()).sort("month")
    return {"median_by_product": g.to_dicts(), "median_by_month": mo.to_dicts()}


def main() -> None:
    candles, events_all = load_candles(), load_events(["CPI", "NFP", "FOMC", "PCE"])
    mkt = build_market(candles, events_all)
    o = load_orders(config.TRAIN_CSV).filter(pl.col("realizedProfit_USDC").is_not_null())
    end_idx = int(minute_index(np.array([np.datetime64(config.TRAIN_END)]), mkt.t0)[0]) - 1
    first, last = o.sort("createdAt").head(1), o.sort("createdAt").tail(1)
    facts = {
        "payout_rule": payout_rule(o, candles),
        "loss_ratio_training": float(o["realizedProfit_USDC"].sum() / o["premiumAmount_USDC"].sum()),
        "release_effects_to_train_end": release_effects(mkt, events_all, end_idx),
        "markup": markup_groups(o),
        "implied_vs_realised_vol": implied_vs_realised(o, mkt),
        "btc_price": {
            "first_training_order": {"time": str(first["createdAt"][0]), "price": float(price_at(candles, first["createdAt"].to_numpy())[0])},
            "last_training_order": {"time": str(last["createdAt"][0]), "price": float(price_at(candles, last["createdAt"].to_numpy())[0])},
            "last_candle_in_price_file": {"time": str(candles["ts"][-1]), "price": float(candles["close"][-1])},
        },
    }
    path = config.RESULTS / "descriptive_facts.json"
    path.write_text(json.dumps(facts, indent=2, default=str))
    print(json.dumps(facts, indent=1, default=str))


if __name__ == "__main__":
    main()
