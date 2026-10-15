# Code explanation — `aman/pp_pricing.ipynb`

**Status: final.** Team decision at the 16 Oct regroup: model F1, theta_level = 0, band 0.8-1.2. The specification was
locked at 2026-10-16 04:46 SGT (section 11). Sections 12-13 are report-only risk tables, and section 14 is the 544-row
reference check, first run after the lock.

This file is for a teammate who has to rerun the notebook or defend it. It explains every section and function: what it
does, its inputs and outputs, the equation in plain text, how it avoids look-ahead, and where the idea comes from. The
results themselves are explained in `REPORT_EXPLANATION.md`; the plan the code follows is `PLAN.md` (JV-05, amended 16 Oct).

## 1. How to run it

| Step | Command (from the repository root) | Notes |
|---|---|---|
| Environment (once) | `uv venv --python 3.12 aman/.venv` then `uv pip install --python aman/.venv/bin/python -r aman/requirements.txt` | Python 3.12.14 and the exact versions in `requirements.txt` (numpy 2.5.4, pandas 3.0.6, scipy 1.18.1, scikit-learn 1.9.1, statsmodels 0.15.0, matplotlib 3.11.2) |
| Run everything | `aman/.venv/bin/jupyter nbconvert --to notebook --execute --inplace aman/pp_pricing.ipynb --ExecutePreprocessor.timeout=1800` | About one minute (55 s on a laptop). No internet needed. Stops at the first failed check |
| Refresh snapshots (optional) | `aman/.venv/bin/python aman/fetch_external.py [calendar \| market \| gdelt \| all]` | Needs internet and the git history (teammates' files are read with `git show` at fixed commits). Not needed to rerun the notebook |

Everything is seeded (`SEED = 2026`) and every input is a saved file, so a rerun reproduces every number, and
`validation_predictions.csv` byte for byte (its computed columns are rounded to 6 decimals; see section 11). The
notebook writes only inside `aman/`.

**What is optional.** `fetch_external.py` is optional because its outputs are saved. Inside the notebook nothing is
optional: Phase 4 reads saved snapshots, and a candidate whose snapshot is missing is logged as "not run: data
unavailable" instead of failing.

## 2. Files

| Path | What it is |
|---|---|
| `aman/pp_pricing.ipynb` | The whole model, top to bottom (sections 1-14 plus checks and phase summaries) |
| `aman/checks/test_pricing.py` | 25 checks, called once at the end of the notebook (section 8 below) |
| `aman/checks/jump_attribution.py` | Standalone script behind the payout-attribution table; its logic is repeated in notebook section 9.9 |
| `aman/fetch_external.py` | Builds every snapshot in `aman/data_external/` (calendar, teammates' outputs, Phase 4 series, GDELT) |
| `aman/data_external/` | Offline snapshots; `sources.md` lists URL, access time, time zone, lag, revisions and coverage for each |
| `aman/team_scorecard/` | Every table the notebook saves (list in section 7) |
| `aman/validation_predictions.csv` | Final prices for the 4,155 blind orders (status "final") |
| `aman/model_params.json` | Every fitted parameter of the final model, `"spec_locked": true`, the lock time and the predictions' SHA-256 |
| `aman/README.md`, `aman/PLAN.md`, `aman/TEAM_SUMMARY.md`, `aman/REPORT_EXPLANATION.md` | Start page, plan, one-page team summary, plain-English results |

## 3. Where each data file comes from

| File | Source | Used for |
|---|---|---|
| `data/with_base_premium/pp_transactions_training.csv` | JV's training release: 7,204 orders, Feb-Jul 2026 (7,150 resolved) | Fitting the reference price, scoring |
| `data/validation/pp_transactions_validation.csv` | JV's blind file: 4,155 orders, 31 Jul - 14 Oct 2026, premiums and payouts blank | Phase 5 prices only |
| `data/validation/btc_market_history.csv` | One-minute BTC candles, 1 Jan 00:00 - 14 Oct 03:59 UTC (412,080 rows) | Every market feature and the move model |
| `aman/data_external/macro_events_2026_checked.csv` | Maksim's release calendar at commit `65daf8c`, cross-checked against Subham's list (all 27 core rows agree) and official Fed/BLS pages | Release times (times only, never the released numbers) |
| `aman/data_external/teammates/` | Maksim's and Subham's saved training-period outputs at fixed commits, plus `inventory.json` | Comparators M and S; reproducing Maksim's engine |
| `aman/data_external/binance_funding_BTCUSDC.csv`, `deribit_dvol_btc_hourly.csv`, `fear_greed_daily.csv` | Public APIs, fetched 16 Oct 2026 | Phase 4 candidates 4a-4, 4a-5 (and 4c-4), 4a-6 |
| FRED VIX, 10-year yield, S&P 500 | FRED did not answer (4 tries per series, 180 s timeout, 16 Oct): no snapshot, so not run | Phase 4 candidates 4a-1 to 4a-3 |
| GDELT hourly "bitcoin" counts | GDELT did not answer (6 tries with growing waits, 03:20-03:43 SGT 16 Oct): no snapshot, so not run | Phase 4 candidates 4b1-1 and 4b1-2 |

`fetch_status.json` and `fetch_status_gdelt.json` record every download attempt. A failed source is never replaced by
another source (registry rule R3).

## 4. The notebook, section by section

Notation: q = quantity in BTC, K = strike, T = product length in years (seconds / (365 x 24 x 3600)), A = JV's actual
premium, FV = fair value, P_ref = reference price, k = index of the last one-minute candle that closed before the order.

### Section 1 — Setup
Imports, versions, paths and constants: `DURATIONS_S` (the seven lengths, 30 min to 24 h), `TRAIL_MIN` (60, 240, 1,440
and 10,080 minutes), `CORE_EVENTS` (CPI, NFP, FOMC), `EVENT_WINDOW_MIN = 30`, `FINAL_CUTOFF = 2026-07-31 17:11:00`
(the first blind order) and `ATM = 0.3989`.

### Section 2 — Orders

| Function | What it does | Guard / source |
|---|---|---|
| `parse_times(s)` | Parses the two timestamp formats in the files, `2026-08-24 16:05:59` and minute-only `2026/7/31 17:11`. Anything else becomes missing | `load_orders` stops if a `createdAt` does not parse |
| `load_orders(path)` | Reads an order file and adds `row` (position in the file, the only key), `T_years`, `notional = q x K`, `scale = 0.3989 x q x K x sqrt(T)`, `base_usd = q x base per BTC` (blank when there is no base), `month`, `day` | `closedAt` is parsed but only used to decide which labels were known at a cutoff (`eligible`) |
| `check_row`, `implied_vol` | Compare a number with its verified value. `implied_vol = sum(amount) / sum(scale)` puts base, JV's price and payouts on one volatility ruler | Black & Scholes (1973), short at-the-money options |

The first table must reproduce 12 numbers verified by two earlier scripts (for example premium 248,089, payouts
230,652, loss ratio 0.930, charged vol 0.494). The blind-file table confirms 4,155 orders, 2,195 without a base,
1,898 minute-only timestamps in rows 0-1,897, and that `closedAt` is filled in (so it is never an input).

### Section 3 — BTC candles and quote-time features

| Function | What it does | Guard / source |
|---|---|---|
| `load_candles(path)` | Reads the one-minute candles | Stops unless the grid is gap-free |
| `load_releases(path, types)` | Core release times from the checked calendar | Times are scheduled in advance; released numbers are never read |
| `minute_index(ts, t0)` | Minute number since 1 Jan 2026 00:00 UTC of the candle containing each time | — |
| `build_market(candles, releases)` | Log prices, one-minute returns r, `cum_r2` = running sum of r², a 96-slot New York half-hour slot for every minute (weekday 0-47, weekend 48-95), release flags and their running count. Calendar arrays run two days past the last candle | Calendar arrays use no prices |
| `last_closed_minute(created)` | k = `minute_index(createdAt) - 1` | **The as-of rule**: the candle that contains `createdAt` is still open |
| `trailing_var(mkt, k, h)` | Mean squared one-minute return over the h minutes ending at k: `(cum_r2[k+1] - cum_r2[k+1-h]) / h` | Uses minutes up to k only |
| `release_in_window(mkt, k, T)` | 1 if a core release falls in minutes k+1 to k+T | Release times only |
| `bar_indicators(mkt)` | RSI 14 (Wilder smoothing) and Bollinger %b (20 bars, 2 sd) on clock-aligned 15-minute bars: `%b = (close - (mean - 2 sd)) / (4 sd)` | Both are running (causal) calculations |
| `add_market_features(d, mkt, bars)` | Adds k, log realised variance over 60/240/1,440/10,080 min, annualised RV_60, RV_1d, RV_7d (`sqrt(variance x 525,600)`), RSI and %b of the last finished bar `(k+1)//15 - 1`, the release flag and the time-of-day slot | Every input ends at minute k |
| `fit_tod_profile(mkt, k_start, k_end)` | Time-of-day profile: mean squared return in each of the 96 slots / overall mean, leaving out the 30 minutes after each release. Also returns its running sum over all minutes | Fitted per fold on minutes up to the cutoff (Maksim's design) |
| `window_mean(cum, a, b)` | Average profile value over minutes a..b | — |
| `release_excess_var(mkt, k_end)` | For each release whose 30-minute window ends by k_end: squared 30-minute log move after it, minus the mean squared move over the same UTC half hour on up to 28 earlier release-free weekdays | Maksim's estimator; only releases before the cutoff |

A pandas `merge_asof` on candle close times (`allow_exact_matches=False`) cross-checks k for all 11,359 orders; the
largest gap between the feature candle's close and `createdAt` is 59.0 seconds. Realised variance at several horizons
follows Corsi (2009).

### Section 4 — Teammates' saved outputs

| Function | What it does | Guard / source |
|---|---|---|
| `check_mapping(snap)` | Confirms every saved teammate row points at the same training order (same time, length, size and strike; Subham's fold = the order's month) | Training-period rows only; validation material listed in `inventory.json` was excluded on purpose |

Our features match Maksim's saved ones to 4.2e-11 and his release flags on 100% of orders.

### Section 5 — Pre-registration

`SETTINGS` and `FOLDS` hold every setting, grid and threshold, fixed on 15 Oct before any held-out score. Folds: May
(fit before 1 May, defaults), June (choose on May, refit through May), July (choose on June, retrospective), final (the
July fold's choices, refit before `FINAL_CUTOFF`). Section 5.1 adds the 16 Oct notes (model list, F1h infeasible,
clipping, hand-entered dates) without changing a setting. The cell after it asserts that every event time used by a
feature comes from `macro_events_2026_checked.csv`.

### Section 6 — Fair-value engine (Maksim's design, reimplemented)

| Function | What it does | Equation / guard / source |
|---|---|---|
| `to_minute(mkt, ts)` | Minute index of one time | — |
| `market_windows(k_from, k_to, t)` | Window start minutes every 5 minutes, after one week of warm-up, such that every window ends by k_to | Guard: no training window crosses the cutoff |
| `engine_matrix(mkt, cum_prof, k, t)` | Six inputs per window: log realised variance over 60, 240, 1,440, 10,080 min before the window, and the log mean profile over the window and over the last 60 minutes | Inputs end at minute k |
| `abs_move_bps(mkt, k, t)` | Target y = 10,000 x \|log P[k+t] - log P[k]\| | Used only to fit and to score, never as a feature |
| `fit_engine(mkt, cutoff, k_event)` | Per length: `StandardScaler` then `PoissonRegressor(alpha=0, max_iter=1000)` of y on the six inputs; profile and release variance fitted on minutes before the cutoff. A non-converged fit stops the notebook | Maksim's engine; Poisson GLM with log link |
| `jump_var(eng, k_event)` | Release variance, shrunk: `m / (m + k_event) x max(mean excess, 0)`, m = releases seen | **Our one declared change** to Maksim's engine |
| `predict_move(...)` | Expected absolute move: s = E\|R\| x sqrt(pi/2); `s_total² = s² + jump_var x release flag`; returns `s_total / sqrt(pi/2)` | Normal-move identity E\|R\| = s x sqrt(2/pi) |
| `fair_value(eng, mkt, d, k_event)` | **FV = q x K x E\|R_total\| / 2**: at the money, protection pays about half the expected absolute move | Expected payout = the cost of selling the protection |
| `poisson_deviance(y, p)` | `2 x (y log(y/p) - (y - p))` per window | Proper score for a mean forecast |
| `window_scores(...)` | Mean deviance per length on the windows of a period (optionally only windows with a release) | — |
| `choose_k_event(...)` | Picks k_event in {0, 5, 10, 20} by mean deviance on the calibration month's release windows; exact ties go to 10 | Calibration month is before the test month |
| `boot_ratio(d, num, den)` | Ratio of totals with a 90% interval from resampling whole days | Diagnostic only |

Reproduction anchors (they must hold): mean deviance 47.5130 on Maksim's June-July windows, coefficients equal to his
pre-June fit (largest difference 1.5e-13), release term 45.48 bps from 13 releases, and his time-of-day diagnostics. Section 6.5 compares payouts
with fair value by length (Feb-Jul walk-forward); it is a diagnostic and changes nothing in the core model.

### Section 7 — Reference price (our estimate of JV's current price)

| Function | What it does | Equation / guard / source |
|---|---|---|
| `add_ref_columns(d)` | Adds log(RV_60 / RV_1d), log RV_1d, log RV_7d | Pre-trade only |
| `eligible(cutoff)` | Training labels created **and settled** before the cutoff | Guard: a fit never sees an outcome that was unknown at its cutoff |
| `ref_design(d, dur_cols)` | Length dummies plus RSI, %b and the three log-vol columns | — |
| `reference_raw(ref, d)` | dur: `P_ref_raw = scale x level(length) x RV_1d`; ridge: `scale x exp(predicted log ratio) x RV_1d` for lengths seen in the fit, the dur level otherwise | Never reads the base, paid price or markup |
| `fit_reference(fit, kind, value)` | Target ratio = (A / scale) / RV_1d. dur: per-length ratio shrunk toward the pooled ratio with weight n / (n + k_ref); levels for all seven lengths by linear interpolation in log T (nearest level at the ends). ridge: `StandardScaler` + `Ridge(alpha)` on log ratio, weights = notional / mean notional. Level factor = sum(A) / sum(P_ref_raw) over the last three eligible months | Credibility-style shrinkage; ridge regression |
| `reference_price(ref, d)` | `reference_raw x level_factor` | — |
| `ref_errors(p_ref, d)` | bias = (sum P_ref - sum A) / sum A; weighted error = sum(notional x \|P_ref / A - 1\|) / sum(notional) | — |
| `choose_reference(inner_fit, cal)` | dur with k_ref in {25, 100, 400} (ties to 100); ridge with alpha in {100, 10, 1} only if it beats the best dur by at least 0.5 points | Chosen on the calibration month, before the test month |

Audit (pre-registered): in May and June, \|bias\| <= 15% and weighted error <= 30%.

### Section 8 — The price step

| Function | What it does | Equation / guard / source |
|---|---|---|
| `quote_f1(p_ref, fv, n, lam, theta, floor)` | `shape = 1 + lam x (clip(FV / P_ref / n, 0.8, 1.2) - 1)`; `P = P_ref x shape x (1 + theta)`; **cost floor** `P_final = max(P, FV)` | The floor is the Lerner-rule lower bound: price at least marginal cost (expected payout) |
| `solve_n(p_ref, fv, lam)` | **Bisection for n**: the quoted total falls as n rises, so geometric bisection on [0.01, 100] finds n with `sum(P_final) = sum(P_ref)` on the fold's fitting orders, to a relative 1e-8. If the total at n = 100 is still too high, the cost floor alone exceeds the reference total: status INFEASIBLE, no quotes | n is solved once on training orders and then frozen |
| `fit_c3(fit)` | Comparator C3 (the JV-03 ladder): break-even vol per length shrunk with k = 100, plus 7.5% | Uses training payouts only |

The fold loop also builds F0 = FV x sum(A) / sum(FV) on the fitting orders, F1nf (F1 without the floor), F1h
(lambda = 0.5) and R0 = P_ref, and runs the clipping checkpoint.

### Section 9 — Phase 3, the team scorecard

| Function | What it does | Equation / guard / source |
|---|---|---|
| `demand_weight(r, scen)` | Volume kept at price ratio r = P / A: none (1), smooth `min(r^-e, 3)`, conservative `min(r^-e, 1)`, threshold `1 if r <= v` | An **assumption**, not an estimate of demand |
| `month_panel(month)` | Test-month orders with every model's quote (C0 = JV's price, C1 = base, M, S from saved files) | Each month priced by models fitted before it |
| `central_profit(P, A, pay)` | `sum(w x (P - payout))` under conservative e = 2 | — |
| `f1_shape(t)`, `shuffle_within(values, groups, rng)` | **Placebo power check**: shuffle F1's shape among orders of the same month and length (200 times), keep the band, floor and n, and score the gain over R0; the 5th-95th percentile range is the noise floor | A permutation test |
| `scenario_metrics(...)`, `score_panel(t, models)` | Profit, revenue, loss ratio, premium kept, volume, worst day, daily spread and top-1% payout share for each model **and its C2** (JV's prices scaled by sum(P) / sum(A)) under 12 scenarios | C2 separates "where you charge" from "how much you charge" |
| `day_counts`, `day_sums`, `profit_draws`, `c2_draws`, `interval`, `mj_draws`, `point_profit` | **Paired day bootstrap**: 2,000 draws of days within each month (seed 2026), the same draws for every model; C2's factor is recomputed inside each draw; 90% interval = 5th and 95th percentiles | Days, not orders, are resampled because payouts cluster by day |
| `tie_groups`, `gini_from_groups`, `gini`, `gini_draws` | **Tie-grouped Gini** (Frees, Meyers & Cummings, 2011): sort by P / A, merge ratios equal within a relative 1e-9 into one step, x = cumulative share of A, y = cumulative share of payouts, `Gini = 2 x area between x and y`. Grouping ties makes the result independent of row order | Checked by permutation and zero-Gini tests |
| `mean_dev`, `corp(quote, pay, scale)` | **CORP** (Gneiting & Resin, 2023): x = quote / scale, y = payout / scale, isotonic recalibration of y on x (weights = scale), Poisson deviance S. `MCB = S(x) - S(recalibrated)`, `DSC = S(mean) - S(recalibrated)`, `UNC = S(mean)` | Wüthrich (2023): high Gini with poor calibration does not win |
| `bound`, `cell` | Look up an interval; format "point [lo, hi]" | — |
| (selection cell) | Rules (a)-(d) exactly as pre-registered; writes `selection.json` | Applied to May + June only |
| `central_gain`, `gains_table`, `drop_top_notional` | Robustness slices: top 1% notional removed, RV_60 terciles (cut points from each fold's training orders), trending versus quiet days (retrospective) | Nothing retuned |
| `f1_requote(t, theta, eps)` | F1 with a level shift theta and a reference error eps, for the theta frontier and the minimax-regret table (Bergemann & Schlag, 2011) | Informs the team's theta_level decision; selects nothing |
| `near_release`, `attribution_group`, `attribution_table` | **Payout attribution** (descriptive): orders with a release in the window, orders whose window holds one of the largest 0.5% of 15-minute moves not within an hour after a release, and the rest; premium share, payout share and loss ratio per group | Hindsight groups: never a feature. Anchors from `checks/jump_attribution.py` are asserted |

The post-hoc placebo diagnostic (`placebo_explained.csv`) repeats the same 200 shuffles without the floor. It is
labelled "post-hoc diagnostic, not part of the selection rule" and changes nothing.

### Section 10 — Phase 4, closed registry of extensions

The 15 candidates and rules R1-R4 are in `team_scorecard/phase4_registry.csv`, written and approved before any run.
Every run, pass, failure or "not run" goes to `phase4_trials.csv`.

| Function | What it does | Equation / guard / source |
|---|---|---|
| `log_trial(...)` | Appends one row to the trial log, with the gain for each length when there is one | Xia et al. (2026): log failures |
| `engine_matrix_x`, `fit_engine_x`, `predict_move_x` | Maksim's engine with extra columns; a missing value takes that fit's training median | Declared fallback (registry) |
| `skill_gains(extra, mkt_x)` | For May and June windows (each month's engine fitted before it): `gain = (deviance of core - deviance of candidate) / deviance of a training-average move`, per length | Same windows for core and candidate |
| `skill_rule(mean_gains)` | Pass if the May-June mean gain is >= 0.005 in at least 5 of 7 lengths | Fixed in the plan |
| `run_skill(...)` | Runs and logs the skill test | — |
| `week_shifts()`, `placebo_shift_test(...)` | **Week-shift placebo**: 20 random whole-week shifts (2 or more weeks, seed 2026) of the feature (`np.roll` by w x 10,080 minutes); the real feature must beat at least 18 of 20 on mean gain | Keeps the hour-of-week pattern, breaks the link to moves (Bajgrowicz, Scaillet & Treccani, 2016) |
| `fv_from_engine_x`, `f1_variant_quotes` | F1 rebuilt on a candidate's fair value (or reference), with its own training-only n | — |
| `evaluate_variant(label, quotes)` | Guards (a)-(d), plus "Gini not below F1" and "profit vs F1 with lower 90% bound above 0" | Commercial guards |
| `guard_note`, `level_vs_allocation(quotes)` | Text summary; **level** = quoted total / JV's total and **allocation** = central profit minus the variant's own C2, with its interval | Separates price level from where the price is charged |
| `follow_up(...)` | Placebo, then pricing guards, then rule R2 (an external feature must cover the blind period and need its fallback on at most 5% of blind orders) | Rules R1-R2 |
| `minute_features_from_candles(mkt)` | 4c-1 jump share `max(RV - BV, 0) / RV` over the last hour, BV = (pi/2) x sum \|r_i\| \|r_(i-1)\| (Barndorff-Nielsen & Shephard, 2004); 4c-2 log realised kurtosis over 240 min, `log(240 x sum r^4 / (sum r^2)^2)` (in the spirit of Du & Shen, 2025) | Past minutes only |
| `asof_feature`, `daily_feature`, `build_4a(rid)` | 4a series attached to each window with its declared availability lag (US closes from 22:00 UTC, the 10-year yield one business day later, funding one minute after settlement, DVOL at the hourly bar close, Fear & Greed the next UTC day); older than its limit -> training median | Lags from the registry |
| `gdelt_attention()`, `by_window_hour(series)` | 4b1: s = (value + 1) / norm per hour; `A1 = log s_H - log median(s at H - 168 h x j, j = 1..4)` (at least 2 values); A24 = its 24-hour mean; only hours ending at least 1 h before the window | Leetaru & Schrodt (2013) for GDELT; Kong et al. (2025) for news in volatility forecasts |
| `ref_design_x`, `dvol_ratio`, `dvol_reference`, `dvol_inner_check` | 4c-4: log(DVOL / 100) - log RV_1d as an extra input to a Ridge reference; must beat the declared reference by 0.5 points on the calibration month, then the week-shift placebo, the audit and the guards | Almeida et al. (2025) |
| (4d cell) | F1d: per-length payout / fair-value factor from earlier settled orders and their out-of-fold fair values, shrunk toward 1 with weight n / (n + 100) | No July tuning |

The last Phase 4 cell applies rule R1 (at most one feature), writes `phase4_trials.csv`, `phase4_feature_table.csv`
and `phase4_level_vs_allocation.csv`, and sets `PHASE4_VERDICT`. **GDELT fetch:** `fetch_external.py gdelt` asks the
GDELT DOC 2.0 API for 7-day chunks (`mode=TimelineVolRaw`, query `bitcoin sourcelang:english`, the same query as
Subham's file), caches each chunk, waits 20 s between calls and halves a chunk whose resolution is not hourly. The
snapshot counts as usable only if every step is one hour and at least 95% of the hours from 1 Feb to 14 Oct are present;
otherwise 4b1 is logged "not run" with no interpolation. **This run:** GDELT did not answer the first chunk after 6 tries, so no snapshot exists and 4b1-1 and 4b1-2 are logged "not run: data unavailable".

### Section 11 — Phase 5 final fit, `price_orders` and the lock

The cell first asserts that Phase 4 adopted nothing. The final model is the team's decision, F1 at theta_level = 0
with the 0.8-1.2 band and the July fold's choices, refitted once on labels created and settled before `FINAL_CUTOFF`
and on market windows ending before it.

| Function | What it does | Guard |
|---|---|---|
| `price_orders(df, model, mkt_, bars_)` | Blind-format rows in, one price per row out, in the original order (see section 6) | Reads only `ALLOWED` columns; parameters fixed; no web, API or AI call |
| `engine_params(eng)` | Per-length intercept, coefficients, scaler means/scales and window counts for `model_params.json` | — |

**The lock.** `model_params.json` stores the 96-value profile, release estimates, reference parameters and level
factor, n, lambda, theta, band, cost floor, units, package versions, the cutoff, the excluded labels and the selection
and Phase 4 status. It also stores `"status": "final"`, `"spec_locked": true`, `"locked_at": "2026-10-16 04:46 SGT"`, the
team decision, and the SHA-256 of `validation_predictions.csv` (`0a733667...`). The lock time is a constant in the
cell (`SPEC_LOCKED_AT`): it is metadata and never reaches a price. The computed columns of `validation_predictions.csv`
are written rounded to 6 decimals, the precision of USDC. The first lock run (04:43 SGT) showed floating-point noise of
about 1e-13 USDC between runs in the reference price, which would change the file's SHA-256 on every rerun. So the file
is rounded and the lock was redone at 04:46, before the 544-row check was ever run. Rounding moves no price by more than
5e-7 USDC.

### Section 12 — Risk report (report-only)

| Function | What it does | Equation / source |
|---|---|---|
| `daily_risk(daily)` | Four risk measures of a daily P&L series in date order: worst day; mean of the worst 5% of days (the ceil(5% x days) lowest, at least one); maximum drawdown = largest fall of cumulative P&L from its running peak, starting at zero; daily standard deviation (ddof = 1) | Same definitions as Maksim's `daily_risk` (`maksim/src/evaluate.py`, commit 65daf8c) |
| `daily_pnl(t, P, scen, keep)` | P&L of the kept orders per UTC creation day: `sum(w x keep x (P - payout))`, with w the scenario's volume weight | Creation days, as in the scorecard's worst day |

The table `risk_daily_pnl.csv` covers C0 and F1, no demand response and the central scenario, for May, June, May +
June and July (retrospective). Only days with orders count. Training orders only.

### Section 13 — Exposure cap overlay (report-only)

| Function | What it does | Equation / source |
|---|---|---|
| `exposure_cap(created, closed, direction, notional, cap)` | Takes orders in creation order. Before each one, releases accepted protections whose `closedAt` is at or before its `createdAt`. Accepts it only if the open notional in its direction (0 = call, 1 = put) plus its own stays at or below the cap; otherwise it is declined | Maksim's `exposure_cap` (`maksim/run_extensions.py`, commit 65daf8c), reimplemented; cap 250,000 USDC per direction, his policy setting |
| `peak_open_notional(...)` | Largest open notional per direction with no cap (a close at the same time as an open counts first) | Context for how often the cap can bind |

The book is all May, June and July training orders, starting empty on 1 May. Under the central scenario an order's
notional is weighted by its expected volume w. Declined orders lose their premium and payout. `closedAt` is used only to
know which **earlier** orders had already closed when a new order arrives, which JV knows at that time. The cell asserts
that no F1 quote changed. No hedge is modelled. Output: `exposure_cap_overlay.csv` (orders declined, notional declined,
premium collected and kept, profit, worst day and drawdown, with and without the cap).

### Section 14 — The 544-row reference check (after the lock)

The cell first checks that the predictions on disk match the SHA-256 recorded at the lock, then:

| Step | What it does |
|---|---|
| Identity | On the training export: \|q x (base + markup) / premium - 1\| <= 1e-9 on every row with both (largest gap 4.4e-16) |
| Units | Every revealed blind base is positive and every markup non-negative, and their median markup / base lies inside the training interquartile range |
| Coverage | Rows with both a base and a markup: 544 (counted, not forced) |
| `revealed_errors(g)` | Bias = sum(P_ref - P_revealed) / sum(P_revealed); weighted error = sum(q x K x \|P_ref / P_revealed - 1\|) / sum(q x K), with P_revealed = q x (base + markup) and P_ref read from the locked file. Overall, by block and by length |

It reports bias and error only: no payout is rebuilt, no validation profit is computed, and nothing is refitted or
changed. Output: `reference_check_544.csv`, with the status "identity and units confirmed" (it would say "CONDITIONAL"
if either check failed).

## 5. Leakage guards in one place

1. **As-of rule.** Every market feature uses candles that closed before `createdAt` (k = containing minute - 1),
   checked against a pandas as-of join for all 11,359 orders.
2. **Cutoffs.** Engine windows end before each cutoff (`market_windows`), order fits use labels created **and**
   settled before it (`eligible`), and the profile and release variance are fitted per fold.
3. **Outcomes are never inputs.** `closedAt` and `realizedProfit_USDC` only define eligibility and score results (and,
   in the report-only cap overlay, which earlier training orders had already closed). `price_orders` selects its
   columns explicitly.
4. **Chronological splits only.** Settings are chosen on an earlier calibration month; July never chooses anything.
5. **Event times** come only from the checked calendar (asserted). No hand-entered dates reach a feature.
6. **External data** carry their declared publication lag; a failed download is "not run", never swapped for another source.
7. **Validation.** No validation outcome is reconstructed; the 544 revealed JV prices are not used for pricing.
8. **Lock before the validation-price check.** The specification was locked (time and SHA-256 in `model_params.json`)
   before the 544-row check first ran; the check verifies the SHA-256 and changes nothing.

## 6. `price_orders`: input and output schema

**Input**: a frame in the blind-file schema. Only these columns are read: `createdAt` (either timestamp format),
`optionType`, `productType` (seconds), `quantity_BTC`, `strikePrice`, and `apiBasePrice_per_BTC_USDC` (for the
multiplier only; may be blank). A file read as text works. `closedAt`, `premiumAmount_USDC`, `orderPrice_per_BTC_USDC`,
`markup_per_BTC_USDC` and `realizedProfit_USDC` are never read.

**Output** (`validation_predictions.csv`), one row per input row in the same order:

| Column | Meaning |
|---|---|
| `row_position` | Position in the input file (0-based); the blind file has no order ID |
| `createdAt`, `optionType`, `productType`, `quantity_BTC`, `strikePrice` | Copied from the input (time as `YYYY-MM-DD HH:MM:SS`, UTC) |
| `recommended_premium_USDC` | **Our price** for the whole order, in USDC (computed columns are rounded to 6 decimals) |
| `multiplier_vs_base` | recommended premium / (q x base per BTC); blank when there is no positive base. Changing the base never changes the premium |
| `predicted_reference_premium_USDC` | P_ref, our estimate of JV's current price |
| `fair_value_USDC` | FV, the expected payout |
| `release_in_window` | 1 if a scheduled CPI, jobs-report or FOMC release falls inside the protection window |
| `shape` | F1's shape after the 0.8-1.2 band (the premium is P_ref x shape unless the cost floor lifts it to FV) |
| `status` | "final" |

## 7. Saved tables (`aman/team_scorecard/`)

| File | Content |
|---|---|
| `f1h_infeasibility.csv`, `clipping_and_floor.csv` | Why F1h is infeasible; how often F1's band and floor bind, by month and length |
| `placebo_gains.csv`, `placebo_explained.csv` | The 200 placebo gains; the post-hoc diagnostic (labelled as such) |
| `scores_by_month_and_scenario.csv`, `scores_C1_base_rows.csv` | Every model and its C2 under 12 scenarios, by month |
| `profit_differences_bootstrap.csv` | Paired profit differences with 90% intervals (vs C0, own C2, R0; May + June and July) |
| `gini_by_month.csv`, `corp_may_june.csv` | Gini by month with intervals; CORP terms |
| `selection.json`, `main_table.csv` | The selection rule's result; the main table |
| `robustness.csv`, `theta_frontier.csv`, `level_regret.csv` | Robustness slices; the price-level frontier; the regret table |
| `payout_attribution.csv` | Where payouts come from (descriptive) |
| `phase4_registry.csv`, `phase4_trials.csv`, `phase4_feature_table.csv`, `phase4_level_vs_allocation.csv` | Phase 4: the closed list, every run, the per-length skill table, level versus allocation |
| `risk_daily_pnl.csv`, `exposure_cap_overlay.csv` | Sections 12-13 (report-only): daily risk of C0 and F1; the exposure cap with and without |
| `reference_check_544.csv` | Section 14: bias and error of the locked reference on the 544 revealed prices |

## 8. What each check proves (`checks/test_pricing.py`)

| Check | What it proves |
|---|---|
| timestamp formats | Both blind-file formats parse to the right UTC time |
| asof strict | The feature candle closed before `createdAt` and no later closed candle was skipped (training and blind) |
| future candles do not move features | Changing candles at or after an order leaves all its features unchanged |
| past candles move features | Changing the last hour's candles changes 1-hour volatility (the features are live) |
| calendar daylight saving | 09:30 New York maps to the same slot under EST and EDT; weekends use slots 48-95 |
| release window | A window ending before a release is not flagged; one containing it is |
| outcomes never used | Blanking `closedAt`, payouts and markups leaves features unchanged |
| engine windows end before cutoff | Every fold's training windows end by its cutoff; window counts unchanged |
| fit rows before cutoff | Every fold's fitting orders were created and settled before the cutoff |
| reference ignores prices and outcomes | Blanking premiums, prices, markups, bases and payouts leaves P_ref unchanged |
| fair value ignores prices and outcomes | Same for FV |
| f1 floor band and normalisation | No F1 quote below FV; quotes within 0.8-1.2 x P_ref unless the floor binds; training totals match to 1e-8 |
| event times from checked calendar | Every event time behind a feature is in the checked calendar |
| gini permutation ties and zero | Gini ignores row order, handles ties, and is zero for JV's own price and any uniform multiple |
| c2 same profit without demand response | With no demand response a model and its same-total C2 earn the same, so C2 isolates allocation |
| final fit obeys cutoff | The final engine's windows and fitting orders all end before 31 Jul 17:11 UTC |
| mock blind file | On a mock blind file (premiums, prices and payouts blank; both timestamp formats; bases missing in the later 53%): one positive finite price per row in the original order, multipliers blank exactly where bases are; with **all** bases missing the premiums do not change |
| premiums ignore outcomes and prices | Changing or blanking `closedAt`, markup, paid prices, payouts and bases leaves every premium unchanged |
| quote ignores future candles with fixed parameters | With all fitted parameters fixed, changing candles at or after an order leaves its quote unchanged (three blind orders) |
| earlier candles move fair value and an unclipped quote | On an unclipped blind order not on the floor, changing the last hour's candles changes FV and the quote |
| single row equals batch and n fixed | Pricing one row alone gives the same price as in the batch; n does not change during inference |
| final bounds floor and calibration | Final quotes are >= FV, within the band unless the floor binds, and the final training total matches the reference total |
| unseen length fallback | A length unseen in a fit (1 hour in the May fold) still gets a positive price, interpolated between its neighbours |
| daily risk on a toy series | The risk measures give the hand-computed answers on a five-day series (worst day, worst 5%, drawdown 7, sd) |
| exposure cap respects the cap and changes no quote | On the May-July book the cap binds, accepted orders never hold more than 250,000 USDC open in one direction, an infinite cap declines nothing, and no F1 quote changes |

## 9. Known limitations (code side)

- F1's band binds often (58-75% of held-out quotes), so a better forecast moves few final prices.
- The blind file cannot be filtered for below-base orders the way JV filtered the training file (2,195 blind orders
  have no base). The size and direction of any resulting bias are unknown; nothing is corrected.
- The snapshots of external series are today's view of past values, not real-time vintages.
- The 544-row check covers only August orders with a revealed markup, and the blind inputs were profiled before it.
- The risk tables book P&L on creation days and use assumed demand; Maksim's saved risk results use closing-day
  payouts and a hedge, so the two are not directly comparable.
