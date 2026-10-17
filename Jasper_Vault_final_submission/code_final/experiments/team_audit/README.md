# team_audit (Chris)

> **code_final copy.** Copied from `chris/audit/`, `chris/holdout_all.py` and `chris/TEAM_SAME_HOLDOUT_CHECK.md` at
> commit `461f015`. The scripts used paths on the auditor's own computer. Those lines now use a work folder and the
> repository root ([`../../CHANGES.md`](../../CHANGES.md)). `make_audit_inputs.py` and its test are new.

An independent audit of all the team's models. The pricing rules are scored on the same orders (May to July 2026),
under the same demand rules. Read [`AUDIT_MEMO.md`](AUDIT_MEMO.md) first, then
[`TEAM_SAME_HOLDOUT_CHECK.md`](TEAM_SAME_HOLDOUT_CHECK.md). The final report in `main/` uses
`same_holdout_scores.csv`.

| File | What it is |
|---|---|
| `AUDIT_MEMO.md` | The audit: findings, risks and the recommended final setup |
| `TEAM_SAME_HOLDOUT_CHECK.md` | The same-orders comparison of every model |
| `score_panels.py` → `same_holdout_scores.csv` | Every model under 7 demand rules, per month |
| `bootstrap_diffs.py` → `bootstrap_vs_JV.csv` | Day-bootstrap intervals for profit against JV |
| `combos.py` → `combos_scores.csv` | Models combined with the order-flow loading |
| `book_proxy_check.py` | The open book built from expiry dates, against the book built from close times |
| `holdout_all.py` | The tables in `TEAM_SAME_HOLDOUT_CHECK.md` |
| `make_audit_inputs.py` (new) | Rebuilds the two inputs above, in the way the auditor made them |

## Reproduce

The scripts read Aman's per-order panels and Chris's open book. `make_audit_inputs.py` runs Aman's notebook on a copy
of `../jv_reference_f1/` with one extra last cell that saves the panels (the step written at the top of
`holdout_all.py`). It also runs Chris's steps 00 and 01 from `../order_flow_book/`. Everything goes to `work/` (or to
the `AUDIT_WORK` folder).

```bash
python -m pip install -r ../jv_reference_f1/requirements.txt   # Aman's notebook needs these packages
python make_audit_inputs.py      # about one minute
python score_panels.py           # -> work/audit/same_holdout_scores.csv
python bootstrap_diffs.py        # -> work/audit/bootstrap_vs_JV.csv
python combos.py                 # -> work/audit/combos_scores.csv
python book_proxy_check.py
python holdout_all.py            # -> work/holdout_*_all_models.csv
python -m pytest test_make_audit_inputs.py -q
```

Result on 18 Oct 2026 (Windows, Python 3.14.3): every step ran. `same_holdout_scores.csv`, `bootstrap_vs_JV.csv` and
`combos_scores.csv` match the saved files within 0.00000002 USDC. Before code_final, the audit could not be re-run
from the repository.
