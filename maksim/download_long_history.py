"""Download three years of one-minute BTC perpetual prices for the long-history test.

Source: Binance public data (data.binance.vision), USD-M futures, BTCUSDT, monthly one-minute
klines, January 2023 to December 2025. Each zip is checked against the SHA-256 that Binance
publishes next to it. BTCUSDT is used because the BTCUSDC contract (used in the case data) only
has history from 2024; the two track the same BTC price within a few basis points.

Output: data/btcusdt_1m_2023_2025.parquet (open time in UTC and close price), and the raw zips
in data/binance_cache/ (not committed; delete after the parquet is built if space is short).
"""
import hashlib
import io
import sys
import urllib.request
import zipfile

import polars as pl

from src import config

URL = "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-{ym}.zip"
MONTHS = [f"{y}-{m:02d}" for y in (2023, 2024, 2025) for m in range(1, 13)]
CACHE = config.ROOT / "data" / "binance_cache"
OUT = config.ROOT / "data" / "btcusdt_1m_2023_2025.parquet"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def month_frame(ym: str) -> pl.DataFrame:
    path = CACHE / f"BTCUSDT-1m-{ym}.zip"
    if not path.exists():
        data = fetch(URL.format(ym=ym))
        expected = fetch(URL.format(ym=ym) + ".CHECKSUM").decode().split()[0]
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"checksum mismatch for {ym}")
        path.write_bytes(data)
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    # Some monthly files have a header row and some do not; read without one and drop non-numeric rows.
    df = pl.read_csv(io.BytesIO(raw), has_header=False, infer_schema_length=0)
    df = df.select(pl.col(df.columns[0]).alias("open_time_ms"), pl.col(df.columns[4]).alias("close"))
    return df.filter(pl.col("open_time_ms").str.contains(r"^\d+$")).select(
        ts=pl.col("open_time_ms").cast(pl.Int64).cast(pl.Datetime("ms")).cast(pl.Datetime("us")),
        close=pl.col("close").cast(pl.Float64))


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    frames = []
    for ym in MONTHS:
        frames.append(month_frame(ym))
        print(ym, frames[-1].height, file=sys.stderr)
    df = pl.concat(frames).unique("ts").sort("ts")
    full = pl.DataFrame({"ts": pl.datetime_range(df["ts"][0], df["ts"][-1], "1m", eager=True)})
    missing = full.height - df.height
    df = full.join(df, on="ts", how="left").with_columns(pl.col("close").forward_fill())  # rare exchange gaps
    print(f"{df.height} minutes on the grid, {missing} missing minutes forward-filled", file=sys.stderr)
    df.write_parquet(OUT, compression="zstd", compression_level=19)
    print(OUT, file=sys.stderr)


if __name__ == "__main__":
    main()
