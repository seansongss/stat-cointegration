import argparse
import pandas as pd
from statsmodels.tsa.stattools import coint
from .config import RAW_DIR, RESULTS_DIR

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, required=True)
    ap.add_argument("--end", type=str, required=True)
    args = ap.parse_args()

    tickers = [f.stem.split("_")[0] for f in RAW_DIR.glob("*.csv")]
    prices = {}
    for t in tickers:
        df = pd.read_csv(RAW_DIR / f"{t}_dsf_1y.csv", parse_dates=["date"])
        mask = (df["date"] >= args.start) & (df["date"] <= args.end)
        prices[t] = df.loc[mask].set_index("date")["prc"]

    tickers = list(prices.keys())
    pairs = []
    for i in range(len(tickers)):
        for j in range(i+1, len(tickers)):
            t1, t2 = tickers[i], tickers[j]
            s1, s2 = prices[t1], prices[t2]
            if len(s1) != len(s2): continue
            score, pval, _ = coint(s1, s2)
            pairs.append((t1, t2, pval))

    out_df = pd.DataFrame(pairs, columns=["ticker1", "ticker2", "pval"]).sort_values("pval")
    save_path = RESULTS_DIR / "pairs.csv"
    out_df.to_csv(save_path, index=False)
    print(f"Saved pairs to {save_path}")

if __name__ == "__main__":
    main()
    