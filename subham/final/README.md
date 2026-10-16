# Final PP pricing solution (team)

This folder holds the team's final pricing solution. The rest of `subham/` is my earlier hybrid experiment.

The core is Maksim's model: `premium = quantity × fair value × 1.25`, never below the API base price.
The improvement is Chris's order-flow loading. This section was committed **before** any scoring of the loading on
the model's prices. The commit hash of this file is the proof.

## Adoption rule for the order-flow loading

**Panel.** `maksim/results/walk_forward_orders_priced.parquet`: 7,150 training orders, February to July 2026. Each
month is priced by Maksim's model fitted on earlier data only (`model_premium_USDC`). `row_id` is the row number in
`data/with_base_premium/pp_transactions_training.csv`.

**Strategies.**

| Name | Premium |
|---|---|
| M | Maksim's walk-forward premium |
| M+L | M × loading |
| Flat-M | M × f, with f set so that the total of Flat-M equals the total of M+L in the same period |

- Loading = 1 + 0.3 × max(−s_add, 0) when the open book holds at least 1 BTC, else 1.
- Open book at time t = earlier orders (`createdAt` < t) with `expirationDate` > t. `closedAt` is never used.
- imb = (open call BTC − open put BTC) ÷ (open call BTC + open put BTC). s_add = imb for a call, −imb for a put.
- k = 0.3 and the 1-BTC threshold are fixed in advance (Chris, chosen on February to June). No other value is tried.

**Demand rules.** The reference price A is JV's actual premium. "None": every order is kept.
"Conservative e = 2": an order is kept with weight min((P ÷ A)^−2, 1), so price rises lose orders and price cuts win none.

**Decision.** M+L becomes the main column only if all three conditions hold:

1. July 2026: profit(M+L) − profit(M) > 0 under "none" and under "conservative e = 2".
2. February to June 2026: the same two conditions.
3. July 2026: profit(M+L) ≥ profit(Flat-M) under "conservative e = 2". This shows better allocation, not only a
   higher price level.

If any condition fails, Maksim's frozen premium stays the main column, and M+L becomes an optional column.

Note: the loading never decreases a premium, so the "none" part of conditions 1 and 2 always holds. The informative
tests are "conservative e = 2" and condition 3. The report shows every other demand rule too, including any rule
where the loading loses. Those rules do not change the decision.
