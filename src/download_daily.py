from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from .wrds_utils import get_db, save_csv
from .config import RAW_DIR

def map_tickers_to_permno(db, tickers: list[str], on_date: date) -> pd.DataFrame:
    """
    Map a list of tickers to PERMNO using CRSP.STOCKNAMES at `on_date`.
    """
    # Normalize tickers upper
    tickers = [t.upper().strip() for t in tickers if t.strip()]
    sql = f"""
        select permno, ticker, namedt, nameenddt
        from crsp_a_stock.stocknames
        where upper(ticker) in ({",".join(["'"+t+"'" for t in tickers])})
          and namedt <= '{on_date:%Y-%m-%d}'
          and (nameenddt >= '{on_date:%Y-%m-%d}' or nameenddt is null)
    """
    df = db.raw_sql(sql, date_cols=["namedt","nameenddt"])
    if df.empty:
        return pd.DataFrame(columns=["ticker","permno"])
    # in case duplicates, keep latest namedt per ticker
    df = (df.sort_values(["ticker","namedt"])
            .groupby("ticker", as_index=False)
            .tail(1))
    return df[["ticker","permno"]]

def fetch_daily_window_for_permnos(db, permnos: list[int], years_back: int = 1) -> pd.DataFrame:
    """
    Download CRSP.dsf for the provided PERMNOs over the last `years_back` years.
    """
    end_dt = pd.to_datetime("2024-12-31").date()
    start_dt = pd.to_datetime(end_dt - pd.offsets.DateOffset(years=years_back)).date()

    sql = f"""
        select permno, date, abs(prc) as prc, vol, ret, shrout, hexcd
        from crsp_a_stock.dsf
        where permno in ({",".join(map(str, permnos))})
          and date between '{start_dt:%Y-%m-%d}' and '{end_dt:%Y-%m-%d}'
          and prc is not null and vol is not null
    """
    df = db.raw_sql(sql, date_cols=["date"])
    df = df[(df["prc"] > 0) & (df["vol"] > 0)].copy()
    return df

def main():
    ap = argparse.ArgumentParser(description="Download CRSP daily bars for a few tickers")
    ap.add_argument("--tickers", type=str, default="AAPL,MSFT")
    ap.add_argument("--years_back", type=int, default=1)
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    on_date = pd.to_datetime("2024-12-31").date()

    with get_db() as db:
        mapdf = map_tickers_to_permno(db, tickers, on_date)
        if mapdf.empty:
            raise SystemExit("No PERMNO mapping found for supplied tickers and date.")
        permnos = mapdf["permno"].astype(int).tolist()

        df = fetch_daily_window_for_permnos(db, permnos, years_back=args.years_back)

    # save one csv per ticker (merge by permno if multiple share classes)
    for t in tickers:
        p = mapdf.loc[mapdf["ticker"] == t, "permno"]
        if p.empty:
            continue
        sub = df[df["permno"] == p.iloc[0]].copy()
        out = Path(RAW_DIR) / f"{t}_dsf_{args.years_back}y.csv"
        save_csv(sub, out)
        print(f"{t}: {len(sub):,} rows to {out}")

if __name__ == "__main__":
    main()
