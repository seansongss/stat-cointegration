from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .config import META_DIR
from .wrds_utils import (
    get_db, previous_business_day, endpoints_for_days,
    fetch_crsp_dsf_window, fetch_crsp_tickers_at, save_csv
)

def build_universe(end: str | None, days: int, top: int) -> Path:
    """
    Build a Top-N universe by ADDV over the last `days` trading days,
    ending at `end` (YYYY-MM-DD or "AUTO" for previous business day).
    """
    # Resolve end date
    if not end or end.upper() == "AUTO":
        end_dt = previous_business_day()
    else:
        end_dt = pd.to_datetime(end).date()

    start_dt, end_dt = endpoints_for_days(end_dt, days)

    with get_db() as db:
        # 1) Pull CRSP daily window
        print(f"[CRSP] Loading dsf from {start_dt} to {end_dt} ...")
        df = fetch_crsp_dsf_window(db, start_dt, end_dt, debug=True)
        if df.empty:
            raise RuntimeError("No CRSP data returned — check WRDS permissions or date range.")

        # 2) Keep only the last `days` distinct market dates
        trading_days = sorted(df["date"].unique())
        if len(trading_days) < days:
            print(f"[WARN] Only {len(trading_days)} trading days in window; using all available.")
            recent_days = trading_days
        else:
            recent_days = trading_days[-days:]

        df = df[df["date"].isin(recent_days)].copy()
        df["dollar_vol"] = df["prc"] * df["vol"]

        # 3) Compute ADDV per PERMNO & require decent coverage (>= 40 days present)
        coverage = df.groupby("permno")["date"].nunique().rename("days_present")
        addv = (df.groupby("permno")["dollar_vol"]
                  .mean()
                  .rename("ADDV_60d")
                  .to_frame()
                  .join(coverage, how="left")
                  .reset_index())
        addv = addv[addv["days_present"] >= min(40, days)].copy()

        # 4) Map PERMNO → ticker valid on end_dt
        print(f"[CRSP] Mapping PERMNO → ticker at {end_dt} ...")
        tmap = fetch_crsp_tickers_at(db, end_dt)

    uni = (addv.merge(tmap, on="permno", how="left")
               .sort_values("ADDV_60d", ascending=False)
               .head(top))

    # 5) Save outputs (snapshot date embedded)
    snap = pd.DataFrame({
        "snapshot_end_date": [end_dt],
        "days_lookback": [days],
        "universe_size": [len(uni)]
    })
    snap_path = Path(META_DIR) / f"snapshot_meta_{end_dt}.csv"
    uni_path  = Path(META_DIR) / f"universe_top{top}_{end_dt}.csv"

    snap.to_csv(snap_path, index=False)
    uni.to_csv(uni_path, index=False)

    print(f"Universe saved to {uni_path}  (meta to {snap_path})")
    return uni_path

def main():
    ap = argparse.ArgumentParser(description="Build universe from CRSP (WRDS)")
    ap.add_argument("--end",  type=str, default="AUTO", help="'YYYY-MM-DD' or 'AUTO' for prev biz day")
    ap.add_argument("--days", type=int, default=60,      help="lookback trading days for ADDV")
    ap.add_argument("--top",  type=int, default=300,     help="top N by ADDV")
    ap.add_argument("cmd", nargs="?", default="build",   help="only 'build' supported")
    args = ap.parse_args()

    if args.cmd != "build":
        ap.error("only 'build' supported")

    build_universe(args.end, args.days, args.top)

if __name__ == "__main__":
    main()
