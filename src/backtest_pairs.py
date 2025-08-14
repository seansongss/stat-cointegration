import pandas as pd
import numpy as np
import argparse
from .config import (
    RAW_DIR, RESULTS_DIR, BACKTEST_PAIRS
)

def backtest_pair(t1, t2, start, end, zscore_threshold=2.0):
    df1 = pd.read_csv(RAW_DIR / f"{t1}_dsf_1y.csv", parse_dates=["date"]).set_index("date")
    df2 = pd.read_csv(RAW_DIR / f"{t2}_dsf_1y.csv", parse_dates=["date"]).set_index("date")
    df = pd.concat([df1["prc"], df2["prc"]], axis=1, keys=[t1, t2])
    df = df.loc[start:end].dropna()

    spread = df[t1] - df[t2]
    zscore = (spread - spread.mean()) / spread.std()

    position = np.where(zscore > zscore_threshold, -1, np.where(zscore < -zscore_threshold, 1, 0))
    ret = position[:-1] * (spread.diff().shift(-1)[:-1])
    return np.nanmean(ret) * 252, np.nanstd(ret) * np.sqrt(252), np.nansum(ret)

def main():
    parser = argparse.ArgumentParser(description='Backtest pairs trading strategy')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to test')
    parser.add_argument('--pairs', nargs='+', help='Specific pairs to test (format: TICKER1,TICKER2)')
    
    args = parser.parse_args()
    
    if args.tickers:
        # Generate pairs from ticker list
        tickers = args.tickers
        pairs = []
        for i in range(len(tickers)):
            for j in range(i+1, len(tickers)):
                pairs.append((tickers[i], tickers[j]))
        print(f"Generated {len(pairs)} pairs from {len(tickers)} tickers")
    elif args.pairs:
        # Use specific pairs
        pairs = [tuple(pair.split(',')) for pair in args.pairs]
        print(f"Using {len(pairs)} specified pairs")
    else:
        # Use config default
        if BACKTEST_PAIRS:
            pairs = BACKTEST_PAIRS
            print(f"Using {len(pairs)} pairs from config")
        else:
            # Fall back to reading from pairs.csv
            pairs_df = pd.read_csv(RESULTS_DIR / "pairs.csv").head(args.max_pairs)
            pairs = [(row.ticker1, row.ticker2) for _, row in pairs_df.iterrows()]
            print(f"Using {len(pairs)} pairs from pairs.csv")
    
    results = []
    for t1, t2 in pairs[:args.max_pairs]:
        try:
            mean_ret, vol, total = backtest_pair(t1, t2, args.start, args.end, args.zscore)
            sharpe = mean_ret / vol if vol != 0 else 0
            results.append((t1, t2, mean_ret, sharpe, total))
            print(f"{t1}-{t2}: {mean_ret:.4f} return, {sharpe:.4f} sharpe")
        except Exception as e:
            print(f"Failed to backtest {t1}-{t2}: {e}")
            continue

    if results:
        out_df = pd.DataFrame(results, columns=["t1", "t2", "ann_return", "sharpe", "total_return"])
        save_path = RESULTS_DIR / "backtest_results.csv"
        out_df.to_csv(save_path, index=False)
        print(f"Saved backtest results → {save_path}")
        print(f"Tested {len(results)} pairs, avg sharpe: {out_df['sharpe'].mean():.4f}")
    else:
        print("No successful backtests completed")

if __name__ == "__main__":
    main()
