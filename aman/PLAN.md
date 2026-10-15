# JV-05 — Converged build plan (Aman + Maksim)

Written 15 Oct 2026, 21:30 SGT. **Supersedes [[JV-04-claude-code-build-prompt]] and its three rounds of amendments.**
Revised after reviewing Maksim's code and saved results at commit `65daf8c840db98f336b29d2eaa4a9d9585e7c603`.
Revised again 15 Oct, 22:15 SGT: reference price measured relative to recent BTC volatility; audit and tie-order defaults declared; summary table updated.
**Final, 15 Oct, 23:15 SGT. Team decision: the 544 revealed JV prices are NOT used for pricing (Option A); they serve only the post-lock check.**
Revised 15 Oct, 23:00 SGT after a second review: cost floor at fair value; three-month level correction; the Ridge may learn the vol pass-through (b = 1 kept as default on time-ordered evidence); selection by ranking and calibration with profit as a guard, after a placebo power check; regret table for theta_level.
**Amended 16 Oct, after Phase 2 (LLM-trading and news papers). Changes are marked [16 Oct] and touch Phases 3-6 only:** a payout-attribution table in Phase 3; a closed feature registry, trial log, shift placebo and no hand-entered dates in Phase 4; 4b becomes a GDELT news-attention test, with an LLM headline score allowed only if that passes; no LLM or network call when quoting. Evidence and sources are in "Amendment 16 Oct" at the end.
Built on [[JV-01-brief-data-and-findings]], [[JV-03-paper-ideas]], [[_papers-index]] and Maksim's branch `origin/maksim/pp-pricing-strategy`.

**The agreement in one line:** Maksim's market-fitted fair value decides *which orders should cost more or less*.
Our estimate of JV's current price sets *the training calibration total and per-order bounds*. Future total premiums can differ.
A placebo power check, the tie-safe Gini, the CORP calibration split and the same-total flat-change comparator (C2)
assess whether the allocation improves pricing; profit under demand scenarios acts as a guard. Prices never go below fair value.
The result goes in `aman/`; the team compares everyone's work at the regroup tomorrow.

Copy everything inside the box into Claude Code or Codex, started from `Assignments/DBA5106_Jasper_Vault_Assignment/`.
Editing this document does not start implementation or authorize execution of its phases.

~~~text
You are helping me (Aman, NUS MSBA) build our team's converged pricing model for Jasper Vault's
Perpetual Protect (PP): DBA5102 Blockchain Group Assignment, Option 2. Due Sun 18 Oct 2026, 23:59 SGT.
I manage the schedule. The team regroups tomorrow to compare everyone's work, so the output must be
complete, honest and easy to compare. This plan replaces notes/JV-04 and all earlier amendments.
First, save this plan unchanged as aman/PLAN.md and work from it.

=====================================================================
0. READ FIRST, then summarise back in about 10 lines and wait for my OK
=====================================================================
Notes (~/Desktop/NUS MSBA Sem1/DBA5102 - Capstone/notes/): JV-01, JV-03, papers/_papers-index.md.
Repo (read-only outside aman/):
- aman/checks/reproduce_checks.py and aman/checks/jv03_evidence.py: run both and confirm the outputs.
- Maksim, origin/maksim/pp-pricing-strategy: maksim/README.md, src/model.py, src/market.py, src/config.py,
  src/pipeline.py, src/evaluate.py, run_backtest.py, run_extensions.py,
  data/macro_events_2026.csv (+ _sources.md), results/ (walk_forward_orders_priced.parquet,
  test_orders_priced.parquet, move_forecast_scores.csv, summary.json, extensions/hedging_summary.csv,
  extensions/exposure_limits.csv). Read with git show; do not switch branches. Record the source commit.
- Subham, origin/main: subham/README.md, subham/pricing/external.py, subham/outputs/.
- Jay, origin/main: jay/revision_v3_2/README.md, PROTOCOL.md.
- data/validation/README.md, the case brief (materials/case-study/) and the assignment brief (materials/briefs/).
Preserve phase approvals already given in this session; do not ask for the same approval again.
[16 Oct] Phases 1-2 are complete. Changes marked [16 Oct] apply from Phase 3 on and do not reopen Phases 1-2.

What Jasper Vault told us (requirements):
- Base premium = a Black-Scholes price. Final price = base + a "CTA" overlay (RSI, Bollinger bands).
  The base is not the correct answer; the question is whether the final price is right.
- All orders are at-the-money (0% deductible). Moneyness is out of scope.
- Approach 1 (base x multiplier) and approach 2 (own fair value) are both fine. JV suggested a hybrid:
  an interpretable fair-value model adjusted with data for market conditions.
- JV scores our prices on the blind orders against the hidden outcomes and its current pricing, under an
  undisclosed conversion constraint. "Simply increasing every PP price is not a valid solution."
  "We don't know how much they're willing to pay ... make your prediction of the pricing cheap and good."
- JV suggested macro-event and sentiment data.

=====================================================================
1. GROUND RULES
=====================================================================
Files and git
- Write only inside aman/. Never edit data/, materials/, notes/ or other members' folders.
  Never commit, push, merge, switch branches or reset. Don't message JV or teammates.
- Training orders: data/with_base_premium/pp_transactions_training.csv (don't mix with data/en/).
  Blind orders: data/validation/pp_transactions_validation.csv.
  Candles for everything: data/validation/btc_market_history.csv (1 Jan - 14 Oct 2026). No downloads of candles.

Facts about the blind file (check them in Phase 1)
- 4,155 orders, 2026-07-31 17:11 -> 2026-10-14 02:46 UTC. Premium, order price and payout are blank.
- 2,195 rows (53%) have no base price, mostly after 24 Aug. closedAt is filled (an outcome: never an input).
- Rows 0-1,897 have minute-only timestamps; later rows keep seconds. Parse both. No order ID: keep row order.
- Training excludes 627 orders charged below base, according to the release guide. Do not restore them
  from data/en/. Missing bases in validation prevent applying or verifying the same filter. This is possible
  sample shift: the reference could overprice discounted orders, but missing bases do not prove a discount
  or establish the size/direction of bias. State this limitation; do not invent a correction.

Leakage
- closedAt and realizedProfit_USDC: only for training labels and historical scoring. Never inputs.
- Order features: only candles whose close_time_utc is strictly before createdAt (merge_asof backward,
  allow_exact_matches=False; assert max gap <= 60 s).
- Move-model training windows must END before the fold's cutoff. Fit scalers, time-of-day profiles,
  release estimates, reference models and all calibrations separately inside each permitted training split.
- Reference model: quote-time features only. Base, paid price and markup are never predictors.
- Releases: the schedule only, never the released numbers.
- Do not rebuild validation payouts or use already reconstructed validation outcomes from teammates to
  tune, select, compare or report performance. Filter mixed saved results to historical training-period rows
  before analysis; exclude sealed_check/ and validation rows in extension files. Record prior team exposure.
  The only planned validation-price diagnostic is the post-lock 544-row reference check below; no profit
  calculation or model change may use it. Decided 15 Oct (Option A): the 544 revealed JV prices are never used
  to set the reference level or any other part of the price. Any additional validation-period evaluation
  needs a team decision.

Validation design
- Chronological only. Outer test months: May, June, July. For each, fit only on labels created AND
  settled before the month starts. July is a retrospective check (the team has looked at it).
- May: use fixed numeric defaults declared before scores; no inner split of the small Feb-Apr order sample.
  The move engine may use eligible January-April market windows, while order-based fits use Feb-Apr labels.
- June: inner fit through April, calibrate/select on May, then refit through May before scoring June.
  July: inner fit through May, calibrate/select on June, then refit through June before scoring July.
  Apply the same cutoff rules inside inner fits. Inner reference-level correction and shape normalization
  use INNER fitting rows only; do not normalize on the held-out calibration month being scored.
  Calibration labels must also have settled before the next outer test begins.
- Declare reference-model grids, release-shrinkage settings and any optional duration calibration before
  evaluation. Neither July nor validation diagnostics can select settings, event types or extensions.
- Also run a Feb-Jul monthly walk-forward for the fair-value engine, to compare with Maksim's tables.
  Treat this as a separate diagnostic. Missing early order histories do not prevent fitting a market-only
  engine from earlier candles. Specify fixed defaults for those earlier diagnostic fits.
- Final fit: order labels created AND settled before 2026-07-31 17:11:00 UTC, and market targets ending
  before that cutoff. Keep the selected specification and settings from the predeclared June calibration
  used for the July fold; do not add a July hyperparameter search. Refit coefficients and predefined level/
  normalization constants on eligible training rows. Report cutoff exclusions rather than forcing counts.

Checks before trusting the pipeline (assert with rounding tolerance)
- 7,204 rows; 7,150 resolved; premium 248,089; payouts 230,652; loss ratio 0.930; margin 7.0%;
  1,131 rows without base; loss ratio at base x 1.00 = 1.403 on 6,019 rows; vol ladder 34.3 / 49.4 / 48.1%.

=====================================================================
2. CODE STYLE: write like a student in this MSBA programme
=====================================================================
- One lean notebook, aman/pp_pricing.ipynb: data -> features -> fair value -> reference price -> price
  -> scorecard -> final prices. Heavy checks live in aman/checks/test_pricing.py, called once.
- pandas, numpy, scipy, scikit-learn, statsmodels, matplotlib. Short functions (~20 lines), plain names,
  no classes, decorators, type-hint walls, logging, argparse, polars or config systems.
- Reimplement Maksim's move model compactly; do not import his modules. Say in markdown that the design
  comes from our teammate Maksim's model. First reproduce the specified engine, then identify our changes.
- Fix random seeds and pin the package versions actually used. Check convergence and units explicitly.
- One short comment where it helps; 2-4 sentences of "why" per markdown cell; simple labelled charts.
- Use course concepts by name without citing lectures (shrinkage/ridge, chronological validation,
  Poisson regression, isotonic regression, permutation (placebo) tests, non-inferiority testing,
  price discrimination, elasticity, Lerner rule, grid search, minimax regret, sensitivity analysis,
  as-of joins). Cite papers (Author, year) where their idea is used, with a reference list:
  Black & Scholes (1973); Bandi, Fusari & Renò (forthcoming, J. Finance); Bandi, Fusari, Gazzani & Renò (2026);
  Corsi (2009) [multi-horizon realised-vol features]; Chong (SSRN WP) [premium pays for rare large moves];
  Du & Shen (2025); Almeida, Grith, Miftachov & Wang (2025); Zbandut (2025);
  Barndorff-Nielsen & Shephard (2004); Frees, Meyers & Cummings (2011) [Gini]; Araci (2019); Hutto & Gilbert (2014);
  Gneiting & Resin (2023) [CORP]; Wüthrich (2023) [Gini under auto-calibration]; Denuit, Charpentier & Trufin (2021);
  Bergemann & Schlag (2011) [robust pricing]; Einav, Finkelstein & Cullen (2010); Misra, Schwartz & Abernethy (2019);
  Deng, Xu, Kohavi & Walker (2013) [CUPED]; Gibbs & Candès (2021).
  [16 Oct] Leetaru & Schrodt (2013) [GDELT]; Kong et al. (2025) [news for volatility forecasts];
  Bajgrowicz, Scaillet & Treccani (2016) [news, jumps, volatility bursts, multiple testing];
  Glasserman & Lin (2023); He, Lv, Manela & Wu (2025); Yan et al. (2026); Li, Wang & Ma (2026) [LLM look-ahead];
  Tang et al. (2025) [hypothesis and complexity checks for LLM-driven feature search];
  Xia et al. (2026) [agentic-trading survey]; Fish, Gonczarowski & Shorrer (2024); Benhenda (2026).
  Verify details before citing; add nothing else without telling me.

=====================================================================
3. THE MODEL
=====================================================================
Notation: q = BTC quantity, K = strike (= BTC price at purchase, ATM), T = duration,
scale = 0.3989 x q x K x sqrt(T in years), A = JV's actual premium (training only), B = q x base per BTC.

Step 1 - Fair value from market data (Maksim's engine)
- For each product length (0.5, 1, 2, 4, 8, 12, 24 h): a Poisson regression (log link) of
      y_bps = 10,000 x |log(P[t+T] / P[t])|
  on log realised variance over the last 60 min, 240 min, 1 day and 1 week (Corsi, 2009 style), plus
  log time-of-day factors for the window and for the last 60 min.
  Reproduction specification: StandardScaler then PoissonRegressor(alpha=0, max_iter=1000), as in his code;
  do not silently use the library's regularized default. Divide predicted basis points by 10,000 before
  pricing. All s and jump_var calculations below use fractional log returns and squared fractional returns.
- Time-of-day profile: 48 HALF-HOUR New York-time slots for weekdays plus 48 for weekends: 96 values
  total, with DST handled. Fit on earlier candles separately per fold and exclude the 30 minutes following
  each included release, as Maksim's code does. Normalize to mean one over the fitting period.
  His reported 3.76x US-open variance, 0.71x weekend variance and 0.93 weekday profile correlation are
  diagnostics to reproduce on their stated samples, not fixed profile parameters.
- Window starts every 5 minutes; every window must end before the cutoff. Fitted on candles only, so
  durations with few or no orders in a fold (1h before June, 12h before July) are still priced.
  Allow a week of feature warm-up. Overlapping windows are not independent observations; do not equate
  their count with effective sample size or use a random window split to claim out-of-sample accuracy.
- Scheduled releases add variance:  s_total^2 = s^2 + jump_var x release_in_window,  with
  s = E|R| x sqrt(pi/2). Keep CPI, jobs report and FOMC as the core event set. PCE is optional: an estimated
  event-study ratio above one alone is not grounds to add it. Any PCE variant must be declared before
  scoring and pass the Phase 4 development rules; do not choose it from a January-July event study.
  Calendar: start from maksim/data/macro_events_2026.csv, cross-check with
  subham/pricing/external.py and the official schedules, save the checked copy in aman/data_external/.
  Reproduce his nonnegative excess-variance estimate first. Shrinkage in our engine is a declared change:
  jump_var = m / (m + k_event) x jump_var_raw, where m counts eligible distinct releases. Declare k_event
  defaults/grid before scoring; use the inner chronology above, with zero jump when no eligible releases
  or controls exist. Report counts, raw/shrunk estimates and the difference from the reproduced engine.
- Fair value in USDC: FV approximately equals q x K x E|R_total| / 2, where
  E|R_total| = s_total / sqrt(pi/2). This is the short-maturity ATM approximation to his Black-Scholes
  conversion. It assumes negligible directional drift for the symmetric call/put approximation; it is an
  expected-cost proxy, not proof of a risk-neutral price or an exact early-close payout model.
- Payout / FV by duration with day-bootstrap 90% intervals is diagnostic only in the core model. Do not
  automatically alter prices when an interval excludes one. Maksim's 24h ratio near 0.45 uses Feb-Jul
  results and must not become a fixed factor in earlier folds or be used to select on July.
  Optional F1d is a separate payout-calibrated variant: estimate each duration's payout/FV ratio using only
  earlier eligible orders and their chronological out-of-fold FV predictions; shrink toward one using
  n_g / (n_g + k_duration). Declare k_duration before scoring; unseen groups use one. Report it separately
  and evaluate under the same selection rules. Once used in prices, this is fitting, not just a check.
- Reproduction target: 47.5130 is the unweighted mean of the SEVEN duration-specific Poisson deviances
  in Maksim's move_forecast_scores.csv, in basis-point units. It uses one pre-1-June fit evaluated on
  June-July market windows, not monthly refits. Match his sample start/end, window grid and unshrunk release
  term for this check. Report per-duration deviations; do not tune to hit the number. Show scores for our
  changed engine separately. Reproducing July numerics is not permission to select on July performance.

Step 2 - Estimated JV price (the reference, P_ref)
- Target: JV's charged vol RELATIVE to pre-trade 1-day realised vol: ratio = (A / scale) / RV_1d.
  Why: from April to July JV's raw charged-vol level moved -22%, +38% and -14% between consecutive months;
  relative to 1-day realised vol the moves were -4%, -5% and +12%. A raw duration-only level would be about
  25% wrong in some months. Default (May fold and the fallback): a duration-level shrunk ratio, so
  P_ref_raw = scale x ratio_duration x RV_1d. Compare it with a small Ridge on log(ratio) using duration,
  RSI, Bollinger %b, RV_60 / RV_1d, log RV_1d and log RV_7d (JV said its overlay uses RSI and Bollinger bands).
  The log-vol coefficients equal b - 1, where b is how strongly JV's price follows market vol. Ridge shrinks them
  toward 0, i.e. toward b = 1, so the data can move away from b = 1 only if the inner calibration supports it.
  Evidence in the plan's time order: b fitted on Feb-Apr and Feb-May was 0.17-0.19 and missed JV's level by
  +9% to +13% in May and -16% to -20% in June, against -3% to 0% and +4% to +6% for b = 1. So b = 1 stays the
  default. (A Feb-Jul fit gives b near 0.3, but that includes July.)
  RV_1d and RV_7d use only candles closed before createdAt.
  Choose using the inner chronology above; May uses the declared duration-only default. Specify a positive
  prediction rule and reference diagnostic acceptance criteria before scores; never divide by a zero price.
- Durations without orders in a fold: interpolate the charged vol in log(T) between the nearest seen durations.
  Predeclare the endpoint fallback when interpolation is impossible; use the nearest available duration
  level. All interpolation inputs and any Ridge fallback come from that fold's earlier training data.
- Level correction: P_ref = P_ref_raw x sum(A) / sum(P_ref_raw), with sums pooled over the last THREE eligible
  training months (fewer if fewer exist). One month is a noisy level; in the time-order check the pooled version
  moved bias by at most 3 points and was steadier. This is a training level fit, not held-out accuracy.
  Never recalibrate on an outer test month.
- Report bias and notional-weighted error on each held-out month. After the model is locked, also on the
  544 potentially recoverable validation prices, subject to the identity/units check in Phase 5.
  Bias = sum(P_ref - A) / sum(A); weighted error = sum(qK x abs(P_ref/A - 1)) / sum(qK).

Step 3 - Price = JV level x fair-value shape
    shape_raw = FV / P_ref
    n         = a positive constant calibrated AFTER clipping and the cost floor (then fixed)
    shape_cap = clip(shape_raw / n, 0.8, 1.2)
    shape     = 1 + lambda x (shape_cap - 1), lambda in {0.5, 1}
    P_band    = P_ref x shape x (1 + theta_level)
    P_final   = max(P_band, FV)          # cost floor: never quote below expected payout
    multiplier_vs_base = P_final / B   (blank when there is no base)
- Cost floor: FV is the market-based expected payout and exists for every order. Pricing below expected cost
  loses money on each sale, while pricing above JV's price only risks losing the order, so this is the
  Lerner-rule lower bound (price >= marginal cost). It matters most where the upper band would cap a
  high-risk order below its cost, for example when the reference runs low. It uses no payouts.
  Report how often it binds, by duration. F1nf (F1 without the floor) is a diagnostic row, not a candidate.
- On each fold's eligible fitting orders, solve the one-variable equation (floor included)
      sum(max(P_ref x shape, FV)) = sum(P_ref),  with shape computed from n as above,
  separately for each lambda. If the total at the largest bracket value of n still exceeds sum(P_ref), the
  floor alone is above the reference total: stop and report it.
  Use deterministic bisection with a positive bracket and declared tolerance; assert relative total error
  <= 1e-8. sum(FV)/sum(P_ref) is only a starting estimate, because clipping and the floor change the total.
  Save n with the model;
  never recompute it from test or validation batches. A changed FV variant needs its own training-only n.
- theta_level = 0 is the primary setting: calibrated to the estimated reference total ON THE FITTING
  SAMPLE. It does not guarantee equal premiums on later months, equal actual JV premiums, or equal
  collected revenue after demand. Report quoted totals versus both P_ref and actual A where available.
  For lambda = 1 and theta_level = 0, P_final = max(clip(FV/n, 0.8 x P_ref, 1.2 x P_ref), FV): inside the band,
  fair value sets the price, while the reference sets the normalization target and per-order limits.
- The team may choose theta_level from the May-June frontier and the level-error regret table (Phase 3); default zero. A nonzero choice is a separate
  operating-price decision: re-score it under all scenarios, C2 and guards before describing it as supported.
  Do not choose theta from July or validation diagnostics. Record the decision and any failed guard.
- Bounds apply to shape before theta_level. Final P/P_ref lies between
      (1 - 0.2 x lambda) x (1 + theta_level) and (1 + 0.2 x lambda) x (1 + theta_level).
  For lambda = 1 and theta_level = 0.25 this is [1.0, 1.5]. These are predicted-reference bounds, not
  guarantees against actual JV prices. Do not silently apply a second clip or normalize after theta.
  The cost floor can lift a quote above the upper bound; report those orders separately.
- Clipping: report by duration, lower and upper separately, by orders and by notional. Lower-band
  clipping of 30-min orders is expected. Stop and tell me only if upper-band clipping is above 30% of
  orders, or any duration other than 30 min has more than 50% of its orders clipped.
  Measure binding on shape_raw/n before lambda and theta; report final ratios separately. Do not widen
  bounds or change n using evaluation rows to escape this checkpoint.
- No floor at the base price: it changes the pricing policy and is unavailable on 53% of validation rows.
- No size surcharge, no put/call markup, no moneyness model.

Step 4 - Risk layer (kept separate from the price)
- The reported training worst day -8,399 -> -3,976 and roughly 30% profit reduction refer to the COMBINED
  policy: 250,000 USDC cap on open protected notional per direction plus a 0.5 BTC net-delta hedge band,
  with assumed trading fees of 0.04% per side. Source: the training rows in
  maksim/results/extensions/exposure_limits.csv; hedging_summary.csv alone is not the combined policy.
  These results use Maksim's prices and cash-flow dates (premium at opening, payout at closing, fees when
  paid). Keep them separate from creation-cohort scorecard P&L. They are not measured benefits under F1.
  Replication is optional; retain source attribution and assumptions if quoting the saved trade-off.
  Do not drop validation orders or change quoted quantity because of this separate risk-policy illustration.

=====================================================================
4. WHAT WE COMPARE (the team scorecard)
=====================================================================
Models, on the same rows and months wherever possible:
  C0  JV's actual price (benchmark; can't be produced for blind rows)
  C1  base x 1.00 (rows with a base)
  R0  estimated JV price alone (P_ref)
  F0  fair value scaled to the actual TRAINING premium total: FV x sum(A)/sum(FV) on training (no reference
      model in its pricing path). Fix the scale for future rows; later totals are not guaranteed equal.
  F1  THE CONVERGED MODEL (Step 3, theta_level = 0, lambda = 1, with the cost floor)
  F1h F1 with lambda = 0.5
  F1nf F1 without the cost floor (diagnostic only, not a candidate)
  F1d Optional F1 with the separately fitted duration factors from Step 1; evaluate in Phase 4.
  C3  payout-fitted duration ladder from JV-03 (comparator)
  M   Maksim's model as he submitted it (FV x 1.25 with base floor), from his saved walk-forward outputs
  S, J  Subham's and Jay v3.2's models where their saved historical outputs allow; otherwise N/A
  C2  for every model: A x sum(P_model)/sum(A) on the same rows within each test month. This is a
      diagnostic batch comparator, not a deployable policy. Match quoted totals before demand; compute
      conversion from C2's own price ratio, and do not clip or rebalance it afterward.
Do not re-run teammates' training. Use saved row-level outputs and record the commit, fitting/selection
dates, months, sample definitions and coverage. Re-score compatible quotes under our scenarios; do not
substitute unmatched published totals. Missing folds or only aggregate results mean N/A for unsupported
comparisons. Use separate matched-row panels for partial coverage, with C0 and C2 on those exact rows.
M's common scorecard uses walk_forward_orders_priced.parquet; test_orders_priced.parquet is a separate
fixed-pre-June-fit comparison. Their cutoffs differ. Record previous selection and validation exposure.
Jay's relative factors need a compatible reference before they can be treated as absolute USDC quotes;
do not invent a reference substitution to fill missing results.

Demand scenarios use Maksim's functional forms plus an explicitly expanded stress grid. Numbers line up
only when rows, fitted quotes and scenarios also match. Ratio r = P / A, using ACTUAL historical premiums:
- no response: weight = 1
- smooth: weight = min(r^(-e), 3), e in {0.5, 1, 2}
- conservative: weight = min(r^(-e), 1), e in {1, 2, 4, 8, 20}; discounts win no extra buyers
- thresholds: weight = 1 if r <= 1, 1.10, 1.20 or 1.25 respectively, otherwise zero
Scenario profit = sum(weight x (P - payout)). Smooth weights can exceed one: they are volume factors,
not purchase probabilities, and assume unchanged conditional payout risk. Demand is not estimated here.
Under an UNCONSTRAINED, uncapped constant-elasticity model with e > 1 and fixed expected cost C,
the optimum is e/(e-1) x C. If C/A were 0.95, e = 2 would imply 1.9 x A, and optimal P = A would imply
e = 20. This is an illustrative implication of those assumptions, not an estimate of JV's elasticity.
An observed book loss ratio is not each order's expected C/A. Do not apply this optimum unchanged to
capped-volume, conservative or threshold rules, or infer demand from JV's observed margin.

Metrics per model, month (May, June, July) and the May+June sum:
- profit in every scenario; loss ratio; total quoted premium vs C0 and P_ref; orders and premium kept
  Weight premium and payout consistently in scenario loss ratios. Distinguish collected revenue sum(wP),
  today's premium retained sum(wA)/sum(A), and order-volume ratio sum(w)/N; smooth ratios can exceed one.
- profit vs its C2 (does re-allocation beat a flat change of the same size?)
- Gini of the ordered Lorenz curve (Frees, Meyers & Cummings, 2011): sort orders from lowest to highest
  P_model/A. GROUP tied ratios first, summing their actual premiums and payouts; declare a numerical tie
  tolerance. Plot cumulative A share x against cumulative payout share y, including (0,0) and (1,1).
  Gini = 2 x integral(x - y) dx: signed area, not absolute area. A stable row sort alone does not resolve
  ties fairly. Assert row-permutation invariance and Gini = 0 for C0 and any uniform multiplier per month.
  Report N/A if reference premiums or total payouts cannot support the calculation; do not invent zero.
  Use actual payouts and original premiums, without scenario-volume weights, for this ranking diagnostic.
  Report FV/A Gini separately from FINAL-QUOTE/A Gini; selection uses final quotes. Also report base-relative
  Gini on matched rows. Maksim's published roughly 0.175 is FV/A on 3,947 base-present June-July orders,
  not automatically the Gini of his floored quotes or of our full sample.
  Report each month and a selection summary: actual-premium-weighted mean of May and June monthly Ginis.
  Do not use pooled month-level price changes to create apparent within-month ranking. Positive estimates
  are evidence of association in that sample; an interval crossing zero leaves the ranking uncertain.
- worst UTC creation day, daily P&L std, share of P&L from the top 1% by historical payout (with stable tie
  handling). Show contribution in USDC too; flag negative/near-zero total profit and use N/A for a zero
  denominator. These are creation-cohort metrics, distinct from the risk layer's settlement cash flows.
- Paired day-bootstrap 90% intervals (2,000 resamples, fixed seed) for differences vs C0/C2 and for Gini.
  Resample days within each month, preserve monthly day counts, then sum May-June profits. Use identical
  draws across models/scenarios; recompute monthly C2 factors and Gini tie groups in each draw, without
  refitting models. For the Gini summary, recompute monthly premium weights too. Intervals are conditional
  on the chosen models/scenarios, not adjusted for model selection or proof of commercial demand.

Selection rule (write it in the notebook before scoring):
- Eligible final candidates: R0, F0, F1, F1h, plus F1d or other declared extensions ONLY if their Phase 4
  checks pass and a complete price_orders implementation is available. C0, C1, C2, C3 and saved M/S/J
  results remain comparison rows, not automatic deployment candidates.
- Power check FIRST, before printing any candidate's real score: build 200 placebo versions of F1 by
  shuffling its shape at random within each duration and month (same band, floor and n), and score them in
  the central scenario against R0. The 90% range of placebo gains is the noise floor; report it and the
  minimum detectable gain. A real gain inside that range is not evidence.
- Score = May + June profit in the central scenario (conservative, e = 2). Profit is noisy (a few large
  payouts drive it), so it acts as a guard; ranking and calibration decide.
- A candidate (F1, F1h or F0) is selected over R0 only if ALL hold on May + June final quotes:
  (a) ranking: the final-quote Gini summary > 0 AND its 90% day-bootstrap interval lies above 0;
  (b) calibration split (CORP; Gneiting & Resin, 2023): DSC(candidate) > DSC(R0) and
      MCB(candidate) <= MCB(R0) + 0.01 x UNC. Use x = quote / scale, y = payout / scale, isotonic
      recalibration of y on x (sklearn IsotonicRegression with scale weights) and Poisson deviance.
      DSC = ranking power, MCB = level and shape error, UNC = outcome noise. This stops a high Gini from a
      badly calibrated model winning (Wüthrich, 2023);
  (c) profit not worse: lower 90% bound of central profit (candidate - R0) > -delta, with delta = 2% of
      May + June actual premium. If the power check shows the placebo 90% half-width is larger than delta,
      this test is underpowered and (c) becomes "upper 90% bound of (candidate - R0) >= 0" (no clear
      harm); the notebook says so. This switch is decided now, before scoring;
  (d) Guard 1 in every scenario: the 90% interval for (candidate - C0) is not entirely below zero.
- If several candidates pass, prefer F1, then F1h, then F0, unless one beats another on (a)-(c) outside noise.
  A passing candidate whose central point profit is not above C0 is labelled "ranks risk better than the
  reference; no demonstrated gain over JV's current price".
- C2 (same-total flat change) is still reported for every model: it is the profit view of the same question.
- If none qualifies, still deliver the scorecard and candidate quotes. Predeclared provisional fallback:
  R0 at theta_level = 0, provided it passes the reference audit criteria declared in Phase 2 and gives valid
  quotes for every row. Label it "provisional reference estimate; no demonstrated improvement", not a
  winner or exact current pricing. Do not automatically select the best central score among failed models.
  Distinguish inconclusive evidence from clear harm in a stress scenario. If R0 fails its own audit, deliver
  the failure report and draft candidate outputs for review without presenting an accepted final model.
- July is reported separately and never changes the choice.

Robustness (report, don't retune):
- each month separately; top 1% of orders by notional removed
  Keep all genuine payouts in the primary result; do not refit on this diagnostic subset. Rematch C2.
- pre-trade 60-min vol terciles (cut points from training)
- trending days (|full-day BTC return| in the top quartile of completed training days), retrospective only;
  never a quote-time feature, routing rule or tuning target
- theta_level frontier: for theta_level in {-0.05, 0, +0.05, +0.10, +0.25}, show profit under
  conservative e = 1 and e = 2, orders kept, today's premium kept, and the "keep only if r <= 1" profit
  Show the shifted final price bounds. Any chosen nonzero theta must also be scored on the full scenario
  grid with C2 and the same selection guards; it cannot inherit the zero-theta model's pass status.
- level-error regret table (for the team's theta_level choice): multiply P_ref by (1 + eps) for
  eps in {-20%, -10%, 0, +10%, +20%}, re-quote May + June, and show central profit for each theta_level.
  Regret = best profit in that eps column minus this theta's profit; report each theta's maximum regret
  (minimax-regret pricing; Bergemann & Schlag, 2011). Use this fixed eps grid, not July's level error.
- sanity table: volume needed after a price cut x = (P - C) / ((1 - x)P - C); "no finite volume" if the
  denominator is <= 0

=====================================================================
5. PHASES (stop after each with one short summary table; wait for my OK)
=====================================================================
PHASE 1 - Data, features, checks
- Load both order files and the candles; reproduce the checks and blind-file facts.
- Build backward-looking realised variances, RSI, Bollinger %b, calendar-only half-hour bucket IDs and the
  checked release calendar. Implement profile-fitting functions, but do not fit one profile on the full
  history: learned profiles belong inside Phase 2's fold fits. Inventory saved teammate outputs and confirm
  historical row mappings, months, columns, cutoffs and source commits without reconstructing outcomes.
- Draft aman/questions_for_jv.md (don't send): (a) premium, multiplier or both, and which columns/row order;
  (b) are all 4,155 rows scored; (c) the form of the conversion constraint; (d) is the filled closedAt intended.
PHASE 2 - Engines
- BEFORE scoring, write the model list, numeric defaults/grids, inner selection criteria, reference audit
  acceptance criteria, complexity tie order and full selection rule. Do not invent thresholds after results.
  Use these defaults unless I change them before scoring:
    reference audit passes if, in EACH of the May and June held-out months, |bias| <= 15% and
    notional-weighted absolute error <= 30%. Bias drives F1's price level; per-order error is mostly
    JV's own order-level markup scatter (a rough check gave 21-25% for both reference versions);
    R0 is the default if no candidate passes the selection rule; among passing candidates prefer F1, F1h, F0;
    delta for the profit test = 2% of May + June actual premium; 200 placebo shuffles for the power check.
- Reproduce Maksim's engine with its original specification and the defined fixed-pre-June-fit check.
  Separately fit our move engine, profiles, release estimates, reference model and clipped-total normalizer
  within each fold. Payout/FV intervals are diagnostics; any optional duration fit is a distinct F1d variant.
- Show per-duration deviance and the mean versus 47.5130, differences due to deliberate changes,
  coefficient stability, training normalization error, and held-out reference bias/error. Use July only
  to report the predeclared retrospective checks, not to repair, choose or tune the models.
PHASE 3 - Scorecard
- Run the placebo power check first. Then score every model in section 4: all scenarios, Gini, CORP
  (MCB / DSC / UNC), C2, cost-floor binding, robustness slices, the theta_level frontier and the level-error
  regret table. Apply the selection rule exactly as written in Phase 2.
  Save everything under aman/team_scorecard/. Show the main table.
- [16 Oct] Payout attribution. This is descriptive only: the groups are defined with outcomes, so they are
  never a feature or a selection input. Split resolved orders into "core release in window", "a top-0.5%
  15-minute BTC move in window that is not within the hour after a release" and "neither" (cut points from
  Feb-Jul 15-minute bars, as in aman/checks/jump_attribution.py). Show premium share, payout share and loss
  ratio for C0 and for the selected or provisional model, for May, June and July separately and without the
  10 largest losses. Check on 16 Oct (all Feb-Jul orders at JV's actual premium): release windows 5.7% of
  premium, 8.5% of payout, loss ratio 1.39; big unscheduled moves 4.5% / 8.8% / 1.81, almost all in June
  (July has 2 such orders); 0 of the 18 largest 15-minute moves were within an hour of a release. Use it
  to show what the release term covers and what no quote-time model can foresee, which is the case for the
  risk layer. Most news causes bursts of volatility rather than jumps (Bajgrowicz, Scaillet & Treccani, 2016).
PHASE 4 - Extensions (optional; in this order; each must pass a rule written down first)
- External features are tested inside the MOVE MODEL on chronological market windows. Adapt Maksim's
  rule to MAY AND JUNE ONLY; his original March-July evaluation includes July and cannot be copied as our
  selection period. For each duration/month, on identical windows:
      skill = 1 - deviance_model / deviance_training-fitted_average_move_model.
  Fit the average-move baseline on earlier training windows, not the mean of the test month. Compare each
  candidate's skill with the core engine, average the two monthly gains equally within each duration,
  and require a gain >= 0.005 in at least 5 of 7 durations. Do not compare raw deviances across units.
  Also require that the May-June final-quote Gini summary does not fall versus the core F1 policy, using
  our normalization and clipping, not just raw FV ranking. Apply all commercial scorecard guards and
  compare central profit with the core; prefer the core if their paired difference includes zero.
  Every inner/outer fit respects the earlier cutoffs. July and validation coverage cannot choose features.
  Keep day-based uncertainty and monthly checks; overlapping five-minute windows are not independent trials.
- [16 Oct] Feature-search discipline. You are an LLM searching for features, so guard against our own data
  snooping (Tang et al., 2025, regularise LLM factor search with hypothesis and complexity checks; many
  "detections" are false when many tests are run, Bajgrowicz, Scaillet & Treccani, 2016):
  * Before any Phase 4 run, write aman/team_scorecard/phase4_registry.csv: one row per candidate in a-d below
    (a closed list; nothing else without my OK), with a one-line hypothesis written before testing, the
    exact formula, the number of added parameters, the data source and the availability lag.
  * Log every run, including failed and abandoned variants, in aman/team_scorecard/phase4_trials.csv. Few
    LLM-trading studies log their failed branches (Xia et al., 2026). The summary states how many were tried.
  * For any a-c feature that passes: placebo with 20 circular shifts of its series by whole weeks (at least two
    weeks; this keeps the hour-of-week pattern but breaks the event timing). Rerun the skill test on each.
    Keep the feature only if its mean skill gain beats at least 18 of the 20 shifted gains, as well as
    passing the rule above. Report how many shifted copies would also have passed.
  * No hand-entered dates. The only event times allowed are the checked, pre-scheduled release calendar.
    Do not add dummies or features for specific days or events known from memory or seen in the outcomes:
    an LLM's training data can contain the period being tested (Li, Wang & Ma, 2026).
  a. daily series, last value published before each window: VIX, US 10-year yield, S&P 500 return,
     Binance funding rate, Deribit DVOL, Crypto Fear & Greed. Check publication lags. The Fed's broad
     dollar index can be revised: use a vintage or skip it.
  b. [16 Oct] news attention first; an LLM headline score only if that passes. Checked 16 Oct: the repo's
     timestamped crypto headlines are too sparse to test (CoinDesk headlines Feb-Jul: 2, 15, 5, 14, 3, 13;
     the official records repeat the release calendar). Jay's social snapshots have gaps of up to 13 days
     and reconstructed clocks. News is used only to forecast the SIZE of the move, never its direction.
     b1. GDELT news attention (Leetaru & Schrodt, 2013). Hourly counts of English articles matching "bitcoin"
         from the GDELT DOC 2.0 API (mode=TimelineVolRaw, the same query as subham/data/external/gdelt/),
         1 Jan - 14 Oct 2026, fetched by fetch_external.py in 7-day chunks with a pause between calls, and
         cached. Assert hourly resolution and >= 95% of hours present in Feb-Oct; otherwise stop b and report.
         Two features only: share = (value + 1) / norm; abnormal attention over the last complete hour and over
         the last 24 complete hours = log(share) minus the log of its median in the same hour-of-week over
         the previous 28 days. Use only hours that end at least 1 hour before the window starts (indexing
         lag). In sources.md, say the snapshot is today's view of past counts, not a real-time vintage.
         Kong et al. (2025) use a daily article count beside text embeddings to forecast volatility.
     b2. LLM headline impact score, only if b1 passes and the team agrees there is time. Headlines from
         GDELT article lists, one query per day. Score each headline 0/1/2 for "could this move BTC sharply
         in the next few hours?" with a model whose training data ends before 1 Feb 2026: a 2024 ChronoBERT/
         ChronoGPT checkpoint (He, Lv, Manela & Wu, 2025), DatedGPT 2024 (Yan et al., 2026), or FinBERT/VADER
         as a non-generative fallback. Never a model trained on 2026 text: a model that has seen the test
         period inflates backtests (Yan et al., 2026; Li, Wang & Ma, 2026). Mask numbers, prices and dates
         before scoring (in the spirit of Glasserman & Lin, 2023). Fixed prompt, temperature 0, every score
         cached in aman/data_external/ so reruns are identical and offline. Feature: abnormal count of
         high-impact headlines, built like b1, with the same tests.
  c. optional model ideas: jump share from bipower variation; vol-of-vol proxy (Du & Shen, 2025), or the
     predeclared PCE variant. Apply the same market-forecast and pricing screens; report failures too.
     If DVOL is downloaded in (a), also test log(DVOL / RV_1d) as a REFERENCE-model input under the inner
     chronology: Bitcoin's variance risk premium is higher when volatility is low (Almeida et al., 2025).
  d. optional F1d duration calibration: this adjusts the payout mapping, not the market-move forecast, so
     the market-feature skill threshold does not apply. Fit factors only on earlier eligible orders with
     earlier out-of-fold FV predictions. Require the common commercial guards, no lower development Gini
     than F1 and higher central profit; retain F1 if their paired difference includes zero. No July tuning.
- Snapshots in aman/data_external/ with sources.md (URL, access date, timezone, availability lag, revisions,
  coverage and missingness); fetching code in
  aman/fetch_external.py so the notebook runs offline.
PHASE 5 - Final model and deliverables
- Use an eligible selected model or the declared provisional fallback. A team-chosen theta_level defaults
  to zero and must have its own scorecard/pass status recorded. Lock the specification/settings before
  validation-price diagnostics. Refit using the final cutoff and chronology in section 1; no new July tuning.
  Save all parameters in aman/model_params.json, including scalers, 96-value profiles, release estimates,
  reference level factors, any duration factors, n (or F0's scaling constant), lambda, theta, units, versions,
  cutoff and selection/fallback status. n and all fitted quantities remain fixed during inference.
- price_orders(df) selects allowed predictors explicitly from the blind schema: one row per input in the
  original order with row_position, createdAt,
  optionType, productType, quantity_BTC, strikePrice, recommended_premium_USDC, multiplier_vs_base,
  predicted_reference_premium_USDC, fair_value_USDC, release_in_window and shape.
  For a candidate without a clipped shape (R0/F0), label shape not applicable instead of implying it obeys
  F1's band. Multiplier is blank when no positive base exists; changing bases cannot change premiums.
  [16 Oct] No LLM, web or API call inside price_orders. Any external feature is read from its cached
  snapshot. A missing value follows a fallback declared in the Phase 4 registry, and a test covers it.
- aman/checks/test_pricing.py, called once by the notebook with a pass/fail summary and failure on errors:
  * Mock the blind file with paid premiums/order prices/payouts blank, ~53% missing bases in a later block,
    and both timestamp formats; also test all bases missing. Changing or blanking closedAt, markup, paid
    prices, payouts or bases must leave quoted premiums unchanged (only multiplier_vs_base may change).
  * Hold all fitted parameters fixed. Perturb candles whose close time is at/after an order: its features
    and quote must stay unchanged. Separately assert every fitted component/target obeyed its cutoff.
  * On controlled fixtures, perturb earlier candles and check that volatility features and raw fair value
    respond. Test final-quote sensitivity on an explicitly unclipped, market-sensitive example; do not
    demand a changed quote for every order when clipping or a duration-only reference can keep it fixed.
  * Check positive finite prices, original row count/order, unseen-duration fallbacks, strict as-of joins,
    identical single-row/batch prices and invariant n. Assert training-total calibration for F1 variants
    within tolerance, not future-total equality; verify candidate-specific final bounds after lambda/theta
    (except where the cost floor binds) and that no F1 quote is below FV.
  * Check Gini permutation invariance, tied-ratio grouping and zero monthly Gini for C0/uniform C2.
    Under no demand response, candidate and same-total C2 must have equal profit on identical rows.
- Price all 4,155 validation rows and save aman/validation_predictions.csv for a selected model or valid
  provisional fallback, with its status in model_params.json and TEAM_SUMMARY.md. If neither is acceptable,
  deliver draft_candidate_predictions.csv plus the failure report; do not label it an accepted final model.
- After specification lock, run the separate 544-row reference check. Verify the export's units and identity
  P_revealed = q x (base_per_BTC + markup_per_BTC); if unconfirmed, label results conditional. Check coverage
  rather than forcing 544 rows. Report reference bias/error only; never reconstruct payouts or compute
  validation profit. The revealed subset need not represent missing-base rows. Do not refit, select or
  alter this version from its results, and do not call previously inspected validation data untouched.
- Write aman/TEAM_SUMMARY.md for the regroup (one page): the scorecard table, what F1 adds over
  Maksim's M (level and comparison tests) and over R0/F0, the theta_level frontier, selected/provisional
  status, failed guards, reference limitations and the open decision on theta_level (with the regret table).
  The 544 revealed JV prices are not used for pricing (team decision, 15 Oct); they serve only the post-lock
  check. Distinguish uncertainty from clear harm.
- Write the two explanation files (section 6), aman/requirements.txt, and make the notebook
  restart-and-run-all clean.

=====================================================================
6. THE TWO EXPLANATION FILES
=====================================================================
aman/CODE_EXPLANATION.md, for a teammate who must rerun or defend the code:
- every notebook section and function: what it does, inputs/outputs, the equation in plain text,
  the leakage guard, and the source (paper, or Maksim's design); include the cost floor, the bisection for n,
  the tie-grouped Gini, the CORP decomposition and the placebo check
- [16 Oct] the Phase 4 registry, trial log and week-shift placebo; the GDELT fetch, if run; and the
  payout-attribution table
- how to run it, how long it takes, what is optional, where each data snapshot comes from
- the input/output schema and what each test proves

aman/REPORT_EXPLANATION.md, for an MSBA classmate without a finance background:
- what each metric means: loss ratio, margin, fair value, expected move, reference price, shape,
  multiplier vs base, conversion scenario, Gini, C2, worst day, cost floor, placebo power check,
  CORP terms (MCB = level/shape error, DSC = ranking power, UNC = outcome noise), regret table
- how to read every table and chart, quoting the actual numbers
- results per model; how sure we are (May, June, July separately; without the biggest orders;
  bootstrap intervals); what we must NOT claim (we did not estimate demand; July is retrospective;
  the reference price is an estimate; scenario profits are not proven commercial gains)
- the recommendation for JV, its risks, the risk layer, and the A/B price test JV should run to learn
  willingness to pay (elasticity = change in log orders / change in log price; Lerner rule under its assumptions)
- why ranking matters even when backtest profit is flat: the scenarios hold payout risk fixed, but with adverse
  selection the lowest-risk buyers leave first when prices rise, so a flat raise keeps the riskiest buyers while
  risk-based pricing charges them more (Einav, Finkelstein & Cullen, 2010)
- for the A/B test: run it as a bandit experiment that limits lost profit while learning (Misra, Schwartz &
  Abernethy, 2019), with fair value as a pre-test covariate to cut the sample needed (CUPED; Deng et al., 2013)
- for day-to-day use: watch JV's price against the reference with an adaptive band that widens after misses
  (adaptive conformal inference; Gibbs & Candès, 2021), as an alarm to recalibrate the level
- [16 Oct] why we did not build an LLM trader or an LLM pricer. In a small benchmark, standard LLM trading
  agents lost 15-22 percentage points of alpha after their training period (Benhenda, 2026). LLM pricing
  agents reached supracompetitive prices and were sensitive to small changes in wording (Fish, Gonczarowski &
  Shorrer, 2024). We used news only as a tested input to the volatility forecast, scored by a model trained
  before our data starts, and we report the result even if it failed
- simple English, short sentences, equations in plain text

If anything here conflicts with what the data shows, tell me instead of forcing it.
~~~

## What changed from JV-04

| Topic | JV-04 + amendments | JV-05 (current) |
|---|---|---|
| Fair value | Payout-fitted ladder / Ridge | **Maksim's move model fitted on market windows** (48 half-hour x weekday/weekend profile, PoissonRegressor alpha=0); payouts are diagnostics, and any payout calibration is a separate variant F1d |
| Price level | Margin θ tuned on profit | **Calibrated to the estimated JV price total on training data, after clipping and the cost floor** (bisection for n); later totals are reported, not guaranteed. θ_level is a team decision, informed by a level-error regret table and re-scored before use |
| Reference price | JV's charged vol by duration | Charged vol **relative to 1-day realised vol** (b = 1 default; the Ridge may learn b), level corrected over three training months |
| "Better, not higher" test | Same-total flat raise (C2) | C2 **plus a tie-safe Gini** on final quotes (permutation and zero-Gini checks) |
| Releases | Event-in-window flag | Added variance with declared shrinkage; PCE only as a declared optional variant |
| Floors | — | No base floor; **cost floor at fair value** (price >= expected payout) |
| Demand scenarios | Ours | Maksim's forms plus an expanded stress grid; Lerner arithmetic stated as an illustration only |
| Selection | Highest score | Placebo power check first. A candidate beats R0 only with a Gini interval above 0, better CORP ranking without worse calibration, profit not worse than R0, and no clear harm vs C0; otherwise R0 (if its audit passes) |
| External data | Order-level tests | Inside the move model, rule adapted to May-June only, then the pricing scorecard |
| Teammates | Re-run where possible | Saved row-level outputs only; M from his walk-forward file |
| Risk layer | — | Maksim's combined cap + hedge result, quoted with its own prices and cash-flow conventions |
| Validation | Never reconstruct | No outcome reconstruction; only the post-lock 544-row reference check. Revealed JV prices are not used for pricing (decided 15 Oct) |

## Amendment 16 Oct (after Phase 2): what we took from the LLM-trading and news papers

The test for each paper was whether it changes how we price PP. Most LLM-trading work predicts **direction**. A seller of at-the-money protection mainly cares about the **size** of the move, so most of that work does not carry over. What does carry over is (1) news as a possible volatility input, and (2) the look-ahead and data-snooping safeguards, which apply to us because the coding agent building our features is itself an LLM.

| # | Idea | Source and key number | Decision | Where |
|---|---|---|---|---|
| 1 | News helps forecast volatility (article count + text) | Kong et al. (2025, ICAIF): 7 US stocks, daily, one step ahead; news model beat the best baseline on QLIKE for 6 of 7 stocks and lost on 1 (CMCSA +11%) | **Test cheaply**: GDELT hourly attention, two features | 4b1 |
| 2 | Most news causes bursts of volatility, not jumps; many jump detections are false under multiple testing | Bajgrowicz, Scaillet & Treccani (2016): up to 90% of initially detected jumps were spurious | Supports keeping release-only jumps + short-window RV; motivates the placebo | Phase 3, Phase 4 rules |
| 3 | An LLM that saw the test period inflates backtests | Yan et al. (2026): look-ahead premium 26.4 bp per s.d. (t = 10.65); Li, Wang & Ma (2026): in-sample returns corrected by up to 67.1%; Benhenda (2026): standard LLMs lost 15–22 pp of alpha out of sample, point-in-time models stayed stable | Only pre-2026 models may score text; **no hand-entered dates** from the coding agent's memory | 4b2, Phase 4 rules |
| 4 | Point-in-time language models exist | He, Lv, Manela & Wu (2025): ChronoBERT 149M / ChronoGPT 1.5B, yearly checkpoints 1999–2024; Yan et al. (2026): DatedGPT 1.3B, 2013–2024, weights at hf.co/datedGPT | Allowed scorers for b2 | 4b2 |
| 5 | Removing identifiers reduces look-ahead and "distraction" | Glasserman & Lin (2023) | Mask numbers, prices and dates | 4b2 |
| 6 | LLM-driven factor search needs hypothesis and complexity checks | Tang et al. (2025, AlphaAgent) | Closed registry with a hypothesis and parameter count per feature | Phase 4 rules |
| 7 | Agent studies rarely log failed attempts or use time-consistent splits | Xia et al. (2026 survey): 2 of 19 primary studies report time-consistent splits, 1 of 19 an explicit cost model | Trial log; report failures | Phase 4 rules |
| 8 | LLM-labelled jump narratives: macro news carries the largest jump-risk premium | He (2026) | A descriptive attribution table instead of an LLM classifier | Phase 3 |
| 9 | LLM pricing agents drift to supracompetitive prices and are prompt-sensitive | Fish, Gonczarowski & Shorrer (2024) | No LLM in the quote path; deck point | Phase 5, report |
| 10 | Direction-trading agents | TradingAgents (Xiao et al., 2025: Jan–Mar 2024 test, Sharpe 5.6–8.2, which the authors say exceeds the expected range); CryptoTrade; Lopez-Lira & Tang (v6, 2025) | **Rejected**: direction barely changes ATM option value, short test windows, leakage risk | — |
| 11 | LLM time-series forecasters for BTC | Fakhari & Safayani (2026, PRICE): no simple baselines or leakage controls reported | **Rejected** | — |
| 12 | Social sentiment snapshots (Jay) | Our data: ~40 snapshots a month, gaps up to 316 h, reconstructed clocks | **Rejected** for intraday features | — |

**What we computed (16 Oct, from the repo):**
- News coverage: `news_combined_2026.jsonl` has 153 rows; the CoinDesk headlines by month Feb–Jul are 2, 15, 5, 14, 3, 13, and the 36 official records duplicate the release calendar. Only Fear & Greed (daily, 2018 to 14 Oct) has full coverage, and it is already in 4a. GDELT's DOC API timeline modes reach back to 2017; Subham pulled one week at hourly resolution, so the endpoint works from a normal connection. It is blocked from my workspace and from the shell on your Mac's VM, so Codex must fetch it from your Mac.
- `aman/checks/jump_attribution.py` (anchors checked: 7,150 orders, loss ratio 0.930): only 0.37% of 15-minute bars fall in the hour after a core release, yet they hold 3.4% of the top-1% moves (about 9 times their share) and **0 of the 18 top-0.1% moves**. Of those 18, 8 fell in the 2–7 Feb sell-off and 3 at the US stock-market open (13:30–14:00 UTC), which the half-hour time-of-day profile already covers. Orders with a release in the window: 5.7% of premium, 8.5% of payout, loss ratio 1.39 (June 1.20, July 1.64). Orders with a big unscheduled move: 4.5% / 8.8% / 1.81, almost all in June (9.8% / 19.2% / 1.84; July has 2 such orders). Without the 10 worst losses: 1.59 and 1.11. Groups are defined after the fact, so a loss ratio above 1 here is expected and is not a pricing error.
- Reading: the biggest moves are unscheduled and lumpy (one month), so no quote-time feature will reliably foresee them. That is the case for the risk layer (caps + hedge), not for a bigger model.

**Prior expectation, stated before testing:** news is absorbed within minutes (Lopez-Lira & Tang report about a 90% hit rate on the initial, non-tradable reaction), so by quote time most of it already shows up in the 60-minute realised variance. Expect b1 to add little. A clean failure is a fine result to report.

**Cost:** b1 is about 1–2 hours (around 37 API calls plus one more Phase 4 test). b2 takes several hours plus a model download. Recommend skipping b2 before Sunday unless b1 passes clearly.

**Message for Codex** (paste before Phase 3):

```text
aman/PLAN.md was amended on 16 Oct. Re-read it. Changes are marked [16 Oct]; Phases 1-2 stay approved
and are not reopened. In short: (1) Phase 3 adds a descriptive payout-attribution table (see
aman/checks/jump_attribution.py); (2) before Phase 4, write phase4_registry.csv (closed list, hypothesis,
formula, parameter count, source, lag) and log every run in phase4_trials.csv; any passing feature must
beat 18 of 20 whole-week shift placebos; no hand-entered dates; (3) 4b is now GDELT hourly attention (b1),
with an LLM headline score (b2) only if b1 passes and I agree; (4) no LLM, web or API call inside
price_orders. Summarise the changes back to me in five lines before continuing.
```
