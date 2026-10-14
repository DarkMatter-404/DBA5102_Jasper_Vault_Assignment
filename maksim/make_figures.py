"""Figures for the slides and README (results/figures/*.png). Run after run_backtest.py and run_validation.py."""
import json

import matplotlib
import matplotlib.ticker
import numpy as np
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import config  # noqa: E402
from src.data import load_candles, load_events  # noqa: E402
from src.evaluate import ordered_lorenz  # noqa: E402
from src.market import build_market, market_sample  # noqa: E402
from src.model import add_event_jump  # noqa: E402
from src.pipeline import fit_pricer  # noqa: E402

# Reference palette (light mode). Colour follows the entity in every figure.
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
MODEL, CURRENT, BASE = "#2a78d6", "#eb6834", "#1baf7a"
BLUE_RAMP = ["#b7d3f2", "#7fb0e8", "#3f86d9", "#1d5aa6"]  # sequential, light to dark

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 13, "axes.titlesize": 16,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False, "lines.linewidth": 2.0,
})
R = config.RESULTS


def out_dir():
    return config.FIGURES


def figure(w, h, *args, **kw):
    return plt.subplots(*args, figsize=(w, h), **kw)


def title(obj, t, **kw):
    obj.set_title(t, **kw)


def suptitle(fig, t, **kw):
    fig.suptitle(t, **kw)


def foot(fig, t, **kw):
    fig.text(0.01, 0.005, t, color=MUTED, fontsize=10, **kw)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(out_dir() / name, dpi=125)
    plt.close(fig)


def label_bars(ax, bars, fmt):
    for b in bars:
        ax.annotate(fmt(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=11, color=INK2)


def fig_loss_ratio_by_quintile(wf):
    d = wf.with_columns(rel=pl.col("fair_value_USDC") / pl.col("premiumAmount_USDC"))
    d = d.with_columns(q=(pl.col("rel").rank("ordinal") / pl.len() * 5).ceil().cast(pl.Int32))
    g = d.group_by("q").agg(cur=pl.col("realizedProfit_USDC").sum() / pl.col("premiumAmount_USDC").sum(),
                            mod=pl.col("realizedProfit_USDC").sum() / pl.col("model_premium_USDC").sum(),
                            prem=pl.col("premiumAmount_USDC").sum()).sort("q")
    fig, ax = figure(12.8, 7.2)
    x = np.arange(5)
    b1 = ax.bar(x - 0.2, g["cur"], 0.38, color=CURRENT, label="Current price (base + CTA markup)")
    b2 = ax.bar(x + 0.2, g["mod"], 0.38, color=MODEL, label="Model price")
    label_bars(ax, b1, lambda v: f"{v:.2f}"); label_bars(ax, b2, lambda v: f"{v:.2f}")
    ax.axhline(1.0, color=INK2, lw=1.2, ls="--"); ax.text(-0.45, 1.02, "break-even", color=INK2, ha="left", fontsize=11)
    ax.set_xticks(x, ["1\n(model risk far\nbelow current price)", "2", "3", "4", "5\n(model risk above\ncurrent price)"])
    ax.set_ylabel("Loss ratio (payouts / premiums)")
    ax.set_xlabel("Quintile of orders by model fair value / current price")
    title(ax, "Loss ratio by model risk quintile: current pricing loses money where the model sees more risk", pad=14)
    ax.legend(loc="upper left")
    ax.set_ylim(0, max(g["cur"].max(), g["mod"].max()) * 1.18)
    foot(fig, "All 7,150 training orders with a payout, Feb to Jul 2026; each month priced by a model fitted on earlier data only.")
    save(fig, "loss_ratio_by_model_quintile.png")


def fig_lorenz(wf):
    m = wf.filter(pl.col("base_premium_USDC").is_not_null())
    x, a, b, f = (m[c].to_numpy() for c in ["realizedProfit_USDC", "premiumAmount_USDC", "base_premium_USDC", "fair_value_USDC"])
    fig, axes = figure(12.8, 6.6, 1, 2, sharey=True)
    for ax, (ref, ref_name), cands in [
        (axes[0], (a, "current price"), [(f, "Model fair value", MODEL), (b, "API base price", BASE)]),
        (axes[1], (b, "API base price"), [(f, "Model fair value", MODEL), (a, "Current price", CURRENT)]),
    ]:
        ax.plot([0, 1], [0, 1], color=MUTED, lw=1.2, ls="--")
        for cand, name, col in cands:
            cx, cy, g = ordered_lorenz(ref, cand, x)
            ax.plot(cx, cy, color=col, label=f"{name} (Gini {g:.2f})")
        ax.set_title(f"Reference: {ref_name}", fontsize=14)
        ax.set_xlabel(f"Cumulative share of {ref_name} premium")
        ax.legend(loc="upper left", fontsize=12)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    axes[0].set_ylabel("Cumulative share of payouts")
    suptitle(fig, "Ordered Lorenz curves, Feb to Jul walk-forward (below the diagonal = finds underpriced orders)",
                 x=0.01, ha="left", fontweight="bold", fontsize=15)
    foot(fig, f"{m.height:,} orders with an API base quote, Feb to Jul 2026, out-of-sample fair values. Method: Frees, Meyers and Cummings (2011).")
    save(fig, "ordered_lorenz_curves.png")


def fig_time_of_day():
    card = json.loads((config.OUTPUTS / "model_card.json").read_text())
    p = np.array(card["time_of_day_profile_weekday_then_weekend_et_half_hours"])
    hours = np.arange(48) / 2
    fig, ax = figure(12.8, 6.6)
    ax.step(hours, p[:48], where="post", color=INK, label="Weekday")
    ax.step(hours, p[48:], where="post", color=MUTED, ls="--", label="Weekend")
    ax.axhline(1.0, color=GRID, lw=1.5)
    # label positions (hour, variance) chosen in empty areas of the plot
    for h, txt, xy_text in [(8.5, "08:30 CPI and jobs\nreport release time", (1.0, 2.3)),
                            (9.5, "09:30 US equity\nmarket open", (11.0, 3.45)),
                            (14.0, "14:00 FOMC\nstatement time", (14.6, 3.0))]:
        ax.annotate(txt, (h, p[int(h * 2)]), xytext=xy_text, fontsize=11, color=INK2,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
    ax.set_xticks(range(0, 25, 3), [f"{h:02d}:00" for h in range(0, 25, 3)])
    ax.set_xlim(0, 24)
    ax.set_xlabel("Time of day, US Eastern time")
    ax.set_ylabel("BTC variance relative to the daily average")
    title(ax, "BTC variance by time of day (US Eastern), relative to the average", pad=14)
    ax.legend(loc="upper right")
    foot(fig, "Average squared one-minute return per half hour, Jan to Jul 2026, release windows excluded. The API base price does not vary with time of day.")
    save(fig, "time_of_day_volatility.png")


def fig_walk_forward():
    w = pl.read_csv(R / "walk_forward_monthly.csv")
    fig, axes = figure(12.8, 6.6, 1, 2, sharey=True)
    for ax, scen, panel in [(axes[0], "elasticity=0", "No demand response"), (axes[1], "elasticity=1", "Elasticity 1 (10% higher price, about 10% fewer orders)")]:
        months = sorted(w["month"].unique().to_list())
        x = np.arange(len(months))
        for off, strat, col, lab in [(-0.2, "current price (base + CTA markup)", CURRENT, "Current price"), (0.2, "model", MODEL, "Model")]:
            vals = [w.filter((pl.col("month") == mo) & (pl.col("strategy") == strat) & (pl.col("scenario") == scen))["profit"][0] / 1000 for mo in months]
            ax.bar(x + off, vals, 0.38, color=col, label=lab)
        ax.axhline(0, color=INK2, lw=1)
        ax.set_xticks(x, [m[5:] + "/" + m[2:4] for m in months])
        ax.set_title(panel, fontsize=14)
        ax.set_xlabel("Month (2026)")
    axes[0].set_ylabel("Profit, thousand USDC")
    axes[0].legend(loc="upper left")
    suptitle(fig, "Walk-forward test: each month priced by a model fitted only on earlier data",
                 x=0.01, ha="left", fontweight="bold", fontsize=15)
    tot = w.group_by("strategy", "scenario").agg(pl.col("profit").sum())
    t = {(r["strategy"], r["scenario"]): r["profit"] for r in tot.to_dicts()}
    foot(fig, "Six-month total profit: current {:,.0f} USDC; model {:,.0f} USDC (no demand response), {:,.0f} USDC (elasticity 1).".format(
        t[("current price (base + CTA markup)", "elasticity=0")], t[("model", "elasticity=0")], t[("model", "elasticity=1")]))
    save(fig, "walk_forward_monthly_profit.png")


def daily_pnl(day, price, payout, weight=None):
    w = np.ones_like(price) if weight is None else weight
    df = pl.DataFrame({"day": day, "pnl": w * (price - payout)}).group_by("day").agg(pl.col("pnl").sum()).sort("day")
    return df["day"].to_numpy(), np.cumsum(df["pnl"].to_numpy())


def fig_cumulative(test):
    a, x, p, d = (test[c].to_numpy() for c in ["premiumAmount_USDC", "realizedProfit_USDC", "model_premium_USDC", "day"])
    fig, ax = figure(12.8, 6.6)
    dd, c = daily_pnl(d, a, x); ax.plot(dd, c / 1000, color=CURRENT, label="Current price")
    dd, c = daily_pnl(d, p, x); ax.plot(dd, c / 1000, color=MODEL, label="Model, no demand response")
    dd, c = daily_pnl(d, p, x, np.minimum(a / p, 3.0)); ax.plot(dd, c / 1000, color=MODEL, ls="--", label="Model, elasticity 1")
    ax.axhline(0, color=INK2, lw=1)
    ax.set_ylabel("Cumulative profit, thousand USDC")
    title(ax, "Out-of-sample test, June and July 2026: cumulative profit of the PP book", pad=14)
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    foot(fig, "4,841 orders; model fitted on market data before 1 June 2026; margin 25 percent fixed in advance.")
    save(fig, "cumulative_profit_test_period.png")


def fig_margin():
    g = pl.read_csv(R / "margin_sensitivity_test_period.csv")
    cur = g.filter(pl.col("margin").is_null())["profit"][0] / 1000
    m = g.filter(pl.col("margin").is_not_null())
    fig, ax = figure(12.8, 6.6)
    for e, col in zip(config.ELASTICITIES, BLUE_RAMP):
        s = m.filter(pl.col("elasticity") == e).sort("margin")
        ax.plot(s["margin"] * 100, s["profit"] / 1000, color=col, marker="o", ms=6, label=f"Model, elasticity {e:g}")
    ax.axhline(cur, color=CURRENT, lw=2, label="Current price")
    ax.axvline(25, color=MUTED, ls="--", lw=1.2); ax.text(25.6, ax.get_ylim()[0] + 3, "chosen margin\n(target loss ratio 80%)", color=INK2, fontsize=11)
    ax.set_xlabel("Margin over fair value, percent")
    ax.set_ylabel("Profit, June and July 2026, thousand USDC")
    title(ax, "June and July profit by margin and demand assumption", pad=14)
    ax.legend(loc="upper left", fontsize=12)
    save(fig, "margin_sensitivity.png")


def fig_price_change(test):
    r = (test["model_premium_USDC"] / test["premiumAmount_USDC"]).to_numpy()
    fig, ax = figure(12.8, 6.6)
    bins = np.logspace(np.log10(0.2), np.log10(5), 41)
    ax.hist(r, bins=bins, color=MODEL, edgecolor=SURFACE, linewidth=1.5)
    ax.set_xscale("log")
    ax.axvline(1.0, color=INK2, lw=1.2, ls="--")
    ticks = [0.25, 0.5, 1, 2, 4]
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(ticks, [f"{t:g}x" for t in ticks])
    share = (r < 1).mean()
    a = test["premiumAmount_USDC"].to_numpy()
    up = a[r > 1].sum() / a.sum()
    tot = test["model_premium_USDC"].sum() / a.sum() - 1
    ax.text(0.97, 0.92, f"{share:.0%} of orders pay less than today (median {np.median(r):.2f}x)\n"
                        f"orders holding {up:.0%} of today's premium pay more\ntotal premium {tot:+.1%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=13, color=INK)
    ax.set_xlabel("Model premium / current premium (log scale)")
    ax.set_ylabel("Number of orders")
    title(ax, "Model premium relative to the current premium, per order", pad=14)
    foot(fig, "June and July 2026 orders.")
    save(fig, "price_change_distribution.png")


def fig_calibration():
    mkt = build_market(load_candles(), load_events())
    pr = fit_pricer(mkt, config.DEV_SPLIT)
    k0 = int(((np.datetime64(config.DEV_SPLIT) - mkt.t0) // np.timedelta64(60, "s"))) - 1
    k1 = int(((np.datetime64(config.TRAIN_END) - mkt.t0) // np.timedelta64(60, "s"))) - 1
    fig, ax = figure(12.8, 6.6)
    lim = 0
    for t_s, col, lab in [(1800, BLUE_RAMP[1], "30-minute"), (14400, BLUE_RAMP[2], "4-hour"), (86400, BLUE_RAMP[3], "24-hour")]:
        k = market_sample(mkt, k0 + 1, k1, t_s // 60, config.SAMPLE_STEP_MIN)
        t = np.full(len(k), t_s)
        y = mkt.forward_abs_return(k, t // 60) * 1e4
        p = add_event_jump(pr.move.predict_abs_move(mkt, pr.seas, k, t, pr.hmm), mkt.events_in_window(k, t // 60), pr.event_jump_var) * 1e4
        q = np.quantile(p, np.linspace(0, 1, 11))
        idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, 9)
        px = [p[idx == i].mean() for i in range(10)]; py = [y[idx == i].mean() for i in range(10)]
        ax.plot(px, py, color=col, marker="o", ms=8, label=f"{lab} windows")
        lim = max(lim, max(px), max(py))
    ax.plot([0, lim * 1.05], [0, lim * 1.05], color=MUTED, ls="--", lw=1.2)
    ax.set_xlabel("Predicted average move, basis points (decile of prediction)")
    ax.set_ylabel("Realised average move, basis points")
    title(ax, "The expected-move forecast is calibrated out of sample", pad=14)
    ax.legend(loc="upper left")
    foot(fig, "Every 5-minute window in June and July 2026; model fitted on data before 1 June. Points on the dashed line are perfectly calibrated.")
    save(fig, "move_forecast_calibration.png")


def fig_payout_ratio():
    d = pl.read_csv(R / "payout_over_fair_value_walk_forward.csv")
    order = [("all", "all orders", "All orders"), ("tier", "small", "Small (< 1k USDC)"), ("tier", "medium", "Medium (1k to 10k)"),
             ("tier", "large", "Large (>= 10k)"), ("optionType_label", "Call", "Call (protects shorts)"), ("optionType_label", "Put", "Put (protects longs)")]
    rows = [d.filter((pl.col("group_by") == g) & (pl.col("group") == v)).to_dicts()[0] | {"label": lab} for g, v, lab in order]
    fig, ax = figure(12.8, 6.6)
    y = np.arange(len(rows))[::-1]
    for yi, r in zip(y, rows):
        ax.plot([r["ci05"], r["ci95"]], [yi, yi], color=MODEL, lw=2.5)
        ax.plot(r["payout_over_fair_value"], yi, "o", color=MODEL, ms=10, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(r["ci95"] + 0.02, yi, f"{r['payout_over_fair_value']:.2f}", va="center", color=INK2, fontsize=12)
    ax.axvline(1.0, color=INK2, ls="--", lw=1.2)
    ax.set_yticks(y, [r["label"] for r in rows])
    ax.set_xlabel("Actual payouts / model fair value (90% interval, resampling days)")
    title(ax, "Actual payouts / model fair value, by group", pad=14)
    foot(fig, "Feb to Jul 2026, out-of-sample fair values from the walk-forward run. The model is fitted without any order outcome; size and direction are not used for pricing.")
    save(fig, "payout_over_fair_value.png")


def main():
    out_dir().mkdir(parents=True, exist_ok=True)
    wf = pl.read_parquet(R / "walk_forward_orders_priced.parquet")
    test = pl.read_parquet(R / "test_orders_priced.parquet")
    fig_loss_ratio_by_quintile(wf)
    fig_lorenz(wf)
    fig_time_of_day()
    fig_walk_forward()
    fig_cumulative(test)
    fig_margin()
    fig_price_change(test)
    fig_calibration()
    fig_payout_ratio()
    print("figures:", sorted(p.name for p in out_dir().glob("*.png")))


if __name__ == "__main__":
    main()
