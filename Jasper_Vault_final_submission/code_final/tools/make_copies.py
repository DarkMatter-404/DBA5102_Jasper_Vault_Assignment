"""Copy the team's code into code_final, byte for byte.

Each file is added to the git index under its new path with the SAME blob ID as its source at SOURCE_COMMIT, then
checked out. So every copy is identical to its source, and git stores no new file content.

Run once, from anywhere inside the repository:  python make_copies.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SOURCE_COMMIT = "461f015d4b7d1caf132c89c25d6bd57a42e86a2f"  # main on 18 Oct 2026: final solution, deck and video
DEST = "Jasper_Vault_final_submission/code_final"
EXP = "experiments/"
ENGINE = "main/fair_value_engine/"

# (source, copy, files excluded from the source). A source that ends in "/" is a folder; otherwise it is one file.
RULES = [
    ("maksim/", EXP + "fair_value_model/", ()),
    ("subham/final/", "main/final_pricing/", ()),
    ("subham/final/requirements.txt", "main/requirements.txt", ()),
    ("subham/", EXP + "hybrid_base_multiplier/", ("subham/final/",)),
    ("aman/", EXP + "jv_reference_f1/", ()),
    ("chris/audit/", EXP + "team_audit/", ()),
    ("chris/holdout_all.py", EXP + "team_audit/holdout_all.py", ()),
    ("chris/TEAM_SAME_HOLDOUT_CHECK.md", EXP + "team_audit/TEAM_SAME_HOLDOUT_CHECK.md", ()),
    ("chris/requirements.txt", EXP + "team_audit/requirements.txt", ()),
    ("chris/.gitignore", EXP + "team_audit/.gitignore", ()),
    ("chris/", EXP + "order_flow_book/",
     ("chris/audit/", "chris/holdout_all.py", "chris/TEAM_SAME_HOLDOUT_CHECK.md")),
    ("jay/", EXP + "duration_sentiment/", ()),
    ("revision_v2/", EXP + "duration_sentiment/revision_v2/", ()),
    ("llm assisted trading/", EXP + "llm_event_research/", ()),
    # The LLM study's inputs were never committed. These repository files are the same files (see data/raw/README.md).
    ("data/with_base_premium/pp_transactions_training.csv",
     EXP + "llm_event_research/data/raw/pp_transactions_training.csv", ()),
    ("data/validation/pp_transactions_validation.csv",
     EXP + "llm_event_research/data/raw/pp_transactions_validation.csv", ()),
    ("jay/docs/classnotes.md", EXP + "llm_event_research/data/raw/classnotes.md", ()),
    ("jay/revision_v3_2/data/assignment_inputs/btc_market_history.csv.gz",
     EXP + "llm_event_research/data/raw/btc_market_history.csv.gz", ()),
]

# main/fair_value_engine: only the files that make the frozen prices and the functions main imports.
ENGINE_SOURCES = ["maksim/.gitattributes", "maksim/requirements.txt", "maksim/run_validation.py",
                  "maksim/run_extensions.py", "maksim/src/", "maksim/data/", "maksim/outputs/", "maksim/tests/"]
RULES += [(src, ENGINE + src[len("maksim/"):], ()) for src in ENGINE_SOURCES]

# main/evidence: the saved results that the final notebooks read, under <experiment>/<path inside the experiment>.
EVIDENCE_SOURCES = {
    "maksim/": "fair_value_model/",
    "chris/audit/": "team_audit/",
    "subham/": "hybrid_base_multiplier/",
}
EVIDENCE_FILES = [
    "maksim/results/walk_forward_orders_priced.parquet",
    "maksim/results/sealed_check/summary.json",
    "maksim/results/sealed_check/sealed_check_monthly.csv",
    "maksim/results/extensions/exposure_limits.csv",
    "maksim/results/margin_sensitivity_walk_forward.csv",
    "maksim/results/walk_forward_monthly.csv",
    "maksim/results/payout_over_fair_value_walk_forward.csv",
    "chris/audit/same_holdout_scores.csv",
    "subham/outputs/backtest_summary.csv",
    "subham/outputs/validation_premiums.csv",
]
for _src in EVIDENCE_FILES:
    _prefix = next(p for p in EVIDENCE_SOURCES if _src.startswith(p))
    RULES.append((_src, "main/evidence/" + EVIDENCE_SOURCES[_prefix] + _src[len(_prefix):], ()))

SOURCE_ROOTS = ["maksim", "subham", "aman", "chris", "jay", "revision_v2", "llm assisted trading",
                "data/with_base_premium/pp_transactions_training.csv", "data/validation/pp_transactions_validation.csv"]


def destinations(src: str) -> list[str]:
    """Every copy path (relative to the repository root) for one source path. Empty when the file is not copied."""
    out = []
    for source, copy, excluded in RULES:
        if any(src == e or (e.endswith("/") and src.startswith(e)) for e in excluded):
            continue
        if source.endswith("/") and src.startswith(source):
            out.append(f"{DEST}/{copy}{src[len(source):]}")
        elif src == source:
            out.append(f"{DEST}/{copy}")
    return sorted(set(out))


def plan_copies(entries) -> list[tuple[str, str, str, list[str]]]:
    """(copy path, mode, blob, sources) for every (mode, blob, source path) entry. Two sources may share one copy
    path only when their content is the same."""
    plan: dict[str, tuple[str, str, list[str]]] = {}
    for mode, blob, src in entries:
        for dst in destinations(src):
            if dst in plan:
                if plan[dst][1] != blob:
                    raise ValueError(f"{dst}: sources {plan[dst][2]} and {src} have different content")
                plan[dst][2].append(src)
            else:
                plan[dst] = (mode, blob, [src])
    return [(dst, m, b, sorted(s)) for dst, (m, b, s) in sorted(plan.items())]


def index_info(plan) -> bytes:
    """Records for `git update-index -z --index-info`: '<mode> <blob>TAB<path>NUL'."""
    return b"".join(f"{mode} {blob}\t{dst}\0".encode() for dst, mode, blob, _ in plan)


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, check=True).stdout


def source_entries(repo: Path) -> list[tuple[str, str, str]]:
    """(mode, blob, path) of every file under SOURCE_ROOTS at SOURCE_COMMIT."""
    raw = git(repo, "ls-tree", "-r", "-z", SOURCE_COMMIT, "--", *SOURCE_ROOTS)
    entries = []
    for rec in raw.decode().split("\0"):
        if rec:
            meta, path = rec.split("\t", 1)
            mode, kind, blob = meta.split()
            if kind == "blob":
                entries.append((mode, blob, path))
    return entries


def main() -> None:
    repo = Path(git(Path(__file__).resolve().parent, "rev-parse", "--show-toplevel").decode().strip())
    plan = plan_copies(source_entries(repo))
    git(repo, "update-index", "--add", "-z", "--index-info", data=index_info(plan))
    git(repo, "checkout", "--", DEST)
    print(f"{len(plan)} copies of {sum(len(p[3]) for p in plan)} source files into {DEST}")


if __name__ == "__main__":
    sys.exit(main())
