"""Chronological backtest of the PP pricing model on the training period (February to July 2026).

Design. The model is fitted on BTC market data before 1 June 2026 and tested on the 4,841
orders created in June and July. A walk-forward run repeats this for every month from
February to July, each month priced by a model fitted only on earlier data. Orders whose
payout is blank in the source file (54 orders without a close time) are excluded from every
evaluation.

Outputs in results/ (see README for a description of each file).
"""
import json
import sys

import numpy as np
import polars as pl

from src import config
from src.data import load_candles, load_events, load_orders, minute_index
from src.evaluate import (conversion_weight, evaluate, evaluate_scenarios, gini_with_interval,
                          move_forecast_scores, ordered_lorenz, threshold_weight)
from src.market import build_market, market_sample
from src.model import FINAL_VARIANT, VARIANTS, add_event_jump
from src.pipeline import fit_pricer

CURRENT = "current price (base + CTA markup)"
BASE = "API base price"
MONTHS = [("2026-02-01", "2026-03-01"), ("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"),
          ("2026-05-01", "2026-06-01"), ("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-08-01")]


def ts(s: str) -> pl.Expr:
    return pl.lit(np.datetime64(s)).cast(pl.Datetime("us"))


def flat_markup(orders: pl.DataFrame, before: str) -> float | None:
    """Current average markup over the API base price, from orders that expired before `before`."""
    m = orders.filter((pl.col("expirationDate") < ts(before)) & pl.col("base_premium_USDC").is_not_null())
    return float(m["premiumAmount_USDC"].sum() / m["base_premium_USDC"].sum()) if m.height else None


def move_scores(mkt, pricers: dict, k_from: int, k_to: int) -> pl.DataFrame:
    rows = []
    for name, pr in pricers.items():
        for t_s in config.DURATIONS_S:
            k = market_sample(mkt, k_from, k_to, t_s // 60, config.SAMPLE_STEP_MIN)
            t = np.full(len(k), t_s)
            y = mkt.forward_abs_return(k, t // 60) * 1e4
            p = pr.move.predict_abs_move(mkt, pr.seas, k, t, pr.hmm)
            p = add_event_jump(p, mkt.events_in_window(k, t // 60), pr.event_jump_var) * 1e4
            rows.append({"variant": name, "productType": t_s, "n_windows": len(k), **move_forecast_scores(y, p)})
    return pl.DataFrame(rows)


def ranking_table(priced: pl.DataFrame, pricers: dict, mkt) -> pl.DataFrame:
    """Gini of each candidate premium against the current price and against the base price."""
    m = priced.filter(pl.col("base_premium_USDC").is_not_null())
    x, a, b, d = m["realizedProfit_USDC"].to_numpy(), m["premiumAmount_USDC"].to_numpy(), m["base_premium_USDC"].to_numpy(), m["day"].to_numpy()
    rows = [{"candidate": CURRENT, "reference": BASE, **gini_with_interval(b, a, x, d)},
            {"candidate": BASE, "reference": CURRENT, **gini_with_interval(a, b, x, d)}]
    for name, pr in pricers.items():
        fv = pr.fair_value(mkt, m)["fair_value_USDC"].to_numpy()
        rows.append({"candidate": f"model: {name}", "reference": CURRENT, **gini_with_interval(a, fv, x, d)})
        rows.append({"candidate": f"model: {name}", "reference": BASE, **gini_with_interval(b, fv, x, d)})
        if name == FINAL_VARIANT:  # does the base price add information once the model is known?
            rows.append({"candidate": BASE, "reference": f"model: {name}", **gini_with_interval(fv, b, x, d)})
    return pl.DataFrame(rows)


def equal_revenue_test(priced: pl.DataFrame, k_flat: float) -> pl.DataFrame:
    """Every strategy is rescaled to collect the same total premium as current pricing.

    The scale uses test-period totals, so this is a diagnostic of how well each strategy
    allocates a fixed amount of premium across orders (better pricing at the same price level),
    not a deployable price. Run on all orders and on orders with a base quote.
    """
    out = []
    for subset, m in [("all orders", priced), ("orders with an API base price", priced.filter(pl.col("base_premium_USDC").is_not_null()))]:
        a = m["premiumAmount_USDC"].to_numpy()
        cands = {CURRENT: a, "model": m["model_premium_USDC"].to_numpy()}
        if subset != "all orders":
            cands[f"flat markup x{k_flat:.2f} on base"] = m["base_premium_USDC"].to_numpy() * k_flat
        scaled = {n: (p * a.sum() / p.sum() if n != CURRENT else a) for n, p in cands.items()}
        out.append(evaluate_scenarios(scaled, m["realizedProfit_USDC"].to_numpy(), a, m["day"].to_numpy(),
                                      elasticities=[0.5, 1.0, 2.0], tolerances=(0.0, 0.25)).with_columns(subset=pl.lit(subset)))
    return pl.concat(out)


def margin_grid(priced: pl.DataFrame) -> pl.DataFrame:
    a, x, d = priced["premiumAmount_USDC"].to_numpy(), priced["realizedProfit_USDC"].to_numpy(), priced["day"].to_numpy()
    fv = priced["fair_value_USDC"].to_numpy()
    base = priced["base_premium_USDC"].fill_null(0.0).to_numpy()  # no quote: no floor
    rows = []
    for m in config.MARGIN_GRID:
        p = np.maximum(fv * (1 + m), base) if config.FLOOR_AT_BASE else fv * (1 + m)
        for e in config.ELASTICITIES:
            r = evaluate(f"model margin {m:.0%}", p, x, a, d, conversion_weight(p, a, e), f"elasticity={e:g}")
            rows.append({**r, "margin": m, "elasticity": e})
        for tol in (0.0, 0.25):
            r = evaluate(f"model margin {m:.0%}", p, x, a, d, threshold_weight(p, a, tol), f"keep_if_within_{int(tol * 100)}pct")
            rows.append({**r, "margin": m, "elasticity": None})
    for e in config.ELASTICITIES:
        rows.append({**evaluate(CURRENT, a, x, a, d, None, f"elasticity={e:g}"), "margin": None, "elasticity": e})
    return pl.DataFrame(rows)


def walk_forward(mkt, orders: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Price every month with a model fitted only on data before that month."""
    res, priced_all = [], []
    for start, end in MONTHS:
        pr = fit_pricer(mkt, start)
        mo = orders.filter((pl.col("createdAt") >= ts(start)) & (pl.col("createdAt") < ts(end)))
        p = pr.price(mkt, mo).with_columns(month=pl.lit(start[:7]))
        priced_all.append(p)
        a, x, d = p["premiumAmount_USDC"].to_numpy(), p["realizedProfit_USDC"].to_numpy(), p["day"].to_numpy()
        strat = {CURRENT: a, "model": p["model_premium_USDC"].to_numpy()}
        kf = flat_markup(orders, start)
        if kf is not None:
            flat = (p["base_premium_USDC"] * kf).to_numpy()
            strat[f"flat markup on base"] = np.where(np.isnan(flat), a, flat)  # no base quote: keep current price
        r = evaluate_scenarios(strat, x, a, d, elasticities=(0.0, 1.0), tolerances=(0.0, 0.25))
        g = ordered_lorenz(a, p["fair_value_USDC"].to_numpy(), x)[2]
        res.append(r.with_columns(month=pl.lit(start[:7]), orders=pl.lit(mo.height), gini_model_vs_current=pl.lit(g),
                                  event_jump_bps=pl.lit(np.sqrt(pr.event_jump_var) * 1e4)))
    return pl.concat(res), pl.concat(priced_all)


def segments(priced: pl.DataFrame) -> pl.DataFrame:
    seg = priced.with_columns(
        hour_utc=((pl.col("createdAt").dt.hour() // 4) * 4).cast(pl.Utf8).str.zfill(2) + ":00-" + ((pl.col("createdAt").dt.hour() // 4) * 4 + 4).cast(pl.Utf8).str.zfill(2) + ":00",
        direction=pl.col("optionType_label"),
        duration=(pl.col("productType") / 3600).round(1).cast(pl.Utf8) + "h",
        release=pl.when(pl.col("event_in_window") > 0).then(pl.lit("release in window")).otherwise(pl.lit("no release")),
    )
    out = []
    for col in ["duration", "tier", "hour_utc", "direction", "release"]:
        out.append(seg.group_by(col).agg(
            orders=pl.len(), notional=pl.col("notional_USDC").sum(), payout=pl.col("realizedProfit_USDC").sum(),
            current_premium=pl.col("premiumAmount_USDC").sum(), fair_value=pl.col("fair_value_USDC").sum(),
            model_premium=pl.col("model_premium_USDC").sum(),
        ).with_columns(
            segment_type=pl.lit(col), segment=pl.col(col).cast(pl.Utf8),
            current_loss_ratio=pl.col("payout") / pl.col("current_premium"),
            model_loss_ratio=pl.col("payout") / pl.col("model_premium"),
            payout_over_fair_value=pl.col("payout") / pl.col("fair_value"),
            model_vs_current_price=pl.col("model_premium") / pl.col("current_premium") - 1,
        ).drop(col))
    return pl.concat(out, how="diagonal").select(
        "segment_type", "segment", "orders", "notional", "payout", "current_premium", "fair_value", "model_premium",
        "current_loss_ratio", "model_loss_ratio", "payout_over_fair_value", "model_vs_current_price").sort("segment_type", "segment")


def price_change(priced: pl.DataFrame) -> dict:
    """How the model price compares with today's price, by order count and by premium."""
    r = (priced["model_premium_USDC"] / priced["premiumAmount_USDC"]).to_numpy()
    a = priced["premiumAmount_USDC"].to_numpy()
    by_tier = priced.group_by("tier").agg((pl.col("model_premium_USDC").sum() / pl.col("premiumAmount_USDC").sum() - 1).alias("change"),
                                          (pl.col("premiumAmount_USDC").sum() / priced["premiumAmount_USDC"].sum()).alias("share_of_current_premium"))
    return {"share_of_orders_cheaper": float((r < 1).mean()), "median_ratio": float(np.median(r)),
            "share_of_current_premium_priced_up": float(a[r > 1].sum() / a.sum()),
            "total_premium_change": float(priced["model_premium_USDC"].sum() / a.sum() - 1),
            "by_tier": {row["tier"]: {"premium_change": row["change"], "share_of_current_premium": row["share_of_current_premium"]} for row in by_tier.to_dicts()}}


def worst_days(priced: pl.DataFrame, candles: pl.DataFrame, n: int = 5) -> pl.DataFrame:
    """The worst days of the model's book (no demand response) with the BTC move that day."""
    day_px = candles.group_by(pl.col("ts").dt.date().alias("day")).agg(
        btc_open=pl.col("open").first(), btc_close=pl.col("close").last(), btc_high=pl.col("high").max(), btc_low=pl.col("low").min())
    d = priced.group_by("day").agg(
        orders=pl.len(), model_pnl=(pl.col("model_premium_USDC") - pl.col("realizedProfit_USDC")).sum(),
        current_pnl=(pl.col("premiumAmount_USDC") - pl.col("realizedProfit_USDC")).sum(), payout=pl.col("realizedProfit_USDC").sum(),
        share_of_payout_from_largest_order=pl.col("realizedProfit_USDC").max() / pl.col("realizedProfit_USDC").sum(),
    ).join(day_px, on="day", how="left").with_columns(
        btc_change_pct=(pl.col("btc_close") / pl.col("btc_open") - 1) * 100, btc_range_pct=(pl.col("btc_high") / pl.col("btc_low") - 1) * 100)
    return d.sort("model_pnl").head(n)


def payout_over_fv_by(priced: pl.DataFrame, col: str) -> pl.DataFrame:
    """Payout / fair value with a day-block 90 percent interval, using out-of-sample fair values."""
    rows = []
    rng = np.random.default_rng(1)
    for g in sorted(priced[col].unique().to_list()):
        s = priced.filter(pl.col(col) == g).group_by("day").agg(pl.col("realizedProfit_USDC").sum().alias("x"), pl.col("fair_value_USDC").sum().alias("f"))
        x, f = s["x"].to_numpy(), s["f"].to_numpy()
        idx = rng.integers(0, len(x), size=(2000, len(x)))
        boots = x[idx].sum(1) / f[idx].sum(1)
        rows.append({"group_by": col, "group": str(g), "orders": priced.filter(pl.col(col) == g).height,
                     "payout_over_fair_value": x.sum() / f.sum(), "ci05": np.percentile(boots, 5), "ci95": np.percentile(boots, 95)})
    return pl.DataFrame(rows)


def main() -> None:
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    candles, events = load_candles(), load_events()
    mkt = build_market(candles, events)
    raw = load_orders(config.TRAIN_CSV)
    orders = raw.filter(pl.col("realizedProfit_USDC").is_not_null())
    print(f"orders {raw.height} ({raw.height - orders.height} without payout excluded), candles {mkt.n}, releases {events.height}", file=sys.stderr)

    test = orders.filter(pl.col("createdAt") >= ts(config.DEV_SPLIT))
    k_split = int(minute_index(np.array([np.datetime64(config.DEV_SPLIT)]), mkt.t0)[0]) - 1
    k_end = int(minute_index(np.array([np.datetime64(config.TRAIN_END)]), mkt.t0)[0]) - 1

    pricers = {name: fit_pricer(mkt, config.DEV_SPLIT, name) for name in VARIANTS}
    final = pricers[FINAL_VARIANT]

    # 1. accuracy of the expected-move forecast on June-July market windows
    scores = move_scores(mkt, pricers, k_split + 1, k_end)
    scores.write_csv(config.RESULTS / "move_forecast_scores.csv")

    # 2. order-level prices for the test period
    k_flat = flat_markup(orders, config.DEV_SPLIT)
    priced = final.price(mkt, test).with_columns(flat_premium_USDC=pl.col("base_premium_USDC") * k_flat)
    priced.write_parquet(config.RESULTS / "test_orders_priced.parquet")

    # 3. ranking power (does a premium charge more where payouts are larger?)
    ranking = ranking_table(priced, pricers, mkt)
    ranking.write_csv(config.RESULTS / "ranking_gini_test_period.csv")

    # 4. deployable comparison at the target margin
    matched = priced.filter(pl.col("base_premium_USDC").is_not_null())
    bt = evaluate_scenarios(
        {CURRENT: matched["premiumAmount_USDC"].to_numpy(), BASE: matched["base_premium_USDC"].to_numpy(),
         f"flat markup x{k_flat:.2f} on base": matched["flat_premium_USDC"].to_numpy(), "model": matched["model_premium_USDC"].to_numpy()},
        matched["realizedProfit_USDC"].to_numpy(), matched["premiumAmount_USDC"].to_numpy(), matched["day"].to_numpy(),
        config.ELASTICITIES, base=matched["base_premium_USDC"].to_numpy(), base_caps=(1.5, 2.0)
    ).with_columns(subset=pl.lit("orders with an API base price"))
    # Benchmarks for "better, not just higher": raise every current price by the same factor.
    # level = model total premium / current total premium on the test orders (evaluation only).
    a_all = priced["premiumAmount_USDC"].to_numpy()
    level = float(priced["model_premium_USDC"].sum() / priced["premiumAmount_USDC"].sum())
    bt_all = evaluate_scenarios(
        {CURRENT: a_all, "model": priced["model_premium_USDC"].to_numpy(),
         f"flat raise of current price x{level:.3f} (same total as model)": a_all * level,
         "flat raise of current price x1.25": a_all * 1.25},
        priced["realizedProfit_USDC"].to_numpy(), a_all, priced["day"].to_numpy(),
        config.ELASTICITIES).with_columns(subset=pl.lit("all orders"))
    backtest = pl.concat([bt, bt_all])
    backtest.write_csv(config.RESULTS / "backtest_test_period.csv")

    # 5. allocation at equal total premium, 6. margin sensitivity
    eqrev = equal_revenue_test(priced, k_flat)
    eqrev.write_csv(config.RESULTS / "equal_revenue_test_period.csv")
    grid = margin_grid(priced)
    grid.write_csv(config.RESULTS / "margin_sensitivity_test_period.csv")

    # 7. walk-forward by month, 8. segments, 9. size and direction diagnostics
    wf, wf_priced = walk_forward(mkt, orders)
    wf.write_csv(config.RESULTS / "walk_forward_monthly.csv")
    wf_priced.write_parquet(config.RESULTS / "walk_forward_orders_priced.parquet")
    segments(priced).write_csv(config.RESULTS / "segments_test_period.csv")
    worst_days(priced, candles).write_csv(config.RESULTS / "worst_days_test_period.csv")
    diag = pl.concat([payout_over_fv_by(wf_priced, c) for c in ["tier", "optionType_label", "month"]]
                     + [payout_over_fv_by(wf_priced.with_columns(all=pl.lit("all orders")), "all")])
    diag.write_csv(config.RESULTS / "payout_over_fair_value_walk_forward.csv")
    final.move.coefficients().write_csv(config.RESULTS / "move_model_coefficients_dev.csv")
    pl.DataFrame({"et_half_hour": [f"{(i % 48) // 2:02d}:{30 * (i % 2):02d}" for i in range(96)],
                  "day_type": ["weekday"] * 48 + ["weekend"] * 48, "relative_variance": final.seas.profile}).write_csv(
        config.RESULTS / "time_of_day_profile_dev.csv")

    def pick(df, strat, scen, subset):
        r = df.filter((pl.col("strategy") == strat) & (pl.col("scenario") == scen) & (pl.col("subset") == subset))
        return r.to_dicts()[0] if r.height else None
    summary = {
        "dev_split": config.DEV_SPLIT, "orders_excluded_blank_payout": raw.height - orders.height,
        "test_orders": test.height, "test_orders_with_base": matched.height, "flat_markup_on_base": k_flat,
        "margin": final.margin, "event_jump_bps": float(np.sqrt(final.event_jump_var) * 1e4), "events_fitted": final.n_events_fitted,
        "price_change": price_change(priced),
        "all_orders": {s: {sc: pick(backtest, s, sc, "all orders") for sc in ["elasticity=0", "elasticity=1", "elasticity=2", "keep_if_within_0pct"]}
                       for s in [CURRENT, "model"]},
    }
    (config.RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float))

    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(250); pl.Config.set_tbl_rows(80); pl.Config.set_fmt_str_lengths(45)
    print(scores.group_by("variant").agg(pl.col("mean_poisson_deviance").mean().alias("dev"), pl.col("spearman").mean(),
                                         pl.col("calibration_actual_over_pred").mean().alias("calib")).sort("dev"))
    print(ranking)
    cols = ["subset", "strategy", "scenario", "premium", "payout", "profit", "loss_ratio", "sharpe_annualised", "worst_day",
            "cvar5_daily", "max_drawdown", "median_price_vs_current", "share_cheaper_than_current"]
    print(backtest.select(cols))
    print(eqrev.select([c for c in cols if c != "subset"]))
    print(wf.select("month", "orders", "strategy", "scenario", "premium", "payout", "profit", "loss_ratio", "gini_model_vs_current", "event_jump_bps"))
    print(diag)
    print(json.dumps({k: v for k, v in summary.items() if k != "all_orders"}, indent=1, default=float))


if __name__ == "__main__":
    main()
