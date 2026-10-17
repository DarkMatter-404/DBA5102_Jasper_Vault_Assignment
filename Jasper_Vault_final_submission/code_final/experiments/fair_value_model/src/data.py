"""Loading and cleaning the PP order files and the BTC one-minute candles."""
import numpy as np
import polars as pl

from . import config

_TS_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"]


def parse_ts(col: str) -> pl.Expr:
    """Parse a timestamp column that mixes several text formats (the validation file does).

    All order timestamps are UTC. The result is a naive datetime in UTC.
    """
    attempts = [pl.col(col).str.strptime(pl.Datetime("us"), fmt, strict=False) for fmt in _TS_FORMATS]
    return pl.coalesce(attempts).alias(col)


def load_orders(path) -> pl.DataFrame:
    """Read a PP transaction file and add the derived columns used everywhere else."""
    raw = pl.read_csv(path, infer_schema_length=0)  # read as text, then cast explicitly
    num = ["premiumAmount_USDC", "quantity_BTC", "strikePrice", "realizedProfit_USDC",
           "orderPrice_per_BTC_USDC", "apiBasePrice_per_BTC_USDC", "markup_per_BTC_USDC"]
    df = raw.with_columns(
        [parse_ts(c) for c in ["createdAt", "closedAt", "expirationDate"]]
        + [pl.col(c).cast(pl.Float64, strict=False) for c in num]
        + [pl.col("optionType").cast(pl.Int64), pl.col("productType").cast(pl.Int64)]
    )
    bad = df.filter(pl.col("createdAt").is_null()).height
    if bad:
        raise ValueError(f"{bad} rows in {path} have an unparseable createdAt")
    return df.with_row_index("row_id").with_columns(
        notional_USDC=pl.col("quantity_BTC") * pl.col("strikePrice"),
        T_min=(pl.col("productType") // 60).cast(pl.Int64),
        base_premium_USDC=pl.col("apiBasePrice_per_BTC_USDC") * pl.col("quantity_BTC"),
        day=pl.col("createdAt").dt.date(),
    )


def size_tier(notional: pl.Expr) -> pl.Expr:
    """Map protected notional (USDC) to the size tiers defined in config."""
    expr = pl.lit(config.SIZE_TIERS[0][0])
    for name, lower in config.SIZE_TIERS[1:]:
        expr = pl.when(notional >= lower).then(pl.lit(name)).otherwise(expr)
    return expr


def load_candles() -> pl.DataFrame:
    """One-minute BTCUSDC perpetual candles, checked for gaps."""
    df = pl.read_parquet(config.BTC_PARQUET, columns=["open_time_utc", "open", "high", "low", "close", "volume",
                                                      "taker_buy_base_asset_volume"])
    df = df.with_columns(ts=pl.col("open_time_utc").str.strptime(pl.Datetime("us"), "%Y-%m-%dT%H:%M:%SZ")).drop("open_time_utc").sort("ts")
    steps = df["ts"].diff().dt.total_seconds().drop_nulls().unique().to_list()
    if steps != [60]:
        raise ValueError(f"candle series is not a gap-free one-minute grid: steps {steps}")
    return df


def load_events(types: list[str] | None = None) -> pl.DataFrame:
    """Scheduled US macro releases of the given types (default config.EVENT_TYPES), in UTC.

    Returns an empty frame when the calendar file is absent, so the rest of the pipeline
    still runs (the event feature is then zero everywhere).
    """
    if not config.EVENTS_CSV.exists():
        return pl.DataFrame({"event_type": [], "ts_utc": []}, schema={"event_type": pl.Utf8, "ts_utc": pl.Datetime("us")})
    types = config.EVENT_TYPES if types is None else types
    ev = pl.read_csv(config.EVENTS_CSV, infer_schema_length=0).filter(pl.col("event_type").is_in(types))
    ev = ev.with_columns(
        ts_et=(pl.col("date_et") + " " + pl.col("time_et")).str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M")
    ).with_columns(
        ts_utc=pl.col("ts_et").dt.replace_time_zone("America/New_York").dt.convert_time_zone("UTC").dt.replace_time_zone(None)
    )
    return ev.select("event_type", "ts_utc").sort("ts_utc")


def load_holidays() -> list:
    """NYSE full-day closures (US Eastern dates), from the exchange's published calendar."""
    return pl.read_csv(config.HOLIDAYS_CSV)["date"].str.to_date().to_list()


def minute_index(ts: np.ndarray, t0: np.datetime64) -> np.ndarray:
    """Index of the one-minute candle that contains each timestamp."""
    return ((ts - t0) // np.timedelta64(60, "s")).astype(np.int64)
