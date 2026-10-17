"""Checks for pp_pricing.ipynb. Called once at the end of the notebook:

    import test_pricing
    test_pricing.run_all(globals())

Each test receives the notebook's namespace (its functions and data), so the notebook stays the only
place where the pricing code lives. A failed check stops the notebook.

Phase 1: timestamp parsing, strict as-of joins, no look-ahead in features, daylight saving in the
calendar, release windows, outcome columns never used. Phase 2-3: cutoffs of every fit, the reference and
fair value ignore prices and outcomes, F1's floor/band/normalisation, Gini and C2 checks. Phase 5 (run when
price_orders exists): the final fit's cutoff and the blind-file pricing function on a mock blind file. Sections
12-13 (report-only): the daily risk measures and the exposure-cap overlay.
"""
import numpy as np
import pandas as pd

FEATURES = ["k", "log_var_60m", "log_var_240m", "log_var_1440m", "log_var_10080m", "rv_60", "rv_1d", "rv_7d",
            "rsi_15m", "pctb_15m", "release_in_window", "tod_slot"]


def same(a, b):
    return np.array_equal(np.asarray(a, dtype=float), np.asarray(b, dtype=float), equal_nan=True)


def features_with_candles(ns, orders, candles):
    # Rebuild every market array from (possibly changed) candles and recompute the order features.
    mkt = ns["build_market"](candles, ns["releases"])
    return ns["add_market_features"](orders, mkt, ns["bar_indicators"](mkt))


def sample_orders(ns):
    # One-row frames: two training orders (Feb, Jul), one minute-only blind row and one later blind row.
    tr, bl = ns["train"], ns["blind"]
    return [tr[tr.month == "2026-02"].iloc[[5]], tr[tr.month == "2026-07"].iloc[[-3]], bl.iloc[[10]], bl.iloc[[3000]]]


def test_timestamp_formats(ns):
    got = ns["parse_times"](pd.Series(["2026/7/31 17:11", "2026-08-24 16:05:59", "2026/10/1 9:05"]))
    want = pd.to_datetime(["2026-07-31 17:11:00", "2026-08-24 16:05:59", "2026-10-01 09:05:00"])
    assert (got.to_numpy() == want.to_numpy()).all(), "timestamp parser"


def test_asof_strict(ns):
    # The feature candle must have closed before createdAt, and the next one must not have.
    close = ns["candles"].close_time.to_numpy()
    for name in ["train", "blind"]:
        d = ns[name]
        k = d.k.to_numpy()
        assert (close[k] < d.createdAt.to_numpy()).all(), f"{name}: a feature candle closes at/after createdAt"
        assert (close[k + 1] >= d.createdAt.to_numpy()).all(), f"{name}: a later closed candle was skipped"


def test_future_candles_do_not_move_features(ns):
    rng = np.random.default_rng(7)
    for o in sample_orders(ns):
        c = ns["candles"].copy()
        later = np.arange(len(c)) >= o.k.iloc[0] + 1               # the open candle and everything after it
        c.loc[later, "close"] *= 1 + 0.05 * rng.standard_normal(later.sum())
        new = features_with_candles(ns, o, c)
        for f in FEATURES:
            assert same(new[f], o[f]), f"feature {f} moved when only future candles changed (row {o.row.iloc[0]})"


def test_past_candles_move_features(ns):
    o = sample_orders(ns)[1]
    k = o.k.iloc[0]
    c = ns["candles"].copy()
    recent = (np.arange(len(c)) >= k - 59) & (np.arange(len(c)) <= k)
    c.loc[recent, "close"] *= 1 + 0.01 * np.random.default_rng(8).standard_normal(recent.sum())
    new = features_with_candles(ns, o, c)
    assert not same(new.rv_60, o.rv_60), "1-hour volatility did not respond to the last hour's candles"


def test_calendar_daylight_saving(ns):
    idx = ns["minute_index"](pd.to_datetime(["2026-03-09 13:30", "2026-03-06 14:30", "2026-03-07 15:00"]), ns["mkt"]["t0"])
    got = ns["mkt"]["bucket"][idx]
    # 09:30 New York on a Monday (EDT) and a Friday (EST) are the same slot 19; Saturday 10:00 is 48 + 20.
    assert list(got) == [19, 19, 68], f"time-of-day slots {list(got)}"


def test_release_window(ns):
    mkt, t0 = ns["mkt"], ns["mkt"]["t0"]
    k = ns["minute_index"](pd.to_datetime(["2026-06-10 12:00:30"]), t0) - 1   # CPI at 12:30 UTC that day
    assert ns["release_in_window"](mkt, k, np.array([30]))[0] == 0, "30-min window ending before the release"
    assert ns["release_in_window"](mkt, k, np.array([60]))[0] == 1, "60-min window containing the release"


def test_outcomes_never_used(ns):
    d = ns["blind"].iloc[:200].copy()
    before = ns["add_market_features"](d, ns["mkt"], ns["bars"])
    d["closedAt"] = pd.NaT
    d["realizedProfit_USDC"] = 12345.0
    d["markup_per_BTC_USDC"] = np.nan
    after = ns["add_market_features"](d, ns["mkt"], ns["bars"])
    for f in FEATURES:
        assert same(before[f], after[f]), f"feature {f} depends on an outcome or price column"


# ---------- Phase 2: engines, reference and the price step ----------

def test_engine_windows_end_before_cutoff(ns):
    for c, eng in ns["engines"].items():
        for t_s in ns["DURATIONS_S"]:
            t = t_s // 60
            k = ns["market_windows"](0, eng["k_end"], t)
            assert k.max() + t <= eng["k_end"], f"engine {c}: a {t}-minute training window ends after the cutoff"
            assert len(k) == eng["n_windows"][t_s], f"engine {c}: window count changed"


def test_fit_rows_before_cutoff(ns):
    for month, f in ns["FOLDS"].items():
        fit, cut = ns["folds"][month]["fit"], pd.Timestamp(f["cutoff"])
        assert (fit.createdAt < cut).all() and (fit.closedAt < cut).all(), f"{month}: a fitting order was created or settled after the cutoff"
        assert set(fit.month) <= {m for m in fit.month if m < month}, f"{month}: test-month orders in the fit"


def test_reference_ignores_prices_and_outcomes(ns):
    for month in ns["FOLDS"]:
        d = ns["folds"][month]["test"].iloc[:300].copy()
        before = ns["reference_price"](ns["refs"][month], d)
        for col in ["premiumAmount_USDC", "orderPrice_per_BTC_USDC", "markup_per_BTC_USDC", "apiBasePrice_per_BTC_USDC",
                    "base_usd", "realizedProfit_USDC"]:
            d[col] = np.nan
        d["closedAt"] = pd.NaT
        assert same(before, ns["reference_price"](ns["refs"][month], d)), f"{month}: reference price uses a price or outcome column"


def test_fair_value_ignores_prices_and_outcomes(ns):
    f = ns["folds"]["2026-06"]
    d = f["test"].iloc[:300].copy()
    before = ns["fair_value"](ns["engines"]["2026-06-01"], ns["mkt"], d, f["k_event"])
    d["closedAt"], d["realizedProfit_USDC"], d["premiumAmount_USDC"], d["base_usd"] = pd.NaT, 9.0, np.nan, np.nan
    assert same(before, ns["fair_value"](ns["engines"]["2026-06-01"], ns["mkt"], d, f["k_event"])), "fair value uses a price or outcome"


def test_f1_floor_band_and_normalisation(ns):
    lo, hi = ns["SETTINGS"]["band"]
    for month, f in ns["folds"].items():
        for part in ["fit", "test"]:
            d = f[part]
            q, fv, pr = d.q_F1.to_numpy(), d.fv.to_numpy(), d.p_ref.to_numpy()
            assert (q >= fv * (1 - 1e-12)).all(), f"{month} {part}: an F1 quote is below fair value"
            above_floor = q > fv * (1 + 1e-12)
            r = q[above_floor] / pr[above_floor]
            assert ((r >= lo - 1e-12) & (r <= hi + 1e-12)).all(), f"{month} {part}: an F1 quote is outside the 0.8-1.2 band"
        err = f["fit"].q_F1.sum() / f["fit"].p_ref.sum() - 1
        assert abs(err) <= ns["SETTINGS"]["n_tol"], f"{month}: F1 training total off by {err:.2e}"
        assert np.isfinite(f["n"]["F1"]) and f["n"]["F1"] > 0, f"{month}: n is not a positive number"


# ---------- Phase 3: scorecard mechanics ----------

def test_event_times_from_checked_calendar(ns):
    cal = pd.read_csv(ns["EXT"] / "macro_events_2026_checked.csv")
    core = pd.to_datetime(cal.loc[cal.in_core_set.astype(str) == "True", "ts_utc"]).astype("datetime64[ns]")
    idx = ns["minute_index"](core, ns["mkt"]["t0"])
    idx = np.sort(idx[(idx >= 0) & (idx < len(ns["mkt"]["event_cum"]) - 1)])
    assert np.array_equal(np.sort(ns["mkt"]["event_idx"]), idx), "an event time used by features is not in the checked calendar"


def test_gini_permutation_ties_and_zero(ns):
    gini, rng = ns["gini"], np.random.default_rng(11)
    ratio = np.round(rng.uniform(0.7, 1.3, 400), 2)                  # rounding creates many exact ties
    a, y = rng.uniform(1, 5, 400), rng.exponential(2, 400) * (rng.uniform(size=400) < 0.5)
    g = gini(ratio, a, y)
    for _ in range(5):
        perm = rng.permutation(400)
        assert abs(gini(ratio[perm], a[perm], y[perm]) - g) < 1e-12, "Gini changes when rows are reordered"
    for month, t in ns["panels"].items():
        A, pay = t.q_C0.to_numpy(), t.realizedProfit_USDC.to_numpy()
        assert abs(gini(A / A, A, pay)) < 1e-12, f"{month}: Gini of C0 is not zero"
        assert abs(gini(1.3 * A / A, A, pay)) < 1e-12, f"{month}: Gini of a uniform multiplier is not zero"


def test_c2_same_profit_without_demand_response(ns):
    for month, t in ns["panels"].items():
        A, pay = t.q_C0.to_numpy(), t.realizedProfit_USDC.to_numpy()
        for m in ns["MODELS"]:
            P = t[f"q_{m}"].to_numpy()
            c2 = A * P.sum() / A.sum()
            assert abs((P - pay).sum() - (c2 - pay).sum()) < 1e-6 * A.sum(), f"{month} {m}: model and same-total C2 differ with no demand response"


# ---------- Phase 5: price_orders on blind-format input ----------

def mock_blind(ns, missing_base_share=0.53):
    # The last 1,898 training rows in the blind format: prices and payouts blank, both timestamp formats,
    # and the base removed from a later block of rows (as in the real blind file).
    raw = pd.read_csv(ns["TRAIN_CSV"], dtype=str).tail(1898).reset_index(drop=True)
    for c in ["premiumAmount_USDC", "orderPrice_per_BTC_USDC", "realizedProfit_USDC"]:
        raw[c] = np.nan
    first = raw.index < len(raw) // 2
    ts = pd.to_datetime(raw.loc[first, "createdAt"])
    raw.loc[first, "createdAt"] = [f"{t.year}/{t.month}/{t.day} {t.hour}:{t.minute:02d}" for t in ts]   # minute-only format
    later = raw.index >= int(len(raw) * (1 - missing_base_share))
    raw.loc[later, ["apiBasePrice_per_BTC_USDC", "markup_per_BTC_USDC"]] = np.nan
    return raw


def test_final_fit_obeys_cutoff(ns):
    eng, cut = ns["FINAL"]["engine"], ns["FINAL_CUTOFF"]
    assert eng["k_end"] == ns["to_minute"](ns["mkt"], cut) - 1, "final engine: last minute is not the one before the cutoff"
    for t_s in ns["DURATIONS_S"]:
        t = t_s // 60
        k = ns["market_windows"](0, eng["k_end"], t)
        assert k.max() + t <= eng["k_end"] and len(k) == eng["n_windows"][t_s], f"final engine: a {t}-minute window ends after the cutoff"
    fit = ns["final_fit"]
    assert (fit.createdAt < cut).all() and (fit.closedAt < cut).all(), "final fit: an order was created or settled after the cutoff"

def test_mock_blind_file(ns):
    raw = mock_blind(ns)
    out = ns["price_orders"](raw)
    q = out.recommended_premium_USDC.to_numpy()
    assert len(out) == len(raw) and (out.row_position.to_numpy() == np.arange(len(raw))).all(), "row count or order changed"
    assert np.isfinite(q).all() and (q > 0).all(), "a price is missing, zero or not finite"
    has_base = pd.to_numeric(raw.apiBasePrice_per_BTC_USDC).notna().to_numpy()
    assert out.multiplier_vs_base[has_base].notna().all() and out.multiplier_vs_base[~has_base].isna().all(), "multiplier blank rule"
    raw_all = raw.copy()
    raw_all["apiBasePrice_per_BTC_USDC"] = np.nan
    out_all = ns["price_orders"](raw_all)
    assert same(out_all.recommended_premium_USDC, q) and out_all.multiplier_vs_base.isna().all(), "missing bases changed a premium"


def test_premiums_ignore_outcomes_and_prices(ns):
    raw = mock_blind(ns)
    base = ns["price_orders"](raw).recommended_premium_USDC
    changed = raw.copy()
    changed["closedAt"] = ""
    changed["markup_per_BTC_USDC"] = "999"
    changed["premiumAmount_USDC"], changed["orderPrice_per_BTC_USDC"], changed["realizedProfit_USDC"] = 1e6, 1e6, 1e6
    changed["apiBasePrice_per_BTC_USDC"] = 1.0
    out = ns["price_orders"](changed)
    assert same(out.recommended_premium_USDC, base), "a premium moved when only outcomes, paid prices or bases changed"


def test_quote_ignores_future_candles_with_fixed_parameters(ns):
    raw = pd.read_csv(ns["BLIND_CSV"], dtype=str)
    for i in [5, 2500, 4154]:
        row = raw.iloc[[i]]
        q = ns["price_orders"](row).recommended_premium_USDC.iloc[0]
        k = ns["last_closed_minute"](ns["parse_times"](row.createdAt), ns["mkt"])[0]
        c = ns["candles"].copy()
        later = np.arange(len(c)) >= k + 1
        c.loc[later, "close"] *= 1 + 0.05 * np.random.default_rng(i).standard_normal(later.sum())
        mkt_x = ns["build_market"](c, ns["releases"])
        q_x = ns["price_orders"](row, mkt_=mkt_x, bars_=ns["bar_indicators"](mkt_x)).recommended_premium_USDC.iloc[0]
        assert q == q_x, f"blind row {i}: the quote moved when only candles at or after the order changed"


def test_earlier_candles_move_fair_value_and_an_unclipped_quote(ns):
    out = ns["val_pred"]
    free = out[(out["shape"] > 0.81) & (out["shape"] < 1.19) & (out.recommended_premium_USDC > out.fair_value_USDC * 1.001)]
    assert len(free), "no unclipped blind order to test"
    i = int(free.row_position.iloc[len(free) // 2])
    row = pd.read_csv(ns["BLIND_CSV"], dtype=str).iloc[[i]]
    k = ns["last_closed_minute"](ns["parse_times"](row.createdAt), ns["mkt"])[0]
    c = ns["candles"].copy()
    recent = (np.arange(len(c)) >= k - 59) & (np.arange(len(c)) <= k)
    c.loc[recent, "close"] *= 1 + 0.02 * np.random.default_rng(3).standard_normal(recent.sum())
    mkt_x = ns["build_market"](c, ns["releases"])
    new = ns["price_orders"](row, mkt_=mkt_x, bars_=ns["bar_indicators"](mkt_x)).iloc[0]
    assert new.fair_value_USDC != out.fair_value_USDC.iloc[i], "fair value did not respond to the last hour's candles"
    assert new.recommended_premium_USDC != out.recommended_premium_USDC.iloc[i], "an unclipped quote did not respond"


def test_single_row_equals_batch_and_n_fixed(ns):
    raw = pd.read_csv(ns["BLIND_CSV"], dtype=str)
    batch, n_before = ns["val_pred"], ns["FINAL"]["n"]
    for i in [0, 1897, 1898, 4000]:
        one = ns["price_orders"](raw.iloc[[i]]).recommended_premium_USDC.iloc[0]
        assert abs(one - batch.recommended_premium_USDC.iloc[i]) <= 1e-9 * one, f"row {i}: single-row price differs from batch"
    assert ns["FINAL"]["n"] == n_before, "n changed during inference"


def test_final_bounds_floor_and_calibration(ns):
    out, lo, hi = ns["val_pred"], *ns["SETTINGS"]["band"]
    q, fv, pr = out.recommended_premium_USDC.to_numpy(), out.fair_value_USDC.to_numpy(), out.predicted_reference_premium_USDC.to_numpy()
    assert (q >= fv * (1 - 1e-12)).all(), "a final quote is below fair value"
    free = q > fv * (1 + 1e-12)
    r = q[free] / pr[free]
    assert ((r >= lo - 1e-12) & (r <= hi + 1e-12)).all(), "a final quote is outside the 0.8-1.2 band without the floor"
    fit = ns["final_fit"]
    total = ns["quote_f1"](fit.p_ref.to_numpy(), fit.fv.to_numpy(), ns["FINAL"]["n"]).sum() / fit.p_ref.sum() - 1
    assert abs(total) <= ns["SETTINGS"]["n_tol"], f"final training total off by {total:.2e}"


def test_unseen_length_fallback(ns):
    # The May fold's reference saw no 1-hour orders: it must still give a finite, positive, interpolated price.
    ref = ns["refs"]["2026-05"]
    assert 3600 not in ref["dur_cols"], "fixture assumption changed"
    d = ns["panels"]["2026-06"]
    one_hour = d[d.productType == 3600].head(20)
    p = ns["reference_price"](ref, one_hour)
    assert np.isfinite(p).all() and (p > 0).all(), "no valid price for an unseen product length"
    lv = ref["levels"]
    assert min(lv[1800], lv[7200]) <= lv[3600] <= max(lv[1800], lv[7200]), "1-hour level is not between its neighbours"


# ---------- Sections 12-13 (report-only): risk measures and the exposure cap ----------

def test_daily_risk_on_a_toy_series(ns):
    r = ns["daily_risk"]([5.0, -3.0, -4.0, 6.0, -1.0])
    # cumulative P&L 5, 2, -2, 4, 3: the deepest fall from a running peak is 5 -> -2 = 7
    assert r["worst day"] == -4.0 and r["max drawdown"] == 7.0 and r["mean of worst 5% of days"] == -4.0, r
    assert r["profit"] == 3.0 and abs(r["daily sd"] - np.std([5, -3, -4, 6, -1], ddof=1)) < 1e-12, r


def test_exposure_cap_respects_the_cap_and_changes_no_quote(ns):
    b, cap = ns["cap_book"], ns["CAP_USDC"]
    created, closed, direction, notional = b.createdAt.to_numpy(), b.closedAt.to_numpy(), b.optionType.to_numpy(), b.notional.to_numpy()
    keep = ns["exposure_cap"](created, closed, direction, notional, cap)
    assert ns["exposure_cap"](created, closed, direction, notional, np.inf).all(), "an infinite cap declined an order"
    assert not keep.all(), "fixture assumption: the cap binds at least once"
    order = np.argsort(created, kind="stable")
    pos = np.empty(len(order), dtype=int)
    pos[order] = np.arange(len(order))
    for i in np.flatnonzero(keep):
        still_open = keep & (direction == direction[i]) & (pos <= pos[i]) & (closed > created[i])
        assert notional[still_open].sum() <= cap * (1 + 1e-12), "accepted orders exceed the cap"
    assert np.array_equal(b.q_F1.to_numpy(), ns["quotes_before"]), "the overlay changed a quote"


TESTS = [test_timestamp_formats, test_asof_strict, test_future_candles_do_not_move_features,
         test_past_candles_move_features, test_calendar_daylight_saving, test_release_window, test_outcomes_never_used,
         test_engine_windows_end_before_cutoff, test_fit_rows_before_cutoff, test_reference_ignores_prices_and_outcomes,
         test_fair_value_ignores_prices_and_outcomes, test_f1_floor_band_and_normalisation,
         test_event_times_from_checked_calendar, test_gini_permutation_ties_and_zero,
         test_c2_same_profit_without_demand_response]
PHASE5_TESTS = [test_final_fit_obeys_cutoff, test_mock_blind_file, test_premiums_ignore_outcomes_and_prices,
                test_quote_ignores_future_candles_with_fixed_parameters,
                test_earlier_candles_move_fair_value_and_an_unclipped_quote, test_single_row_equals_batch_and_n_fixed,
                test_final_bounds_floor_and_calibration, test_unseen_length_fallback]

REPORT_TESTS = [test_daily_risk_on_a_toy_series, test_exposure_cap_respects_the_cap_and_changes_no_quote]


def run_all(ns):
    rows = []
    for t in TESTS + (PHASE5_TESTS if "price_orders" in ns else []) + (REPORT_TESTS if "exposure_cap" in ns else []):
        try:
            t(ns)
            rows.append({"check": t.__name__[5:].replace("_", " "), "status": "pass", "detail": ""})
        except AssertionError as e:
            rows.append({"check": t.__name__[5:].replace("_", " "), "status": "FAIL", "detail": str(e)})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    assert (out.status == "pass").all(), "a check failed: see the table above"
    return out
