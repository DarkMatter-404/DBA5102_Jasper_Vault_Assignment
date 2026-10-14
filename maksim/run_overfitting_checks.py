"""Overfitting checks for the PP pricing model (training period only, February to July 2026).

1. Forecast skill in sample and out of sample. The move model is refitted at five monthly
   cut-offs. Skill = 1 - deviance(model) / deviance(average-move model) on the same windows.
   Overfitting would show up as clearly higher skill in sample than out of sample.
2. Parameter stability. Coefficients of the move model and the time-of-day profile, refitted
   on different periods.
3. Design decisions by sub-period. Several design choices were made after looking at June and
   July results. Each choice is re-evaluated month by month (each month priced by a model fitted
   on earlier data only), separately for February to May and for June and July, and compared
   with the simplest version of the model (recent volatility and time of day, nothing else).

Outputs: results/overfitting/*.csv
"""
import sys

import numpy as np
import polars as pl

from src import config
from src.data import load_candles, load_events, load_orders, minute_index
from src.evaluate import conversion_weight, move_forecast_scores, ordered_lorenz
from src.market import build_market, fit_seasonality, market_sample
from src.model import add_event_jump
from src.pipeline import fit_pricer

OUT = config.RESULTS / "overfitting"
CUTOFFS = [("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"), ("2026-05-01", "2026-06-01"),
           ("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-07-31 17:11:12")]
MONTHS = [("2026-02-01", "2026-03-01"), ("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"),
          ("2026-05-01", "2026-06-01"), ("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-08-01")]
FINAL = "+ macro releases (final)"


def kidx(mkt, ts: str) -> int:
    return int(minute_index(np.array([np.datetime64(ts)]), mkt.t0)[0]) - 1


def ts(s: str) -> pl.Expr:
    return pl.lit(np.datetime64(s)).cast(pl.Datetime("us"))


def predict(pr, mkt, k, t_s):
    t = np.full(len(k), t_s)
    p = pr.move.predict_abs_move(mkt, pr.seas, k, t, pr.hmm)
    return add_event_jump(p, mkt.events_in_window(k, t // 60), pr.event_jump_var) * 1e4


def forecast_skill(mkt) -> pl.DataFrame:
    rows = []
    for cut, oos_end in CUTOFFS:
        final, naive = fit_pricer(mkt, cut, FINAL), fit_pricer(mkt, cut, "average move only")
        k_cut, k_oos = kidx(mkt, cut), kidx(mkt, oos_end)
        for t_s in config.DURATIONS_S:
            for sample, (k0, k1) in [("in sample", (0, k_cut)), ("out of sample", (k_cut + 1, k_oos))]:
                k = market_sample(mkt, k0, k1, t_s // 60, config.SAMPLE_STEP_MIN)
                y = mkt.forward_abs_return(k, np.full(len(k), t_s // 60)) * 1e4
                sf, sn = move_forecast_scores(y, predict(final, mkt, k, t_s)), move_forecast_scores(y, predict(naive, mkt, k, t_s))
                rows.append({"cutoff": cut, "productType": t_s, "sample": sample, "windows": len(k),
                             "deviance_model": sf["mean_poisson_deviance"], "deviance_average_move": sn["mean_poisson_deviance"],
                             "skill": 1 - sf["mean_poisson_deviance"] / sn["mean_poisson_deviance"],
                             "calibration_actual_over_pred": sf["calibration_actual_over_pred"]})
    return pl.DataFrame(rows)


def coefficient_stability(mkt) -> tuple[pl.DataFrame, pl.DataFrame]:
    rows = []
    for cut in [c for c, _ in CUTOFFS] + [config.TRAIN_END]:
        pr = fit_pricer(mkt, cut, FINAL)
        for t_s, pipe in pr.move.models.items():
            sc, glm = pipe[0], pipe[-1]
            raw = glm.coef_ / sc.scale_  # change in log expected move per unit of each (log) feature
            rows.append({"cutoff": cut, "productType": t_s, "n_windows": pr.move.n_windows[t_s], **dict(zip(pr.move.feature_names, raw)),
                         "event_jump_bps": np.sqrt(pr.event_jump_var) * 1e4})
    coef = pl.DataFrame(rows)
    k_apr, k_end = kidx(mkt, "2026-04-01"), kidx(mkt, config.TRAIN_END)
    early, late = fit_seasonality(mkt, k_apr), fit_seasonality(mkt, k_end, fit_start_idx=k_apr + 1)
    prof = pl.DataFrame({"et_half_hour": [f"{(i % 48) // 2:02d}:{30 * (i % 2):02d}" for i in range(96)],
                         "day_type": ["weekday"] * 48 + ["weekend"] * 48,
                         "fit_jan_to_mar": early.profile, "fit_apr_to_jul": late.profile})
    return coef, prof


def release_double_counting(mkt, orders: pl.DataFrame) -> pl.DataFrame:
    """How much the fair value changes if release-containing windows are left out of the regression.

    The final model fits the baseline on all windows (some contain a release) and then adds the
    release variance, so part of the release effect may be counted twice. Diagnostic only: the
    frozen recommendations are not changed.
    """
    rows = []
    for start, end in MONTHS:
        mo = orders.filter((pl.col("createdAt") >= ts(start)) & (pl.col("createdAt") < ts(end)))
        a = fit_pricer(mkt, start, FINAL).fair_value(mkt, mo)
        b = fit_pricer(mkt, start, FINAL, exclude_release_windows=True).fair_value(mkt, mo)
        rows.append(a.select("productType", "event_in_window", "fair_value_USDC", "premiumAmount_USDC", "realizedProfit_USDC")
                    .with_columns(fv_excluding=b["fair_value_USDC"], month=pl.lit(start[:7])))
    d = pl.concat(rows)
    g = d.group_by(pl.when(pl.col("event_in_window") > 0).then(pl.lit("release in window")).otherwise(pl.lit("no release")).alias("window")).agg(
        orders=pl.len(), fair_value=pl.col("fair_value_USDC").sum(), fair_value_excluding=pl.col("fv_excluding").sum())
    tot = d.select(pl.lit("all orders").alias("window"), pl.len().alias("orders"), pl.col("fair_value_USDC").sum().alias("fair_value"),
                   pl.col("fv_excluding").sum().alias("fair_value_excluding"))
    out = pl.concat([g, tot]).with_columns(change=pl.col("fair_value_excluding") / pl.col("fair_value") - 1)
    x, a_ = d["realizedProfit_USDC"].to_numpy(), d["premiumAmount_USDC"].to_numpy()
    return out.with_columns(gini_vs_current_final=pl.lit(ordered_lorenz(a_, d["fair_value_USDC"].to_numpy(), x)[2]),
                            gini_vs_current_excluding=pl.lit(ordered_lorenz(a_, d["fv_excluding"].to_numpy(), x)[2]))


def tier_loading(pr, mkt, orders: pl.DataFrame, before: str) -> dict[str, float]:
    """Payout / fair value per size tier on orders that expired before `before` (1.0 if none)."""
    cal = orders.filter(pl.col("expirationDate") < ts(before))
    if cal.height == 0:
        return {}
    f = pr.fair_value(mkt, cal)
    g = f.group_by("tier").agg(r=pl.col("realizedProfit_USDC").sum() / pl.col("fair_value_USDC").sum())
    return dict(zip(g["tier"].to_list(), g["r"].to_list()))


def design_variants(mkt, mkt_pce, orders: pl.DataFrame) -> pl.DataFrame:
    """Each variant priced month by month with a model fitted on earlier data only."""
    variants = {
        "A. recent volatility only": dict(variant="recent volatility", floor=False, tiers=False, market=mkt),
        "B. simplest: recent volatility + time of day": dict(variant="+ time of day", floor=False, tiers=False, market=mkt),
        "C. B + releases (CPI, jobs report, FOMC)": dict(variant=FINAL, floor=False, tiers=False, market=mkt),
        "D. C + floor at base price (final model)": dict(variant=FINAL, floor=True, tiers=False, market=mkt),
        "E. D with PCE as a fourth release type": dict(variant=FINAL, floor=True, tiers=False, market=mkt_pce),
        "F. D + size-tier loading": dict(variant=FINAL, floor=True, tiers=True, market=mkt),
    }
    rows = []
    for start, end in MONTHS:
        mo = orders.filter((pl.col("createdAt") >= ts(start)) & (pl.col("createdAt") < ts(end)))
        a, x, day = mo["premiumAmount_USDC"].to_numpy(), mo["realizedProfit_USDC"].to_numpy(), mo["day"].to_numpy()
        base = mo["base_premium_USDC"].fill_null(0.0).to_numpy()
        rows.append(month_row("current price", start, a, a, x))
        for name, v in variants.items():
            m = v["market"]
            pr = fit_pricer(m, start, v["variant"])
            fv = pr.fair_value(m, mo)
            lam = np.ones(mo.height)
            if v["tiers"]:
                tl = tier_loading(pr, m, orders, start)
                lam = fv["tier"].replace_strict(tl, default=1.0, return_dtype=pl.Float64).to_numpy()
            p = fv["fair_value_USDC"].to_numpy() * lam * (1 + pr.margin)
            if v["floor"]:
                p = np.maximum(p, base)
            rows.append(month_row(name, start, p, a, x))
    return pl.DataFrame(rows)


def month_row(name, month, p, a, x) -> dict:
    out = {"strategy": name, "month": month[:7], "orders": len(p), "premium": p.sum(), "payout": x.sum(),
           "profit_e0": (p - x).sum(), "gini_vs_current": ordered_lorenz(a, p, x)[2] if name != "current price" else 0.0}
    w = conversion_weight(p, a, 1.0)
    out["profit_e1"] = (w * (p - x)).sum()
    w = (p <= a).astype(float)
    out["profit_keep_if_not_dearer"] = (w * (p - x)).sum()
    return out


def by_period(d: pl.DataFrame) -> pl.DataFrame:
    d = d.with_columns(period=pl.when(pl.col("month") <= "2026-05").then(pl.lit("Feb to May")).otherwise(pl.lit("Jun and Jul")))
    both = d.with_columns(period=pl.lit("Feb to Jul"))
    return pl.concat([d, both]).group_by("strategy", "period").agg(
        pl.col("profit_e0").sum(), pl.col("profit_e1").sum(), pl.col("profit_keep_if_not_dearer").sum(),
        (pl.col("payout").sum() / pl.col("premium").sum()).alias("loss_ratio"),
        pl.col("gini_vs_current").mean().alias("mean_monthly_gini_vs_current"),
    ).sort("period", "strategy")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candles = load_candles()
    mkt = build_market(candles, load_events())
    mkt_pce = build_market(candles, load_events(["CPI", "NFP", "FOMC", "PCE"]))
    orders = load_orders(config.TRAIN_CSV).filter(pl.col("realizedProfit_USDC").is_not_null())

    skill = forecast_skill(mkt)
    skill.write_csv(OUT / "forecast_skill_in_vs_out_of_sample.csv")
    coef, prof = coefficient_stability(mkt)
    coef.write_csv(OUT / "move_model_coefficients_by_cutoff.csv")
    prof.write_csv(OUT / "time_of_day_profile_early_vs_late.csv")
    dv = design_variants(mkt, mkt_pce, orders)
    dv.write_csv(OUT / "design_variants_monthly.csv")
    per = by_period(dv)
    per.write_csv(OUT / "design_variants_by_period.csv")
    dc = release_double_counting(mkt, orders)
    dc.write_csv(OUT / "release_double_counting.csv")
    print(dc, file=sys.stderr)

    pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_tbl_rows(60); pl.Config.set_fmt_str_lengths(48); pl.Config.set_float_precision(3)
    print(skill.group_by("cutoff", "sample").agg(pl.col("skill").mean(), pl.col("calibration_actual_over_pred").mean()).sort("cutoff", "sample"), file=sys.stderr)
    print(skill.group_by("productType", "sample").agg(pl.col("skill").mean()).sort("productType", "sample"), file=sys.stderr)
    feats = [c for c in coef.columns if c.startswith("log_")]
    print(coef.group_by("productType").agg([pl.col(f).mean().alias(f + "_mean") for f in feats[:2]] + [pl.col(f).std().alias(f + "_sd") for f in feats[:2]]
                                           + [pl.col("event_jump_bps").min().alias("jump_min"), pl.col("event_jump_bps").max().alias("jump_max")]).sort("productType"), file=sys.stderr)
    w = prof.filter(pl.col("day_type") == "weekday")
    print("time-of-day profile correlation, Jan-Mar fit vs Apr-Jul fit (weekday, weekend):",
          round(np.corrcoef(w["fit_jan_to_mar"], w["fit_apr_to_jul"])[0, 1], 3),
          round(np.corrcoef(prof.filter(pl.col("day_type") == "weekend")["fit_jan_to_mar"], prof.filter(pl.col("day_type") == "weekend")["fit_apr_to_jul"])[0, 1], 3), file=sys.stderr)
    print(per, file=sys.stderr)


if __name__ == "__main__":
    main()
