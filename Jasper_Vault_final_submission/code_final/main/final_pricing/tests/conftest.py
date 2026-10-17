import sys
from pathlib import Path

FINAL = Path(__file__).resolve().parents[1]  # .../code_final/main/final_pricing
ENGINE = FINAL.parent / "fair_value_engine"  # Maksim's engine, copied into main
for p in (FINAL, ENGINE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
