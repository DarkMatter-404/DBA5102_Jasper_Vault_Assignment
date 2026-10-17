"""Write MANIFEST.csv: one row for every file in code_final, with its source and whether it changed.

status: identical   = the same bytes as the source file at the source commit
        path-edited = only file paths changed (each such file is named in CHANGES.md)
        regenerated = main's notebooks, report and outputs, re-run from their new place
        new         = written for code_final (READMEs, these tools, data/raw/README.md)

Run after committing:  python build_manifest.py
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import make_copies as mc

REGENERATED = ("main/final_pricing/final_solution.ipynb", "main/final_pricing/final_report.ipynb",
               "main/final_pricing/final_report.html", "main/final_pricing/outputs/")
FIELDS = ["copy_path", "source_path", "source_commit", "status", "bytes", "sha256"]


def status(dst: str, head_blob: str, src_blob: str | None) -> str:
    if src_blob is None:
        return "new"
    if head_blob == src_blob:
        return "identical"
    inside = dst[len(mc.DEST) + 1:] if dst.startswith(mc.DEST + "/") else dst
    return "regenerated" if inside.startswith(REGENERATED) else "path-edited"


def undocumented_edits(rows, changes_text: str) -> list[str]:
    """Path-edited files that CHANGES.md does not name (by their path inside code_final)."""
    return [r["copy_path"] for r in rows if r["status"] == "path-edited"
            and r["copy_path"][len(mc.DEST) + 1:] not in changes_text]


def head_files(repo: Path) -> list[tuple[str, str]]:
    """(path, blob) of every file under code_final at HEAD."""
    raw = mc.git(repo, "ls-tree", "-r", "-z", "HEAD", "--", mc.DEST)
    out = []
    for rec in raw.decode().split("\0"):
        if rec:
            meta, path = rec.split("\t", 1)
            out.append((path, meta.split()[2]))
    return out


def main() -> None:
    repo = Path(mc.git(Path(__file__).resolve().parent, "rev-parse", "--show-toplevel").decode().strip())
    plan = {dst: (blob, sources) for dst, _, blob, sources in mc.plan_copies(mc.source_entries(repo))}
    manifest = repo / mc.DEST / "MANIFEST.csv"
    rows = []
    for path, blob in head_files(repo):
        if path == manifest.relative_to(repo).as_posix():
            continue
        data = mc.git(repo, "cat-file", "blob", blob)
        src_blob, sources = plan.get(path, (None, []))
        rows.append({"copy_path": path[len(mc.DEST) + 1:], "source_path": " | ".join(sources),
                     "source_commit": mc.SOURCE_COMMIT[:7] if sources else "",
                     "status": status(path, blob, src_blob), "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()})
    missing = sorted(set(plan) - {p for p, _ in head_files(repo)})
    if missing:
        raise SystemExit(f"{len(missing)} planned copies are missing, e.g. {missing[:3]}")
    changes = (repo / mc.DEST / "CHANGES.md").read_text(encoding="utf-8")
    bad = undocumented_edits([{**r, "copy_path": f"{mc.DEST}/{r['copy_path']}"} for r in rows], changes)
    if bad:
        raise SystemExit(f"Edited files not named in CHANGES.md: {bad}")
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    counts = {s: sum(r["status"] == s for r in rows) for s in ("identical", "path-edited", "regenerated", "new")}
    print(f"MANIFEST.csv: {len(rows)} files", counts)


if __name__ == "__main__":
    sys.exit(main())
