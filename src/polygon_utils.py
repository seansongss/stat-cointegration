from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from datetime import date, datetime, timedelta
import time

import pandas as pd
from tenacity import retry, wait_exponential, stop_after_attempt
from tqdm import tqdm

from polygon import RESTClient
from .config import POLYGON_API_KEY, MARKET_TZ, REGULAR_OPEN, REGULAR_CLOSE

# ---------- Client ----------
# list_* methods auto-paginate; limit is page size, not total rows.
_CLIENT = RESTClient(api_key=POLYGON_API_KEY)

# ---------- Helpers ----------
def _ensure_tz_aware(ts: pd.Timestamp) -> pd.Timestamp:
    if ts.tzinfo is None:
        return ts.tz_localize(MARKET_TZ)
    return ts.tz_convert(MARKET_TZ)

def trading_days_back(n: int, end: Optional[date] = None) -> list[date]:
    """Naive 'last n weekdays' (good enough for liquidity screen).
    You can swap to an exchange calendar later."""
    out: list[date] = []
    d = end or pd.Timestamp.today(tz=MARKET_TZ).date()
    while len(out) < n:
        d = d - timedelta(days=1)
        if pd.Timestamp(d).dayofweek < 5:
            out.append(d)
    return sorted(out)

def session_mask(series: pd.Series) -> pd.Series:
    t = series.dt.time
    return (t >= pd.Timestamp(REGULAR_OPEN).time()) & (t <= pd.Timestamp(REGULAR_CLOSE).time())

# ---------- Aggregates (1-minute) ----------
@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(6))
def fetch_minute_aggs(
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    adjusted: bool = True,
    limit: int = 50_000
) -> pd.DataFrame:
    """
    Fetch 1-minute aggregates using list_aggs (auto-pagination).
    - start/end can be naive (assumed MARKET_TZ) or tz-aware.
    - returns regular session only (09:30–16:00 ET) sorted by timestamp.
    """
    s = _ensure_tz_aware(pd.Timestamp(start))
    e = _ensure_tz_aware(pd.Timestamp(end))

    # list_aggs expects strings YYYY-MM-DD for minute data ranges
    rows = []
    for a in _CLIENT.list_aggs(
        ticker=ticker,
        multiplier=1,
        timespan="minute",
        from_=s.strftime("%Y-%m-%d"),
        to=e.strftime("%Y-%m-%d"),
        limit=limit,
        adjusted=adjusted,
    ):
        # a is a model with attributes: timestamp, open, high, low, close, volume, vwap, transactions
        rows.append({
            "ts": pd.to_datetime(a.timestamp, unit="ms", utc=True).tz_convert(MARKET_TZ),
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": a.volume,
            "vwap": getattr(a, "vwap", None),
            "trades": getattr(a, "transactions", None),
            "ticker": ticker
        })
    if not rows:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","vwap","trades","ticker"])

    df = pd.DataFrame(rows).sort_values("ts")
    # keep regular session (you can remove this filter if you want pre/post)
    return df.loc[session_mask(df["ts"])].reset_index(drop=True)

def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

# ---------- Grouped Daily (for ADDV) ----------
@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(6))
def fetch_grouped_daily_ohclv(day: date, adjusted: bool = True, include_otc: bool = False) -> pd.DataFrame:
    """
    Return daily OHLCV for the entire market for 'day'.
    We’ll filter to our universe later.
    """
    resp = _CLIENT.get_grouped_daily_aggs(
        date=day,
        adjusted=adjusted,
        include_otc=include_otc
    )
    # resp has .results list of dicts with keys like T (ticker), o,h,l,c,v,vw,n
    if not getattr(resp, "results", None):
        return pd.DataFrame(columns=["ticker","date","open","high","low","close","volume","vwap","transactions"])
    r = []
    for x in resp.results:
        r.append({
            "ticker": x.get("T"),
            "date": pd.to_datetime(day).date(),
            "open": x.get("o"),
            "high": x.get("h"),
            "low":  x.get("l"),
            "close": x.get("c"),
            "volume": x.get("v"),
            "vwap": x.get("vw"),
            "transactions": x.get("n")
        })
    return pd.DataFrame(r)

def compute_addv60(tickers: Iterable[str], n_days: int = 60) -> pd.DataFrame:
    """
    For the provided tickers, compute 60-day average daily dollar volume (ADDV).
    Uses one Grouped Daily call per day (efficient on free tier).
    """
    days = trading_days_back(n_days)
    frames: list[pd.DataFrame] = []
    for d in tqdm(days, desc="GroupedDaily"):
        df = fetch_grouped_daily_ohclv(d, adjusted=True)
        if df.empty:
            continue
        df = df[df["ticker"].isin(set(tickers))].copy()
        if df.empty:
            continue
        df["dollar_vol"] = (df["close"] or 0) * (df["volume"] or 0)
        frames.append(df[["ticker","date","dollar_vol"]])
        time.sleep(1)  # Add a 1-second delay between requests
    if not frames:
        return pd.DataFrame(columns=["ticker","ADDV_60d"])
    adv = (pd.concat(frames)
             .groupby("ticker", as_index=False)["dollar_vol"]
             .mean()
             .rename(columns={"dollar_vol":"ADDV_60d"}))
    return adv

# ---------- Utilities ----------
def normalize_polygon_ticker(t: str) -> str:
    """
    Polygon expects share-class separators as '.' per SIP conventions.
    Convert any dashes to dots; keep dots as-is.
    """
    return t.replace("-", ".").strip().upper()
