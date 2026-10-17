# Jasper Vault PP: revised pricing model and submission argument

Research date: 13 October 2026. Status: a reproducible research candidate for the assignment, not a proven production replacement.

## Recommendation

Use **duration credibility with a small, analytically bounded price adjustment** as the next candidate for blind evaluation. Keep the existing premium as the reference, estimate which contract durations have higher or lower payout-to-premium experience, shrink uncertain group estimates toward the portfolio average, and limit the resulting markup or markdown.

This improves the original proposal's commercial design and makes the limits explicit. It does **not** establish that we have found a model that reliably beats Jasper. July's simulated margin improves, but April and May decrease slightly, July cost prediction remains slightly worse than the calibrated reference, and the gain over equally sized uniform price increases is uncertain.

The assignment asks for sustainable returns, controlled risk and attractive prices, rather than the most complex forecast. The revised work therefore evaluates prices and assumed acceptance together, includes markdowns, checks large loss cohorts, and compares differentiation against a uniform change. It preserves the failed first model as evidence rather than hiding it.

## What changed after the first model failed

The original option-anchor/state model had July payout RMSE of **144.82 USDC**, versus **135.09** for the calibrated recorded-premium benchmark. Its full adjustment also hurt commercial results, so its default adjustment was disabled.

The revision changes five things:

1. Preserve information in the existing premium, rather than replacing it with the first option-shaped anchor.
2. Use coarse duration groups with shrinkage. Persistent direction effects and richer market-state/tree effects did not justify their added complexity in the tested family.
3. Separate expected payout from the pricing decision. A more accurate cost estimate does not automatically produce a better price.
4. Derive a per-quote price limit from an explicit retention scenario. A rule that satisfied average retention in development failed when July's duration mix changed.
5. Compare against uniform policies with the same aggregate quoted premium and the same assumed order retention. This exposes gains caused mainly by charging more.

## Model specification

For order i, let B_i be the recorded premium and Y_i the gross payout. Per the class notes, the supplied contracts are ATM; the target is gross payout, not net profit. Actual early closure is an outcome, so future holding time and settlement information never become quote-time predictors. Binance-versus-platform price differences are not treated as observed moneyness.

Only labels from orders both created and settled before the fit cutoff enter training. Define the pooled ratio and a prior premium exposure:

$$r_0=\frac{\sum_i Y_i}{\sum_i B_i},\qquad h=200\,\overline B_{train}.$$

For duration group g, shrink its experience toward the pooled ratio:

$$\widetilde r_g=\frac{\sum_{i\in g}Y_i+h r_0}{\sum_{i\in g}B_i+h},\qquad \widehat C_i=B_i\widetilde r_{g(i)}.$$

The prior has the premium exposure of 200 average training orders. This is credibility-inspired exposure shrinkage, not a fitted exact Bühlmann–Straub posterior. The 200-order specification was selected from the seven-model EN family using April–June rolling-origin scores. An unsupported duration uses the pooled ratio internally; the quote contract validator accepts only the seven supplied product durations.

Translate relative cost into a raw adjustment:

$$M_i^{raw}=\operatorname{clip}\!\left(c\sqrt{\widetilde r_{g(i)}/r_0},\;0.85,\;1.15\right).$$

The positive constant c makes total quoted premium unchanged **on the settled training sample**. It is frozen for later quotes. Future premium totals can change when the contract mix changes; the July results disclose that drift.

For commercial sensitivity, assume:

$$q_e(M)=\min(1,M^{-e}),\qquad 0\leq e\leq4.$$

This represents retention among historical buyers after a price change. Discounts introduce no extra buyers, and retained buyers' conditional payouts are held fixed. These are assumptions, not estimated demand or a correction for adverse selection.

Propose a 95% minimum per-quote retention **inside that scenario**, then derive the blend weight:

$$w=\min\!\left(1,\frac{0.95^{-1/4}-1}{1.15-1}\right)=0.0860393.$$

The final quote is:

$$P_i=B_i\left[1+w(M_i^{raw}-1)\right].$$

Consequently, the final multiplier lies between **0.987094 and 1.012906**, or at most **±1.2906%**. At its upper bound, assumed retention is exactly 95% when e=4; lower elasticities or smaller increases retain more. The bound holds regardless of a future change in duration mix **within this demand formula**. It is not a guarantee about real customers, profit or solvency. Both 95% and e=4 are proposed design assumptions, not Jasper's undisclosed scoring rules. The cap was designed after inspecting July diagnostics; an algebraic rule does not turn July into a fresh test.

The pre-July fit gives these adjustments:

| Duration | Final price change |
| --- | ---: |
| 30 minutes | −1.2906% |
| 1 hour | +0.4929% |
| 2 hours | +0.0030% |
| 4 hours | +0.7160% |
| 8 hours | +1.2906% |
| 12 hours | +0.0877% |
| 24 hours | −0.1184% |

These are that fit's coefficients, not timeless rules for duration risk. Refitting changes the table while preserving the analytic cap.

## Evidence on the original EN sample

The source contains 7,831 orders; the common audit retains 7,603 labelled observations. The July comparison contains 2,625 orders. A calibrated recorded-premium **cost benchmark** multiplies premium by the prior training payout/premium ratio; the **commercial benchmark** uses the actual recorded premium. They serve different purposes.

At assumed elasticity 4:

| July pricing policy | Scenario gross margin, USDC | Assumed mean order retention | Aggregate quoted-premium change |
| --- | ---: | ---: | ---: |
| Recorded premium | 4,042.04 | 100.00% | 0.000% |
| Revised duration model | **4,542.88** | **98.28%** | **+0.542%** |
| Uniform: same aggregate quoted premium | 4,517.34 | 97.86% | +0.542% |
| Uniform: same mean order retention | 4,423.82 | 98.28% | +0.434% |

Gross margin is premium minus gross payout, before fees, funding, hedging, operating and capital costs. Scenario margin is `sum(q_i * (P_i - Y_i))`; it is an expected value under assumed thinning, not actual realized trading performance. **32.95%** of July orders receive discounts. The margin gain versus recorded prices is **500.84 USDC, or 12.39%**; the percentage uses a relatively small baseline margin and should be presented with the dollar amount.

The same-premium uniform comparator uses the evaluation cohort's total candidate premium divided by its recorded total. The same-retention comparator chooses a uniform multiplier that gives the candidate's mean assumed retention. Neither uses payout values to set its price, but both use the evaluation cohort's quote mix. They are diagnostic accounting comparators, not policies frozen before sequential quote arrival. The deployable training-premium-neutral uniform comparator is 1.0, already included as recorded pricing.

Two thousand paired resamples of UTC order-creation days give these **conditional** July intervals:

| Candidate margin difference versus | Point estimate, USDC | Conditional 95% interval, USDC |
| --- | ---: | ---: |
| Recorded premium | +500.84 | +16.86 to +1,014.84 |
| Same-premium uniform | +25.53 | −145.64 to +185.77 |
| Same-retention uniform | +119.05 | −83.88 to +318.95 |

These intervals condition on the fitted model, assumed demand and fixed diagnostic uniform quotes. They do not include model-selection uncertainty, unknown real demand, changing buyer risk mix, or full dependence across adjacent days. They are not evidence of a causal or fresh out-of-sample pricing advantage. In particular, the uniform-comparator intervals include zero.

The month-by-month results prevent a July-only success story:

| Month | Evaluated orders | Recorded margin | Candidate scenario margin, e=4 | Difference, USDC |
| --- | ---: | ---: | ---: | ---: |
| April | 984 | 2,796.49 | 2,775.32 | −21.17 |
| May | 1,046 | 4,745.69 | 4,701.35 | −44.34 |
| June | 2,322 | 6,128.43 | 6,381.22 | +252.79 |
| July, retrospective | 2,625 | 4,042.04 | 4,542.88 | +500.84 |

July candidate margin is 4,616.16 / 4,597.25 / 4,578.73 / 4,542.88 USDC for assumed elasticities 0 / 1 / 2 / 4. At e=0, all gain comes from the disclosed increase in total premium. With unchanged fills and equal aggregate premiums, repricing alone cannot increase total gross margin.

The July worst creation-cohort margin improves from **−5,056.73 to −4,911.66 USDC**. The mean of the worst 20% of creation cohorts improves from **−2,538.91 to −2,456.00**, using a fractional boundary-day weight. These are modest scenario reductions in cohort losses, not a full portfolio capital model, settlement cashflow test or hedge backtest.

Cost accuracy remains a limitation:

| July expected-payout model | RMSE, USDC |
| --- | ---: |
| Calibrated recorded-premium reference | **135.0931** |
| Revised duration credibility | 135.8428 |
| Original selected option-anchor/state model | 144.8236 |

The revised predictor is 0.56% worse than the cost reference on July RMSE. Across April–June, its average relative deviance is 1.49% lower and average relative RMSE is 0.94% lower. July aggregate predicted/actual payouts are 1.0682 for the candidate and 0.9535 for the calibrated reference. We cannot claim improved July forecasting or stable calibration across all months.

## Alternatives tested and why they were not recommended

Twenty declared cost specifications were examined across three families: seven on the original EN data, nine using paid/API/blended anchors on the matched enriched sample, and four shallow boosted-tree challengers on that matched sample. Reference specifications are included in the count. Selection scores use only April–June outcomes; all revised July analysis is retrospective because July was already examined during version 1.

| Alternative | Result and decision |
| --- | --- |
| EN pooled, 60-day exponentially decayed calibration, two duration priors, and three strongly shrunk market-state variants | Duration with a 200-order prior won the stated development rule. Avoid a persistent direction coefficient given its observed instability. |
| Full duration adjustment, raw ±15% cap | July e=4 margin 7,572.26 but assumed retention only about 84.3%. A uniform policy with the same quoted-premium total produced still higher margin with lower retention. Too aggressive for the proposed commercial design. |
| Blend grid: 0, 0.25, 0.5, 1 | Weight 0.5 met each development month's 95% average-retention constraint and was selected, but July retention fell to 91.09%. Do not choose a different weight because its July result looks better. This motivated an analytic quote-level bound. |
| Daily batch premium neutrality | July e=4 margin 3,895.78, below 4,042.04. Also requires the full day's future quote mix, so it is an explanatory allocation, not a live sequential quote engine. |
| Nine API/paid/blended cost specifications | API anchor with a 200-order duration prior won development deviance on the matched sample. July RMSE 136.8639 versus 137.3101 for its matched calibrated-paid reference: a small cost improvement, not a proven pricing win. |
| Four shallow gradient-boosting specifications | All failed the mean development-RMSE eligibility condition. Added flexibility did not justify replacing the simpler model. |
| API cost-plus grid: three target loss ratios × three nonzero adjustment weights | All nine nonzero policies failed the stated development constraints. Unchanged pricing was selected. Do not present the slight API cost gain as successful profit optimization. |

The research runner preserves the full score tables and failed policies. This is a limited comparison, not a search over every possible model and not a guarantee that duration credibility is globally optimal.

## API-base dataset: separate, important limitations

The enriched release has **7,204 orders**, versus 7,831 in EN. Its guide reports removal of **627 negative residual-markup rows**, while **1,131 orders have no matched API base**. The common audit yields 7,011 valid labels, of which **5,887** also have a positive matched base; **2,539** of those are in July.

We calculate the order-sized API amount as `quantity_BTC × apiBasePrice_per_BTC_USDC`. The dictionary describes a matched 0DTE quote and warns that the residual can reflect PP conversion, moneyness, subsidy or other execution differences. Thus the difference from paid premium is not necessarily a configurable platform markup.

The guide says enriched fields are observable at order creation, but its matching rule uses the **nearest quote within ±120 seconds**. Individual matched timestamps are not supplied, so past-only availability cannot be independently verified. Treat the API experiment as conditional on those semantics; obtain the quote timestamp and PP conversion rule before live use.

On the same 2,539 July rows, paid premium totals 105,667.70 USDC, raw order-sized API amounts total 70,724.68, and payouts total 101,779.71. The resulting accounting margins are +3,887.99 and −31,055.03 respectively. These numbers do not prove Jasper's actual internal model loses that amount: the raw matched API amount may omit the PP conversion and other components. They do show why silently equating raw API base with the final commercial PP price would be misleading.

The recommended EN model still uses a recorded-premium proxy. Do not report its multiplier as an API-base multiplier. If Jasper evaluates against its verified internal base, either submit the absolute premium in the accepted schema or implement an explicitly verified conversion first.

## Evaluation and implementation controls

April, May and June are expanding-window development folds. Training includes only orders created **and settled** before each monthly cutoff; development scoring includes only orders settled before the next cutoff. Training counts are 619, 1,603 and 2,650. The frozen July fit has 4,975 labels and scores the same 2,625 eventually labelled July observations as version 1. July outcomes include settlements through August 1. No test payout is used to fit its model, normalizer or quote.

Market features join only candles completed by creation time. The shared audit requires fresh market coverage and a nominal-duration discrepancy of no more than 120 seconds. Although the final price uses only premium and duration, retaining this audit preserves comparability across the tested families. Stale/ambiguous rows are explicitly marked rather than silently counted as supported quotes.

The verification script checks input hashes; absence of outcome dependence at inference; exclusion of not-yet-settled labels; future-candle removal; UTC cutoff equivalence; serialization; price bounds under extreme duration estimates; invalid-contract handling; row preservation; and reference-result reproduction. Predictions made with a model containing later labels are labelled historical diagnostics.

The same specification is refitted through **31 July 2026, 17:11:48 UTC** using 7,585 labels. Eighteen otherwise eligible labels are not yet settled at that cutoff. This pre-blind research artifact has no performance estimate of its own. The separate validation order CSV is not present, and the available candle history ends about 7 hours 22 minutes before the documented end of validation.

## Proposed assignment submission

Submit the executable v2 pricing model, reproducible comparisons and an honest presentation of the conditional result. Keep unchanged pricing as the control. Freeze the candidate before receiving the partner's final outcomes; apply the actual conversion/scoring rule when it is supplied. Do not call this production-ready or claim verified superior pricing.

For a single ten-minute deck, use this sequence:

| Slide | Main message | Time |
| --- | --- | ---: |
| 1 | Better pricing must balance margin, risk and willingness to buy | 0:40 |
| 2 | Data, payout definition, ATM scope and chronological evaluation | 1:00 |
| 3 | Why the first model failed and what we changed | 0:50 |
| 4 | Duration credibility: retain the reference and shrink noisy groups | 1:10 |
| 5 | Pricing rule: a small markup/markdown with an explicit scenario cap | 1:10 |
| 6 | July commercial results alongside both uniform comparators | 1:20 |
| 7 | Monthly losses, forecast accuracy and uncertainty | 1:10 |
| 8 | API-base and boosted-tree alternatives: what did not work | 0:50 |
| 9 | Quote workflow, safeguards and blind submission format | 0:50 |
| 10 | Decision: test the frozen candidate; what remains unproven | 1:00 |

Total: 10 minutes. Use the regenerated figures under `jay/output/v2/figures/`. The earlier PowerPoint describes version 1 and should not be presented as evidence for this revised model.

The defensible takeaway is: **“We replaced an unstable proposal with a small, interpretable duration adjustment and explicit commercial limits. Retrospective margin improves under stated assumptions, while superiority over simple uniform pricing and unseen-data performance remain to be established.”**

The highest-value next information is Jasper's actual conversion rule, verified quote-time base prices, accepted/rejected quote logs, and settlement/hedging/capital costs. With those, estimate demand and changing buyer risk, then optimize an explicit net-profit objective subject to retention and portfolio-exposure limits. Additional research areas include local calibration checks, early-close payout models using only quote-time predictors, and inventory-aware controls once open-book exposure is available. These are proposed next experiments, not components already validated here.

## Method references

The assignment PDF, Jasper Vault options brief, `jay/docs/classnotes.md`, and both supplied dataset guides/dictionaries define this study's scope and field interpretation. External sources motivate methods; they do not validate our numerical performance:

- Society of Actuaries, [Credibility Methods for Life, Health and Pensions](https://www.soa.org/globalassets/assets/files/resources/tables-calcs-tools/credibility-methods-life-health-pensions.pdf): blending experience with broader information under stated assumptions.
- Denuit, Charpentier and Trufin, [Autocalibration and Tweedie-dominance for Insurance Pricing with Machine Learning](https://arxiv.org/abs/2103.03635): checking local as well as aggregate calibration.
- Scikit-learn, [HistGradientBoostingRegressor documentation](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html): implementation reference for the four rejected tree challengers; reproducible code pins version 1.8.0.

All reported results can be regenerated from the repository CSVs. No external market series or online demand estimates were added to the empirical study.
