# Assignment and Jasper Vault materials

These five files were supplied in the Capstone course's Blockchain Assignment folder. Original documents and ZIP archives are preserved byte-for-byte.

| Material | Description |
| --- | --- |
| [Blockchain Group Assignment](briefs/Blockchain%20Group%20Assignment.pdf) | Official assignment brief. Page 2 covers the selected Jasper Vault option, evaluation, deliverables, and submission deadline; page 3 covers team requirements. |
| [Jasper Vault Options Pricing Optimisation](case-study/Jasper%20Vault%20Options%20Pricing%20Optimisation.docx) | Detailed PP pricing problem, acceptable approaches, commercial constraint, and validation process. |
| [Original English dataset ZIP](archives/Jasper%20Vault%20Options%20Pricing%20Optimisation%20EN.zip) | Original transaction dataset, market history, guide, dictionary, and metadata. Extracted in [data/en](../data/en/). |
| [Dataset ZIP including base premium](archives/Jasper%20Vault%20Options%20Pricing%20Optimisation%28Included%20Base%20Premium%29.zip) | Pricing-enriched dataset and accompanying documentation. Extracted in [data/with_base_premium](../data/with_base_premium/). |
| [Coding with AI Copilot — 17 September](workshop/Coding%20with%20AI%20Copilot%20-17September.pdf) | Supporting workshop handout included alongside the assignment materials. |

The original ZIPs retain all their contents. Their extracted copies omit only macOS `__MACOSX` / AppleDouble housekeeping entries; all five substantive files from each archive are included.

[SHA256SUMS.txt](SHA256SUMS.txt) records the five supplied files and ten extracted files using paths relative to the repository root. Verify them from the root with:

```bash
shasum -a 256 -c materials/SHA256SUMS.txt
```

The supplied guides and metadata describe additional source workbooks, raw quote files, and a validation CSV. Those underlying files were not included in the supplied packages. See the [data inventory](../data/README.md) for what is available.
