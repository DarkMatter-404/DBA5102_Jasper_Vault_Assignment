# Jasper Vault: unused research directions

Research date: **16 October 2026 (Singapore)**. Repository audited: team `main` at **`da91c05dc77001ee91f0f599acea2c655f373da2`**, including the newer Aman and Chris contributions. This is a research note, not a change to the locked prices or a claim of improved performance.

**Recommendation:** start with a joint demand–risk sensitivity study; then investigate marginal portfolio capital. Early-close modeling and empirical price-path scenarios are promising research extensions. Online payout monitoring is useful operationally, but overlaps an existing proposal. “Unused” below means **not implemented in the inspected work**, not an original invention or something no teammate has mentioned.

## Charter

- **Goal:** identify useful unimplemented extensions, distinguish them from existing work, connect them to primary sources, and specify a falsifiable first experiment.
- **Scope / object / subjects:** short-duration BTC protection pricing / Jasper Vault PP profitability and risk / retained-buyer selection, portfolio capital, stopping behavior, cashflow distributions, and online monitoring.
- **Type:** exploratory. The assignment and existing implementations were inspected before selecting directions; no new model was fitted.
- **Q1:** Which apparent ideas are already used, rejected, or merely proposed?
- **Q2:** Which concrete extensions address a remaining modeling assumption?
- **Q3:** What data, evaluation, and failure criterion would justify proceeding?
- **Sources:** supplied assignment materials and version-pinned team artifacts first; original author/publisher papers for methods. Search results were used for discovery, not as standalone evidence. Firecrawl returned HTTP 402; accessible primary documents were read through web fallback.

## Canonical sources

| ID | Rank and source | What it establishes |
| --- | --- | --- |
| R1 | Originating materials: [project guide][guide], [assignment brief][brief], [case statement][case] | PP objective, commercial constraints, contract/data interpretation. The conversion/scoring rule remains unspecified. |
| R2 | Direct inspection: [Maksim README][maksim], [model][model], [evaluation][evaluate] | Existing expected-move model, validation history, risk reporting and demand scenarios. |
| R3 | Direct inspection: [Aman summary][aman], [plan][plan], [code explanation][aman-code], [pricing notebook][aman-notebook] | Latest locked F1, completed extension tests, reference-error robustness, and ideas proposed but not built. |
| R4 | Direct inspection: [Chris README][chris], [skew backtest][chris-code] | Book reconstruction and imbalance-based pricing already implemented. |
| R5 | Direct inspection: [v2 findings][v2], [Subham models][subham], [Jay methodology][jay], [Jay v3.2][jay32] | Existing direct payout models, calibration experiments, news/social inputs, latency controls and research limitations. |
| P1 | Original research: [Einav, Finkelstein & Cullen, 2010][efc]; inspected full [September 2008 author draft][efc-draft], §2.3 | Exogenous price variation can identify demand and changes in the cost of selected insurance buyers. |
| P2 | Original research: [Tasche, arXiv v3, 22 June 2008][tasche], §§2–3 | Portfolio risk contributions, capital allocation and risk-sensitive pricing; finite marginal contributions differ from Euler allocation. |
| P3 | Original research: [Rockafellar & Uryasev, author manuscript 5 September 1999; published 2000][cvar], §2 | Scenario evaluation/optimization of conditional value at risk. |
| P4 | Original research: [Bauer, Kling & Russ, November 2008][bauer], ASTIN Bulletin 38(2), 621–651 | Guarantee valuation distinguishes prescribed policyholder behavior from optimal behavior. This is an annuity study, not evidence about PP buyers. |
| P5 | Original research: [Longstaff & Schwartz, 2001][ls], RFS 14(1), 113–147 | Simulation and regression of continuation values for optimal stopping. |
| P6 | Original research: [Barone-Adesi, Giannopoulos & Vosper, April 1997, revised February 1998][fhs] | Filter historical innovations by volatility, rescale to current conditions, and revalue nonlinear portfolios under scenarios. |
| P7 | Original research: [Gibbs & Candès, JMLR 25(162), May 2024][aci], §§2, 4 | Adaptive prediction sets under distribution shift; the method does not turn predictive coverage into a profit guarantee. |

All external sources were checked on 16 October 2026. Publication years above identify the method versions used; this is a bounded, project-specific review, not an exhaustive survey of the latest literature.

## Findings ledger

| ID | Evidence-backed finding | Evidence | Answers |
| --- | --- | --- | --- |
| F1 | Recent volatility, intraday seasonality, macro releases, HMM, range/volume, holidays, size/direction adjustments and hedging have already been investigated. | R2, README Appendix A and §7.1 | Q1 |
| F2 | Aman already tested funding, DVOL, jump share, kurtosis, PCE and tenor payout calibration. None was adopted; some other registered feeds were unavailable. | R3, summary “Phase 4” | Q1 |
| F3 | Inventory/flow pricing is already used by Chris; expected shortfall is already reported elsewhere. Neither is itself a new suggestion. | R4, steps 1–5; R2, `evaluate.py:33–48`; R3, risk section | Q1 |
| F4 | Existing demand scenarios multiply premiums and fixed historical payouts by the same retention weights; Aman explicitly assumes unchanged conditional payout risk. | R2, `evaluate.py:52–73`; R3, `PLAN.md:299–306` | Q2 |
| F5 | Insurance demand and selected-buyer cost can both respond to price; exogenous variation is needed to identify their relationship. | P1, author draft §2.3 | Q2–Q3 |
| F6 | Portfolio risk contributions support capital-sensitive decisions; scenario CVaR can represent correlated nonlinear losses. | P2 §§2–3; P3 §2 | Q2–Q3 |
| F7 | Maksim reports 67% of orders closing over 30 seconds before expiry, but forecasts the contractual window. Broad early-close modeling was already proposed. | R2 §1; R5, `findings.md:186`; R3, `PLAN.md:179` | Q1–Q2 |
| F8 | Behavioral stopping and optimal stopping are different modeling objects. | P4; P5 | Q2–Q3 |
| F9 | The current Maksim target is absolute log return, mapped through a normal-equivalent volatility into Black–Scholes; Aman uses a symmetric approximation. Subham already has direct payout/anchor regression. | R2, `model.py:54–64, 122–132`; R3 notebook; R5 Subham models | Q1–Q2 |
| F10 | Filtered historical simulation provides volatility-scaled empirical scenarios and nonlinear revaluation; applying it to PP cashflows would be an adaptation. | P6 | Q2–Q3 |
| F11 | Adaptive monitoring is already proposed for JV/reference-price discrepancies; an implemented payout-tail monitor was not found. | R3, `PLAN.md:569–570`, code explanation and notebook | Q1 |
| F12 | Online conformal methods adapt prediction sets; their theory does not establish conditional mean calibration or solvency. | P7 §§2, 4 | Q2–Q3 |
| F13 | Existing July and August–October results have already been inspected by parts of the team. New variants cannot reuse them as untouched holdouts. | R2 §6 and Appendix B; R3 summary; R5 methodology | Q3 |

Proposals and formulas below are **our adaptations/inferences**, not findings that those papers demonstrate gains for Jasper Vault. No new numerical results were generated.

## Scope filter

- Excluded generic HMM, news/sentiment, HAR volatility, jump-share, funding and DVOL suggestions as “unused”: the team already investigated them (F1–F2).
- Excluded generic inventory skew, daily CVaR reporting, randomized price tests and static tenor calibration as new ideas (F2–F3; R2 §5.4).
- Retained joint selection stress and marginal capital because they change assumptions beyond existing elasticity scenarios, reference-error minimax regret, fixed caps and imbalance loading.
- Rejected the blanket argument “fat tails imply our premiums are too low.” For a common stopping rule, the exact absolute **price** move already contains the tail contribution to an ATM mean payoff; see direction 4.

## Object filter

- All proposals concern the actual 0.5–24-hour PP cashflow. Annuity surrender and American-option methods provide frameworks, not transferable PP coefficients or behavioral evidence.
- Historical expected cashflow under the physical probability measure is distinct from a risk-neutral market option price. Existing labels called “fair value” do not resolve this distinction.
- No incoming order’s future `closedAt`, future price, or label unavailable at fitting time may become a quote input. A live book may use a prior contract’s close once that close has actually happened.
- Mean-price accuracy, tail-risk accuracy, demand identification and net profit are separate outcomes. Improving one does not establish the others.
- The latest F1 and submitted recommendations remain the reference versions for this research. All new evaluations require a declared protocol and genuinely new outcomes for confirmation (F13).

## Conclusions

### 1. Joint demand–risk stress: do price increases keep the riskiest buyers?

**Priority: first. Novelty: a concrete unused experiment within an already mentioned research family.**

Current elasticity tests change the number of orders while keeping conditional payouts fixed (F4). The missing question is whether buyers with private information remain willing to pay when lower-risk buyers leave. The insurance identification literature supports estimating both demand and selected cost from exogenous price changes (F5/P1). Chris’s crowd/contrarian evidence motivates investigation but does not establish causal adverse selection.

Write the commercial objective as:

`profit(p,x) = Pr(accept | p,x) × [p − E(payout | accept,p,x)] − other costs`.

**Smallest experiment:** retain the existing elasticity scenarios, then stress which original buyers remain after price increases. Within prespecified duration/risk cells, use feasible selection weights between zero and one at the assumed retention budget. Report the **break-even selected-risk uplift** that removes each strategy’s advantage over unchanged pricing and its matched flat-price comparator. With nonnegative payouts, retention fraction `q` and conditional mean-cost uplift `u`, pure thinning requires `q × (1+u) ≤ 1`; available payout support can impose a tighter limit. At 95% retention, even the theoretical maximum uplift is only 5.26%; at full retention it is zero. Larger cost stresses must be labeled behavior/exposure changes, not buyer selection. Apply the same stress construction to every policy. These are assumptions, not estimated responses. Keep price-cut/new-buyer risk separate; purchase-only data cannot identify it.

An optional adverse historical bound retains the largest-loss orders first within prespecified duration/risk groups at a fixed retention budget. Label this as a clairvoyant sensitivity bound, never a live rule. It concerns only historical buyers, not demand generated by discounts.

**What would justify proceeding:** a policy’s economic case survives the agreed demand/risk stress range; otherwise its reported gain is fragile. This is a robustness result, not proof of real demand.

**Data needed for identification:** all eligible quotes, including no purchase; exact price and assignment probability; frozen quote-time features; session/client identifier; acceptance, quantity, settlement and payout. A prespecified randomized price experiment should estimate profit and payout **per eligible quote**, as well as conversion and cost among accepted contracts. Consistent session assignment and client/time clustering help address repeated quote shopping and common BTC shocks. A/B testing itself is already proposed in the repository; the addition is joint acceptance–cost identification.

### 2. Marginal portfolio capital: charge or admit by the risk added to the whole book

**Priority: second. Novelty: unused pricing/admission mechanism; inventory pricing already exists.**

Chris’s imbalance surcharge and Maksim’s caps are important comparators (F3). Equal notional can nevertheless create different tail losses when strikes, remaining tenors and settlement times differ. Portfolio risk allocation and scenario CVaR provide a basis for assessing that increment (F6/P2–P3).

Let `L` be the remaining payout liability of the open book on shared BTC paths. Define unexpected-loss capital as `Kα(L) = ESα(L) − E[L]`, then compute `ΔK = Kα(L + new liability) − Kα(L)`. Here `ESα` is the upper-loss expected shortfall, with a definition that handles probability mass at its quantile. For scenario losses, use `min_z {z + E[(L−z)+]/(1−α)}`. Finite `ΔK` is not automatically an Euler allocation.

**Smallest experiment:** leave premiums fixed and test admission under a management-set capital budget. At each quote, value all open contracts on the **same** modest library of past-only, volatility-scaled BTC paths, accounting consistently for settlements through the longest remaining tenor. A contract-level independent simulation would erase the dependence this experiment needs. Begin with a clearly labeled hold-to-expiry approximation; it is not a guaranteed upper bound on early-exercise liabilities. Aggregate payout ES does not measure the maximum interim cash deficit: retain a separate settlement-liquidity stress.

Compare the existing cap, Chris’s loading and capital admission on identical eligible orders, matching retained premium/notional where practical. Report worst settlement day, drawdown, ES, lost premium and peak capital alongside profit. For every scenario pool, disclose how many independent time blocks populate its tail.

**What would justify proceeding:** lower tail loss at comparable business volume, with a stable benefit across chronological periods. A price loading can follow later, with an explicit opportunity cost and capital-release convention. `ΔK` changes the chosen unexpected-loss capital proxy; it is not itself a premium. Because `ES−mean` is not monotone, this increment can be negative even for a nonnegative new liability. Keep gross-liability/liquidity limits and do not automatically rebate negative contributions. Adding both expected claims and full ES would double-count expected loss. Calls and puts with different strikes/tenors are not exact offsets.

**Missing inputs:** available vault capital, collateral, hedge margin, withdrawals and settlement mechanics. Without them, this is a capital proxy, not an insolvency estimate or optimal charge.

### 3. Early-close hazard coupled to the price path

**Priority: research extension. Novelty: specific implementation unused; early-close models already proposed.**

Most PP orders close early, while the adopted model forecasts the full contractual window (F7). A fixed tenor multiplier cannot distinguish early closing at a loss from early closing after the protected move. The literature distinguishes prescribed policyholder behavior from optimal exercise (F8/P4–P5); PP users need not exercise like textbook option holders.

**Smallest experiment:** compare three versions: expiry only; an age/tenor close model; and an age/tenor model with state-dependent closing. A small regularized logistic model at five-minute decision points can estimate `h_j = Pr(close at j | still open, quote features, current path state)`. Candidate state variables are signed moneyness, elapsed fraction, remaining time and recent volatility. Treat expiry as the remaining probability mass.

Value each possible close using its survival-weighted hazard and actual intrinsic payoff. At quote time, future states must come from prospective simulated/historical scenario paths, not the contract’s realized future. Close-hazard fitting may use an unresolved contract’s already observed at-risk intervals with censoring; payout fitting requires its label to be observed before cutoff. Never turn unresolved contracts into zero payouts. Declare the simulated within-bin closing/settlement convention and check finer bins; training payouts retain their actual close timestamps.

**What would justify proceeding:** improved chronological close-time calibration **and** mean payout calibration over the expiry and age-only controls. Score these separately. A Longstaff–Schwartz optimal exercise model may provide a comparison, but must not be presented as an estimated PP user policy or automatic American-option surcharge.

**Main limits:** underlying leverage, liquidation, trade-closing motives and policy rules may be unavailable. Buyers’ closing behavior may itself change after repricing. Substituting average holding time into a square-root-time formula misses this dependence.

### 4. Empirical price-path cashflows, with an exact payoff diagnostic

**Priority: diagnostic first, distribution research second. Novelty: narrower than “use direct payout regression,” which Subham already does.**

The unused variant is a market-trained arithmetic-payoff/scenario layer sharing the existing volatility engine, rather than another order-level payout multiplier (F9). Filtered historical simulation standardizes historical innovations by their then-current volatility and rescales them to present volatility before nonlinear revaluation (F10/P6). Its application to PP mean cashflows is a proposed adaptation.

First check the algebra. For the **same stopping time**, let `D = Sτ − strike`, `a = E[|D| | information]` and `m = E[D | information]`. Then:

- `expected call payoff per BTC = (a + m) / 2`;
- `expected put payoff per BTC = (a − m) / 2`.

These identities follow directly from positive/negative parts; they require neither Gaussian returns nor Black–Scholes. With zero conditional arithmetic drift and ATM strike, a correct expected absolute price move already gives the mean payoff. Fat tails alone therefore do not justify increasing it. Do not apply the identity across different call/put-specific stopping policies.

**Smallest experiment:** preserve features and folds but replace absolute log-return targets with absolute arithmetic-return targets, using the matching arithmetic payoff map. For ATM, expiry-only, zero arithmetic drift, the expected payout per BTC is `strike × predicted E|S_T/S_0−1| / 2`; do not feed that prediction through the existing normal-volatility/Black–Scholes conversion. Keep the signed mean at zero initially; a strongly shrunk signed-mean model is a separate declared challenger. This is a diagnostic, not a claim that the existing approximation is materially wrong.

For tail analysis, construct out-of-fold standardized residual paths, rescale to current conditions, and average exact contract payoffs with positive scenario weights summing to one. Use a pooled residual library before adding sparse tenor/event cells. The same shared paths can support direction 2. For a fair distribution comparison, match expected absolute **price** change, not merely expected absolute log return, and separate scale changes from shape changes.

**What would justify proceeding:** better mean cashflow calibration or better large-loss calibration, stated separately. Preserve the same margin/floor for pricing comparisons. Historical resampling cannot create an unseen shock; add explicitly labeled stress paths rather than treating their assigned weights as observed probabilities. This produces physical-measure cashflow forecasts, not automatically market-consistent option prices.

### 5. Online payout-tail monitoring with delayed labels

**Priority: operational extension. Novelty: unimplemented and partly proposed already.**

Aman already proposes adaptive conformal alarms for actual JV prices versus the estimated reference (F11). Extend that idea to mature expected-move/payout errors, rather than claiming online monitoring is newly discovered. Gibbs & Candès’ 2024 method adapts prediction-set calibration to distribution shift; it does not guarantee conditional mean accuracy or profitable prices (F12/P7).

**Smallest experiment:** freeze the core model and replay quote, expiry and settlement events in time order. Update a monitor only after its target becomes observable. Separate fixed-horizon market-move scores from settled-order payout scores, since order closing can select which labels arrive first. Use non-overlapping windows per horizon for the first market test; dependence and delayed feedback still require explicit evaluation.

Benchmark a fixed calibration window against an adaptive quantile monitor. For a declared miscoverage target `α`, the basic adaptive update has form `α_next = α_current + γ × (α − observed_miss)`. A delayed/batched implementation is an adaptation whose theoretical guarantees must not be assumed from the immediate-feedback paper.

Report rolling coverage, band width, alarm frequency and detection delay. Monitor aggregate payout/expected-payout separately for mean calibration. Define in advance whether an alarm triggers investigation, lower exposure limits or a fallback; copying an upper prediction quantile into the premium confuses a tail reserve with an expected claim.

**What would justify proceeding:** useful alarms with acceptable false-alert frequency, evaluated prospectively. Coverage alone does not establish economic value; this may be a risk-control improvement without any price change.

## Next steps / Risks

1. **Start with direction 1.** It challenges an assumption shared by the commercial comparisons and initially needs no new model or external dataset.
2. **Develop direction 2 as a separate book-risk experiment.** Reuse Chris’s book state and compare against the existing cap before introducing capital-based price changes.
3. **Investigate directions 3–4 together only after separate baselines.** Changing the close policy, mean target, residual distribution and pricing rule simultaneously would obscure the cause of any gain.
4. **Treat direction 5 as monitoring.** It extends Aman's existing proposal and should first be evaluated without adaptive repricing.

For every experiment, declare one primary outcome, comparator, selection rule and rejection criterion before evaluation. Keep the locked F1 and Maksim recommendation files as controls. Use chronological folds and label-availability cutoffs, including the full 24-hour horizon; overlapping labels require purging and time-block uncertainty. Existing months can support retrospective diagnostics, not a new untouched holdout. A materially revised candidate needs genuinely new outcomes.

Compute requirements for the first studies are small: existing candle/order files, compact scenario pools and regularized models. No GPU, model API or large training job is needed for these initial protocols; no such computation was run for this note.

**Unresolved:** JV’s actual conversion/scoring rule; rejection/quote logs; precise close/settlement rules; capital and hedge costs; past-only timestamp evidence for matched base quotes; enough independent extreme periods. Primary papers motivate methods but cannot establish gains on the supplied 2026 PP data. Unmerged branches, external notebooks and later commits were outside the audit boundary.

Research progress: source ranking and charter complete; existing-work audit complete; primary-method review complete; scope/object filters complete. **Empirical status: proposed only.** No new fit, backtest, validation reconstruction, price recommendation or deployment was performed.

[brief]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/materials/briefs/Blockchain%20Group%20Assignment.pdf
[case]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/materials/case-study/Jasper%20Vault%20Options%20Pricing%20Optimisation.docx
[guide]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/materials/guides/project-guide.md
[maksim]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/maksim/README.md
[model]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/maksim/src/model.py
[evaluate]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/maksim/src/evaluate.py
[aman]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/aman/TEAM_SUMMARY.md
[plan]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/aman/PLAN.md
[aman-code]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/aman/CODE_EXPLANATION.md
[aman-notebook]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/aman/pp_pricing.ipynb
[chris]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/chris/README.md
[chris-code]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/chris/04_backtest_skew.py
[v2]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/revision_v2/findings.md
[subham]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/subham/pricing/models.py
[jay]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/jay/docs/methodology.md
[jay32]: https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment/blob/da91c05dc77001ee91f0f599acea2c655f373da2/jay/revision_v3_2/README.md
[efc]: https://academic.oup.com/qje/article-abstract/125/3/877/1903679
[efc-draft]: https://law.yale.edu/sites/default/files/area/workshop/leo/document/Einav_Finkelstein_Cullen_September_08.pdf
[tasche]: https://arxiv.org/html/0708.2542v3
[cvar]: https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf
[bauer]: https://www.cambridge.org/core/services/aop-cambridge-core/content/view/5EC877F9533FBC065FDD192803931211/S0515036100015312a.pdf/universal_pricing_framework_for_guaranteed_minimum_benefits_in_variable_annuities_1.pdf
[ls]: https://galton.uchicago.edu/~mykland/345A08/Longstaff.pdf
[fhs]: https://filteredhistoricalsimulation.com/downloads/paws_feb98.pdf
[aci]: https://jmlr.org/papers/volume25/22-1218/22-1218.pdf
