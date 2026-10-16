"""Final PP pricing solution: Maksim's model plus the team's tested layers.

Core:      Maksim's frozen premium (fair value x 1.25, never below the API base price).
Layer:     Chris's order-flow loading, with JV's open book built from expiry dates only (no closedAt).
Risk rule: Maksim's exposure cap per direction (reported, not priced).

Nothing here fits a model. The functions combine saved team outputs, so every number traces back to a teammate's
folder at a fixed commit.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

K_LOADING = 0.3                    # Chris: chosen on February to June, fixed before this work
MIN_BOOK_BTC = 1.0                 # Chris: load only when the open book holds at least 1 BTC
MARGIN = 0.25                      # Maksim: target loss ratio 0.80
CAP_PER_DIRECTION_USDC = 250_000   # Maksim: open protected notional per direction

OUTCOME_COLUMNS = ["closedAt", "realizedProfit_USDC"]  # outcomes: never read into the pricing data
SUBMISSION_COLUMNS = ["row", "createdAt", "optionType", "productType", "quantity_BTC", "strikePrice",
                      "apiBasePrice_per_BTC_USDC", "recommended_premium_USDC", "recommended_multiplier_vs_base",
                      "fair_value_USDC", "premium_frozen_model_USDC", "orderflow_loading"]
SUMMARY_KEYS = ["adopted", "decision", "frozen_sha256_matches", "submission_sha256", "rows",
                "premium_total_frozen", "premium_total_with_loading", "premium_total_final",
                "loaded_share", "mean_load_on_loaded", "revealed_ratio_frozen", "revealed_ratio_final",
                "cap_paused_share_orders", "cap_paused_share_premium"]
BOOK_COLUMNS = ["createdAt", "expirationDate", "optionType", "quantity_BTC"]


def find_repo_root(start: Path | None = None) -> Path:
    """The first parent folder that contains maksim/src; else the folder in the JV_REPO environment variable."""
    here = Path(start).resolve() if start else Path(__file__).resolve().parent
    for p in (here, *here.parents):
        if (p / "maksim" / "src").is_dir():
            return p
    env = os.environ.get("JV_REPO")
    if env and (Path(env) / "maksim" / "src").is_dir():
        return Path(env)
    raise FileNotFoundError("No repository root (a folder with maksim/src) above this folder. Set JV_REPO.")


def _use_maksim_code() -> None:
    """Put maksim/ on the import path, so that `src.*` and `run_extensions` import Maksim's code."""
    p = str(find_repo_root() / "maksim")
    if p not in sys.path:
        sys.path.insert(0, p)


def read_orders(path) -> pd.DataFrame:
    """Orders in file order, with a `row` number. Both timestamp formats are parsed. Outcome columns are dropped."""
    d = pd.read_csv(path)
    d = d.drop(columns=[c for c in OUTCOME_COLUMNS if c in d.columns])
    for c in ("createdAt", "expirationDate"):
        if c in d.columns:
            d[c] = pd.to_datetime(d[c], format="mixed")
    d.insert(0, "row", np.arange(len(d)))
    return d


def book_state(book_orders: pd.DataFrame, new_orders: pd.DataFrame) -> pd.DataFrame:
    """JV's open book just before each new order.

    An order is open at time t if it was created before t and expires after t. s_add = imb for a call and -imb for a
    put, where imb = (open call BTC - open put BTC) / (open call BTC + open put BTC). Positive s_add means the new order
    joins the larger side of the book.
    """
    created = book_orders["createdAt"].to_numpy("datetime64[ns]")
    expiry = book_orders["expirationDate"].to_numpy("datetime64[ns]")
    qty = book_orders["quantity_BTC"].to_numpy(float)
    call = book_orders["optionType"].to_numpy() == 0
    t = new_orders["createdAt"].to_numpy("datetime64[ns]")
    open_call, open_put = np.empty(len(t)), np.empty(len(t))
    for i, ti in enumerate(t):
        is_open = (created < ti) & (expiry > ti)
        open_call[i] = qty[is_open & call].sum()
        open_put[i] = qty[is_open & ~call].sum()
    total = open_call + open_put
    imb = np.divide(open_call - open_put, total, out=np.zeros_like(total), where=total > 0)
    s_add = np.where(new_orders["optionType"].to_numpy() == 0, imb, -imb)
    return pd.DataFrame({"open_call_btc": open_call, "open_put_btc": open_put, "book_btc": total,
                         "imb": imb, "s_add": s_add}, index=new_orders.index)


def orderflow_loading(s_add, book_btc, k: float = K_LOADING, min_book_btc: float = MIN_BOOK_BTC) -> np.ndarray:
    """Chris's loading: 1 + k x max(-s_add, 0) when the book holds at least min_book_btc, else 1. Never below 1."""
    s_add, book_btc = np.asarray(s_add, float), np.asarray(book_btc, float)
    return np.where(book_btc >= min_book_btc, 1.0 + k * np.maximum(-s_add, 0.0), 1.0)


def flat_factor(target_total: float, prices) -> float:
    """The single multiplier that brings the total of `prices` to `target_total`."""
    return float(target_total) / float(np.sum(prices))


def adoption_decision(profits: dict) -> dict:
    """The rule committed in README.md before scoring. All three conditions must hold to adopt the loading.

    profits[period][rule][strategy]: period "Jul" or "Feb-Jun"; rule "none" or "cons_e2";
    strategy "M", "M+L" or "Flat-M" (Flat-M is needed only for July under cons_e2).
    """
    def gain(p: dict) -> bool:
        return all(p[r]["M+L"] - p[r]["M"] > 0 for r in ("none", "cons_e2"))

    jul, feb_jun = profits["Jul"], profits["Feb-Jun"]
    c1, c2 = gain(jul), gain(feb_jun)
    c3 = jul["cons_e2"]["M+L"] >= jul["cons_e2"]["Flat-M"]
    return {"c1_july_gain": bool(c1), "c2_febjun_gain": bool(c2), "c3_july_beats_flat": bool(c3),
            "adopt": bool(c1 and c2 and c3)}


def build_submission(valid: pd.DataFrame, frozen: pd.DataFrame, loading, adopted: bool) -> pd.DataFrame:
    """One row per validation order, in the original order. Maksim's frozen premium is kept unchanged in its own
    column; the main column is frozen x loading only when the adoption rule passed."""
    lined_up = (len(valid) == len(frozen)
                and (valid["createdAt"].to_numpy() == frozen["createdAt"].to_numpy()).all()
                and np.allclose(valid["quantity_BTC"].to_numpy(float), frozen["quantity_BTC"].to_numpy(float)))
    if not lined_up:
        raise ValueError("The validation file and the frozen file do not line up row by row.")
    qty = valid["quantity_BTC"].to_numpy(float)
    loading = np.asarray(loading, float)
    frozen_premium = frozen["recommended_premium_USDC"].to_numpy(float)
    premium = np.round(frozen_premium * loading, 6) if adopted else frozen_premium  # USDC has 6 decimals
    sub = valid[SUBMISSION_COLUMNS[:7]].copy()
    sub["recommended_premium_USDC"] = premium
    sub["recommended_multiplier_vs_base"] = premium / (valid["apiBasePrice_per_BTC_USDC"].to_numpy(float) * qty)
    sub["fair_value_USDC"] = np.round(frozen["fair_value_per_BTC_USDC"].to_numpy(float) * qty, 6)
    sub["premium_frozen_model_USDC"] = frozen_premium
    sub["orderflow_loading"] = loading
    return sub[SUBMISSION_COLUMNS]


def price_blind_file(repo: Path, adopted: bool, valid_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Price every validation order: Maksim's frozen premium, times the order-flow loading when adopted.

    The open book before each validation order holds earlier training and validation orders that have not expired.
    Returns (submission, book state per validation order).
    """
    repo = Path(repo)
    train = read_orders(repo / "data" / "with_base_premium" / "pp_transactions_training.csv")
    valid = read_orders(valid_path or repo / "data" / "validation" / "pp_transactions_validation.csv")
    frozen = read_orders(repo / "maksim" / "outputs" / "validation_recommendations.csv")
    book = book_state(pd.concat([train[BOOK_COLUMNS], valid[BOOK_COLUMNS]], ignore_index=True), valid)
    loading = orderflow_loading(book["s_add"], book["book_btc"])
    return build_submission(valid, frozen, loading, adopted), book


def exposure_cap_accepts(orders: pd.DataFrame, cap: float = CAP_PER_DIRECTION_USDC) -> np.ndarray:
    """Maksim's exposure cap per direction (maksim/run_extensions.py). Each protection counts until its expiry, so no
    outcome is used. Returns True where the order would be accepted."""
    import polars as pl
    _use_maksim_code()
    from run_extensions import exposure_cap

    o = pl.DataFrame({"createdAt": orders["createdAt"].to_numpy("datetime64[ns]"),
                      "closedAt": orders["expirationDate"].to_numpy("datetime64[ns]"),  # expiry stands in for close
                      "optionType": orders["optionType"].to_numpy(),
                      "notional_USDC": orders["notional_USDC"].to_numpy(float)})
    return np.asarray(exposure_cap(o, cap), dtype=bool)


def moneyness_table(abs_move: float, spot: float, distances, margin: float = MARGIN) -> pd.DataFrame:
    """Fair value and premium per BTC when the strike moves out of the money, from Maksim's Black-Scholes pricer."""
    _use_maksim_code()
    from src.model import fair_value_per_btc

    def fv(strike: float, option_type: int) -> float:
        return float(fair_value_per_btc(np.array([abs_move]), np.array([strike]), np.array([option_type]),
                                        spot=np.array([spot]))[0])

    rows = []
    for side, option_type, sign in (("put", 1, -1.0), ("call", 0, 1.0)):
        at_the_money = fv(spot, option_type)
        for d in distances:
            value = fv(spot * (1.0 + sign * d), option_type)
            rows.append({"side": side, "otm_distance": d, "strike": spot * (1.0 + sign * d),
                         "fair_value_per_btc": value, "premium_per_btc": value * (1.0 + margin),
                         "vs_at_the_money": value / at_the_money})
    return pd.DataFrame(rows)


def revealed_price_ratio(valid: pd.DataFrame, premium) -> dict:
    """Our premium over JV's revealed price, quantity x (base + markup), on the rows that show a markup.
    A price-level check only: no outcome is used."""
    shown = (valid["markup_per_BTC_USDC"].notna() & valid["apiBasePrice_per_BTC_USDC"].notna()).to_numpy()
    jv = (valid["quantity_BTC"] * (valid["apiBasePrice_per_BTC_USDC"] + valid["markup_per_BTC_USDC"])).to_numpy(float)
    ours = np.asarray(premium, float)
    return {"rows": int(shown.sum()), "ratio": float(ours[shown].sum() / jv[shown].sum()),
            "jv_total": float(jv[shown].sum()), "our_total": float(ours[shown].sum())}
