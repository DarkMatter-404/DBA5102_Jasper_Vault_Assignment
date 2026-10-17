# Independent audit and decision memo — Jasper Vault PP pricing (DBA5102, Option 2)

Written Fri 16 Oct 2026 (~17:00 SGT). Deadline Sun 18 Oct 23:59 SGT.
Repository read-only at `/home/claude/dba5102_jasper_vault_assignment`. All my scripts and tables are in this folder
(`chris/audit/`). Money in USDC. "JV" = Jasper
Vault's actual historical price (panel column `q_C0`). No validation payout was computed by me; the only
validation-outcome numbers quoted are Maksim's one agreed sealed check (`maksim/results/sealed_check/`).

## 0. Bottom line

1. **Every headline number in the four main workspaces reproduces** from the saved files (Maksim's 45,101 vs 10,576
   and 62,879 vs 17,437; Subham's 34,124 vs 15,195; Aman's whole scorecard; Chris's crowded/contrarian split). The
   team's problem is not arithmetic, it is **which price level to submit**.
2. **The locked model F1 (theta = 0) should not be the main submission.** On the same orders it is below JV's own
   profit in July under every demand rule (3,785 vs 4,319 with no demand response; −7,635 [−13.9k, −1.0k] under
   "keep only if ≤1.10× JV"). Its margin over expected payout is 3–13% in training and **8.6% on the blind file**
   (177,986 vs fair value 163,929), while Maksim's sealed check found realised payouts were **1.23× fair value**
   over Aug–Oct (1.45× in August). F1 also quotes 0.86× JV's revealed price on the 544 August rows (0.65× on 30-min).
3. **Recommend Maksim's model (fair value × 1.25, floored at the API base) as the main scored price**, with his
   exposure cap as the risk layer and Chris's contrarian loading as a documented add-on. It is the only candidate that
   is pre-registered, fully reproducible, sealed-checked, beats JV significantly under no-response and conservative
   demand in both holdout periods, and is **0.96× JV's revealed August price** on the 544 rows — so "higher pricing"
   is not what JV will see.
4. Fallback if the team will not reopen the F1 lock: re-level F1 to theta = +0.10 (evidence pre-dates the lock) and add
   the loading. Do not submit F1 at theta = 0 and do not submit Subham's hybrid as main (selection on the same months
   it reports; 53% of blind rows priced off a rebuilt base; lower ranking power).
5. The grade risks are coherence (three "final" files and a Jay README calling his framework "the main assignment
   framework"), an undisclosed or badly disclosed data leak, and an over-complicated story. One file, one narrative,
   one honest validation slide.

---

## 1. Workspace audit

### 1.1 Maksim (`maksim/`) — fair-value model, risk policy, sealed check

**What it is.** `premium = quantity × fair value per BTC × 1.25`, never below the API base where one exists. Fair
value = Black-Scholes at an expected |move| from a per-duration Poisson regression on realised variance (1h, 4h, 1d,
1w) plus a 96-slot US-Eastern time-of-day profile and extra variance for CPI/NFP/FOMC inside the window. Fitted on
candles only; no order payout enters any parameter. Risk policy: 250,000 USDC open-notional cap per direction + net
delta hedge within 0.5 BTC. One sealed check on the blind file (commit c70c413, 14 Oct), nothing changed after.

**Verified (my recomputation from `results/*.parquet`).**

| Claim (README) | Recomputed | File |
|---|---|---|
| Jun+Jul test: model 45,101 vs current 10,576; premium +16.5% | 45,101 / 10,576 / 1.165 | `results/test_orders_priced.parquet` |
| cons e=1 36,485; keep ≤1.00 12,280; keep ≤1.25 18,463 | 36,485 / 12,280 / 18,463 | same |
| 61% of orders cheaper, median ratio 0.885 | 0.610 / 0.885 | same |
| Walk-forward Feb–Jul: 62,879 vs 17,437; cons e=1 49,790; keep≤1.25 28,911; keep≤1 15,401 | all match | `results/walk_forward_orders_priced.parquet` |
| Validation premium-weighted multiplier 1.60× base on 1,960 rows | 1.599 | `outputs/validation_recommendations.csv` |

**What it proves.** The fair-value shape ranks risk (walk-forward Gini vs JV price 0.14 / 0.27 / 0.10 in May / Jun /
Jul — Aman's `gini_by_month.csv`; F0, M and raw FV are identical to three decimals, so the ranking is entirely the FV
engine). It is calibrated: payout / FV = 0.86, 1.02, 1.00 in May, June, July. It beats JV significantly under no
response and conservative e=1/e=2 in both holdout periods (section 2) and cuts the worst day (July −3,818 vs −5,073;
May+Jun −7,636 vs −9,630).

**What it does not prove.** (i) Better *allocation* than an equal flat raise: model − flat×1.165 under cons e=1 is
−2,232 [−11.4k, +7.2k] (his own interval). (ii) Any gain under "keep only if not dearer" (12,280 vs 10,576, n.s.;
walk-forward 15,401 vs 17,437). (iii) June–July were used to compare variants, so they are not clean. (iv) On the blind
period the ranking advantage vs the base did not hold (Gini −0.085). (v) Sealed check: +4,821 on all 4,155 orders
(LR 0.98); **August −12,667 while BTC rose 25% (calls paid 2.0× FV)**, Sep +10,812, Oct +6,679; on the 544 rows with a
recoverable JV price, actual −26,119 vs model −27,684 — parity, both awful (LR 1.7–1.8).

**Errors / over-claims.** None material; the README states "mostly higher" itself. Two things it under-sells that the
deck should use: on the 544 revealed rows **JV's own multiplier was 1.53× base (2.12× on 30-min)** versus 1.33–1.50 in
training months, and Maksim's price there is **0.957× JV's price** (my `blind_prices.pkl`, prices only). The model's
"+17–21% vs JV" is a training-period fact that did not carry into August.

### 1.2 Subham (`subham/`) — hybrid: anchor × risk multiplier + reference/3

**What it is.** Anchor = API base, or a rebuilt base (regression on HAR vol / BS) where missing. Expected payout =
anchor × risk multiplier (GLM; ≈1.36 constant, ×1.23 in a release window). Reference = estimate of JV's price from the
anchor. Premium = expected payout + reference/3, clipped to [0.85, 1.6] × reference, never below expected payout.
The "/3" is the profit-maximising markup under an *assumed* exponential demand a = exp(−3(P/R − 1)) (+10% price →
−26% orders), with discounts allowed to win up to 1.5× volume.

**Verified.** May–Jul "moderate" profit 34,124 vs JV 15,195 reproduces exactly from the panels under his rule
(`outputs/backtest_summary.csv`; my `score_panels.py` run log). Premium level 1.25 / 1.16 / 1.13× JV in May / Jun / Jul;
26–40% of orders cheaper; Gini 0.06 / 0.14 / 0.11 (lowest of the FV-type models).

**What it does not prove / over-claims.**
- **His own out-of-sample benchmark beats him.** `backtest_summary.csv`: "base price × best constant" (constant fitted
  on earlier months) earns 84,662 / 53,044 / 38,383 under none / low / moderate vs the hybrid's 51,556 / 39,909 / 34,124.
  The README headline omits this. The hybrid only wins under "high" sensitivity (28,214 vs 25,836).
- The config (`hybrid_events`) was chosen among 9 on the same May–Jul months that are reported; there is no untouched
  test month.
- 53% of blind rows are priced off a rebuilt base with median error 9%, p90 22% (`validation_summary.json`).
- His blind "expected payout" is 160,251; Maksim's sealed realised total is 201,003. The expected-payout engine
  under-predicted the period by ~20%; only his 1.32× FV price level covers it.
- Under his own moderate rule Maksim's prices earn more than his (36,593 vs 34,124 on the panels).

### 1.3 Jay (`jay/`, `revision_v2/`) — bounded multiplier with news/social sentiment

Bounded multiplier ±1.29% around a "compatible reference" (recorded premium), duration credibility + market + TF-IDF
news + social sentiment. Built on the original EN release with candles ending 24 Aug, so 2,255 of 4,155 blind rows fall
back to the duration component. July: 4,713.57 vs 4,042.04 (+671, +16.6%) under an assumed e=4 on 2,625 EN rows —
not comparable to the team panel; a ±1.3% price change cannot carry commercial weight; the model's July predicted
payouts are 27% above actual (his own number). Honest about all of this. **Not a submission candidate**; it supplies one
slide: "news and social sentiment were tested; headline coverage was 2–15 per month and no incremental signal was
found." Risk: `jay/README.md` calls V3.2 "the main assignment framework" — must be reconciled with the team decision.

### 1.4 "llm assisted trading" — event-to-loss study

Market-path engine + 44 LLM-classified event cards. July: market-only 7,618 and verified-research 7,656 vs actual
4,285 at +3.13% price (no demand); increment from research +38 [−44, +166]; under e=2 the engine is −1,639 vs +7,198
for the same-total flat raise; expected claims cover 64% of actual July payouts. Honest README. Not a candidate; one
slide: "LLM event research adds nothing measurable at 0.5–24h horizons once the release calendar is in."

### 1.5 Aman (`aman/`) — model F1 and the team scorecard

**What it is.** `P = max(clip(FV / n, 0.8 R0, 1.2 R0), FV)`: FV is Maksim's engine re-implemented (identical to 0.1%,
my check), R0 is a ridge estimate of JV's price from quote-time features (duration, RSI, Bollinger %b, realised vols),
n makes the training total equal the reference total, theta_level = 0. Pre-registered selection on May+Jun (placebo
power check, Gini, CORP calibration, profit guards); July retrospective; locked 16 Oct 04:46 SGT; 544-row price check
after the lock.

**Verified.** The entire scorecard reproduces from `panels_dump.pkl` (my `score_panels.py`): C0 10,876; F1 16,594
(cons e=2, May+Jun); M 23,656; S 20,622; F1 July cons e=2 1,436 vs 4,319; R0/JV 0.98 / 1.07 / 0.88 by month; 544-row
reference bias −7.6% (my recomputation −7.6%, F1/JV 0.864, FV/JV 0.748).

**What it proves.** F1 ranks (Gini 0.10 / 0.27 / 0.10) and is calibrated, with a disciplined protocol. Aman says
plainly "no demonstrated profit gain over JV's price" and "the reference level is the weak point". Both are correct.

**What it does not prove, and the problems.**
- **July: below JV under every rule**, significantly so under thresholds: keep ≤1.10× −7,635 [−13,898, −1,021],
  keep ≤1.25× −4,463 [−8,668, −387] (my `bootstrap_vs_JV.csv`). Cause: R0 ran 12% low in July; the lower band then cut
  30-min orders to 0.83× JV in the month 30-min payouts were 1.14× FV (F1 lost 278 on 30-min where JV made 1,593).
- **The band binds for 58–75% of quotes** (his `clipping_and_floor.csv`), so F1 is effectively "R0 × 0.8 or R0 × 1.2":
  a two-level shape on a reference whose weighted error is 13% (and 20% low on 30-min and 1h).
- **Thin margin.** F1 / FV = 1.09, 1.13, 1.03 in May, Jun, Jul and **1.086 on the blind file**. The blind period's
  realised payout / FV was 1.226 (Maksim's sealed check, aggregate). Unless JV's conversion rule rewards cheapness
  heavily, F1 as locked is projected to show a gross loss on the blind file. This inference uses only published
  aggregates; nothing was recomputed, and it should not be used to tune anything further.
- "F1 charges 4.5% above JV" (TEAM_SUMMARY) is May+Jun only; July is −0.5%, and 544-row August is −14%.
- The exposure-cap overlay "makes the worst day slightly worse under the central scenario" is an artefact of
  weighting orders by assumed conversion; ignore it.

**Errors.** None found in the numbers. The protocol is excellent; the output is a ranking model priced at JV's level
minus the reference bias, and the "selected / locked" label risks being read as "best model".

### 1.6 Chris (`chris/`) — order flow / book state (read after forming the view above)

**Verified independently** (my `book_proxy_check.py`, built from the raw training file without his code): orders that
join the crowded side of JV's open book pay less, contrarian and empty-book orders pay more. My cut (|s_add| > 0.2,
his `book.pkl`): crowded LR 0.71, payout/FV 0.85; contrarian 1.03 / 1.16; neutral 1.03 / 1.16; direction holds in
May, June and July (April reverses). **It survives a book built only from expiry dates (no `closedAt`)**: strongly
joins LR 0.56 vs strongly opposes 1.16; by month joins 0.70 / 0.75 / 0.58 vs opposes 0.98 / 1.16 / 1.11. So the signal
is deployable on the blind file without touching the leaked column.

**As a pricing layer** (k = 0.3 on books ≥ 1 BTC) it adds +3–4k per period on any base model with no demand response
and +2–3k under cons e=2 (section 2.3), loads 25–26% of orders by +7.7% on average, and never cuts a price. Under the
strict threshold rules it is noise (his own table: July strict10 −2,025 vs flat). **As a risk signal** it is the best
thing the team has: 12 "crowd-right" days gave back almost all of 38 "crowd-wrong" days' profit (his table), and August
2026 was a crowd-right month. I agree with his ranking: risk signal first, pricing signal second.

---

## 2. Same-holdout comparison (identical orders, identical demand rules)

Source: Aman's per-order panels (`panels_dump.pkl`; May 965, Jun 2,270, Jul 2,571 orders; every model priced
walk-forward; `q_M` = Maksim's walk-forward prices, `q_S` = Subham's `hybrid_events` fold prices — both verified to
1e-13 against their source parquet files). Script: `score_panels.py` → `same_holdout_scores.csv`;
intervals: `bootstrap_diffs.py` → `bootstrap_vs_JV.csv` (paired day bootstrap, 2,000 draws, seed 0).
Rules: none; cons e=1 and e=2 = min((P/JV)^−e, 1); keep ≤1.10× and ≤1.25× JV; keep ≤1.00× shown for reference.

### 2.1 July 2026 (JV premium 107,753; payouts 103,434; JV profit 4,319; LR 0.96)

| Policy | Price/JV | Orders cheaper | None | cons e=1 | cons e=2 | keep ≤1.00 | keep ≤1.10 | keep ≤1.25 | Worst day (none) | LR (none) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **JV actual (C0)** | 1.000 | — | 4,319 | 4,319 | 4,319 | 4,319 | 4,319 | 4,319 | −5,073 | 0.960 |
| R0 (est. JV price) | 0.876 | 80% | −9,055 | −9,729 | −10,269 | −12,965 | −12,537 | −10,007 | −5,962 | 1.096 |
| F0 (FV scaled to JV total) | 1.026 | 77% | 7,080 | 4,807 | 3,296 | 957 | 1,432 | 195 | −4,482 | 0.936 |
| **F1 locked** | 0.995 | 78% | 3,785 | 2,383 | 1,436 | 1,986 | **−3,316** | **−144** | −4,796 | 0.965 |
| F1 × 1.10 (floor FV) | 1.095 | 69% | 14,507 | 11,425 | 9,372 | 4,767 | 6,061 | 5,673 | −4,204 | 0.877 |
| **M Maksim** | 1.206 | 66% | **26,506** | **19,509** | **15,101** | 3,715 | **6,666** | 8,298 | **−3,818** | **0.796** |
| M without base floor | 1.204 | 66% | 26,327 | 19,330 | 14,921 | 3,536 | 6,487 | 8,118 | −3,820 | 0.797 |
| S Subham | 1.128 | 40% | 18,098 | 16,121 | 14,518 | 2,388 | 4,524 | **18,705** | −4,189 | 0.851 |
| FV × 1.15 | 1.108 | 72% | 15,946 | 11,919 | 9,306 | 3,653 | 3,155 | 1,674 | −4,168 | 0.866 |
| √(F1·M) | 1.095 | 72% | 14,516 | 11,172 | 8,972 | 4,436 | 4,551 | 3,076 | −4,212 | 0.877 |

Model − JV, 90% day-bootstrap intervals (July): F1 none −533 [−4,537, +3,440]; F1 keep≤1.10 −7,635 [−13,898, −1,021];
M none +22,187 [+15,472, +29,549]; M cons e=2 +10,782 [+3,506, +18,719]; M keep≤1.10 +2,347 [−13,050, +19,130];
S none +13,779 [+9,550, +18,763]; F1×1.10 none +10,188 [+5,178, +15,442], cons e=2 +5,053 [−187, +10,325].

### 2.2 May + June 2026 (JV premium 127,537; JV profit 10,876; LR 0.914) — Aman's development months

| Policy | Price/JV | Orders cheaper | None | cons e=1 | cons e=2 | keep ≤1.00 | keep ≤1.10 | keep ≤1.25 | Worst day (none) | LR (none) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **JV actual (C0)** | 1.000 | — | 10,876 | 10,876 | 10,876 | 10,876 | 10,876 | 10,876 | −9,630 | 0.914 |
| R0 | 1.054 | 48% | 17,693 | 11,995 | 8,336 | 3,434 | −2,272 | 2,742 | −9,315 | 0.868 |
| F0 | 1.014 | 64% | 12,638 | 12,773 | 12,647 | 6,968 | 8,862 | 15,736 | −8,812 | 0.902 |
| **F1 locked** | 1.045 | 55% | 16,587 | 16,662 | 16,594 | 11,071 | 14,157 | 21,360 | −8,620 | 0.875 |
| F1 × 1.10 | 1.149 | 42% | 29,863 | 26,834 | 24,569 | 11,559 | 16,086 | 22,464 | −7,851 | 0.796 |
| **M Maksim** | 1.169 | 50% | 32,314 | 27,225 | 23,656 | 10,764 | 12,982 | 18,656 | **−7,636** | 0.782 |
| S Subham | 1.178 | 26% | 33,458 | 25,580 | 20,622 | 10,898 | 13,230 | 11,295 | −8,929 | 0.776 |
| FV × 1.15 | 1.071 | 59% | 19,859 | 18,414 | 17,159 | 7,020 | 11,704 | 17,349 | −8,332 | 0.854 |
| √(F1·M) | 1.102 | 53% | 23,801 | 22,156 | 20,761 | 11,073 | 14,354 | 21,782 | −8,169 | 0.830 |

Intervals (May+Jun): F1 none +5,710 [−1,489, +12,669]; F1 cons e=2 +5,717 [−5,069, +18,127]; M none +21,438
[+12,652, +30,569]; M cons e=2 +12,779 [+14, +27,678]; F1×1.10 cons e=2 +13,693 [+1,869, +27,377].
Monthly, no demand: May JV 4,620 / F1 5,755 / M 9,800 / S 11,013; June 6,257 / 10,832 / 22,514 / 22,445.

### 2.3 Deployable combinations (`combos.py` → `combos_scores.csv`)

"Deployable" = uses only quote-time inputs available on the blind file (FV, R0, base, book built from expiry dates).
Loading = × (1 + 0.3 × max(−s_add, 0)) on books ≥ 1 BTC (expiry-proxy book, no `closedAt`).

| Policy | Jul price/JV | Jul none | Jul e=2 | Jul ≤1.10 | Jul ≤1.25 | M+J price/JV | M+J none | M+J e=2 | M+J ≤1.10 | M+J ≤1.25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JV | 1.000 | 4,319 | 4,319 | 4,319 | 4,319 | 1.000 | 10,876 | 10,876 | 10,876 | 10,876 |
| M | 1.206 | 26,506 | 15,101 | 6,666 | 8,298 | 1.169 | 32,314 | 23,656 | 12,982 | 18,656 |
| **M + loading** | 1.242 | 30,347 | 16,696 | 6,175 | 9,039 | 1.195 | 35,696 | 25,264 | 14,176 | 21,033 |
| M capped at 1.4·R0, floor 1.10·FV, + loading | 1.156 | 21,158 | 13,735 | 7,366 | 8,647 | 1.151 | 30,004 | 23,338 | 13,934 | 21,584 |
| F1 × 1.10 + loading | 1.127 | 17,988 | 11,626 | 7,317 | 7,595 | 1.176 | 33,217 | 26,102 | 16,673 | 23,175 |
| √(M·S) | 1.157 | 21,264 | 16,167 | 8,746 | 16,160 | 1.162 | 31,408 | 24,549 | 16,774 | 21,936 |
| FV × 1.20 + loading | 1.190 | 24,822 | 14,038 | 4,523 | 11,377 | 1.143 | 29,009 | 21,872 | 13,640 | 20,444 |

M + loading beats JV under every rule in both periods including keep ≤1.00 (July 5,039 vs 4,319; May+Jun 11,053 vs
10,876). The loading is worth +3.3–3.8k per period with no demand response and +1.6k under cons e=2; it raises the
blind-file premium total by 2.7–2.8% (`blind_book_proxy.pkl`).

### 2.4 Reading the tables

- **Level drives profit; shape adds ranking.** All FV-based models share the same Gini. JV already prices at
  ≈ FV × 1.04–1.08 (FV/JV 0.96 / 0.93 / 0.96; payout/JV 0.82 / 0.94 / 0.96). A 25% margin over FV therefore shows up
  as ~17–21% above JV in training.
- **Threshold rules are noisy and month-specific.** Under keep ≤1.25× Subham wins July (18,705) because dropping his
  >1.25× quotes removed loss-makers; Maksim's >1.25× quotes (4h/8h at 1.27–1.37× JV, LR 0.70–0.86) were his most
  profitable. No model is significantly better than JV under either threshold in either period.
- **Where the money is lost.** 16 days with |daily BTC return| > 2.28% (top quartile) carry 29% of premium and 37% of
  payouts; payout/FV was 1.29 on them and puts paid 1.89× FV (BTC fell in May–Jul). JV lost 13,545 on those days,
  F1 −11,820, M −2,360. No quote-time model forecasts direction; this is the case for the exposure cap, not for a price.
- **Payout concentration.** Top 1% of orders carry 20–31% of each month's payout.

---

## 3. Recommendation

### 3.1 Ranked

**1. Main scored price: Maksim's frozen file (`maksim/outputs/validation_recommendations.csv`,
`recommended_premium_USDC` for all 4,155 rows; `recommended_multiplier_vs_base` where a base exists).**
Reasons: pre-registered margin, fitted on market data only, no-lookahead test, walk-forward and sealed-check evidence,
significant gains over JV under no-response and conservative demand in both holdout periods, lower worst days, and the
only submission whose level has been compared with JV's actual blind-period price (0.957× on the 544 rows). Do not
alter the scored column after the sealed check.

**Layers to present with it (operating recommendation, not a change to the scored column):**
- **Exposure cap per direction** (Maksim's 250,000 USDC rule; Chris's crowd-right-day evidence as the rationale). On
  training it cuts the worst day −8,399 → −3,976 for 30% of gross profit (with the hedge) — or, cap alone,
  −8,399 → −6,594 for 11% of profit (`maksim/results/extensions/exposure_limits.csv`). Say clearly it limits but does
  not prevent an August.
- **Order-flow loading** (k = 0.3, book from expiry dates): provide as a second column
  `recommended_premium_with_orderflow_loading_USDC` or as a slide. It was designed on training only, never cuts a price,
  adds +2–4k per period on any base and 2.7% to the blind total.
- **Caps that make "better, not higher" visible:** report the premium-weighted price vs JV by segment (30-min 0.85–0.95,
  1h 1.04–1.11, 2h 1.09–1.15, 4h 1.37–1.51, 8h 1.27–1.46), share of orders cheaper (50–66%), and the 544-row ratio
  (0.957, 0.67 on 30-min). Keep the base floor (it binds on 36% of base rows in the blind file and is a commercial
  safeguard; it changed July profit by only +179).

**2. Fallback if the team keeps F1:** re-level to theta_level = +0.10 (F1 × 1.10, floor at FV). The evidence for a
level correction was in Aman's own tables before the lock (July reference audit −12.4%; frontier). On the panels
F1 × 1.10 beats JV under every rule in both periods (significantly under none and cons e=1), keeps 78% (July) and
55% (May+Jun) of orders under keep ≤1.10, and lands at 1.10–1.15× JV in training, ≈0.95× JV on the 544 rows. Add the loading. Disclose that
the lock was reopened for level only, shape unchanged.

**3. Do not submit as main:** F1 at theta = 0 (section 1.5); Subham's hybrid (section 1.2); Jay / LLM (experimental).
Keep Subham's rebuilt base as a cross-check for the 2,195 no-base rows and his release-window multiplier (1.23) as
corroboration of Maksim's release variance.

### 3.2 The price-level question, stated honestly for the deck

- The reference R0 is an estimate of JV's price with ±10% monthly error (0.98 / 1.07 / 0.88 in May / Jun / Jul;
  0.92 on the 544 August rows). JV's own markup drifts month to month (1.33–1.61× base in training; 1.53× in August).
  Anchoring the submission to an estimate of JV's price therefore carries an error as large as the whole margin.
- A cost-plus price (expected payout × 1.25) is the defensible alternative: expected payout was calibrated in training
  (payout/FV 0.86–1.02) and the 25% margin was set as a business target before testing (Maksim §3). The blind period
  was adverse to every quote-time model (August payouts 1.45× FV); the margin is what kept the sealed result positive.
- Say what the model does to prices: 61–66% of orders cheaper; 30-min orders down 5–15% and 00–04 UTC orders down
  19%; 4h / 8h orders up 27–51% and 08–12 UTC orders up 34%; release windows up 25% (my duration table and Maksim §5.3). Those are exactly the segments where JV's loss ratio was
  above 1.

### 3.3 Limitations to state plainly (one slide)

1. **Demand was not estimated.** All conversion scenarios are assumptions (none / elasticity 1–2 / thresholds); JV's
   rule is unknown. Under "keep only if not dearer" no model beats JV in July. Recommend JV run a randomised price
   test (e.g. ±10% on a random 10% of quotes) to measure its elasticity.
2. **Trending months lose at every model's price.** Maksim's sealed check: August −12,667 (BTC +25%, calls 2.0× FV).
   The exposure cap and the crowd-side evidence are the answer, not a higher price.
3. **Data integrity disclosure.** The blind file's `closedAt` is filled and the candles run to 14 Oct, so outcomes are
   recoverable; 544 rows also reveal JV's price via `markup`. The team used none of this as a model input (no-lookahead
   test in `maksim/tests/`), ran one agreed aggregate check after freezing (Maksim §6, commit c70c413) and one
   price-only bias check after locking F1 (Aman), and changed no scored price afterwards. Say this in one sentence and
   recommend JV blank `closedAt` in future releases.
4. **Gross underwriting profit only**; no fees, funding, capital or hedging costs in the scored numbers.
5. **Sample size.** 24h, 12h and release-window segments are tens to a few hundred orders; monthly profit is driven
   by a handful of days and 1% of orders.

---

## 4. Risks to the grade and the next 48 hours

### 4.1 Top risks

1. **Submitting F1 at theta = 0.** Projected to be below JV in profit on the blind file (sections 1.5, 2.1). The
   team's own evidence (July) already says so.
2. **Incoherence.** Three different "final" price files (`maksim/outputs/`, `aman/validation_predictions.csv`,
   `subham/outputs/validation_premiums.csv`), two different fair-value totals on the blind file (205,824 vs 177,986 vs
   216,764), and `jay/README.md` presenting V3.2 as "the main assignment framework". A grader who opens the repo
   must find one submitted model, one file, one README.
3. **Leak handling.** Not disclosing the `closedAt` / candle leak is a credibility risk if JV knows; disclosing it as
   "we rebuilt the payouts" is worse. Use the wording in 3.3(3).
4. **"Just higher prices."** M is +17–21% vs JV in training. Pre-empt with the 544-row comparison (0.957× JV), the
   61–66% cheaper share, the segment table and the flat-raise comparator (model keeps 90.5% of orders vs 85.8% for an
   equal flat raise under conservative demand; worst day −4,257 vs −7,322 — Maksim §5.1).
5. **Over-complication.** Aman's protocol (placebo, CORP, Lerner, regret) is good science and bad slideware. One
   methods slide; put the protocol in the appendix.
6. **Format unknowns.** No order ID; premium vs multiplier; whether all 4,155 rows are scored. Send the questions
   today; state the assumptions on a slide regardless.
7. **Housekeeping.** Repo and some READMEs say DBA5106; module is DBA5102. Video must be ≤10 minutes.

### 4.2 Concrete to-do list

**Sat 17 Oct, morning (team call, 30 min):** decide main model (recommendation: M), layers, who records which part.

**Single output file** (owner: Aman or Maksim): one CSV, 4,155 rows, original row order, columns
`row, createdAt, optionType, productType, quantity_BTC, strikePrice, apiBasePrice_per_BTC_USDC,
recommended_premium_USDC, recommended_multiplier_vs_base (blank if no base), fair_value_USDC,
recommended_premium_with_orderflow_loading_USDC (optional)`. Checks: no blanks in premium, all > 0, totals printed in
the README (205,824 for M), SHA-256 recorded. Keep `closedAt` out of the file.

**Deck (12–15 slides; owner: Keerthi + Subham for design, Maksim/Aman/Chris for content):**
1 problem & JV's P&L today (248,089 / 230,652 / 7% margin; break-even 1.40× base) · 2 what the data says (base ignores
time of day; markup Gini 0.01 vs risk; 30-min over-, 4h/8h under-priced) · 3 payout mechanics & leakage rules ·
4 the model in one picture (expected move → fair value → ×1.25 → base floor) · 5 factors (US-open 3.8× variance,
release calendar, realised vol) · 6 same-holdout table (JV, F1, M, S under 4 rules, July and May+Jun — section 2) ·
7 "better not higher" (segment price changes, share cheaper, 544-row ratio) · 8 order flow (crowded vs contrarian,
crowd-right days) · 9 risk policy (cap + hedge trade-off table) · 10 validation period (sealed check, August honest) ·
11 what we tested and dropped (size, direction, HMM, news, LLM, sentiment, DVOL, Fear & Greed — all pre-registered
rules) · 12 limitations & what JV should do next (price RCT, blank closedAt, cap) · 13 deployment (off-chain model,
oracle, caps — lecture 6/7 checklist) · appendix: Aman's protocol, Subham's hybrid as cross-check, Jay/LLM summaries.

**Video (10 min; owner: all six, ~90 s each):** script ≈1,300 words from the slide order above; record Sunday
morning; one person stitches; check length < 10:00.

**Code package:** root README naming the submitted model and file, pointing to `maksim/` (model), `chris/` (order flow),
`aman/` (team scorecard), `subham/` (hybrid cross-check), `jay/` and `llm assisted trading/` (experiments); fix
DBA5106 → DBA5102 in submitted text; confirm `maksim/run_validation.py` reproduces `FROZEN.json`; zip without `.venv`.

**Questions to JV (send today, Aman's draft (a)–(d) + (f)):** output format and row matching; whether all 4,155 rows
are scored; the form of the conversion constraint and its reference price; whether the filled `closedAt` was intended;
whether price = quantity × (base + markup) on the 544 rows.

---

## 5. Where I agree and disagree with `chris/TEAM_SAME_HOLDOUT_CHECK.md` (read last)

**Agree:** F1 locked is below JV in July under every rule (his 3,622 vs 4,196; mine 3,785 vs 4,319 — the ~100 USDC
differences come from his join on `createdAt`+`quantity_BTC`, which produced 2,573 July rows instead of 2,571; no
conclusion changes). The cause is level, not shape. A level correction of +8–10% repairs it directionally. The
contrarian loading adds 2–3k per month on any base and never cuts a price. The exposure cap is the risk tool. His
suggested wording if the lock is kept ("a ranking model priced at JV's level minus the reference bias") is exactly right.

**Disagree / corrections:**
1. His two "most robust" rows — `max(F1, min(M, 1.25 × JV))` and `√(M·S) clipped [0.85, 1.4] × JV` — use **JV's actual
   price as an input** (`holdout_all.py`, `t.q_C0` inside the cap/clip). That price is unknown on 3,611 of 4,155 blind
   rows, so neither is a submittable policy. The deployable versions (cap/clip on R0) are weaker: M capped at 1.4·R0
   + loading gives July 21,158 / 13,735 / 7,366 / 8,647 (none / e=2 / ≤1.10 / ≤1.25) vs his 17,342 / 12,797 / 6,912 /
   12,532, and √(M·S) clipped to R0 gives 13,014 / 10,818 / 6,111 / 11,530. Still fine, but not the object he scored.
2. "+8% repairs it under every rule": directionally yes, but the threshold-rule intervals include zero
   (F1 × 1.10 keep ≤1.10 July +1,742 [−10,307, +14,970]); it should be presented as "removes the July deficit", not
   as a proven gain.
3. His loading uses the book built from actual close times (`closedAt` of earlier orders). On the blind file that
   column is the leaked outcome; use the expiry-proxy book (signal verified above) or state that only earlier orders'
   close times are used — JV has that information live, but graders may not read it that way.
4. On the decision: he proposes re-locking F1 at theta +0.08. I would go further — the band-on-a-noisy-reference
   construction is the weak part of F1, not just its level — and submit Maksim's cost-plus model as main, with F1 × 1.10
   as the fallback.

---

## 6. Files in this folder

| File | Content |
|---|---|
| `score_panels.py` → `same_holdout_scores.csv` | 18 policies × 7 demand rules × 5 periods on Aman's panels |
| `bootstrap_diffs.py` → `bootstrap_vs_JV.csv` | paired day-bootstrap 90% intervals, model − JV |
| `combos.py` → `combos_scores.csv` | deployable combinations incl. expiry-proxy order-flow loading |
| `book_proxy_check.py` → `book_proxy.pkl`, `book_actual.pkl` | crowded/contrarian effect with and without `closedAt` |
| `blind_prices.pkl`, `blind_book_proxy.pkl` | the three submitted blind price vectors side by side (prices only, no `closedAt`, no payouts) |

Reproduce: `cd` to this folder and run `python3 -I <script>.py`; inputs are the read-only repo and
`../amanrun/aman/panels_dump.pkl`.
