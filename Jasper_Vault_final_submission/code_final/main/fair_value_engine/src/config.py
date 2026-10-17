"""Paths and settings shared by every script in this folder."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../maksim
REPO = next((p for p in ROOT.parents if (p / "data" / "with_base_premium").is_dir()), ROOT.parent)  # code_final path fix

TRAIN_CSV = REPO / "data" / "with_base_premium" / "pp_transactions_training.csv"
VALID_CSV = ROOT / "data" / "pp_transactions_validation.csv"
BTC_PARQUET = ROOT / "data" / "btc_market_history_2026-01-01_to_2026-10-14.parquet"
EVENTS_CSV = ROOT / "data" / "macro_events_2026.csv"
HOLIDAYS_CSV = ROOT / "data" / "nyse_holidays_2026.csv"

RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
OUTPUTS = ROOT / "outputs"

# Product lengths offered by Perpetual Protect, in seconds.
DURATIONS_S = [1800, 3600, 7200, 14400, 28800, 43200, 86400]

# Trailing windows (minutes) used to measure recent volatility: 1 hour, 4 hours, 1 day, 1 week.
TRAILING_WINDOWS_MIN = [60, 240, 1440, 10080]

# The volatility model is fitted on one sample every SAMPLE_STEP_MIN minutes of market history.
SAMPLE_STEP_MIN = 5

# Order-size tiers by protected notional in USDC (lower bound inclusive). Used for diagnostics
# only: after the volatility model, payouts per unit of fair value do not depend on size.
SIZE_TIERS = [("small", 0.0), ("medium", 1_000.0), ("large", 10_000.0)]

# Scheduled US releases treated as volatility events. PCE is collected in the calendar file but
# not used: in the training period BTC moved no more after PCE releases than on other days.
EVENT_TYPES = ["CPI", "NFP", "FOMC"]
EVENT_WINDOW_MIN = 30  # the extra variance of a release is measured over the 30 minutes after it

# Development split: everything before this date is used for fitting, the rest of the
# training period (June and July 2026) is the out-of-sample test.
DEV_SPLIT = "2026-06-01"
TRAIN_END = "2026-07-31 17:11:12"  # first instant after the last training order

# Price elasticities used to translate a price change into a change in expected orders.
ELASTICITIES = [0.0, 0.5, 1.0, 2.0]

# Pricing margin. Premium = fair value x (1 + margin). A target loss ratio of 80 percent
# (payouts are 80 percent of premiums on average) gives margin = 1 / 0.8 - 1 = 25 percent.
TARGET_LOSS_RATIO = 0.80

# Guardrail: when Jasper Vault's API base quote is available, the premium is never below it.
# The supplied data already excludes every order priced below the base (negative markup), and
# payouts averaged about 1.4 times the base, so a lower price is almost always loss-making.
FLOOR_AT_BASE = True

# Margins shown in the sensitivity analysis.
MARGIN_GRID = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
