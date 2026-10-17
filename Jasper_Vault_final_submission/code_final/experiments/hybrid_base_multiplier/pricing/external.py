"""External data: US macro calendar, Crypto Fear & Greed index, GDELT news tone (if reachable).

All features use only information available before the order:
- macro releases are scheduled in advance (dates from the official sources below);
- Fear & Greed uses the value of the previous UTC day;
- news tone uses hourly buckets that ended before the order.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .data import ROOT

EXT_DIR = ROOT / "data" / "external"
CALENDAR_FILE = EXT_DIR / "macro_calendar_2026.csv"

# Official 2026 schedules, times in US Eastern time.
# FOMC: federalreserve.gov/monetarypolicy/fomccalendars.htm (decision at 14:00 on the 2nd day)
# CPI, Employment Situation, PPI: bls.gov/schedule/2026/home.htm
# Personal Income and Outlays (PCE), GDP: bea.gov/news/schedule/full
_EVENTS = {
    ("FOMC", "14:00", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"):
        ["01-28", "03-18", "04-29", "06-17", "07-29", "09-16", "10-28", "12-09"],
    ("CPI", "08:30", "https://www.bls.gov/schedule/2026/home.htm"):
        ["01-13", "02-13", "03-11", "04-10", "05-12", "06-10", "07-14", "08-12", "09-11", "10-14", "11-10", "12-10"],
    ("Jobs", "08:30", "https://www.bls.gov/schedule/2026/home.htm"):
        ["01-09", "02-11", "03-06", "04-03", "05-08", "06-05", "07-02", "08-07", "09-04", "10-02", "11-06", "12-04"],
    ("PPI", "08:30", "https://www.bls.gov/schedule/2026/home.htm"):
        ["01-14", "01-30", "02-27", "03-18", "04-14", "05-13", "06-11", "07-15", "08-13", "09-10", "10-15", "11-13", "12-15"],
    ("PCE", "08:30", "https://www.bea.gov/news/schedule/full"):
        ["01-22", "02-20", "03-13", "04-09", "04-30", "05-28", "06-25", "07-30", "08-26", "09-30"],
    ("GDP", "08:30", "https://www.bea.gov/news/schedule/full"):
        ["02-20", "03-13", "04-09", "04-30", "05-28", "06-25", "07-30", "08-26"],
}


def macro_calendar() -> pd.DataFrame:
    """Event list with UTC times. Also written to data/external/macro_calendar_2026.csv."""
    rows = []
    for (kind, hhmm, source), days in _EVENTS.items():
        for md in days:
            et = pd.Timestamp(f"2026-{md} {hhmm}").tz_localize("America/New_York")
            rows.append({"event": kind, "time_et": et.strftime("%Y-%m-%d %H:%M"),
                         "time_utc": et.tz_convert("UTC").tz_localize(None), "source": source})
    cal = pd.DataFrame(rows).sort_values("time_utc").reset_index(drop=True)
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    cal.to_csv(CALENDAR_FILE, index=False)
    return cal


def calendar_features(orders: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """Hours to the next / since the last release, and whether a release falls inside the protection window."""
    nat = np.datetime64("NaT", "ns")
    times = np.sort(cal["time_utc"].drop_duplicates().to_numpy().astype("datetime64[ns]"))
    c = orders["created"].to_numpy().astype("datetime64[ns]")
    end = (orders["created"] + pd.to_timedelta(orders["duration_s"], unit="s")).to_numpy().astype("datetime64[ns]")
    i = np.searchsorted(times, c, side="right")  # first event after created
    nxt = np.where(i < len(times), times[np.minimum(i, len(times) - 1)], nat)
    prv = np.where(i > 0, times[np.maximum(i - 1, 0)], nat)
    f = pd.DataFrame(index=orders.index)
    f["hours_to_event"] = np.clip((nxt - c) / np.timedelta64(1, "h"), 0, 168)
    f["hours_since_event"] = np.clip((c - prv) / np.timedelta64(1, "h"), 0, 168)
    f["event_in_window"] = (i < len(times)) & (nxt <= end)
    f = f.fillna(168.0)
    f["event_in_window"] = f["event_in_window"].astype(int)
    return f


def fear_greed(cache: bool = True) -> pd.DataFrame:
    """Daily Crypto Fear & Greed index (alternative.me). Columns: date, fng (0-100)."""
    path = EXT_DIR / "fear_greed.csv"
    if cache and path.exists():
        return pd.read_csv(path, parse_dates=["date"])
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"}, timeout=60)
    r.raise_for_status()
    d = pd.DataFrame(r.json()["data"])
    d["date"] = pd.to_datetime(d["timestamp"].astype(int), unit="s").dt.normalize()
    d["fng"] = d["value"].astype(float)
    d = d[["date", "fng"]].sort_values("date").reset_index(drop=True)
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    d.to_csv(path, index=False)
    return d


def fear_greed_features(orders: pd.DataFrame, fng: pd.DataFrame) -> pd.DataFrame:
    """Previous UTC day's index (0-1) and its change over the 7 days before that."""
    s = fng.set_index("date")["fng"].asfreq("D").ffill()
    prev_day = orders["created"].dt.normalize() - pd.Timedelta(days=1)
    f = pd.DataFrame(index=orders.index)
    f["fng"] = s.reindex(prev_day.to_numpy()).to_numpy() / 100
    f["fng_change7"] = f["fng"] - s.reindex((prev_day - pd.Timedelta(days=7)).to_numpy()).to_numpy() / 100
    return f


def gdelt_hourly_tone(start: str, end: str, query: str = "bitcoin sourcelang:english",
                      pause: float = 6.0, max_tries: int = 4) -> tuple[pd.DataFrame | None, str]:
    """Hourly news tone and article volume from the GDELT DOC 2.0 API, fetched in 7-day windows.

    Returns (frame or None, status message). Windows already fetched are cached as JSON.
    """
    out_dir = EXT_DIR / "gdelt"
    out_dir.mkdir(parents=True, exist_ok=True)
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    frames, failed = [], 0
    for s in pd.date_range(start, end, freq="7D"):
        e = min(s + pd.Timedelta(days=7), pd.Timestamp(end))
        for mode in ("TimelineTone", "TimelineVolRaw"):
            path = out_dir / f"{mode}_{s:%Y%m%d}.json"
            if not path.exists():
                ok = False
                for _ in range(max_tries):
                    time.sleep(pause)
                    r = requests.get(url, params={"query": query, "mode": mode, "format": "json",
                                                  "startdatetime": f"{s:%Y%m%d%H%M%S}",
                                                  "enddatetime": f"{e:%Y%m%d%H%M%S}"}, timeout=90)
                    if r.status_code == 200 and r.text.strip().startswith("{"):
                        path.write_text(r.text, encoding="utf-8")
                        ok = True
                        break
                if not ok:
                    failed += 1
                    if failed >= 2:
                        return None, f"GDELT refused requests (last HTTP {r.status_code}); stopped at {s:%Y-%m-%d}"
                    continue
            data = json.loads(path.read_text(encoding="utf-8"))["timeline"][0]["data"]
            frames.append(pd.DataFrame({"t": pd.to_datetime([x["date"] for x in data], format="%Y%m%dT%H%M%SZ"),
                                        "value": [x["value"] for x in data], "mode": mode}))
    if not frames:
        return None, "no GDELT data"
    d = pd.concat(frames).pivot_table(index="t", columns="mode", values="value").sort_index()
    return d.rename(columns={"TimelineTone": "tone", "TimelineVolRaw": "articles"}), "ok"


def news_features(orders: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """Tone and article count of the last full hour before the order, and the 24-hour average tone."""
    h = hourly.asfreq("h")
    last_full = orders["created"].dt.floor("h") - pd.Timedelta(hours=1)
    f = pd.DataFrame(index=orders.index)
    f["news_tone"] = h["tone"].reindex(last_full.to_numpy()).to_numpy()
    f["news_tone24"] = h["tone"].rolling(24, min_periods=12).mean().reindex(last_full.to_numpy()).to_numpy()
    vol = np.log1p(h["articles"])
    f["news_volume_ratio"] = (vol - vol.rolling(168, min_periods=48).mean()).reindex(last_full.to_numpy()).to_numpy()
    return f
