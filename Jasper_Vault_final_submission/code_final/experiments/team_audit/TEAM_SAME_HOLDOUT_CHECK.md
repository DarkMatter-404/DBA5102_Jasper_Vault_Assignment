# Same-holdout check of the team's models (chris, 16 Oct)

Every team model scored on the **same orders** with the **same demand rules**, from Aman's per-order panels
(`aman/pp_pricing.ipynb`, re-run unchanged on 16 Oct; `panels` dumped after execution) plus chris's book layer
(`chris/01_build_book.py`). Prices: C0 = JV's actual price, F1 = the locked model, M = Maksim, S = Subham.
Demand rules follow Aman's definitions; "cons e=2" is his central scenario. Training months only; the blind file is not
touched. Reproduce: `python chris/holdout_all.py` after running Aman's notebook with the dump cell appended
(see the script header).

## July 2026 (2,573 orders, JV premium 107,864, payouts 103,668; retrospective for everyone)

| Policy | Price / JV | Orders cheaper | No demand | cons e=1 | cons e=2 | keep if ≤1.10× | keep if ≤1.25× | Worst day (e=2) | LR (e=2) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 JV actual price | 1.000 | 0% | 4,196 | 4,196 | 4,196 | 4,196 | 4,196 | -5,073 | 0.96 |
| **F1 locked** | **0.995** | **78%** | **3,622** | **2,219** | **1,272** | **-3,479** | **-307** | **-4,938** | **0.99** |
| M Maksim | 1.205 | 66% | 26,358 | 19,361 | 14,953 | 6,519 | 8,150 | -2,687 | 0.82 |
| S Subham | 1.128 | 40% | 17,988 | 16,022 | 14,430 | 4,524 | 18,595 | -3,136 | 0.84 |
| F1 + contrarian loading (k = 0.3) | 1.034 | 76% | 7,815 | 5,681 | 4,365 | -98 | 3,796 | -4,927 | 0.95 |
| F1 × 1.08 (reference-bias correction) | 1.074 | 71% | 12,205 | 9,525 | 7,729 | 4,964 | 3,569 | -3,917 | 0.91 |
| F1 × 1.08 + contrarian loading | 1.116 | 69% | 16,733 | 12,857 | 10,413 | 6,709 | 5,665 | -3,914 | 0.88 |
| max(F1, min(M, 1.25 × JV)) — level guard | 1.122 | 65% | 17,342 | 14,735 | 12,797 | 6,912 | 12,532 | -2,714 | 0.85 |
| Blend √(M·S) clipped [0.85, 1.4] + loading | 1.196 | 57% | 25,286 | 21,433 | 18,611 | 9,349 | 17,261 | -2,423 | 0.79 |
| Flat × 1.08 | 1.080 | 0% | 12,825 | 11,875 | 10,996 | 12,825 | 12,825 | -3,944 | 0.89 |

## May + June 2026 (3,243 orders, JV premium 127,537, payouts 117,349; Aman's development months)

| Policy | Price / JV | No demand | cons e=1 | cons e=2 | keep if ≤1.10× | keep if ≤1.25× | Worst day (e=2) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 JV actual price | 1.000 | 10,188 | 10,188 | 10,188 | 10,188 | 10,188 | -9,630 |
| F1 locked | 1.046 | 15,994 | 16,251 | 16,315 | 14,237 | 21,441 | -4,228 |
| M Maksim | 1.168 | 31,610 | 26,522 | 22,956 | 12,270 | 17,945 | -2,504 |
| S Subham | 1.178 | 32,888 | 25,198 | 20,376 | 13,329 | 11,395 | -5,816 |
| F1 + contrarian loading | 1.069 | 19,026 | 18,726 | 18,424 | 15,989 | 22,219 | -4,198 |
| F1 × 1.08 | 1.129 | 26,662 | 24,579 | 22,958 | 15,636 | 24,134 | -3,383 |
| F1 × 1.08 + contrarian loading | 1.155 | 29,936 | 26,968 | 24,821 | 17,193 | 24,367 | -3,369 |
| max(F1, min(M, 1.25 × JV)) | 1.115 | 24,890 | 23,523 | 22,294 | 14,881 | 29,712 | -4,064 |
| Blend √(M·S) clipped [0.85, 1.4] + loading | 1.165 | 31,281 | 28,994 | 27,134 | 20,398 | 26,246 | -4,387 |

## What this says

1. **F1 as locked is below JV's own price in July under every demand rule**, including no demand response
   (3,622 vs 4,196), and loses money under the threshold rules. Aman's summary reports the same fact as
   "July vs C0 −2,883 [−6,830, +1,081]". The reason is the level, not the shape: F1's reference R0 ran 12% below JV
   in July (Aman's audit) and 7.6% below JV's revealed prices on the 544 August rows, and the 0.8–1.2 band then cuts
   prices in exactly the segments where JV earns its margin (30-minute orders 0.83× JV, 00–07 and 17–23 UTC
   0.77–0.79× JV; JV's loss ratios there were 0.64–0.85).
2. **A level correction of about +8% repairs it under every rule.** This is a bias correction toward JV's actual
   price, not a price increase over JV; the evidence for it (July audit −12.4%, level frontier peaking at
   theta_level +0.05 under "keep if not dearer") was in Aman's tables before the lock. The 544-row bias measured after
   the lock agrees but is not needed.
3. **The contrarian loading on the crowded-book signal adds 2,000–3,000 USDC per month on top of any model** under
   every rule, including F1, and never cuts a price (chris/README.md).
4. The most robust single candidates across rules are the **level guard** (F1, lifted to Maksim's price where that is
   at most 25% above JV) and the **clipped blend**; both beat JV under all six rules in both periods.
5. Nothing here changes the risk conclusion: July's worst day is −2,400 to −5,000 for every policy; the exposure cap
   on the crowded side (Maksim's rule, Aman's section 13, chris's crowd-right-day table) is still the only tool for it.

## Suggested decision for the team

Keep F1's shape and protocol, but re-lock the level: theta_level = +0.08 (or equivalently calibrate R0's level to the
July audit), add the contrarian loading as a documented layer, and present the exposure cap as part of the
recommendation rather than report-only. If the team prefers not to reopen the lock, the deck must say plainly that
F1 is a ranking model priced at JV's level minus the reference bias, with no expected profit gain in a month like July.

## Corrections after the independent audit (16 Oct, `chris/audit/AUDIT_MEMO.md`)

1. The two rows labelled "level guard" and "clipped blend" above use **JV's actual price** inside the cap/clip. That
   price is unknown on 3,611 of the 4,155 blind rows, so they are not submittable policies. The deployable versions
   (cap/clip on the estimated reference R0) are weaker: M capped at 1.4·R0 + loading gives July 21,158 / 13,735 / 7,366 /
   8,647 (none / e=2 / ≤1.10 / ≤1.25); √(M·S) clipped to R0 gives 13,014 / 10,818 / 6,111 / 11,530 (`chris/audit/combos_scores.csv`).
2. "+8% repairs F1 under every rule" is directional: under the threshold rules the day-bootstrap intervals include zero
   (F1 × 1.10, keep ≤1.10, July: +1,742 [−10,307, +14,970]). Say "removes the July deficit", not "proven gain".
3. The contrarian loading in `chris/01_build_book.py` builds the book from earlier orders' actual close times. JV has
   that information live, but on the blind file `closedAt` is the leaked outcome column. The audit verified the signal
   with a book built from **expiry dates only** (strongly joins LR 0.56 vs strongly opposes 1.16; by month joins
   0.70 / 0.75 / 0.58 vs opposes 0.98 / 1.16 / 1.11), and the loading on that book adds +3.3–3.8k per period with no
   demand response and +1.6k under e=2 on top of Maksim's prices. Use the expiry-proxy book for anything applied to the
   blind file (`chris/audit/book_proxy_check.py`, `combos.py`).
4. The audit's ranked recommendation differs from mine in degree, not direction: submit Maksim's frozen file as the main
   scored price (pre-registered, sealed-checked, 0.957× JV's revealed August price while JV itself moved to 1.53× base),
   with the exposure cap and the loading as layers; F1 × 1.10 + loading as the fallback; never F1 at theta = 0.
