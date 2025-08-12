from __future__ import annotations
from typing import Optional
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import wrds

from .config import (
    WRDS_USERNAME, WRDS_POSTGRES_HOST, WRDS_POSTGRES_PORT,
    META_DIR, VALID_EXCHCD, VALID_SHRCD
)

# ---------- WRDS connection ----------
def get_db() -> wrds.Connection:
    """
    Open a WRDS connection. If env variables are absent, wrds will
    prompt for username/password or use ~/.pgpass.
    """
    if WRDS_USERNAME:
        return wrds.Connection(
            wrds_username=WRDS_USERNAME,
            host=WRDS_POSTGRES_HOST,
            port=WRDS_POSTGRES_PORT
        )
    return wrds.Connection()  # interactive/persisted credentials

# ---------- date helpers ----------
def previous_business_day(d: Optional[date] = None) -> date:
    d = d or date.today()
    # walk back to last weekday
    while d.weekday() >= 5:  # 5,6 = Sat/Sun
        d -= timedelta(days=1)
    return d

def endpoints_for_days(end_dt: date, days: int) -> tuple[date, date]:
    # Overshoot by ~120 calendar days; filter to trading days later
    start_dt = end_dt - timedelta(days=max(80, int(days*2)))
    return start_dt, end_dt

# ---------- fetch CRSP daily window ----------
def fetch_crsp_dsf_window(db: wrds.Connection, start_dt: date, end_dt: date, debug: bool = False) -> pd.DataFrame:
    """
    Pull a compact window from CRSP daily, filtering to common stocks (shrcd 10/11)
    on NYSE/AMEX/NASDAQ (exchcd 1/2/3), by joining to DSENAMES on valid date ranges.
    If the classic 'crsp' schema returns nothing, automatically try 'crspq'.
    """
    def run_sql(schema: str) -> pd.DataFrame:
        sql = f"""
            SELECT
                d.permno,
                d.date,
                ABS(d.prc) AS prc,
                d.vol,
                d.ret,
                d.shrout,
                n.exchcd,
                n.shrcd
            FROM {schema}.dsf AS d
            JOIN {schema}.dsenames AS n
                ON n.permno = d.permno
                AND n.namedt <= d.date
                AND (n.nameendt IS NULL OR n.nameendt >= d.date)
            WHERE d.date BETWEEN '{start_dt:%Y-%m-%d}' AND '{end_dt:%Y-%m-%d}'
                AND n.exchcd IN (1,2,3)
                AND n.shrcd  IN (10,11)
                AND d.prc IS NOT NULL
                AND d.vol IS NOT NULL
        """
        df = db.raw_sql(sql, date_cols=["date"])
        if not df.empty:
            df = df[(df["prc"] > 0) & (df["vol"] > 0)].copy()
        return df

    # Try classic CRSP
    df = run_sql("crsp_a_stock")

    return df

# ---------- map PERMNO -> ticker at a given date ----------
def fetch_crsp_tickers_at(db: wrds.Connection, on_date: date) -> pd.DataFrame:
    """
    Get the ticker valid on 'on_date' for each PERMNO using CRSP.STOCKNAMES.
    """
    sql = f"""
        select
            permno,
            ticker,
            namedt,
            nameenddt
        from crsp.stocknames
        where namedt <= '{on_date:%Y-%m-%d}'
          and (nameenddt >= '{on_date:%Y-%m-%d}' or nameenddt is null)
          and ticker is not null
    """
    names = db.raw_sql(sql, date_cols=["namedt","nameenddt"])
    # deduplicate by choosing latest namedt per permno if multiple rows
    names = (names.sort_values(["permno","namedt"])
                  .groupby("permno", as_index=False)
                  .tail(1))
    return names[["permno","ticker"]]

# ---------- persist helpers ----------
def save_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path

def save_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path
