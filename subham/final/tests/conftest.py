import sys
from pathlib import Path

FINAL = Path(__file__).resolve().parents[1]  # .../subham/final
REPO = FINAL.parents[1]
for p in (FINAL, REPO / "maksim"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
