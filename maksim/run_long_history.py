"""Long-history test of the pricing method on three years of BTC prices (2023 to 2025).

Question: the validation period is a few months. Does the method stay calibrated and profitable
over many months and different market regimes (2023 recovery, 2024 rally, 2025)?

Design (fixed before the first run):
- Prices: Binance BTCUSDT perpetual, one-minute closes, January 2023 to December 2025
  (download_long_history.py). No Jasper Vault orders exist for this period, so a synthetic order
  book is used: every 30 minutes, one call and one put for each product length. Each synthetic
  order's notional follows the training orders' mix of US-Eastern half hour (weekday or weekend)
  and product length, scaled to 10 million USDC of notional per month (about a third of June and
  July 2026). Payout: held to expiry, quantity x max(+/-(price at expiry minus strike), 0).
- Model: the simplest version (recent volatility and time of day; no release calendar, which was
  compiled for 2026 only), margin 25 percent, no base-price floor (no base quotes exist). Refitted
  at the start of every month on the previous six months only (rolling window), from July 2023.
- Benchmark: a plain Black-Scholes price with the realised volatility of the last 24 hours,
  constant through the day, scaled each month to collect the same total premium as the model.
  This isolates what time of day and the volatility forecast add.
- Reported per month and overall: loss ratio, payout / fair value, gross profit, Gini of the model
  against the benchmark, and the BTC change over the month.

Caveats: synthetic orders have no early closing and no buyer selection; real orders paid out 0.98
of fair value in February to July 2026. BTCUSDT is not the BTCUSDC contract used in the case data.

Outputs: results/long_history/*
"""
import json
import sys
from datetime import date, datetime

import numpy as np
import polars as pl

from src import config
from src.data import load_orders
from src.evaluate import daily_risk, ordered_lorenz
from src.market import build_market
from src.pipeline import fit_pricer

OUT = config.RESULTS / "long_history"
PRICES = config.ROOT / "data" / "btcusdt_1m_2023_2025.parquet"
VARIANT = "+ time of day"
FIT_MONTHS = 6
MONTHLY_NOTIONAL = 10_000_000.0
GRID_MIN = 30


def training_mix() -> pl.DataFrame:
    """Share of training notional by US-Eastern half hour (weekday/weekend) and product length."""
    o = load_orders(config.TRAIN_CSV).filter(pl.col("realizedProfit_USDC").is_not_null())
    et = o["createdAt"].dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    o = o.with_columns(bucket=pl.Series(et.dt.hour() * 2 + et.dt.minute() // 30 + 48 * (et.dt.weekday() >= 6).cast(pl.Int32)))
    g = o.group_by("bucket", "productType").agg(pl.col("notional_USDC").sum())
    return g.with_columns(share=pl.col("notional_USDC") / pl.col("notional_USDC").sum()).select("bucket", "productType", "share")


def synthetic_orders(mkt, start: str, end: str, mix: pl.DataFrame) -> pl.DataFrame:
    """Every GRID_MIN minutes in [start, end): a call and a put per product length, weighted by the mix."""
    t = pl.datetime_range(datetime.fromisoformat(start), datetime.fromisoformat(end), f"{GRID_MIN}m", eager=True, closed="left",
                          time_unit="us").alias("createdAt")
    et = t.dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    grid = pl.DataFrame({"createdAt": t, "bucket": et.dt.hour() * 2 + et.dt.minute() // 30 + 48 * (et.dt.weekday() >= 6).cast(pl.Int32)})
    per_bucket = grid.group_by("bucket").len()
    o = grid.join(mix, on="bucket", how="inner").join(per_bucket, on="bucket").with_columns(
        notional_USDC=pl.col("share") / pl.col("len") * MONTHLY_NOTIONAL / 2)  # / 2: call and put
    o = pl.concat([o.with_columns(optionType=pl.lit(0)), o.with_columns(optionType=pl.lit(1))])
    k = mkt.last_closed_index(o["createdAt"].to_numpy())
    t_min = (o["productType"].to_numpy() // 60).astype(np.int64)
    ok = k + t_min < mkt.n
    o, k, t_min = o.filter(pl.Series(ok)), k[ok], t_min[ok]
    s0, s1 = np.exp(mkt.logp[k]), np.exp(mkt.logp[k + t_min])
    sign = np.where(o["optionType"].to_numpy() == 0, 1.0, -1.0)
    q = o["notional_USDC"].to_numpy() / s0
    return o.with_columns(strikePrice=pl.Series(s0), quantity_BTC=pl.Series(q), payout=pl.Series(q * np.maximum(sign * (s1 - s0), 0.0)),
                          apiBasePrice_per_BTC_USDC=pl.lit(None, pl.Float64), day=pl.col("createdAt").dt.date())


def flat_bs_value(mkt, o: pl.DataFrame) -> np.ndarray:
    """Plain Black-Scholes at the money with the last 24 hours' realised volatility (no time of day)."""
    k = mkt.last_closed_index(o["createdAt"].to_numpy())
    var_per_min = mkt.trailing_var(k, 1440)
    sigma_window = np.sqrt(var_per_min * (o["productType"].to_numpy() // 60))
    return 0.398942 * o["strikePrice"].to_numpy() * sigma_window * o["quantity_BTC"].to_numpy()


def month_starts(first: str, last: str) -> list[str]:
    s = pl.date_range(date.fromisoformat(first), date.fromisoformat(last), "1mo", eager=True)
    return [str(d) for d in s]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = pl.read_parquet(PRICES)
    mkt = build_market(prices, pl.DataFrame({"event_type": [], "ts_utc": []}, schema={"event_type": pl.Utf8, "ts_utc": pl.Datetime("us")}))
    mix = training_mix()
    starts = month_starts("2023-01-01", "2026-01-01")
    rows, all_orders = [], []
    for i in range(FIT_MONTHS, len(starts) - 1):
        fit_start, m0, m1 = starts[i - FIT_MONTHS], starts[i], starts[i + 1]
        pr = fit_pricer(mkt, m0, VARIANT, fit_start=fit_start)
        o = pr.price(mkt, synthetic_orders(mkt, m0, m1, mix))
        bench = flat_bs_value(mkt, o)
        bench = bench * o["model_premium_USDC"].sum() / bench.sum()  # same total premium as the model
        o = o.with_columns(benchmark_premium_USDC=pl.Series(bench), month=pl.lit(m0[:7]))
        p, x, fv = o["model_premium_USDC"].to_numpy(), o["payout"].to_numpy(), o["fair_value_USDC"].to_numpy()
        btc0 = np.exp(mkt.logp[mkt.last_closed_index(np.array([np.datetime64(m0)]))[0]])
        btc1 = np.exp(mkt.logp[min(mkt.last_closed_index(np.array([np.datetime64(m1)]))[0], mkt.n - 1)])
        rows.append({"month": m0[:7], "orders": o.height, "premium": float(p.sum()), "payout": float(x.sum()),
                     "gross_profit": float((p - x).sum()), "loss_ratio": float(x.sum() / p.sum()),
                     "payout_over_fair_value": float(x.sum() / fv.sum()),
                     "benchmark_loss_ratio_same_premium": float(x.sum() / bench.sum()),
                     "gini_model_vs_flat_black_scholes": ordered_lorenz(bench, p, x)[2],
                     "btc_change_pct": float((btc1 / btc0 - 1) * 100)})
        all_orders.append(o.select("month", "day", "createdAt", "productType", "optionType", "model_premium_USDC", "benchmark_premium_USDC",
                                   "fair_value_USDC", "payout"))
        print(rows[-1]["month"], round(rows[-1]["loss_ratio"], 3), round(rows[-1]["gini_model_vs_flat_black_scholes"], 3), file=sys.stderr)
    monthly = pl.DataFrame(rows)
    monthly.write_csv(OUT / "monthly.csv")
    allo = pl.concat(all_orders)
    allo.write_parquet(OUT / "synthetic_orders_priced.parquet")

    d, x = allo["day"].to_numpy(), allo["payout"].to_numpy()
    p, b = allo["model_premium_USDC"].to_numpy(), allo["benchmark_premium_USDC"].to_numpy()
    dr_m, dr_b = daily_risk(d, p - x), daily_risk(d, b - x)
    days = np.unique(d)
    by_day = [np.where(d == dd)[0] for dd in days]
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(500):
        idx = np.concatenate([by_day[j] for j in rng.integers(0, len(days), len(days))])
        boots.append(ordered_lorenz(b[idx], p[idx], x[idx])[2])
    yearly = monthly.with_columns(year=pl.col("month").str.slice(0, 4)).group_by("year").agg(
        months=pl.len(), profitable_months=(pl.col("gross_profit") > 0).sum(), loss_ratio=pl.col("payout").sum() / pl.col("premium").sum(),
        payout_over_fair_value=pl.col("payout").sum() / (pl.col("premium").sum() / 1.25)).sort("year")
    summary = {
        "months": monthly.height, "profitable_months": int((monthly["gross_profit"] > 0).sum()),
        "loss_ratio_all": float(x.sum() / p.sum()), "payout_over_fair_value_all": float(x.sum() / allo["fair_value_USDC"].sum()),
        "worst_month": monthly.sort("loss_ratio", descending=True).row(0, named=True),
        "gini_model_vs_flat_black_scholes": ordered_lorenz(b, p, x)[2],
        "gini_ci05_ci95": np.percentile(boots, [5, 95]).tolist(),
        "months_with_positive_gini": int((monthly["gini_model_vs_flat_black_scholes"] > 0).sum()),
        "model_daily_risk": dr_m, "benchmark_daily_risk_same_premium": dr_b,
        "corr_loss_ratio_vs_abs_btc_change": float(np.corrcoef(monthly["loss_ratio"], np.abs(monthly["btc_change_pct"]))[0, 1]),
        "yearly": yearly.to_dicts(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("model_daily_risk", "benchmark_daily_risk_same_premium")}, indent=1, default=float), file=sys.stderr)


if __name__ == "__main__":
    main()
