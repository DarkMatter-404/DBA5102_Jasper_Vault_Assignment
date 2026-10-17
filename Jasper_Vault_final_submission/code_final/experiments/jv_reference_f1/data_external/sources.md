# External snapshots used by `pp_pricing.ipynb`

Built by `aman/fetch_external.py`. The notebook reads only these files, so it runs offline.

## 1. `macro_events_2026_checked.csv` — scheduled US releases

| Item | Detail |
| --- | --- |
| Source | Maksim's `maksim/data/macro_events_2026.csv` at commit `65daf8c840db98f336b29d2eaa4a9d9585e7c603` (his official URLs are kept in `source_url`) |
| Cross-check 1 | Subham's independent list in `subham/pricing/external.py` at commit `d717f9945357686e5813a1e484e04eb7f4d71c04`. **All 27 core rows (CPI, jobs report, FOMC) agree on date and time.** The only differences are PCE (optional, not in the core set): 22 Jan 2026 is 10:00 ET in Maksim's file (from the BEA embargo line) and 08:30 in Subham's; 29 Oct 2026 is missing from Subham's list |
| Cross-check 2 (official, read 15 Oct 2026) | Federal Reserve FOMC calendar page: 2026 meetings 27-28 Jan, 17-18 Mar, 28-29 Apr, 16-17 Jun, 28-29 Jul, 15-16 Sep, 27-28 Oct, 8-9 Dec; no unscheduled meetings listed. BLS archived releases: CPI 13 Feb 2026 and CPI 14 Oct 2026 embargoed until 8:30 a.m. ET; Employment Situation 11 Feb 2026 embargoed until 8:30 a.m. ET. The other dates rely on Maksim's second pass (embargo line read on every release, 14 Oct 2026); the BLS archive list pages show no dates in text |
| Timezone | `date_et` / `time_et` are America/New_York; `ts_utc` is converted with daylight saving (EDT from 8 Mar 2026) |
| Availability lag | None needed: release **times** are scheduled in advance. We never use the released numbers or surprises |
| Core set | CPI, NFP (jobs report), FOMC decision at 14:00 ET. PCE is kept in the file but used only as a declared optional variant |
| Coverage | 38 releases, 9 Jan – 29 Oct 2026 (27 core). Covers every training and blind order window |

## 2. `teammates/` — teammates' saved historical outputs (read-only)

| File | From | Rows | What it is |
| --- | --- | ---: | --- |
| `maksim_walk_forward.csv` | `maksim/results/walk_forward_orders_priced.parquet` @ `65daf8c` | 7,150 | Every resolved training order, priced by a market-only fit on candles before its month (Feb-Jul). Columns: features, expected move, fair value, his submitted price `max(FV x 1.25, base)` |
| `maksim_test_pre_june_fit.csv` | `maksim/results/test_orders_priced.parquet` @ `65daf8c` | 4,841 | June-July orders priced by ONE fit on candles before 1 June (a separate comparison; cutoffs differ from the walk-forward) |
| `subham_backtest_selected.csv` | `subham/outputs/backtest_prices.parquet` @ `d717f99` | 5,806 | His selected configuration (`hybrid_events`) on his May, June and July folds. `row_id` is the row position in the training CSV (his saved pandas index) |
| `inventory.json` | — | — | Commits, cutoffs, selection exposure and the validation material we deliberately excluded |

No validation-period rows are kept. Jay's saved results are July aggregates or use the EN release (7,831 rows) with relative factors, so Jay's model is N/A in our row-level scorecard.

## 3. Phase 4 snapshots (external series)

Fetched by `fetch_external.py market` and `fetch_external.py gdelt` on 16 Oct 2026 SGT; the access times below are UTC (15 Oct). A failed or blocked download is recorded here and logged as 'not run: data unavailable' (registry rule R3); no other source was substituted. FRED was tried twice, the second time with a 180 s timeout and 4 tries per series. GDELT was tried twice: the first attempt got no answer at the 15 Jan chunk, and a single test call right after it returned HTTP 429 ('Please limit requests to one every 5 seconds'); a slower retry (20 s between calls, 6 tries with growing waits) ran 03:20-03:43 SGT and got no answer for the first chunk. No partial GDELT data were kept.

| File | Registry | URL | Time zone | Availability lag used | Revisions | Status, coverage and missingness |
| --- | --- | --- | --- | --- | --- | --- |
| `fred_VIXCLS.csv` | 4a-1 | https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS | US trading days (no time zone; CBOE close at 16:15 ET) | usable from 22:00 UTC on the trading day | FRED may revise; snapshot = FRED's current values | FAILED (RuntimeError: FRED VIXCLS: no answer after 4 tries (timeout 180 s)); accessed 2026-10-15 19:36 UTC |
| `fred_DGS10.csv` | 4a-2 | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10 | US business days | one business day (H.15 publishes the next business day), usable from 22:00 UTC | FRED may revise; snapshot = current values | FAILED (RuntimeError: FRED DGS10: no answer after 4 tries (timeout 180 s)); accessed 2026-10-15 19:48 UTC |
| `fred_SP500.csv` | 4a-3 | https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500 | US trading days | usable from 22:00 UTC on the trading day | not revised in practice; snapshot = current values | FAILED (RuntimeError: FRED SP500: no answer after 4 tries (timeout 180 s)); accessed 2026-10-15 20:00 UTC |
| `binance_funding_BTCUSDC.csv` | 4a-4 | https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDC | UTC (fundingTime) | known at each settlement (00, 08, 16 UTC); used from one minute later | not revised | ok: 955 rows, 2025-12-01 00:00:00 to 2026-10-15 00:00:00; accessed 2026-10-15 18:59 UTC |
| `deribit_dvol_btc_hourly.csv` | 4a-5, 4c-4 | https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=3600 | UTC, hour start | usable at the bar close (hour start + 1 h) | not revised | ok: 7,633 rows, 2025-12-01 00:00:00 to 2026-10-15 00:00:00; accessed 2026-10-15 19:00 UTC |
| `fear_greed_daily.csv` | 4a-6 | https://api.alternative.me/fng/?limit=0&format=json | UTC day | previous UTC day's value (usable from 00:00 UTC the next day) | not revised | ok: 319 rows, 2025-12-01 to 2026-10-15; accessed 2026-10-15 19:00 UTC |
| `gdelt_bitcoin_hourly.csv` | 4b1-1, 4b1-2 | https://api.gdeltproject.org/api/v2/doc/doc?query=bitcoin%20sourcelang:english&mode=TimelineVolRaw&format=json | UTC, hour start | hours ending at least 1 h before the window starts | today's view of past counts, not a real-time vintage | FAILED (no answer for 2026-01-01 after retries) |

Not fetched on purpose: the Fed's broad dollar index (DTWEXBGS) is revised and no vintage was available in time (registry 4a-7).
