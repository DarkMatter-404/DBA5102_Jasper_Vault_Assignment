## Why

The first pricing challenger underperformed its calibrated recorded-premium benchmark in July. Disabling the adjustment avoided shipping that failure, but did not provide a stronger candidate for the assignment's profitability, risk and customer-price objectives.

## Changes

Add a duration-credibility candidate with a fixed, analytically derived price cap. It shrinks duration-level payout/premium experience toward the pooled estimate and makes markups or markdowns of at most 1.2906% under the default assumptions. Its stated 95% retention floor is a bound inside an assumed elasticity model, not a guarantee about real demand.

Include a train/analyze/predict CLI, reproducible research comparisons, verification script, compact reference results, presentation figures, run instructions and the revised findings/submission argument. Preserve version 1 and update the main Jay README to distinguish it from the new candidate.

The comparisons cover seven EN cost specifications, nine matched API/paid/blended specifications, four shallow-tree challengers, and commercial alternatives including uniform-price comparators and unchanged pricing. All nonzero API cost-plus policies failed the stated development constraints.

## Results and limits

On the same 2,625 July EN orders, assumed elasticity 4 gives candidate gross margin of 4,542.88 versus 4,042.04 USDC for recorded prices, with 98.28% assumed retention and a 0.542% aggregate quoted-premium increase. However, the candidate's 25.53 USDC advantage over an equal-premium uniform change has a conditional interval spanning zero. April and May margins decline slightly, and July cost RMSE is 135.8428 versus 135.0931 for the calibrated reference.

July was already inspected before this revision. Results are retrospective and depend on assumed demand and unchanged conditional payouts. The recorded premium is not a verified API base quote. This is a candidate for separate blind evaluation, not a proven production improvement.

## Validation

- Ran the main analysis and all eight research stages from the repository paths.
- Passed ten verification groups covering input hashes, label cutoffs, outcome-free inference, future-market removal, invalid inputs, serialization, historical inference flags, analytic bounds and result reproduction.
- Generated and visually checked three presentation figures.
- Kept raw data, row-level regenerated outputs and environment files out of this contribution.

## Remaining assignment work

Use the new findings and figures to update the earlier version-1 presentation. Obtain the missing blind order file, complete its market coverage, confirm quote/base semantics and apply Jasper's actual conversion/scoring rule before claiming superiority or producing final blind recommendations.
