# DBA5106 Jasper Vault Assignment

Team repository for the NUS MSBA Capstone **Blockchain Group Assignment, Option 2: Options Pricing Model**, using the Jasper Vault Perpetual Protect case study.

**Final submission:** [`Jasper_Vault_final_submission/`](Jasper_Vault_final_submission/) holds the deck, the video and [`code_final/`](Jasper_Vault_final_submission/code_final/): all team code, one folder per idea, with the final solution in `code_final/main/`. Start with [`code_final/README.md`](Jasper_Vault_final_submission/code_final/README.md).

**Submission deadline: 18 October 2026, 11:59 p.m., via Canvas.** The assignment brief says the submission folder closes automatically. The time above is reproduced as written in the brief; check the Canvas assignment for the displayed timezone and any updates.

## Project objective

Develop a pricing approach for Jasper Vault's **Perpetual Protect (PP)** that improves profitability while controlling risk and keeping protection attractive to users. PP is a short-duration hedge for perpetual futures positions: long positions are protected against price declines, and short positions against price increases. Users pay an upfront premium, and Jasper Vault pays out when the protection conditions are triggered.

The case permits either of these approaches:

1. **Adjust the existing base price:** recommend a dynamic pricing multiplier, so that `Final Premium = Base Premium × Pricing Multiplier`.
2. **Build an independent model:** directly estimate an appropriate PP premium using statistical, quantitative, option-pricing, or machine-learning methods.

Simply raising every price is not a valid solution. The case calls for a balance between risk, premium, users' willingness to purchase, and overall profitability. Jasper Vault will evaluate recommendations using a simplified pricing/conversion constraint and unseen outcomes. Its exact scoring and conversion formula is not specified in the supplied materials.

## Assignment requirements

The [assignment brief](materials/briefs/Blockchain%20Group%20Assignment.pdf), page 2, lists these deliverables:

- [ ] PowerPoint presentation deck
- [ ] 10-minute presentation video
- [ ] Code
- [ ] Any additional supporting material
- [ ] Submit the final package on Canvas before the deadline

Evaluation considers long-term, stable, sustainable positive returns within controlled risk limits, commercially attractive PP pricing, and presentation quality. The brief allows teams of 4–6 and requires everyone to contribute. The six member folders below provide individual working areas; task ownership can be agreed by the team.

## Team

| Member | Workspace |
| --- | --- |
| Maksim | [maksim/](maksim/) |
| Subham | [subham/](subham/) |
| Aman | [aman/](aman/) |
| Chris | [chris/](chris/) |
| Keerthi | [keerthi/](keerthi/) |
| Jay | [jay/](jay/) |

## Repository layout

```text
DBA5106_Jasper_Vault_Assignment/
├── README.md
├── data/
│   ├── README.md
│   ├── with_base_premium/       # Training release with API base prices and markup fields
│   ├── validation/              # Blind validation orders + BTC candles to 14 Oct
│   └── en/                      # Original English release
├── materials/
│   ├── README.md
│   ├── SHA256SUMS.txt           # Checksums for supplied files and extracted data
│   ├── guides/                 # Team project guide — start here
│   ├── briefs/                 # Blockchain group assignment PDF
│   ├── case-study/             # Jasper Vault problem statement DOCX
│   ├── lectures/               # Summary of Option 2 slides from Blockchain Lectures 6–7
│   ├── archives/               # All three original dataset ZIPs
│   └── workshop/               # Coding with AI Copilot handout
├── maksim/
├── subham/
├── aman/
├── chris/
├── keerthi/
└── jay/
```

## Data and source materials

Start with the [Jasper Vault case statement](materials/case-study/Jasper%20Vault%20Options%20Pricing%20Optimisation.docx) and the [data inventory](data/README.md). The [materials index](materials/README.md) links every supplied document and archive.

| Dataset release | Training orders | Order columns | Notes |
| --- | ---: | ---: | --- |
| [With base premium](data/with_base_premium/) | 7,204 | 13 | Includes per-BTC order price, API base price, and effective markup; suitable for investigating base-price adjustments |
| [Original EN](data/en/) | 7,831 | 10 | Original order fields, retained for reference and comparisons |
| [Validation](data/validation/) | 4,155 *(blind)* | 13 | Same columns; premium and payout blank; BTC candles to 14 Oct 2026 (412,080 rows) |

Both training releases include the same **338,917 one-minute BTCUSDC market candles**, plus a data dictionary, dataset guide, and metadata. Training orders span **2 February–31 July 2026 (UTC)**. The base-premium release removes 627 training orders with negative effective markup and retains orders with unmatched base quotes; **1,131 training orders have a blank API base price**.

**The blind validation file arrived on 14 October 2026** and is in [data/validation](data/validation/). It has **4,155 orders from 31 July to 14 October** (not the 1,898 the guides describe), **53% of them have no base price**, and `closedAt` is filled in even though it is an outcome. It also ships with BTC candles extended to 14 October — use that file for all market features. Read [data/validation/README.md](data/validation/README.md) first.

**New to the project? Read the [project guide](materials/guides/project-guide.md).** It has the reference numbers to reproduce, the shared rules, and a common way to compare our models.

## Working approach

These are suggested steps for the team, rather than additional assignment requirements:

1. Agree on the dataset version, payout interpretation, baseline, and evaluation assumptions.
2. Audit the data and build pricing features using information available when each order was created.
3. Compare the existing pricing baseline with candidate adjustments or independent models using chronological backtests.
4. Assess profitability, downside risk, and conversion assumptions together; record assumptions that cannot yet be validated.
5. Produce one recommendation per validation observation — a premium for every row, since most rows have no base price — then assemble the deck, video, code, and supporting evidence.

Keep supplied data unchanged and save derived features, notebooks, code, and results in your member folder. Record dependencies, run instructions, data paths, and key assumptions with each contribution. Use branches and pull requests for shared changes.

```bash
git clone https://github.com/DarkMatter-404/DBA5106_Jasper_Vault_Assignment.git
cd DBA5106_Jasper_Vault_Assignment
git switch -c aman/initial-analysis  # Replace with your name and task
```

This initial repository contains source materials and team workspaces. Model code and results will be added by the team.
