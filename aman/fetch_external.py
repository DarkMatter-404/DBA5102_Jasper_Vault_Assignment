"""Build the offline snapshots that pp_pricing.ipynb reads. Aman, 15-16 Oct 2026.

Run from anywhere, with the project environment:
    aman/.venv/bin/python aman/fetch_external.py [calendar | market | gdelt | all]     (default: calendar)

What it writes (all under aman/data_external/):
1. macro_events_2026_checked.csv  Maksim's release calendar, cross-checked against Subham's list
   and the official pages read on 15 Oct 2026 (see sources.md).
2. teammates/*.csv                Teammates' saved HISTORICAL outputs (training months only), read
   with `git show` at fixed commits. No branch is checked out and no validation rows are kept.
3. teammates/inventory.json       Commits, files, row counts, months, cutoffs and exposure notes.

4. fetch_status.json + one CSV per series (`market`): FRED VIXCLS / DGS10 / SP500, Binance BTCUSDC
   funding, Deribit hourly DVOL, Fear & Greed (Phase 4, registry 4a). A failed source is recorded, never replaced.
5. fetch_status_gdelt.json + gdelt_bitcoin_hourly.csv (`gdelt`): hourly GDELT counts for 'bitcoin'
   (registry 4b1), cached per chunk in gdelt_chunks/; marked failed unless hourly with >= 95% Feb-Oct coverage.
"""
import ast
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

AMAN = Path(__file__).resolve().parent
REPO = AMAN.parent
OUT = AMAN / "data_external"
TEAM = OUT / "teammates"

MAKSIM_COMMIT = "65daf8c840db98f336b29d2eaa4a9d9585e7c603"   # origin/maksim/pp-pricing-strategy, named in PLAN.md
MAIN_COMMIT = "d717f9945357686e5813a1e484e04eb7f4d71c04"     # origin/main on 15 Oct 2026 (Subham, Jay)
CORE_EVENTS = ["CPI", "NFP", "FOMC"]

# Official pages read on 15 Oct 2026 (WebFetch). Everything else relies on Maksim's second pass of 14 Oct.
OFFICIAL_CHECKS = {
    ("CPI", "2026-02-13"): "BLS archived release cpi_02132026: embargoed until 8:30 a.m. ET Fri 13 Feb 2026",
    ("CPI", "2026-10-14"): "BLS archived release cpi_10142026: embargoed until 8:30 a.m. ET Wed 14 Oct 2026",
    ("NFP", "2026-02-11"): "BLS archived release empsit_02112026: embargoed until 8:30 a.m. ET Wed 11 Feb 2026",
}
FED_CALENDAR_2026 = ["01-28", "03-18", "04-29", "06-17", "07-29", "09-16", "10-28"]  # 2nd meeting day, Fed calendar page


def git_show(commit, path):
    """Bytes of one file at one commit (read-only; nothing is checked out)."""
    res = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=REPO, capture_output=True, check=True)
    return res.stdout


def subham_calendar():
    """Subham's hard-coded release list, parsed from his source without running it."""
    src = git_show(MAIN_COMMIT, "subham/pricing/external.py").decode()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and n.targets[0].id == "_EVENTS")
    rows = []
    for (kind, hhmm, _url), days in ast.literal_eval(node.value).items():
        name = {"Jobs": "NFP"}.get(kind, kind)
        rows += [{"event_type": name, "date_et": f"2026-{md}", "time_et_subham": hhmm} for md in days]
    return pd.DataFrame(rows)


def build_calendar():
    """Maksim's calendar plus the cross-check columns. Times converted America/New_York -> UTC."""
    ev = pd.read_csv(io.BytesIO(git_show(MAKSIM_COMMIT, "maksim/data/macro_events_2026.csv")))
    sub = subham_calendar()
    ev = ev.merge(sub, on=["event_type", "date_et"], how="left")
    et = pd.to_datetime(ev.date_et + " " + ev.time_et).dt.tz_localize("America/New_York")
    ev["ts_utc"] = et.dt.tz_convert("UTC").dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M")
    ev["in_core_set"] = ev.event_type.isin(CORE_EVENTS)
    ev["matches_subham"] = ev.time_et_subham.eq(ev.time_et)
    fed = ev.event_type.eq("FOMC") & ev.date_et.str[5:].isin(FED_CALENDAR_2026)
    ev["official_check_15oct"] = [OFFICIAL_CHECKS.get((t, d), "") for t, d in zip(ev.event_type, ev.date_et)]
    ev.loc[fed, "official_check_15oct"] = "Fed FOMC calendar page: meeting dates match (2:00 p.m. ET statement per Maksim's pass)"
    cols = ["event_type", "date_et", "time_et", "ts_utc", "in_core_set", "matches_subham", "time_et_subham",
            "official_check_15oct", "source_url", "note"]
    return ev[cols].sort_values("ts_utc").reset_index(drop=True)


def maksim_snapshot(name):
    """Maksim's saved priced orders (training months only), with the columns we compare against."""
    d = pd.read_parquet(io.BytesIO(git_show(MAKSIM_COMMIT, f"maksim/results/{name}.parquet")))
    keep = ["row_id", "createdAt", "productType", "quantity_BTC", "strikePrice", "last_closed_minute",
            "log_var_60m", "log_var_240m", "log_var_1440m", "log_var_10080m", "log_seas_window", "log_seas_last60",
            "event_in_window", "expected_abs_move", "fair_value_USDC", "floor_applied", "model_premium_USDC"]
    d = d[keep + (["month"] if "month" in d.columns else [])]
    assert pd.to_datetime(d.createdAt).max() < pd.Timestamp("2026-07-31 17:11:12")  # training period only
    return d


def subham_snapshot():
    """Subham's saved backtest prices for his selected configuration (May, June, July folds)."""
    d = pd.read_parquet(io.BytesIO(git_show(MAIN_COMMIT, "subham/outputs/backtest_prices.parquet")))
    cfg = json.loads(git_show(MAIN_COMMIT, "subham/outputs/selected_config.json"))["name"]
    d = d[d.config == cfg].rename_axis("row_id").reset_index()
    d = d.rename(columns={"premiumAmount_USDC": "model_premium_USDC"})
    keep = ["row_id", "fold", "config", "anchor_source", "expected_payout_per_BTC", "reference_price_per_BTC",
            "premium_per_BTC", "model_premium_USDC", "pricing_multiplier"]
    return d[keep], cfg


def maksim_engine_diagnostics():
    """Maksim's saved engine results we try to reproduce (training period only).

    From the model card we keep only the fit metadata and the time-of-day profile; its other fields
    describe the validation file and are left out on purpose.
    """
    for name in ["move_forecast_scores", "move_model_coefficients_dev", "overfitting/time_of_day_profile_early_vs_late",
                 "payout_over_fair_value_walk_forward"]:
        raw = git_show(MAKSIM_COMMIT, f"maksim/results/{name}.csv")
        (TEAM / f"maksim_{name.split('/')[-1]}.csv").write_bytes(raw)
    card = json.loads(git_show(MAKSIM_COMMIT, "maksim/outputs/model_card.json"))
    keep = ["fit_end_utc", "event_types", "event_jump_bps", "events_used_in_fit",
            "time_of_day_profile_weekday_then_weekend_et_half_hours"]
    (TEAM / "maksim_model_card_profile.json").write_text(json.dumps({k: card[k] for k in keep}, indent=1))


def inventory(files, subham_cfg):
    """What we took from whom, at which commit, and what the team has already seen."""
    return {
        "built": pd.Timestamp.now(tz="Asia/Singapore").strftime("%Y-%m-%d %H:%M SGT"),
        "maksim": {"commit": MAKSIM_COMMIT, "ref": "origin/maksim/pp-pricing-strategy",
                   "files": {k: v for k, v in files.items() if k.startswith("maksim")},
                   "cutoffs": "walk-forward: market-only fit on candles before each month start (Feb-Jul); "
                              "test file: one fit on candles before 2026-06-01, priced on June-July orders",
                   "model_as_submitted": "premium = max(fair value x 1.25, API base) per BTC x quantity",
                   "selection_exposure": "variant list and 25% margin were chosen with June-July test results visible",
                   "later_commits_on_main": "d76caeb dynamic delta hedge overlay, da4d867 docs (not used here)"},
        "subham": {"commit": MAIN_COMMIT, "ref": "origin/main", "selected_config": subham_cfg,
                   "files": {k: v for k, v in files.items() if k.startswith("subham")},
                   "cutoffs": "each month fitted on orders created and EXPIRED before the month starts",
                   "selection_exposure": "configuration chosen after seeing the May-July backtest folds"},
        "jay": {"commit": MAIN_COMMIT, "ref": "origin/main",
                "row_level_history": "none saved: v3.2 keeps July aggregates only, and v1/v2 row results use "
                                     "the EN release (7,831 rows) with relative factors needing a compatible "
                                     "reference price -> N/A in our scorecard"},
        "prior_validation_exposure": [
            "Maksim: run_sealed_check.py and results/sealed_check/ rebuild validation-period payouts from candles; "
            "validation rows also appear in results/extensions/exposure_limits.csv and hedging_summary.csv",
            "Subham: validation_premiums.csv and validation summaries (premiums and expected payouts, no realised outcomes)",
            "Jay: revision_v3_2/results/validation_predictions.csv (relative factors)",
            "Aman/Claude, 14-15 Oct: profiled validation INPUTS only; while reading Maksim's two extension CSVs in full "
            "on 15 Oct, their post-hoc validation-period rows were displayed. They are not stored or used here.",
        ],
        "excluded_on_purpose": ["maksim/results/sealed_check/*", "validation rows of maksim/results/extensions/*",
                                "subham/outputs/*valid*", "jay/revision_v3_2/results/validation_predictions.csv"],
    }


# ---------- Phase 4 external series (registry rows 4a-1 to 4a-6 and 4b1) ----------
import time
from datetime import datetime, timezone

import requests

STATUS_FILE = OUT / "fetch_status.json"
START, END = "2025-12-01", "2026-10-15"          # a month of history before January, through the blind period


def get_json(url, params, tries=4, pause=2.0):
    # GET with retries and a growing wait; returns (json or None, message).
    msg = ""
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60, headers={"User-Agent": "NUS-MSBA-student-project"})
            if r.status_code == 200:
                return r.json(), "ok"
            msg = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            msg = type(e).__name__
        time.sleep(pause * 2 ** i)
    return None, msg


def fred_series(series_id, tries=4, timeout=180):
    url, text = "https://fred.stlouisfed.org/graph/fredgraph.csv", None
    for i in range(tries):                                                   # same endpoint, retried with a growing wait
        try:
            r = requests.get(url, params={"id": series_id, "cosd": START, "coed": END}, timeout=timeout,
                             headers={"User-Agent": "NUS-MSBA-student-project"})
            if r.status_code == 200:
                text = r.text
                break
        except requests.RequestException:
            pass
        time.sleep(10 * 2 ** i)
    if text is None:
        raise RuntimeError(f"FRED {series_id}: no answer after {tries} tries (timeout {timeout} s)")
    d = pd.read_csv(io.StringIO(text))
    d.columns = ["date", "value"]
    d["value"] = pd.to_numeric(d["value"], errors="coerce")             # FRED marks holidays as blank or "."
    return d.dropna()


def binance_funding():
    url, rows = "https://fapi.binance.com/fapi/v1/fundingRate", []
    start = int(pd.Timestamp(START, tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp(END, tz="UTC").timestamp() * 1000)
    while start < end:
        data, msg = get_json(url, {"symbol": "BTCUSDC", "startTime": start, "endTime": end, "limit": 1000})
        if data is None:
            raise RuntimeError(f"Binance funding: {msg}")
        if not data:
            break
        rows += data
        start = data[-1]["fundingTime"] + 1
        time.sleep(1)
    d = pd.DataFrame(rows)
    d["funding_time_utc"] = pd.to_datetime(d.fundingTime, unit="ms").dt.strftime("%Y-%m-%d %H:%M:%S")
    return d[["funding_time_utc", "fundingRate"]].rename(columns={"fundingRate": "funding_rate"}).drop_duplicates()


def deribit_dvol():
    url, rows = "https://www.deribit.com/api/v2/public/get_volatility_index_data", []
    start = int(pd.Timestamp(START, tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp(END, tz="UTC").timestamp() * 1000)
    step = 40 * 24 * 3600 * 1000                                             # 960 hourly bars per call
    for s in range(start, end, step):
        data, msg = get_json(url, {"currency": "BTC", "start_timestamp": s, "end_timestamp": min(s + step, end), "resolution": "3600"})
        if data is None or "result" not in data:
            raise RuntimeError(f"Deribit DVOL: {msg}")
        rows += data["result"]["data"]
        time.sleep(1)
    d = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"]).drop_duplicates("ts").sort_values("ts")
    d["hour_start_utc"] = pd.to_datetime(d.ts, unit="ms").dt.strftime("%Y-%m-%d %H:%M:%S")
    return d[["hour_start_utc", "open", "high", "low", "close"]]


def fear_greed():
    data, msg = get_json("https://api.alternative.me/fng/", {"limit": 0, "format": "json"})
    if data is None:
        raise RuntimeError(f"Fear & Greed: {msg}")
    d = pd.DataFrame(data["data"])
    d["date_utc"] = pd.to_datetime(d.timestamp.astype(int), unit="s").dt.strftime("%Y-%m-%d")
    d = d[(d.date_utc >= START) & (d.date_utc <= END)]
    return d[["date_utc", "value"]].sort_values("date_utc")


def fetch_market_series():
    """4a: save each series as a CSV snapshot; a failure is recorded, never replaced by another source."""
    status = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    jobs = {"fred_VIXCLS": lambda: fred_series("VIXCLS"), "fred_DGS10": lambda: fred_series("DGS10"),
            "fred_SP500": lambda: fred_series("SP500"), "binance_funding_BTCUSDC": binance_funding,
            "deribit_dvol_btc_hourly": deribit_dvol, "fear_greed_daily": fear_greed}
    for name, job in jobs.items():
        if status.get(name, {}).get("status") == "ok" and (OUT / f"{name}.csv").exists():
            continue                                                          # keep a good snapshot; only retry failures
        try:
            d = job()
            d.to_csv(OUT / f"{name}.csv", index=False)
            status[name] = {"status": "ok", "rows": len(d), "first": str(d.iloc[0, 0]), "last": str(d.iloc[-1, 0]),
                            "accessed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
        except Exception as e:                                                  # recorded as 'not run: data unavailable'
            status[name] = {"status": "failed", "message": f"{type(e).__name__}: {e}"[:300],
                            "accessed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
        print(name, status[name])
    STATUS_FILE.write_text(json.dumps(status, indent=1))


GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = "bitcoin sourcelang:english"           # copied exactly from subham/data/external/gdelt/TimelineVolRaw_20260125.json


GDELT_CACHE = OUT / "gdelt_chunks"                    # one raw JSON per chunk, so a rerun continues where it stopped
GDELT_PAUSE = 20                                       # seconds between calls (GDELT asks for at least 5)


def gdelt_chunk(start, end):
    # One TimelineVolRaw call, cached on disk; waits GDELT_PAUSE before each call and backs off after a refusal.
    cache = GDELT_CACHE / f"TimelineVolRaw_{start:%Y%m%d%H}_{end:%Y%m%d%H}.json"
    params = {"query": GDELT_QUERY, "mode": "TimelineVolRaw", "format": "json",
              "STARTDATETIME": f"{start:%Y%m%d%H%M%S}", "ENDDATETIME": f"{end:%Y%m%d%H%M%S}"}
    text = cache.read_text() if cache.exists() else None
    for i in range(6):
        if text is not None:
            break
        time.sleep(GDELT_PAUSE * 2 ** i)
        try:
            r = requests.get(GDELT_URL, params=params, timeout=90, headers={"User-Agent": "NUS-MSBA-student-project"})
            if r.status_code == 200 and r.text.strip().startswith("{"):
                text = r.text
                GDELT_CACHE.mkdir(exist_ok=True)
                cache.write_text(text)
        except requests.RequestException:
            pass
    if text is None:
        return None, None
    d = json.loads(text)
    return d.get("query_details", {}).get("date_resolution"), (d["timeline"][0]["data"] if d.get("timeline") else [])


def fetch_gdelt():
    """4b1: hourly counts of English articles matching 'bitcoin', 1 Jan - 14 Oct 2026, in 7-day chunks."""
    status_file = OUT / "fetch_status_gdelt.json"                         # its own file: GDELT can run beside 4a
    status = {}
    rows, start, end, step, calls = [], pd.Timestamp("2026-01-01"), pd.Timestamp("2026-10-15"), pd.Timedelta(days=7), 0
    while start < end:
        stop = min(start + step, end)
        resolution, points = gdelt_chunk(start, stop)
        calls += 1
        if points is None:
            status["gdelt_bitcoin_hourly"] = {"status": "failed", "message": f"no answer for {start:%Y-%m-%d} after retries", "calls": calls,
                                              "accessed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
            status_file.write_text(json.dumps(status, indent=1))
            print(status["gdelt_bitcoin_hourly"])
            return
        if resolution != "hour" and step > pd.Timedelta(days=1):              # coarser than hourly: shrink the chunk
            step = step / 2
            continue
        rows += points
        start, step = stop, pd.Timedelta(days=7)
    d = pd.DataFrame(rows)
    d["hour_utc"] = pd.to_datetime(d.date, format="%Y%m%dT%H%M%SZ")
    d = d.drop_duplicates("hour_utc").sort_values("hour_utc")[["hour_utc", "value", "norm"]]
    hourly = bool((d.hour_utc.diff().dropna() % pd.Timedelta("1h") == pd.Timedelta(0)).all())
    span = pd.date_range("2026-02-01", "2026-10-14 02:00", freq="h")
    coverage = float(span.isin(d.hour_utc).mean())
    ok = hourly and coverage >= 0.95
    d.assign(hour_utc=d.hour_utc.dt.strftime("%Y-%m-%d %H:%M")).to_csv(OUT / "gdelt_bitcoin_hourly.csv", index=False)
    status["gdelt_bitcoin_hourly"] = {"status": "ok" if ok else "failed", "rows": len(d), "calls": calls, "hourly_spacing": hourly,
                                      "coverage_feb_oct": coverage, "first": str(d.hour_utc.iloc[0]), "last": str(d.hour_utc.iloc[-1]),
                                      "accessed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
    status_file.write_text(json.dumps(status, indent=1))
    print(status["gdelt_bitcoin_hourly"])


def main():
    TEAM.mkdir(parents=True, exist_ok=True)
    cal = build_calendar()
    cal.to_csv(OUT / "macro_events_2026_checked.csv", index=False)
    files = {}
    for name, short in [("walk_forward_orders_priced", "maksim_walk_forward"), ("test_orders_priced", "maksim_test_pre_june_fit")]:
        d = maksim_snapshot(name)
        d.to_csv(TEAM / f"{short}.csv", index=False)
        files[short] = {"source": f"maksim/results/{name}.parquet", "rows": len(d)}
    s, cfg = subham_snapshot()
    s.to_csv(TEAM / "subham_backtest_selected.csv", index=False)
    files["subham_backtest_selected"] = {"source": "subham/outputs/backtest_prices.parquet", "rows": len(s),
                                         "folds": s.fold.value_counts().sort_index().to_dict()}
    maksim_engine_diagnostics()
    (TEAM / "inventory.json").write_text(json.dumps(inventory(files, cfg), indent=2))
    core = cal[cal.in_core_set]
    print(f"calendar: {len(cal)} releases ({len(core)} core); core rows matching Subham: {core.matches_subham.sum()}/{len(core)}")
    print(json.dumps(files, indent=1))


if __name__ == "__main__":
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else "calendar"     # calendar | market | gdelt | all
    if what in ("calendar", "all"):
        main()
    if what in ("market", "all"):
        fetch_market_series()
    if what in ("gdelt", "all"):
        fetch_gdelt()
