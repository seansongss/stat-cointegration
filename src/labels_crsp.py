import argparse
from pathlib import Path
import pandas as pd

from .config import RAW_DIR, META_DIR
from .wrds_utils import get_db

def fetch_labels(db, tickers: list[str], on_date: str) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame(columns=["ticker","permno","siccd","exchcd","shrcd"])

    tickers_sql = ",".join("'" + t.upper() + "'" for t in tickers)
    sql = f"""
        SELECT permno, ticker, siccd, exchcd, shrcd, namedt, nameendt
        FROM crsp_a_stock.dsenames
        WHERE upper(ticker) IN ({tickers_sql})
          AND namedt <= '{on_date}'
          AND (nameendt IS NULL OR nameendt >= '{on_date}')
          AND ticker IS NOT NULL
    """
    df = db.raw_sql(sql, date_cols=["namedt","nameendt"])
    if df.empty:
        return pd.DataFrame(columns=["ticker","permno","siccd","exchcd","shrcd"])
    # keep most recent namedt per ticker
    df = (df.sort_values(["ticker","namedt"])
            .groupby("ticker", as_index=False)
            .tail(1))
    df = df[["ticker","permno","siccd","exchcd","shrcd"]].copy()
    df["sic2"] = (df["siccd"] // 100).astype("Int64")
    return df

def main():
    ap = argparse.ArgumentParser(description="Fetch SIC/EXCHCD/SHRCD labels for CSV tickers at a snapshot date")
    ap.add_argument("--on", type=str, required=True, help="Snapshot date like 2024-12-31")
    args = ap.parse_args()

    tickers = [f.stem.split("_")[0] for f in RAW_DIR.glob("*_dsf_1y.csv")]
    if not tickers:
        raise SystemExit("No *_dsf_1y.csv files found in data/raw/. Run `make download` first.")

    with get_db() as db:
        lab = fetch_labels(db, tickers, args.on)

    out = META_DIR / f"sic_map_{args.on}.csv"
    lab.to_csv(out, index=False)
    print(f"Saved labels to {out} (tickers={len(lab)})")

if __name__ == "__main__":
    main()
