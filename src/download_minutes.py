from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

from .config import RAW_DIR
from .polygon_utils import fetch_minute_aggs, save_parquet

def download_for(ticker: str, days: int):
    end = pd.Timestamp.today(tz="America/New_York").normalize()
    start = end - pd.Timedelta(days=days)
    df = fetch_minute_aggs(ticker, start, end, adjusted=True)
    out = Path(RAW_DIR) / f"{ticker}_{start.date()}_{end.date()}.parquet"
    save_parquet(df, out)
    print(f"[minutes] {ticker}: {len(df):,} rows → {out}")

def main():
    ap = argparse.ArgumentParser(description="Download 1‑minute bars for a few tickers")
    ap.add_argument("--tickers", type=str, default="KO,PEP")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    for t in tickers:
        download_for(t, args.days)

if __name__ == "__main__":
    main()
