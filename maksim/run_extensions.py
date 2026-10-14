"""Basic extensions to the pricing strategy, evaluated on training data (February to July 2026).

A. Delta hedging overlay. Jasper Vault is short every protection it sells. A static hedge opens a
   BTC perpetual position of delta x quantity when the protection opens (long for a call, short for
   a put; delta from Black-Scholes with the model's window volatility) and closes it when the
   protection closes. It does not change any price and has no fitted parameter. Assumed trading
   cost: 0.04 percent of hedge notional per side, with every order hedged on its own (an upper
   bound; netting the book's delta would trade less).
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


# ------------------------------------------------------------------ A: delta hedging
def close_price(candles: pl.DataFrame, t: np.ndarray) -> np.ndarray:
    return candles["close"].to_numpy()[minute_index(t, candles["ts"].to_numpy()[0])]


def hedge(o: pl.DataFrame, candles: pl.DataFrame, move_col: str = "expected_abs_move") -> pl.DataFrame:
    """Static delta hedge per order: perp position delta x quantity from open to close."""
    move = o[move_col].to_numpy()
    sigma = move * SQRT_PI_2
    d1 = 0.5 * sigma  # at the money: log(S / K) = 0
    call = o["optionType"].to_numpy() == 0
    delta = np.where(call, norm.cdf(d1), norm.cdf(d1) - 1.0)  # the option's delta; Jasper Vault is short it
    q, s0 = o["quantity_BTC"].to_numpy(), o["strikePrice"].to_numpy()
    s1 = close_price(candles, o["closedAt"].to_numpy())
    pos = delta * q  # hedge: hold +delta x quantity BTC, offsetting the short option's -delta x quantity
    return o.with_columns(hedge_position_BTC=pl.Series(pos), hedge_pnl_USDC=pl.Series(pos * (s1 - s0)),
                          hedge_cost_USDC=pl.Series(HEDGE_FEE_PER_SIDE * np.abs(pos) * (s0 + s1)))


def hedge_summary(o: pl.DataFrame, price_col: str, payout_col: str, label: str) -> list[dict]:
    p, x, d = o[price_col].to_numpy(), o[payout_col].to_numpy(), o["day"].to_numpy()
    h, c = o["hedge_pnl_USDC"].to_numpy(), o["hedge_cost_USDC"].to_numpy()
    rows = []
    for name, pnl in [("no hedge", p - x), ("delta hedge before costs", p - x + h), ("delta hedge after costs", p - x + h - c)]:
        r = daily_risk(d, pnl)
        rows.append({"sample": label, "book": name, "profit": float(pnl.sum()), **{k: r[k] for k in
                     ["sd_daily_pnl", "worst_day", "cvar5_daily", "max_drawdown", "share_losing_days"]}})
    return rows


BANDS_BTC = [0.0, 0.25, 0.5, 1.0]  # added after the per-order result: hedge the net book within a band


def band_hedge(o: pl.DataFrame, candles: pl.DataFrame, band: float) -> tuple[pl.DataFrame, float]:
    """Hedge the book's net delta, trading only when it drifts more than `band` BTC from the hedge.

    Returns daily hedge profit (before costs) and the total trading cost. The target hedge is the
    sum of open per-order hedge positions; the hedge is marked at the minute close of each event.
    """
    ev = pl.concat([o.select(t=pl.col("createdAt"), d=pl.col("hedge_position_BTC")),
                    o.select(t=pl.col("closedAt"), d=-pl.col("hedge_position_BTC"))]).sort("t")
    t, d = ev["t"].to_numpy(), ev["d"].to_numpy()
    px = close_price(candles, t)
    target, h, cost = 0.0, 0.0, 0.0
    pnl = np.zeros(len(t))
    for i in range(len(t)):
        if i:
            pnl[i] = h * (px[i] - px[i - 1])  # profit on the hedge held since the previous event
        target += d[i]
        if abs(target - h) > band:
            cost += HEDGE_FEE_PER_SIDE * abs(target - h) * px[i]
            h = target
    daily = pl.DataFrame({"day": t.astype("datetime64[D]"), "hedge": pnl}).with_columns(pl.col("day").cast(pl.Date)).group_by("day").agg(pl.col("hedge").sum())
    return daily, cost


def band_summary(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, label: str) -> list[dict]:
    book = o.group_by("day").agg((pl.col(price_col) - pl.col(payout_col)).sum().alias("book"))
    rows = []
    for band in BANDS_BTC:
        daily, cost = band_hedge(o, candles, band)
        j = book.join(daily, on="day", how="full", coalesce=True).fill_null(0.0).sort("day")
        total = (j["book"] + j["hedge"]).to_numpy()
        r = daily_risk(j["day"].to_numpy(), total)
        rows.append({"sample": label, "band_BTC": band, "profit_before_costs": float(total.sum()), "hedge_cost": cost,
                     "profit_after_costs": float(total.sum() - cost), **{k: r[k] for k in ["sd_daily_pnl", "worst_day", "max_drawdown"]}})
    return rows


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

    # A. hedging on the training walk-forward (current model prices)
    wfo = pl.read_parquet(config.RESULTS / "walk_forward_orders_priced.parquet")
    wfo = hedge(wfo, candles)
    hs = hedge_summary(wfo, "model_premium_USDC", "realizedProfit_USDC", "training, Feb to Jul, model price")
    hs += hedge_summary(wfo, "premiumAmount_USDC", "realizedProfit_USDC", "training, Feb to Jul, current price")
    monthly = wfo.group_by("month").agg(no_hedge=(pl.col("model_premium_USDC") - pl.col("realizedProfit_USDC")).sum(),
                                        hedge_pnl=pl.col("hedge_pnl_USDC").sum(), hedge_cost=pl.col("hedge_cost_USDC").sum()).with_columns(
        hedged_after_costs=pl.col("no_hedge") + pl.col("hedge_pnl") - pl.col("hedge_cost")).sort("month")
    monthly.write_csv(OUT / "hedging_training_monthly.csv")
    exposure = {"training": net_exposure(wfo)}

    # A, post hoc on the validation period: frozen version 1 prices, payouts recomputed from closedAt
    from run_sealed_check import payout_at_close
    rec = pl.read_csv(config.OUTPUTS / "validation_recommendations.csv", infer_schema_length=0).select(
        pl.col("recommended_premium_USDC").cast(pl.Float64), (pl.col("expected_abs_move_bps").cast(pl.Float64) / 1e4).alias("expected_abs_move"))
    val = pl.concat([load_orders(config.VALID_CSV), rec], how="horizontal")
    val = hedge(val.with_columns(payout=pl.Series(payout_at_close(val, candles))), candles)
    hs += hedge_summary(val, "recommended_premium_USDC", "payout", "validation, Aug to Oct, frozen v1 price (post hoc)")
    vm = val.with_columns(month=pl.col("createdAt").dt.strftime("%Y-%m")).group_by("month").agg(
        no_hedge=(pl.col("recommended_premium_USDC") - pl.col("payout")).sum(), hedge_pnl=pl.col("hedge_pnl_USDC").sum(),
        hedge_cost=pl.col("hedge_cost_USDC").sum()).with_columns(hedged_after_costs=pl.col("no_hedge") + pl.col("hedge_pnl") - pl.col("hedge_cost")).sort("month")
    vm.write_csv(OUT / "hedging_validation_monthly_post_hoc.csv")
    exposure["validation"] = net_exposure(val)
    pl.DataFrame(hs).write_csv(OUT / "hedging_summary.csv")
    bands = band_summary(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", "training, Feb to Jul, model price")
    bands += band_summary(val, candles, "recommended_premium_USDC", "payout", "validation, Aug to Oct, frozen v1 price (post hoc)")
    pl.DataFrame(bands).write_csv(OUT / "hedging_net_book_bands.csv")
    print(pl.DataFrame(bands), file=sys.stderr)
    (OUT / "net_exposure.json").write_text(json.dumps(exposure, indent=2))

    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_tbl_rows(40); pl.Config.set_fmt_str_lengths(50); pl.Config.set_float_precision(3)
    print(json.dumps(decision, indent=1), file=sys.stderr)
    print(wf, file=sys.stderr)
    print(pl.DataFrame(hs), file=sys.stderr)
    print(monthly, vm, json.dumps(exposure), sep="\n", file=sys.stderr)


if __name__ == "__main__":
    main()
