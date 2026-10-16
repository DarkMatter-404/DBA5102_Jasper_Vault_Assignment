# Lecture slides relevant to Option 2

The nine slides from the Capstone blockchain lectures that bear on the Jasper Vault assignment,
summarised in our own words. **The slides themselves are not stored here because this
repository is public** — open Lectures 6 and 7 on Canvas to see them.

| # | Source | Slide title | Why it matters for us |
| ---: | --- | --- | --- |
| 1 | Lecture 7, slide 29 | Why short-dated perpetual protection (PP) is hard to price | Lists the risk drivers the lecturer expects us to address: volatility clustering (calm and turbulent periods differ), jumps and fat tails, **duration and strike distance interact**, near-strike exposure changes fast. Also warns that path matters and coarse candles can miss a trigger |
| 2 | Lecture 7, slide 30 | **Optimize profit with a purchase constraint** | The lecturer's own objective: choose price P to maximise **a(P,x) × [P − μ(x) − c(x)]** (a = purchase probability, μ = expected payout, c = cost per sale), using JV's evaluation constraint. Example with 100 quotes, expected payout $60 and cost $5: P=$80 at 80% conversion → $1,200; **P=$100 at 50% → $1,750**; P=$140 at 10% → $750. *"Historical purchases alone cannot identify how demand responds to new prices."* |
| 3 | Lecture 7, slide 28 | Popular derivatives in DeFi | Perpetual futures vs dated futures vs options — one-line background for the deck |
| 4 | Lecture 7, slide 8 | A DeFi risk assessment | Risk table: collateral/oracle risk → buffers, caps, stress testing; contract risk → exposure limits. *"The core of finance is risk management."* Use for the risk-limits part of the evaluation |
| 5 | Lecture 7, slide 12 | Key building blocks of DeFi | Defines oracles (e.g. Chainlink) — how a pricing model gets the BTC price on-chain |
| 6 | Lecture 7, slide 23 | Discussion: design a DeFi bank | The questions to answer for deployment: what if the oracle stops updating? what if the price falls 30% in 10 minutes? who can change risk parameters? |
| 7 | Lecture 6, slide 12 | What belongs on-chain vs off-chain? | Analytics and market data stay off-chain; bring prices in through an oracle. Our model runs off-chain and publishes a quote |
| 8 | Lecture 6, slide 14 | The oracle problem | Data quality, update frequency and fallback behaviour become part of the security model |
| 9 | Lecture 6, slide 15 | A practical dApp design checklist | Eight design questions; *"Best dApp architecture is usually the minimum blockchain necessary."* Good structure for one deployment slide |

Slide numbers are the numbers printed on the slides. In some decks they differ from the PDF page
number (e.g. the purchase-constraint slide is printed 30 but is PDF page 29 of Lecture 7).

**Not included:** Lecture 3 only announces the 10 September Q&A with Jeremy Chen (Jasper Vault
CEO); no recording or notes from that session are in the course folder.
