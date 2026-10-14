"""Basic extensions to the pricing strategy, evaluated on training data (February to July 2026).

A. Risk overlays that do not change prices. (1) Opening-delta hedge: a BTC perpetual position of
   delta x quantity, fixed at each protection's opening delta (long for a call, short for a put;
   Black-Scholes with the model's window volatility), not updated as the price moves, closed with
   the protection; either per order or for the net book within a band. Assumed trading cost 0.04
   percent of hedge notional per side. (2) Exposure limit (added after an external review): cap the
   open protected notional per direction and pause new sales in that direction while the cap binds.
B. Range and volume features (market microstructure): one-hour and four-hour Parkinson
   (high-low) variance, last-hour volume relative to the weekly average, last-hour taker
   buy/sell imbalance.
C. US market holidays: NYSE full-day closures are treated like weekend days in the time-of-day
   profile, so no 09:30 opening spike is expected on those days.

PRE-REGISTERED DECISION RULE (committed before this script was first run). A candidate that
changes prices (B, C, or B and C together) is adopted only if, on training data:
  1. out-of-sample forecast skill, averaged over the five monthly refits (1 March to 1 July, each
     scored on the following month), improves on the current model by at least 0.005 for at
     least 5 of the 7 product lengths; and
  2. the walk-forward Gini against current pricing (all February to July orders, each month priced
     by a model fitted on earlier data only) is not lower than the current model's.
If several pass, the one with the larger mean skill gain is adopted. An adopted candidate becomes
version 2 of the recommendations, frozen separately. Version 2 is built after the version 1 holdout
check, so it is not evaluated on August to October outcomes.

The hedging overlay (A) is also shown on the validation period as a post-hoc illustration (prices
are the frozen version 1 prices; the hedge has no parameter), clearly separated from the training
evidence. The net-book band hedge (band_hedge) was added after the first run showed that hedging
every order separately costs about half the profit; the bands 0, 0.25, 0.5 and 1 BTC are round
numbers, not tuned.

Outputs: results/extensions/*
"""
import json
import sys

import numpy as np
import polars as pl
from scipy.stats import norm

from src import config
from src.data import load_candles, load_events, load_holidays, load_orders, minute_index
from src.evaluate import conversion_weight, daily_risk, move_forecast_scores, ordered_lorenz, threshold_weight
from src.market import build_market, market_sample
from src.model import FINAL_VARIANT, SQRT_PI_2, add_event_jump
from src.pipeline import fit_pricer

OUT = config.RESULTS / "extensions"
CUTOFFS = [("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"), ("2026-05-01", "2026-06-01"),
           ("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-07-31 17:11:12")]
MONTHS = [("2026-02-01", "2026-03-01"), ("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"),
          ("2026-05-01", "2026-06-01"), ("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-08-01")]
CANDIDATE_VARIANT = "+ range and volume (candidate)"
MIN_SKILL_GAIN, MIN_LENGTHS = 0.005, 5
HEDGE_FEE_PER_SIDE = 0.0004


def ts(s: str) -> pl.Expr:
    return pl.lit(np.datetime64(s)).cast(pl.Datetime("us"))


def kidx(mkt, t: str) -> int:
    return int(minute_index(np.array([np.datetime64(t)]), mkt.t0)[0]) - 1


# ------------------------------------------------------------------ B and C: forecast skill
def predict(pr, mkt, k, t_s):
    t = np.full(len(k), t_s)
    return add_event_jump(pr.move.predict_abs_move(mkt, pr.seas, k, t, pr.hmm), mkt.events_in_window(k, t // 60), pr.event_jump_var) * 1e4


def skill_table(models: dict) -> pl.DataFrame:
    """models: name -> (market, variant). Skill on the same out-of-sample windows for every model."""
    rows = []
    for cut, oos_end in CUTOFFS:
        fitted = {n: (m, fit_pricer(m, cut, v)) for n, (m, v) in models.items()}
        mkt0, naive = models["current model"][0], fit_pricer(models["current model"][0], cut, "average move only")
        k_cut, k_oos = kidx(mkt0, cut), kidx(mkt0, oos_end)
        for t_s in config.DURATIONS_S:
            k = market_sample(mkt0, k_cut + 1, k_oos, t_s // 60, config.SAMPLE_STEP_MIN)
            y = mkt0.forward_abs_return(k, np.full(len(k), t_s // 60)) * 1e4
            dn = move_forecast_scores(y, predict(naive, mkt0, k, t_s))["mean_poisson_deviance"]
            for n, (m, pr) in fitted.items():
                d = move_forecast_scores(y, predict(pr, m, k, t_s))["mean_poisson_deviance"]
                rows.append({"cutoff": cut, "productType": t_s, "model": n, "skill": 1 - d / dn})
    return pl.DataFrame(rows)


def walk_forward(models: dict, orders: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for name, (m, v) in models.items():
        parts = []
        for start, end in MONTHS:
            mo = orders.filter((pl.col("createdAt") >= ts(start)) & (pl.col("createdAt") < ts(end)))
            parts.append(fit_pricer(m, start, v).price(m, mo))
        p = pl.concat(parts)
        a, x, d = p["premiumAmount_USDC"].to_numpy(), p["realizedProfit_USDC"].to_numpy(), p["day"].to_numpy()
        price = p["model_premium_USDC"].to_numpy()
        prof = lambda w: float((w * (price - x)).sum())
        rows.append({"model": name, "gini_vs_current": ordered_lorenz(a, p["fair_value_USDC"].to_numpy(), x)[2],
                     "profit_no_demand_response": prof(np.ones_like(price)), "profit_elasticity_1": prof(conversion_weight(price, a, 1.0)),
                     "profit_keep_if_not_dearer": prof(threshold_weight(price, a, 0.0)),
                     "loss_ratio": float(x.sum() / price.sum()), "worst_day": daily_risk(d, price - x)["worst_day"]})
    return pl.DataFrame(rows)


def decide(skill: pl.DataFrame, wf: pl.DataFrame) -> dict:
    mean = skill.group_by("productType", "model").agg(pl.col("skill").mean())
    base = mean.filter(pl.col("model") == "current model").select("productType", pl.col("skill").alias("base"))
    gini0 = wf.filter(pl.col("model") == "current model")["gini_vs_current"][0]
    out = {}
    for name in [n for n in mean["model"].unique().to_list() if n != "current model"]:
        g = mean.filter(pl.col("model") == name).join(base, on="productType").with_columns(gain=pl.col("skill") - pl.col("base")).sort("productType")
        n_ok = int((g["gain"] >= MIN_SKILL_GAIN).sum())
        gini = wf.filter(pl.col("model") == name)["gini_vs_current"][0]
        out[name] = {"skill_gain_by_product": dict(zip(g["productType"].to_list(), g["gain"].round(4).to_list())),
                     "mean_skill_gain": float(g["gain"].mean()), "lengths_with_gain_at_least_0.005": n_ok,
                     "walk_forward_gini": gini, "current_model_gini": gini0,
                     "passes": bool(n_ok >= MIN_LENGTHS and gini >= gini0)}
    passing = [n for n, r in out.items() if r["passes"]]
    adopted = max(passing, key=lambda n: out[n]["mean_skill_gain"]) if passing else None
    return {"rule": f"skill gain >= {MIN_SKILL_GAIN} for >= {MIN_LENGTHS} of 7 lengths and walk-forward Gini not lower",
            "candidates": out, "adopted": adopted}


# ------------------------------------------------------------------ A: delta hedging and exposure limits
# Accounting (revised after an external review, 14 Oct 2026): every row of the hedging and exposure
# tables uses the same cash-flow dates. The premium is booked on the opening day, the payout on the
# closing day and each trading fee on the day it is paid. Per-order hedge profit is booked when the
# protection closes; net-book hedge profit as it accrues between events. Both hedges enter at the
# close of the last minute before the order and exit at the payout price.
BANDS_BTC = [0.0, 0.25, 0.5, 1.0]  # net-book hedge bands (round numbers, not tuned)
CAPS_USDC = [None, 400_000, 250_000, 150_000]  # open protected notional per direction
STRESS_MOVE = 0.05  # illustrative: a 5 percent adverse move turns a cap C into a stress loss of 0.05 x C


def close_price(candles: pl.DataFrame, t: np.ndarray) -> np.ndarray:
    return candles["close"].to_numpy()[minute_index(t, candles["ts"].to_numpy()[0])]


def entry_price(candles: pl.DataFrame, t: np.ndarray) -> np.ndarray:
    """Close of the last one-minute candle that closed before t (the price available at the order)."""
    return candles["close"].to_numpy()[minute_index(t, candles["ts"].to_numpy()[0]) - 1]


def day_of(t: np.ndarray) -> np.ndarray:
    return t.astype("datetime64[D]")


def opening_delta_hedge(o: pl.DataFrame, candles: pl.DataFrame, move_col: str = "expected_abs_move") -> pl.DataFrame:
    """Per-order hedge fixed at the protection's opening delta (Black-Scholes with the model's window
    volatility). It is not updated as the price moves, and it is closed when the protection closes."""
    sigma = o[move_col].to_numpy() * SQRT_PI_2
    d1 = 0.5 * sigma  # at the money: log(S / K) = 0
    call = o["optionType"].to_numpy() == 0
    delta = np.where(call, norm.cdf(d1), norm.cdf(d1) - 1.0)  # the option's delta; Jasper Vault is short it
    q = o["quantity_BTC"].to_numpy()
    s0 = entry_price(candles, o["createdAt"].to_numpy())  # last minute closed before the order
    s1 = close_price(candles, o["closedAt"].to_numpy())   # same convention as the payout
    pos = delta * q  # hold +delta x quantity BTC, offsetting the short option's -delta x quantity
    return o.with_columns(hedge_position_BTC=pl.Series(pos), hedge_entry_price=pl.Series(s0), hedge_exit_price=pl.Series(s1),
                          hedge_pnl_USDC=pl.Series(pos * (s1 - s0)),
                          hedge_fee_open_USDC=pl.Series(HEDGE_FEE_PER_SIDE * np.abs(pos) * s0),
                          hedge_fee_close_USDC=pl.Series(HEDGE_FEE_PER_SIDE * np.abs(pos) * s1))


def ledger(day: np.ndarray, amount: np.ndarray) -> pl.DataFrame:
    return pl.DataFrame({"day": day_of(day), "amount": amount}).with_columns(pl.col("day").cast(pl.Date))


def book_ledger(o: pl.DataFrame, price_col: str, payout_col: str) -> pl.DataFrame:
    return pl.concat([ledger(o["createdAt"].to_numpy(), o[price_col].to_numpy()),
                      ledger(o["closedAt"].to_numpy(), -o[payout_col].to_numpy())])


def per_order_hedge_ledger(o: pl.DataFrame, with_fees: bool) -> pl.DataFrame:
    parts = [ledger(o["closedAt"].to_numpy(), o["hedge_pnl_USDC"].to_numpy())]
    if with_fees:
        parts += [ledger(o["createdAt"].to_numpy(), -o["hedge_fee_open_USDC"].to_numpy()),
                  ledger(o["closedAt"].to_numpy(), -o["hedge_fee_close_USDC"].to_numpy())]
    return pl.concat(parts)


def band_hedge_ledger(o: pl.DataFrame, candles: pl.DataFrame, band: float) -> tuple[pl.DataFrame, float]:
    """Hedge the book's net opening delta, trading only when it drifts more than `band` BTC from the
    hedge, and flattening whenever the book is empty. Opens trade at the price available at the
    order and closes at the payout price, as in the per-order hedge; hedge profit is booked as it
    accrues between events and fees on the trading day."""
    ev = pl.concat([o.select(t=pl.col("createdAt"), d=pl.col("hedge_position_BTC"), px=pl.col("hedge_entry_price"), n=pl.lit(1)),
                    o.select(t=pl.col("closedAt"), d=-pl.col("hedge_position_BTC"), px=pl.col("hedge_exit_price"), n=pl.lit(-1))]).sort("t", maintain_order=True)
    t, d, px, is_open = ev["t"].to_numpy(), ev["d"].to_numpy(), ev["px"].to_numpy(), ev["n"].to_numpy()
    target = h = 0.0
    open_count = 0
    pnl, fee = np.zeros(len(t)), np.zeros(len(t))
    for i in range(len(t)):
        if i:
            pnl[i] = h * (px[i] - px[i - 1])  # profit on the hedge held since the previous event
        target += d[i]
        open_count += int(is_open[i])
        if open_count == 0:
            target = 0.0  # book empty: remove rounding residue and flatten
        if abs(target - h) > band or (open_count == 0 and h != 0.0):
            fee[i] = HEDGE_FEE_PER_SIDE * abs(target - h) * px[i]
            h = target
    return pl.concat([ledger(t, pnl), ledger(t, -fee)]), float(fee.sum())


def metrics(parts: list[pl.DataFrame]) -> dict:
    daily = pl.concat(parts).group_by("day").agg(pl.col("amount").sum()).sort("day")
    r = daily_risk(daily["day"].to_numpy(), daily["amount"].to_numpy())
    return {"profit": float(daily["amount"].sum()), **{k: r[k] for k in ["sd_daily_pnl", "worst_day", "cvar5_daily", "max_drawdown", "share_losing_days"]}}


def hedge_table(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, label: str) -> list[dict]:
    book = book_ledger(o, price_col, payout_col)
    fees_per_order = float((o["hedge_fee_open_USDC"] + o["hedge_fee_close_USDC"]).sum())
    rows = [{"sample": label, "hedge": "no hedge", "hedge_fees": 0.0, **metrics([book])},
            {"sample": label, "hedge": "every order, opening delta, before fees", "hedge_fees": 0.0, **metrics([book, per_order_hedge_ledger(o, False)])},
            {"sample": label, "hedge": "every order, opening delta, after fees", "hedge_fees": fees_per_order, **metrics([book, per_order_hedge_ledger(o, True)])}]
    for band in BANDS_BTC:
        hl, fees = band_hedge_ledger(o, candles, band)
        rows.append({"sample": label, "hedge": f"net book within {band:g} BTC, after fees", "hedge_fees": fees, **metrics([book, hl])})
    return rows


def exposure_cap(o: pl.DataFrame, cap: float | None) -> np.ndarray:
    """Accept an order only if its direction's open protected notional stays within the cap;
    otherwise new sales in that direction pause until earlier protections close."""
    if cap is None:
        return np.ones(o.height, dtype=bool)
    order = np.argsort(o["createdAt"].to_numpy(), kind="stable")
    created, closed = o["createdAt"].to_numpy(), o["closedAt"].to_numpy()
    direction, notional = o["optionType"].to_numpy(), o["notional_USDC"].to_numpy()
    accepted = np.zeros(o.height, dtype=bool)
    open_book: list[tuple] = []  # (closedAt, direction, notional) of accepted protections
    exposure = {0: 0.0, 1: 0.0}
    for i in order:
        still_open = []
        for c, dr, n in open_book:
            if c <= created[i]:
                exposure[dr] -= n
            else:
                still_open.append((c, dr, n))
        open_book = still_open
        if exposure[direction[i]] + notional[i] <= cap:
            accepted[i] = True
            exposure[direction[i]] += notional[i]
            open_book.append((closed[i], direction[i], notional[i]))
    return accepted


def exposure_table(o: pl.DataFrame, price_col: str, payout_col: str, label: str) -> list[dict]:
    rows = []
    for cap in CAPS_USDC:
        m = exposure_cap(o, cap)
        acc = o.filter(pl.Series(m))
        rows.append({"sample": label, "cap_per_direction_USDC": cap, "stress_loss_bound_per_direction_USDC": cap * STRESS_MOVE if cap else None,
                     "orders_rejected_share": float(1 - m.mean()), "premium_rejected_share": float(o.filter(pl.Series(~m))[price_col].sum() / o[price_col].sum()),
                     **metrics([book_ledger(acc, price_col, payout_col)])})
    return rows


POLICY = {"cap_per_direction_USDC": 250_000, "hedge_band_BTC": 0.5}  # one combined policy, round numbers


def policy_row(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, label: str) -> dict:
    """The proposed risk policy: exposure cap per direction, then a net-book hedge of the accepted orders."""
    m = exposure_cap(o, POLICY["cap_per_direction_USDC"])
    acc = o.filter(pl.Series(m))
    hl, fees = band_hedge_ledger(acc, candles, POLICY["hedge_band_BTC"])
    return {"sample": label, "cap_per_direction_USDC": POLICY["cap_per_direction_USDC"],
            "stress_loss_bound_per_direction_USDC": POLICY["cap_per_direction_USDC"] * STRESS_MOVE,
            "orders_rejected_share": float(1 - m.mean()), "premium_rejected_share": float(o.filter(pl.Series(~m))[price_col].sum() / o[price_col].sum()),
            "policy": f"cap plus net-book hedge within {POLICY['hedge_band_BTC']:g} BTC", "hedge_fees": fees,
            **metrics([book_ledger(acc, price_col, payout_col), hl])}


def net_exposure(o: pl.DataFrame) -> dict:
    """Open net option delta of the book over time (BTC), from order opens and closes."""
    ev = pl.concat([o.select(t=pl.col("createdAt"), d=-pl.col("hedge_position_BTC")),
                    o.select(t=pl.col("closedAt"), d=pl.col("hedge_position_BTC"))]).sort("t")
    net = np.cumsum(ev["d"].to_numpy())  # Jasper Vault's unhedged delta = minus the hedge position
    return {"max_abs_net_delta_BTC": float(np.abs(net).max()), "p95_abs_net_delta_BTC": float(np.percentile(np.abs(net), 95))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candles, events = load_candles(), load_events()
    mkt, mkt_h = build_market(candles, events), build_market(candles, events, load_holidays())
    orders = load_orders(config.TRAIN_CSV).filter(pl.col("realizedProfit_USDC").is_not_null())
    models = {"current model": (mkt, FINAL_VARIANT), "B. range and volume": (mkt, CANDIDATE_VARIANT),
              "C. US holidays": (mkt_h, FINAL_VARIANT), "B and C": (mkt_h, CANDIDATE_VARIANT)}

    skill = skill_table(models)
    skill.write_csv(OUT / "forecast_skill_candidates.csv")
    wf = walk_forward(models, orders)
    wf.write_csv(OUT / "walk_forward_candidates.csv")
    decision = decide(skill, wf)
    (OUT / "decision.json").write_text(json.dumps(decision, indent=2))

    # A. hedging and exposure limits on the training walk-forward (model prices)
    wfo = opening_delta_hedge(pl.read_parquet(config.RESULTS / "walk_forward_orders_priced.parquet"), candles)
    hs = hedge_table(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", "training, Feb to Jul, model price")
    ex = exposure_table(wfo, "model_premium_USDC", "realizedProfit_USDC", "training, Feb to Jul, model price")
    ex.append(policy_row(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", "training, Feb to Jul, model price"))
    exposure = {"training": net_exposure(wfo)}

    # A, post hoc on the validation period: frozen version 1 prices, payouts recomputed from closedAt
    from run_sealed_check import payout_at_close
    rec = pl.read_csv(config.OUTPUTS / "validation_recommendations.csv", infer_schema_length=0).select(
        pl.col("recommended_premium_USDC").cast(pl.Float64), (pl.col("expected_abs_move_bps").cast(pl.Float64) / 1e4).alias("expected_abs_move"))
    val = pl.concat([load_orders(config.VALID_CSV), rec], how="horizontal")
    val = opening_delta_hedge(val.with_columns(payout=pl.Series(payout_at_close(val, candles))), candles)
    hs += hedge_table(val, candles, "recommended_premium_USDC", "payout", "validation, Aug to Oct, frozen v1 price (post hoc)")
    ex += exposure_table(val, "recommended_premium_USDC", "payout", "validation, Aug to Oct, frozen v1 price (post hoc)")
    ex.append(policy_row(val, candles, "recommended_premium_USDC", "payout", "validation, Aug to Oct, frozen v1 price (post hoc)"))
    exposure["validation"] = net_exposure(val)
    pl.DataFrame(hs).write_csv(OUT / "hedging_summary.csv")
    pl.DataFrame(ex, infer_schema_length=None).write_csv(OUT / "exposure_limits.csv")
    (OUT / "net_exposure.json").write_text(json.dumps(exposure, indent=2))

    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_tbl_rows(40); pl.Config.set_fmt_str_lengths(50); pl.Config.set_float_precision(3)
    print(json.dumps(decision, indent=1), file=sys.stderr)
    print(wf, file=sys.stderr)
    print(pl.DataFrame(hs), file=sys.stderr)
    print(pl.DataFrame(ex, infer_schema_length=None), file=sys.stderr)
    print(json.dumps(exposure), file=sys.stderr)


if __name__ == "__main__":
    main()
