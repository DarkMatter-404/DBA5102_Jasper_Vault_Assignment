"""Load and clean the PP order files and the BTC 1-minute price file.

Column rules
- Outcome columns (closedAt, realizedProfit_USDC) are known only after an order ends.
  They are kept for evaluation, under names that start with "post_", and are never features.
- Jasper's own price columns (premium, order price, markup) are benchmarks, not features.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _first_existing(*paths: Path) -> Path:
    """First path that exists. If none exists, the first one, so the error names the team-repo place."""
    return next((p for p in paths if p.exists()), paths[0])


# Team repository layout first (this folder is next to ../data), then the original export folders.
TRAIN_FILE = _first_existing(
    ROOT.parent / "data" / "with_base_premium" / "pp_transactions_training.csv",
    ROOT / "Jasper Vault Options Pricing Optimisation(Included Base Premium)" / "pp_transactions_training.csv")
VALID_DIR = _first_existing(ROOT.parent / "data" / "validation", ROOT / "JV validation dataset")
VALID_FILE = VALID_DIR / "pp_transactions_validation.csv"
# The validation copy covers 1 Jan - 14 Oct 2026 and equals the training copy where both exist
# (only the last, unfinished minute of the training copy differs). Without the validation files,
# the training copy (1 Jan - 24 Aug) is enough for the training months.
BTC_FILE = _first_existing(VALID_DIR / "btc_market_history.csv", TRAIN_FILE.parent / "btc_market_history.csv")

MINUTES_PER_YEAR = 365 * 24 * 60


def parse_time(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse both date formats in the files.

    "2026-02-04 09:22:02" (seconds) and "2026/7/31 17:11" (minute only).
    Returns (timestamps as naive UTC datetime64[ns], True where the value has no seconds).
    """
    s = values.astype(str).str.strip()
    minute_only = ~s.str.match(r"^.*\d{1,2}:\d{2}:\d{2}$")
    t = pd.to_datetime(s.str.replace("/", "-", regex=False), format="mixed")
    return t.astype("datetime64[ns]"), minute_only.astype(bool)


def strike_decimals(raw: pd.Series) -> pd.Series:
    """Number of decimal places of the strike as written in the file."""
    s = raw.astype(str).str.strip()
    return s.str.split(".").str[1].fillna("").str.len().astype(int)


def load_orders(split: str) -> pd.DataFrame:
    """Load one order file ("train" or "valid") into a clean frame.

    Prices are per 1 BTC unless the name ends in _usd.
    """
    path = {"train": TRAIN_FILE, "valid": VALID_FILE}[split]
    raw = pd.read_csv(path, dtype={"strikePrice": str})
    df = pd.DataFrame(index=raw.index)
    df["split"] = split
    df["row"] = np.arange(len(raw))
    df["created"], df["created_minute_only"] = parse_time(raw["createdAt"])
    df["expiry"], _ = parse_time(raw["expirationDate"])
    df["duration_s"] = raw["productType"].astype(int)
    df["is_put"] = (raw["optionType"].astype(int) == 1)
    df["qty"] = raw["quantity_BTC"].astype(float)
    df["strike"] = raw["strikePrice"].astype(float)
    df["strike_decimals"] = strike_decimals(raw["strikePrice"])
    # Calculated strike (many decimals), probably the trader's entry price. See analysis/strike_entry_test.py.
    df["strike_calc"] = df["strike_decimals"] > 2
    df["base"] = raw["apiBasePrice_per_BTC_USDC"].astype(float)

    # Jasper's real price per BTC: all training rows; validation only where the markup is given.
    paid = raw["orderPrice_per_BTC_USDC"].astype(float)
    from_markup = raw["apiBasePrice_per_BTC_USDC"] + raw["markup_per_BTC_USDC"]
    df["paid"] = paid.fillna(from_markup)

    # Outcomes: evaluation only.
    df["post_closed"], _ = parse_time(raw["closedAt"].fillna(raw["expirationDate"]))
    df.loc[raw["closedAt"].isna(), "post_closed"] = pd.NaT
    df["post_payout_usd"] = raw["realizedProfit_USDC"].astype(float)
    df["post_payout"] = df["post_payout_usd"] / df["qty"]
    df["has_outcome"] = df["post_payout_usd"].notna()
    return df


def load_btc() -> pd.DataFrame:
    """BTC 1-minute candles, indexed by the minute's open time (naive UTC), no gaps."""
    b = pd.read_csv(BTC_FILE)
    b["t"] = pd.to_datetime(b["open_time_utc"], utc=True).dt.tz_localize(None).astype("datetime64[ns]")
    b = b.set_index("t").sort_index()
    cols = ["open", "high", "low", "close", "volume", "number_of_trades", "taker_buy_base_asset_volume"]
    b = b[cols].rename(columns={"number_of_trades": "trades", "taker_buy_base_asset_volume": "taker_buy"})
    full = pd.date_range(b.index[0], b.index[-1], freq="1min")
    if len(full) != len(b):
        b = b.reindex(full).ffill()
    return b


def info_minute(created: pd.Series) -> pd.Series:
    """Last complete BTC minute before the order.

    For "09:22:02" the minute 09:22 is not finished, so 09:21 is used.
    For minute-only values ("17:11") the order can be at any second of 17:11, so 17:10 is used.
    """
    return created.dt.floor("min") - pd.Timedelta(minutes=1)
