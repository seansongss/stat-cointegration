from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from .config import META_DIR
from .polygon_utils import compute_addv60, normalize_polygon_ticker

# --- 1) S&P 500 snapshot (Wikipedia) ---
def get_sp500_snapshot() -> pd.DataFrame:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0].copy()
    df.rename(columns={"Symbol":"ticker","Security":"name","GICS Sector":"sector"}, inplace=True)
    # Normalize to Polygon’s ticker style
    df["ticker"] = df["ticker"].astype(str).apply(normalize_polygon_ticker)
    df["snapshot_date"] = pd.Timestamp.today(tz="America/Toronto").date()
    return df[["ticker","name","sector","snapshot_date"]]

def cmd_snapshot() -> Path:
    snap = get_sp500_snapshot()
    out = Path(META_DIR) / "sp500_snapshot.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    snap.to_csv(out, index=False)
    print(f"[snapshot] saved {len(snap)} tickers → {out}")
    return out

# --- 2) ADDV60 for S&P tickers ---
def cmd_addv(days: int = 60) -> Path:
    snap_path = Path(META_DIR) / "sp500_snapshot.csv"
    if not snap_path.exists():
        raise FileNotFoundError("Run: python -m src.universe snapshot")
    snap = pd.read_csv(snap_path)
    addv = compute_addv60(snap["ticker"].tolist(), n_days=days)
    out = Path(META_DIR) / f"sp500_addv{days}.csv"
    addv.to_csv(out, index=False)
    print(f"[addv] saved {len(addv)} rows → {out}")
    return out

# --- 3) Finalize trading universe ---
def cmd_finalize(top: int = 300, days: int = 60) -> Path:
    snap_path = Path(META_DIR) / "sp500_snapshot.csv"
    addv_path = Path(META_DIR) / f"sp500_addv{days}.csv"
    if not snap_path.exists():
        raise FileNotFoundError("Run: python -m src.universe snapshot")
    if not addv_path.exists():
        raise FileNotFoundError(f"Run: python -m src.universe addv --days {days}")
    snap = pd.read_csv(snap_path)
    addv = pd.read_csv(addv_path)
    uni = (snap.merge(addv, on="ticker", how="left")
               .sort_values("ADDV_60d", ascending=False)
               .head(top)
               .reset_index(drop=True))
    out = Path(META_DIR) / f"universe_top{top}.csv"
    uni.to_csv(out, index=False)
    print(f"[universe] saved top {top} by ADDV → {out}")
    return out

# --- CLI ---
def main():
    p = argparse.ArgumentParser(description="Universe builder (Polygon.io + Wikipedia S&P snapshot)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("snapshot", help="Fetch S&P 500 snapshot from Wikipedia")
    s2 = sub.add_parser("addv", help="Compute 60D ADDV from Polygon Grouped Daily")
    s2.add_argument("--days", type=int, default=60)
    s3 = sub.add_parser("finalize", help="Finalize universe (top N by ADDV)")
    s3.add_argument("--top", type=int, default=300)
    s3.add_argument("--days", type=int, default=60)

    s4 = sub.add_parser("smoke", help="Do all steps quickly")
    s4.add_argument("--top", type=int, default=20)
    s4.add_argument("--days", type=int, default=30)

    args = p.parse_args()
    if args.cmd == "snapshot":
        cmd_snapshot()
    elif args.cmd == "addv":
        cmd_addv(args.days)
    elif args.cmd == "finalize":
        cmd_finalize(args.top, args.days)
    elif args.cmd == "smoke":
        cmd_snapshot()
        cmd_addv(args.days)
        cmd_finalize(args.top, args.days)

if __name__ == "__main__":
    main()
