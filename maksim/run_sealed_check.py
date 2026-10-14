"""One-time check of the frozen validation recommendations against August to October outcomes.

The validation file hides payouts, but it still contains closedAt, and the supplied BTC history
runs to 14 October 2026, so each payout can be recomputed as
quantity x max(+/-(BTC price at close minus strike), 0). This script:

1. refuses to run unless outputs/validation_recommendations.csv matches the SHA-256 in
   outputs/FROZEN.json and that exact file is committed in git (so the prices provably existed
   before any outcome was looked at);
2. measures how accurately this reconstruction reproduces the known payouts of training orders;
3. scores the frozen prices, the API base price and a flat markup on the base against the
   reconstructed validation payouts.

It is run once. The model is not changed afterwards, whatever the result.
Outputs: results/sealed_check/*
"""
import hashlib
import json
import subprocess
import sys

import numpy as np
import polars as pl

from src import config
from src.data import load_candles, load_orders, minute_index
from src.evaluate import conversion_weight, daily_risk, ordered_lorenz

OUT = config.RESULTS / "sealed_check"
REC = config.OUTPUTS / "validation_recommendations.csv"


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frozen() -> dict:
    frozen = json.loads((config.OUTPUTS / "FROZEN.json").read_text())
    if sha256(REC) != frozen["sha256"]:
        sys.exit("recommendation file does not match FROZEN.json; refusing to run")
    rel = REC.relative_to(config.REPO)
    log = subprocess.run(["git", "-C", str(config.REPO), "log", "-1", "--format=%H %cI", "--", str(rel)],
                         capture_output=True, text=True, check=True).stdout.strip()
    if not log:
        sys.exit("recommendation file is not committed; commit and push it before running this check")
    committed = subprocess.run(["git", "-C", str(config.REPO), "show", f"HEAD:{rel}"], capture_output=True, check=True).stdout
    if hashlib.sha256(committed).hexdigest() != frozen["sha256"]:
        sys.exit("committed recommendation file differs from FROZEN.json; refusing to run")
    commit, when = log.split()
    return {"sha256": frozen["sha256"], "commit": commit, "commit_time": when}


def payout_at_close(orders: pl.DataFrame, candles: pl.DataFrame) -> np.ndarray:
    """quantity x intrinsic value at the close of the one-minute candle containing closedAt.

    On training orders this convention reproduces the recorded payout total to within 0.3 percent
    (see run_descriptive.py and the reconstruction check below)."""
    t0 = candles["ts"].to_numpy()[0]
    k = minute_index(orders["closedAt"].to_numpy(), t0)
    px = candles["close"].to_numpy()[k]
    sign = np.where(orders["optionType"].to_numpy() == 0, 1.0, -1.0)
    return orders["quantity_BTC"].to_numpy() * np.maximum(sign * (px - orders["strikePrice"].to_numpy()), 0.0)


def reconstruction_accuracy(candles: pl.DataFrame) -> dict:
    tr = load_orders(config.TRAIN_CSV).filter(pl.col("realizedProfit_USDC").is_not_null() & pl.col("closedAt").is_not_null())
    rec = payout_at_close(tr, candles)
    act = tr["realizedProfit_USDC"].to_numpy()
    per_btc = np.abs(rec - act) / tr["quantity_BTC"].to_numpy()
    return {"training_orders": tr.height, "sum_reconstructed": float(rec.sum()), "sum_actual": float(act.sum()),
            "ratio_reconstructed_over_actual": float(rec.sum() / act.sum()),
            "median_abs_error_per_btc": float(np.median(per_btc)), "share_within_30_usdc_per_btc": float((per_btc < 30).mean())}


def score(name: str, p: np.ndarray, x: np.ndarray, ref: np.ndarray, day: np.ndarray) -> list[dict]:
    rows = []
    for scen, w in [("no demand response", np.ones_like(p)), ("elasticity 1 vs base", conversion_weight(p, ref, 1.0)),
                    ("elasticity 2 vs base", conversion_weight(p, ref, 2.0)), ("keep if at most 1.5 x base", (p <= 1.5 * ref).astype(float))]:
        prem, pay = float((w * p).sum()), float((w * x).sum())
        rows.append({"strategy": name, "scenario": scen, "orders": float(w.sum()), "premium": prem, "payout": pay,
                     "profit": prem - pay, "loss_ratio": pay / prem if prem else np.nan, **daily_risk(day, w * (p - x))})
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = check_frozen()
    candles = load_candles()
    acc = reconstruction_accuracy(candles)

    rec = pl.read_csv(REC, infer_schema_length=0).select(
        pl.col("recommended_premium_USDC").cast(pl.Float64), pl.col("fair_value_per_BTC_USDC").cast(pl.Float64))
    val = pl.concat([load_orders(config.VALID_CSV), rec], how="horizontal")
    val = val.with_columns(payout=pl.Series(payout_at_close(val, candles)), month=pl.col("createdAt").dt.strftime("%Y-%m"),
                           fv_usd=pl.col("fair_value_per_BTC_USDC") * pl.col("quantity_BTC"))
    k_flat = float(load_orders(config.TRAIN_CSV).filter(pl.col("base_premium_USDC").is_not_null() & pl.col("realizedProfit_USDC").is_not_null())
                   .select(pl.col("premiumAmount_USDC").sum() / pl.col("base_premium_USDC").sum()).item())

    rows = []
    m = val.filter(pl.col("base_premium_USDC").is_not_null())
    x, b, d, p = (m[c].to_numpy() for c in ["payout", "base_premium_USDC", "day", "recommended_premium_USDC"])
    for name, price in [("model (frozen)", p), ("API base price", b), (f"flat markup x{k_flat:.2f} on base", b * k_flat)]:
        rows += [r | {"subset": "orders with an API base price"} for r in score(name, price, x, b, d)]
    allx, alld, allp = val["payout"].to_numpy(), val["day"].to_numpy(), val["recommended_premium_USDC"].to_numpy()
    rows.append({"strategy": "model (frozen)", "scenario": "no demand response", "subset": "all orders", "orders": float(val.height),
                 "premium": float(allp.sum()), "payout": float(allx.sum()), "profit": float((allp - allx).sum()),
                 "loss_ratio": float(allx.sum() / allp.sum()), **daily_risk(alld, allp - allx)})
    cur = val.filter(pl.col("markup_per_BTC_USDC").is_not_null() & pl.col("base_premium_USDC").is_not_null()).with_columns(
        current=(pl.col("apiBasePrice_per_BTC_USDC") + pl.col("markup_per_BTC_USDC")) * pl.col("quantity_BTC"))
    for name, col in [("current price (base + markup, where recorded)", "current"), ("model (frozen)", "recommended_premium_USDC")]:
        pc, xc = cur[col].to_numpy(), cur["payout"].to_numpy()
        rows.append({"strategy": name, "scenario": "no demand response", "subset": "orders with a recorded markup", "orders": float(cur.height),
                     "premium": float(pc.sum()), "payout": float(xc.sum()), "profit": float((pc - xc).sum()), "loss_ratio": float(xc.sum() / pc.sum())})
    table = pl.DataFrame(rows)
    table.write_csv(OUT / "sealed_check_results.csv")

    monthly = val.group_by("month").agg(orders=pl.len(), premium=pl.col("recommended_premium_USDC").sum(), payout=pl.col("payout").sum(),
                                        fair_value=pl.col("fv_usd").sum()).with_columns(
        profit=pl.col("premium") - pl.col("payout"), loss_ratio=pl.col("payout") / pl.col("premium"),
        payout_over_fair_value=pl.col("payout") / pl.col("fair_value")).sort("month")
    monthly.write_csv(OUT / "sealed_check_monthly.csv")

    # Diagnostics (to explain the result, not to change the model): direction, BTC trend, and the
    # realised move on order windows against the model's expected move.
    t0 = candles["ts"].to_numpy()[0]
    k0 = minute_index(val["createdAt"].to_numpy(), t0) - 1
    k1 = minute_index(val["expirationDate"].to_numpy(), t0)
    logc = np.log(candles["close"].to_numpy())
    val = val.with_columns(realised_abs_move_bps=pl.Series(np.abs(logc[k1] - logc[k0]) * 1e4),
                           expected_abs_move_bps=pl.col("expected_abs_move_bps").cast(pl.Float64) if "expected_abs_move_bps" in val.columns else pl.lit(None))
    exp_move = pl.read_csv(REC, infer_schema_length=0)["expected_abs_move_bps"].cast(pl.Float64)
    val = val.with_columns(expected_abs_move_bps=exp_move)
    by_dir = val.group_by("month", "optionType_label").agg(
        orders=pl.len(), premium=pl.col("recommended_premium_USDC").sum(), payout=pl.col("payout").sum(),
        payout_over_fair_value=pl.col("payout").sum() / pl.col("fv_usd").sum(),
        realised_over_expected_move=pl.col("realised_abs_move_bps").mean() / pl.col("expected_abs_move_bps").mean(),
    ).sort("month", "optionType_label")
    by_dir.write_csv(OUT / "sealed_check_by_month_and_direction.csv")
    btc = candles.filter(pl.col("ts") >= np.datetime64("2026-07-01")).group_by(pl.col("ts").dt.strftime("%Y-%m").alias("month")).agg(
        first=pl.col("open").first(), last=pl.col("close").last()).with_columns(change_pct=(pl.col("last") / pl.col("first") - 1) * 100).sort("month")
    btc.write_csv(OUT / "btc_monthly_change.csv")
    print(by_dir, file=sys.stderr)
    print(btc, file=sys.stderr)
    summary = {"frozen_file": frozen, "payout_reconstruction_on_training": acc, "validation_orders": val.height,
               "orders_with_base": m.height, "flat_markup_on_base": k_flat,
               "gini_model_vs_base": ordered_lorenz(b, p, x)[2], "gini_flat_vs_base": 0.0,
               "payout_over_fair_value_all": float(allx.sum() / val["fv_usd"].sum())}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(220); pl.Config.set_tbl_rows(40); pl.Config.set_fmt_str_lengths(45); pl.Config.set_float_precision(3)
    print(json.dumps(summary, indent=1), file=sys.stderr)
    print(table.select("subset", "strategy", "scenario", "orders", "premium", "payout", "profit", "loss_ratio", "worst_day", "max_drawdown"), file=sys.stderr)
    print(monthly, file=sys.stderr)


if __name__ == "__main__":
    main()
