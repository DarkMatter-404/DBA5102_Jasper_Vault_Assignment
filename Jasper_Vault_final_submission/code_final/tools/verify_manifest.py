"""Check every file in code_final against MANIFEST.csv. Works in the repository and in the unzipped package.

A Windows checkout can turn LF line endings into CRLF. Such a file is reported as "ok (CRLF line endings)".

Run:  python verify_manifest.py
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

CODE_FINAL = Path(__file__).resolve().parents[1]


def file_matches(path: Path, sha256: str) -> str:
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() == sha256:
        return "ok"
    if hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == sha256:
        return "ok (CRLF line endings)"
    return "DIFFERENT"


def main() -> int:
    with open(CODE_FINAL / "MANIFEST.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = []
    for r in rows:
        p = CODE_FINAL / r["copy_path"]
        result = file_matches(p, r["sha256"]) if p.exists() else "MISSING"
        if not result.startswith("ok"):
            bad.append((result, r["copy_path"]))
    print(f"{len(rows) - len(bad)} of {len(rows)} files match MANIFEST.csv")
    for result, path in bad:
        print(f"  {result}: {path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
