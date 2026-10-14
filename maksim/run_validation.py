"""Recommended premium for every order in the validation file.

The model is fitted once on BTC candles that closed before the end of the training period
(2026-07-31 17:11:12 UTC) and then frozen. For each validation order it uses only candles that
had closed before the order was created. `closedAt` is dropped before pricing: the source file still
contains it, and together with later prices it would reveal the hidden payout.

Outputs (outputs/):
  validation_recommendations.csv  the 13 original columns unchanged, plus the recommendation
  model_card.json                 fitted parameters, data fingerprints and settings
  FROZEN.json                     SHA-256 of the recommendation file, written last
"""
import hashlib
import json
import sys

import numpy as np
import polars as pl

from src import config
from src.data import load_candles, load_events, load_orders
from src.market import build_market
from src.pipeline import fit_pricer

ANNOUNCED_ROWS = 1898  # rows in the validation set described by the dataset guide
PREDICTION_COLUMNS = ["createdAt", "productType", "optionType", "quantity_BTC", "strikePrice", "apiBasePrice_per_BTC_USDC"]


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    mkt = build_market(load_candles(), load_events())
    pricer = fit_pricer(mkt, config.TRAIN_END)

    raw = pl.read_csv(config.VALID_CSV, infer_schema_length=0)  # original text, written back unchanged
    orders = load_orders(config.VALID_CSV).select(["row_id", *PREDICTION_COLUMNS, "notional_USDC", "T_min", "day"])
    priced = pricer.price(mkt, orders)
    if priced.height != raw.height or priced["model_premium_USDC"].is_null().any() or priced["model_premium_USDC"].is_nan().any():
        raise RuntimeError("every validation row must receive a finite premium")

    rec = priced.select(
        recommended_premium_USDC=pl.col("model_premium_USDC"),
        recommended_price_per_BTC_USDC=pl.col("price_per_btc"),
        recommended_multiplier_vs_base=pl.col("price_per_btc") / pl.col("apiBasePrice_per_BTC_USDC"),
        fair_value_per_BTC_USDC=pl.col("fair_value_per_btc"),
        expected_abs_move_bps=pl.col("expected_abs_move") * 1e4,
        macro_release_in_window=pl.col("event_in_window").cast(pl.Int8),
        floor_at_base_applied=pl.col("floor_applied").cast(pl.Int8),
    )
    out = pl.concat([raw, rec], how="horizontal")
    path = config.OUTPUTS / "validation_recommendations.csv"
    out.write_csv(path, float_precision=6, line_terminator="\r\n")  # same line endings as the input file

    has_base = priced["apiBasePrice_per_BTC_USDC"].is_not_null()
    mult = rec.filter(has_base.to_list())["recommended_multiplier_vs_base"].to_numpy()
    # The file has two blocks: the first 1,898 rows are the validation set announced in the dataset
    # guide (31 July 17:11:48 to 24 August 15:58:54 UTC, almost all with a base quote); the rest is a
    # later extension to 14 October with almost no base quotes and larger orders.
    blk = pl.concat([orders.select("row_id", "createdAt", "quantity_BTC", "notional_USDC", "apiBasePrice_per_BTC_USDC"), rec], how="horizontal").with_columns(
        block=pl.when(pl.col("row_id") < ANNOUNCED_ROWS).then(pl.lit("announced August set (rows 1 to 1,898)")).otherwise(pl.lit("extension (rows 1,899 to 4,155)")))
    if blk.filter(pl.col("row_id") < ANNOUNCED_ROWS)["createdAt"].max() > np.datetime64("2026-08-24T15:58:59"):
        raise RuntimeError("block boundary does not match the dataset guide")
    blocks = []
    for name, g in blk.group_by("block", maintain_order=True):
        gb = g.filter(pl.col("apiBasePrice_per_BTC_USDC").is_not_null())
        mb = gb["recommended_multiplier_vs_base"].to_numpy()
        blocks.append({
            "block": name[0], "rows": g.height, "first_createdAt": str(g["createdAt"].min()), "last_createdAt": str(g["createdAt"].max()),
            "rows_with_base": gb.height, "rows_floored": int(g["floor_at_base_applied"].sum()),
            "recommended_premium_USDC": float(g["recommended_premium_USDC"].sum()), "notional_USDC": float(g["notional_USDC"].sum()),
            "median_quantity_BTC": float(g["quantity_BTC"].median()),
            "multiplier_vs_base_p5_p50_p95": np.percentile(mb, [5, 50, 95]).round(3).tolist() if gb.height else None,
            "premium_weighted_multiplier_vs_base": float(gb["recommended_premium_USDC"].sum() / (gb["apiBasePrice_per_BTC_USDC"] * gb["quantity_BTC"]).sum()) if gb.height else None,
            "share_of_base_rows_with_multiplier_above_1_5": float((mb > 1.5).mean()) if gb.height else None,
        })
    card = {
        "model": "fair value from expected BTC move (recent volatility + US-Eastern time of day + scheduled CPI/NFP/FOMC releases), plus margin, floored at the API base price",
        "fit_end_utc": config.TRAIN_END,
        "margin": pricer.margin,
        "target_loss_ratio": config.TARGET_LOSS_RATIO,
        "floor_at_base": config.FLOOR_AT_BASE,
        "event_types": config.EVENT_TYPES,
        "event_jump_bps": float(np.sqrt(pricer.event_jump_var) * 1e4),
        "events_used_in_fit": pricer.n_events_fitted,
        "move_model_coefficients": pricer.move.coefficients().to_dicts(),
        "move_model_feature_scaling": {str(t): {"mean": p[0].mean_.tolist(), "scale": p[0].scale_.tolist()} for t, p in pricer.move.models.items()},
        "time_of_day_profile_weekday_then_weekend_et_half_hours": pricer.seas.profile.tolist(),
        "validation_rows": out.height,
        "rows_with_api_base": int(has_base.sum()),
        "rows_floored_at_base": int(rec["floor_at_base_applied"].sum()),
        "multiplier_vs_base_quantiles_p5_p25_p50_p75_p95": np.percentile(mult, [5, 25, 50, 75, 95]).round(3).tolist(),
        "recommended_premium_total_USDC": float(rec["recommended_premium_USDC"].sum()),
        "premium_weighted_multiplier_vs_base": float(rec.filter(has_base.to_list())["recommended_premium_USDC"].sum()
                                                     / (priced.filter(has_base)["apiBasePrice_per_BTC_USDC"] * priced.filter(has_base)["quantity_BTC"]).sum()),
        "blocks": blocks,
        "inputs_sha256": {"validation_csv": sha256(config.VALID_CSV), "btc_parquet": sha256(config.BTC_PARQUET),
                          "events_csv": sha256(config.EVENTS_CSV)},
    }
    (config.OUTPUTS / "model_card.json").write_text(json.dumps(card, indent=2))
    frozen = {"file": path.name, "sha256": sha256(path), "rows": out.height,
              "note": "Written before any look at outcomes in the validation period. Any later evaluation must use this exact file."}
    (config.OUTPUTS / "FROZEN.json").write_text(json.dumps(frozen, indent=2))
    print(json.dumps({k: v for k, v in card.items() if k not in ("move_model_coefficients", "move_model_feature_scaling",
                                                                "time_of_day_profile_weekday_then_weekend_et_half_hours")}, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
