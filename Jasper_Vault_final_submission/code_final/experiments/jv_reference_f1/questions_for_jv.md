# Questions for Jasper Vault — DRAFT, not sent

Drafted 15 Oct 2026 for the team regroup. Only the team decides whether, when and how to send these.

## The four we most need answered

**(a) What should we submit for each blind order: a premium, a multiplier, or both? Which columns, in what order?**
The blind file has no order ID, so we plan to keep its row order and repeat `createdAt, optionType, productType,
quantity_BTC, strikePrice` next to our answer. 2,195 of the 4,155 orders have no base price, so a multiplier on the
base cannot be defined for them. Is a premium in USDC acceptable for those rows?

**(b) Are all 4,155 orders scored, or only the 1,898 orders from 31 July to 24 August described in the dataset guide?**
The file we received runs to 14 October 2026.

**(c) What form does the conversion constraint take?**
For example: an order is kept only if our premium is at most some multiple of your current premium; or the chance of
purchase falls with a price elasticity; or something else. Is it applied per order, and against your actual price, the
base price, or another reference?

**(d) Is the filled `closedAt` column in the blind file intended?**
We treat it as an outcome (when the protection ended) and never use it as an input.

## Useful, if there is a chance to ask

**(e)** The guide says orders priced below the base (negative markup) were removed from the data. Was the same filter
applied to the blind file? We cannot check it where the base is missing.

**(f)** For the 544 blind orders that show a markup, is the price you charged equal to
`quantity_BTC x (apiBasePrice_per_BTC_USDC + markup_per_BTC_USDC)`, in USDC?
