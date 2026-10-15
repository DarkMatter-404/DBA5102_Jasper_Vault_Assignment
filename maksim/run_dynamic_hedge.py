"""Dynamic delta hedge of the PP book: a risk overlay chosen on training data. Prices do not change.

Why it was added (after the validation check, section 6 of the README): the August loss came from
the direction of BTC's move, not its size. Realised moves on August order windows were 0.87 to 0.92
of the model's forecasts, yet protection for short positions paid 2.0 times its fair value while
BTC rose 25 percent. Direction is the risk a delta hedge removes. The earlier overlay
(run_extensions.py) fixed each protection's delta at opening; here the delta is recomputed every
minute from the price and the time left, as an option seller normally runs its book (src/hedge.py).

PRE-REGISTERED RULE (written and committed before the validation mode was first run):
  Grid (round numbers): check the hedge every 1, 5 or 15 minutes and at every order open or close;
    trade when it is more than 0.1, 0.25, 0.5, 1 or 2 BTC away from the book's delta. (The 2 BTC band
    was added after the first training run put the best setting at the edge of the grid, 1 BTC.)
  Costs: 0.04 percent of traded notional per side, as in run_extensions.py.
  Score: mean daily gross profit after hedge fees divided by its standard deviation, on the
    February to July walk-forward (model prices, the same orders as section 5.2).
  Adopt the configuration with the highest score, provided it beats both the unhedged book and the
    current policy (cap 250,000 USDC per direction plus the opening-delta hedge within 0.5 BTC).
    Otherwise adopt nothing and keep the current policy.
  The adopted configuration is then run once on the validation period with the frozen version 1
    prices and reported whatever it shows. Also reported there, as fixed in advance: the same metrics
    for the unhedged book and the current policy, results by month, a fee sensitivity (0.02 and
    0.05 percent per side), and the ranking of the model against the base price measured on hedged
    cost (payout minus the profit of hedging that protection on its own every minute).
  Not modelled: funding payments on the perpetual hedge. Each row reports the average absolute hedge
    (BTC) and a funding cost bound at 0.01 percent per 8 hours, assuming every payment goes against
    the hedge.

Usage:
  python run_dynamic_hedge.py              training grid and decision -> results/dynamic_hedge/decision.json
  python run_dynamic_hedge.py validation   refuses to run unless decision.json is committed unchanged
"""
import hashlib
import json
from datetime import timedelta
import subprocess
import sys

import numpy as np
import polars as pl

from run_extensions import (HEDGE_FEE_PER_SIDE, POLICY, band_hedge_ledger, book_ledger, exposure_cap, metrics,
                            opening_delta_hedge)
from src import config
from src.data import load_candles, load_orders, minute_index
from src.evaluate import ordered_lorenz
from src.hedge import band_rebalance, hedge_positions, per_protection_hedge_gain, position_minutes
from src.model import SQRT_PI_2

OUT = config.RESULTS / "dynamic_hedge"
DECISION = OUT / "decision.json"
INTERVALS_MIN = [1, 5, 15]
BANDS_BTC = [0.1, 0.25, 0.5, 1.0, 2.0]
FUNDING_PER_8H = 0.0001  # a typical BTC perpetual funding rate, for the bound only
FEE_SENSITIVITY = [0.0002, 0.0005]
TRAIN_LABEL = "training, Feb to Jul, model price"
VALID_LABEL = "validation, Aug to Oct, frozen v1 price (post hoc)"


class Book:
    """Per-minute view of a set of protections: hedge target, activity flags and prices."""

    def __init__(self, o: pl.DataFrame, candles: pl.DataFrame, move_col: str = "expected_abs_move"):
        t0 = candles["ts"].to_numpy()[0]
        self.t0, self.close = t0, candles["close"].to_numpy()
        created, closed = o["createdAt"].to_numpy(), o["closedAt"].to_numpy()
        # 71 training orders (none in validation) have createdAt logged after closedAt, up to hours
        # later; for them the protection started at expiry minus its length.
        start = np.where(closed < created, o["expirationDate"].to_numpy() - o["productType"].to_numpy().astype("timedelta64[s]"), created)
        entry = minute_index(start, t0) - 1                        # close of the last candle before the order
        exit_ = np.maximum(minute_index(closed, t0), entry + 1)    # candle whose close sets the payout
        expiry_min = (o["expirationDate"].to_numpy() - t0) / np.timedelta64(60, "s")
        sigma = o[move_col].to_numpy() * SQRT_PI_2 / np.sqrt(o["T_min"].to_numpy())
        self.idx, self.k = position_minutes(entry, exit_)
        self.h = hedge_positions(self.close, self.idx, self.k, o["strikePrice"].to_numpy(), o["quantity_BTC"].to_numpy(),
                                 o["optionType"].to_numpy() == 0, sigma, expiry_min)
        self.k0, k1 = int(entry.min()), int(exit_.max())
        n = k1 - self.k0 + 1
        self.target = np.bincount(self.k - self.k0, weights=self.h, minlength=n)
        self.live = np.bincount(self.k - self.k0, minlength=n) > 0
        self.event = np.zeros(n, bool)
        self.event[entry - self.k0] = True
        self.event[exit_ - self.k0] = True
        self.px = self.close[self.k0:self.k0 + n]
        self.times = t0 + (self.k0 + np.arange(n) + 1) * np.timedelta64(60, "s")  # close time of each candle
        self.n_protections = o.height

    def ledger(self, interval: int, band: float, fee_rate: float) -> tuple[pl.DataFrame, float, dict]:
        pnl, fee, held = band_rebalance(self.target, self.live, self.event, self.px, self.k0, interval, band, fee_rate)
        day = self.times.astype("datetime64[D]")
        led = pl.DataFrame({"day": np.concatenate([day, day]), "amount": np.concatenate([pnl, -fee])}).with_columns(pl.col("day").cast(pl.Date))
        exposure = {"mean_abs_hedge_btc": float(np.abs(held).mean()),
                    "funding_cost_bound": float((np.abs(held) * self.px).sum() * FUNDING_PER_8H / (8 * 60))}
        return led, float(fee.sum()), exposure

    def hedged_cost(self, payout: np.ndarray) -> np.ndarray:
        return payout - per_protection_hedge_gain(self.close, self.idx, self.k, self.h, self.n_protections)


def calendar(o: pl.DataFrame) -> pl.DataFrame:
    """Every calendar day from the first order to the last close, with zero amounts. Added to every
    row so that all rows are scored on the same days (the hedge earns or pays on days without orders)."""
    first = o["createdAt"].min().date() - timedelta(days=1)
    last = o["closedAt"].max().date() + timedelta(days=1)
    days = pl.date_range(first, last, "1d", eager=True)
    return pl.DataFrame({"day": days, "amount": np.zeros(len(days))})


def row(label: str, name: str, parts: list[pl.DataFrame], cal: pl.DataFrame, fees: float, **extra) -> dict:
    return {"sample": label, "hedge": name, "hedge_fees": fees, "days": cal.height, **extra, **metrics([*parts, cal])}


def score(r: dict) -> float:
    return r["profit"] / r["days"] / r["sd_daily_pnl"]


def evaluate(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, label: str,
             configs: list[tuple[int, float]], fee_rates: list[float]) -> list[dict]:
    """Unhedged book, the current policy, and each dynamic configuration at each fee rate."""
    book, cal = book_ledger(o, price_col, payout_col), calendar(o)
    rows = [row(label, "no hedge", [book], cal, 0.0)]
    accepted = opening_delta_hedge(o, candles).filter(pl.Series(exposure_cap(o, POLICY["cap_per_direction_USDC"])))
    hl, fees = band_hedge_ledger(accepted, candles, POLICY["hedge_band_BTC"])  # the current policy, as in run_extensions.policy_row
    rows.append(row(label, "current policy: cap 250,000 + opening delta within 0.5 BTC", [book_ledger(accepted, price_col, payout_col), hl], cal, fees))
    b = Book(o, candles)
    for interval, band in configs:
        for fee_rate in fee_rates:
            led, fees, exposure = b.ledger(interval, band, fee_rate)
            rows.append(row(label, f"dynamic, every {interval} min, band {band:g} BTC", [book, led], cal, fees,
                            interval_min=interval, band_btc=band, fee_per_side=fee_rate, **exposure))
    for r in rows:
        r["score_mean_over_sd"] = score(r)
    return rows


def monthly(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, interval: int, band: float, label: str) -> pl.DataFrame:
    book = book_ledger(o, price_col, payout_col)
    led, _, _ = Book(o, candles).ledger(interval, band, HEDGE_FEE_PER_SIDE)
    m = lambda df: df.group_by(pl.col("day").dt.strftime("%Y-%m").alias("month")).agg(pl.col("amount").sum())
    unhedged = m(book).rename({"amount": "no_hedge"})
    hedged = m(pl.concat([book, led])).rename({"amount": "dynamic_hedge"})
    return unhedged.join(hedged, on="month").sort("month").with_columns(sample=pl.lit(label))


def ranking_on_hedged_cost(o: pl.DataFrame, candles: pl.DataFrame, price_col: str, payout_col: str, ref_col: str, label: str) -> dict:
    """Gini of the model against a reference price, measured on raw payouts and on hedged cost."""
    m = o.filter(pl.col(ref_col).is_not_null())
    cost = Book(m, candles).hedged_cost(m[payout_col].to_numpy())
    ref, p = m[ref_col].to_numpy(), m[price_col].to_numpy()
    return {"sample": label, "reference": ref_col, "orders": m.height,
            "gini_on_payout": ordered_lorenz(ref, p, m[payout_col].to_numpy())[2], "gini_on_hedged_cost": ordered_lorenz(ref, p, cost)[2],
            "payout_total": float(m[payout_col].sum()), "hedged_cost_total": float(cost.sum()), "premium_total": float(p.sum())}


def decide(rows: list[dict]) -> dict:
    main = [r for r in rows if r.get("fee_per_side") == HEDGE_FEE_PER_SIDE]
    best = max(main, key=lambda r: r["score_mean_over_sd"])
    bars = {r["hedge"]: r["score_mean_over_sd"] for r in rows if "dynamic" not in r["hedge"]}
    adopt = all(best["score_mean_over_sd"] > s for s in bars.values())
    return {"rule": "highest mean / SD of daily profit after fees (0.04 percent per side) on the Feb-Jul walk-forward; must beat no hedge and the current policy",
            "scores_to_beat": bars, "best": {k: best[k] for k in ["hedge", "interval_min", "band_btc", "score_mean_over_sd", "profit", "worst_day", "max_drawdown"]},
            "adopted": adopt, "interval_min": best["interval_min"] if adopt else None, "band_btc": best["band_btc"] if adopt else None}


def training(candles: pl.DataFrame) -> None:
    wfo = pl.read_parquet(config.RESULTS / "walk_forward_orders_priced.parquet")
    grid = [(i, b) for i in INTERVALS_MIN for b in BANDS_BTC]
    rows = evaluate(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", TRAIN_LABEL, grid, [HEDGE_FEE_PER_SIDE])
    decision = decide(rows)
    if decision["adopted"]:
        cfg = [(decision["interval_min"], decision["band_btc"])]
        rows += [r for r in evaluate(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", TRAIN_LABEL, cfg, FEE_SENSITIVITY) if "dynamic" in r["hedge"]]
        monthly(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", *cfg[0], TRAIN_LABEL).write_csv(OUT / "monthly_training.csv")
    rank = [ranking_on_hedged_cost(wfo, candles, "model_premium_USDC", "realizedProfit_USDC", c, TRAIN_LABEL) for c in ["premiumAmount_USDC", "base_premium_USDC"]]
    pl.DataFrame(rows).write_csv(OUT / "training_grid.csv")
    pl.DataFrame(rank).write_csv(OUT / "ranking_hedged_cost_training.csv")
    DECISION.write_text(json.dumps(decision, indent=2))
    show(pl.DataFrame(rows), pl.DataFrame(rank), decision)


def check_committed() -> str:
    """The validation run is allowed only on a decision that is committed exactly as on disk."""
    rel = DECISION.relative_to(config.REPO)
    committed = subprocess.run(["git", "-C", str(config.REPO), "show", f"HEAD:{rel}"], capture_output=True)
    if committed.returncode != 0 or committed.stdout != DECISION.read_bytes():
        sys.exit("decision.json is missing from HEAD or differs from it; commit the training decision first")
    return hashlib.sha256(committed.stdout).hexdigest()


def validation(candles: pl.DataFrame) -> None:
    digest = check_committed()
    decision = json.loads(DECISION.read_text())
    if not decision["adopted"]:
        sys.exit("no dynamic hedge was adopted on training data; nothing to run")
    from run_sealed_check import check_frozen, payout_at_close
    frozen = check_frozen()  # the prices must be the frozen, committed version 1 file
    rec = pl.read_csv(config.OUTPUTS / "validation_recommendations.csv", infer_schema_length=0).select(
        pl.col("recommended_premium_USDC").cast(pl.Float64), (pl.col("expected_abs_move_bps").cast(pl.Float64) / 1e4).alias("expected_abs_move"))
    val = pl.concat([load_orders(config.VALID_CSV), rec], how="horizontal")
    val = val.with_columns(payout=pl.Series(payout_at_close(val, candles)))
    cfg = (decision["interval_min"], decision["band_btc"])
    rows = evaluate(val, candles, "recommended_premium_USDC", "payout", VALID_LABEL, [cfg], [HEDGE_FEE_PER_SIDE, *FEE_SENSITIVITY])
    by_month = monthly(val, candles, "recommended_premium_USDC", "payout", *cfg, VALID_LABEL)
    rank = [ranking_on_hedged_cost(val, candles, "recommended_premium_USDC", "payout", "base_premium_USDC", VALID_LABEL)]
    pl.DataFrame(rows).write_csv(OUT / "validation.csv")
    by_month.write_csv(OUT / "monthly_validation.csv")
    pl.DataFrame(rank).write_csv(OUT / "ranking_hedged_cost_validation.csv")
    (OUT / "validation_run.json").write_text(json.dumps({"decision_sha256": digest, "prices": frozen, "configuration": cfg}, indent=2))
    show(pl.DataFrame(rows), pl.DataFrame(rank), decision, by_month)


def show(*objs) -> None:
    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(250); pl.Config.set_tbl_rows(60); pl.Config.set_fmt_str_lengths(60); pl.Config.set_float_precision(3)
    for x in objs:
        print(json.dumps(x, indent=1) if isinstance(x, dict) else x, file=sys.stderr)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candles = load_candles()
    if len(sys.argv) > 1 and sys.argv[1] == "validation":
        validation(candles)
    else:
        training(candles)


if __name__ == "__main__":
    main()
