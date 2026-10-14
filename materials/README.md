# Assignment and Jasper Vault materials

Everything we were given for the assignment, plus two team-written aids. Supplied documents and
ZIP archives are preserved byte-for-byte.

**Start with the [project guide](guides/project-guide.md).**

## Supplied by the course and Jasper Vault

| Material | Description |
| --- | --- |
| [Blockchain Group Assignment](briefs/Blockchain%20Group%20Assignment.pdf) | Official assignment brief. Page 2 covers the selected Jasper Vault option, evaluation, deliverables, and submission deadline; page 3 covers team requirements. |
| [Jasper Vault Options Pricing Optimisation](case-study/Jasper%20Vault%20Options%20Pricing%20Optimisation.docx) | Detailed PP pricing problem, acceptable approaches, commercial constraint, and validation process. |
| [Original English dataset ZIP](archives/Jasper%20Vault%20Options%20Pricing%20Optimisation%20EN.zip) | Original transaction dataset, market history, guide, dictionary, and metadata. Extracted in [data/en](../data/en/). |
| [Dataset ZIP including base premium](archives/Jasper%20Vault%20Options%20Pricing%20Optimisation%28Included%20Base%20Premium%29.zip) | Pricing-enriched training dataset and accompanying documentation. Extracted in [data/with_base_premium](../data/with_base_premium/). |
| [**Validation dataset ZIP** (received 14 Oct 2026)](archives/JV%20validation%20dataset%20%28Blockchain_Assignment_export%29.zip) | Blind validation orders (4,155, 31 Jul – 14 Oct 2026) and BTC candles extended to 14 Oct. Supplied as `Blockchain_Assignment_export.zip`; renamed here only to say what it is. Extracted in [data/validation](../data/validation/). |
| [Coding with AI Copilot — 17 September](workshop/Coding%20with%20AI%20Copilot%20-17September.pdf) | Workshop handout on AI-assisted coding, given alongside the assignment. |

## Written by the team

| Material | Description |
| --- | --- |
| [Lecture slides for Option 2](lectures/README.md) | Summary of the nine relevant slides from Blockchain Lectures 6 and 7: why PP is hard to price, **the profit-with-purchase-constraint objective**, DeFi risk, oracles, on/off-chain design. The slides themselves are on Canvas, not in this public repository. |
| [Project guide](guides/project-guide.md) | The problem in one formula, how the payout works, reference numbers to reproduce, the validation file's quirks, shared rules, a common evaluation protocol, open questions for JV, and a submission checklist. |

## The validation file differs from the guides

The supplied guides describe a validation set of 1,898 orders ending 24 August. The file we
received has **4,155 orders ending 14 October**; **53% have no base price**; the premium columns
are blank but **`closedAt` is filled in**. Read [data/validation/README.md](../data/validation/README.md)
before using it.

## Checksums

[SHA256SUMS.txt](SHA256SUMS.txt) records every supplied file and every extracted copy, using
paths relative to the repository root. Verify from the root with:

```bash
shasum -a 256 -c materials/SHA256SUMS.txt
```

The original ZIPs retain all their contents. Extracted copies omit only macOS `__MACOSX` /
AppleDouble housekeeping entries. The source workbooks and raw quote files mentioned in the
supplied guides were never provided.
