import argparse
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint
import statsmodels.api as sm

from .config import DEFAULT_START, DEFAULT_END, RAW_DIR, RESULTS_DIR, META_DIR, MIN_OVERLAP_DAYS

def load_price_series(ticker: str, start: str, end: str) -> pd.Series:
    """Load CRSP CSV for ticker and return a date-indexed price series within [start, end]."""
    f = RAW_DIR / f"{ticker}_dsf_1y.csv"
    if not f.exists():
        raise FileNotFoundError(f"Missing CSV for {ticker}: {f}")
    df = pd.read_csv(f, parse_dates=["date"])
    df = df.sort_values("date")
    df = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))]
    s = df.set_index("date")["prc"].astype(float)
    return s.replace([np.inf, -np.inf], np.nan).dropna()

def ols_beta_alpha(log_p1: pd.Series, log_p2: pd.Series) -> tuple[float, float]:
    """OLS regression: log(P1) ~ log(P2)"""
    X = sm.add_constant(log_p2.values)
    model = sm.OLS(log_p1.values, X, missing="drop").fit()
    alpha = float(model.params[0])
    beta = float(model.params[1])
    return beta, alpha

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, default=DEFAULT_START)
    ap.add_argument("--end", type=str, default=DEFAULT_END)
    ap.add_argument("--within_sector", type=int, default=0, help="1 to restrict pairs to same SIC2")
    ap.add_argument("--labels_date", type=str, default=DEFAULT_END, help="e.g. 2024-12-31 (required if within_sector=1)")
    args = ap.parse_args()

    tickers = [f.stem.split("_")[0] for f in RAW_DIR.glob("*_dsf_1y.csv")]
    
    sic2_map = {}
    if args.within_sector:
        if not args.labels_date:
            raise SystemExit("--labels_date is required when --within_sector=1 (run labels_crsp.py first)")
        lab_path = META_DIR / f"sic_map_{args.labels_date}.csv"
        if not lab_path.exists():
            raise SystemExit(f"Missing labels file: {lab_path}. Run: python -m src.labels_crsp --on {args.labels_date}")
        lab = pd.read_csv(lab_path)
        sic2_map = {r.ticker: int(r.sic2) if pd.notna(r.sic2) else None for _, r in lab.iterrows()}


    prices = {}
    for t in tickers:
        try:
            prices[t] = load_price_series(t, args.start, args.end)
        except FileNotFoundError:
            print(f"skipping {t}: CSV missing")
        except Exception as e:
            print(f"skipping {t}: {e}")

    tickers = [t for t in tickers if t in prices]
    pairs = []
    for i in range(len(tickers)):
        for j in range(i+1, len(tickers)):
            t1, t2 = tickers[i], tickers[j]
            if args.within_sector:
                s1 = sic2_map.get(t1); s2 = sic2_map.get(t2)
                if (s1 is None) or (s2 is None) or (s1 != s2):
                    continue
            
            s1, s2 = prices[t1], prices[t2]
            df = pd.concat([s1, s2], axis=1, keys=[t1, t2]).dropna()
            if len(df) < MIN_OVERLAP_DAYS:
                continue
            
            lp1 = np.log(df[t1])
            lp2 = np.log(df[t2])
            
            # Engle–Granger p-value
            try:
                _, pval, _ = coint(lp1, lp2)
            except Exception as e:
                print(f"Cointegration failed for {t1}-{t2}: {e}")
                continue
            
            # hedge ratio (beta) and intercept (alpha)
            try:
                beta, alpha = ols_beta_alpha(lp1, lp2)
            except Exception as e:
                print(f"OLS failed for {t1}-{t2}: {e}")
                continue
            
            pairs.append({
                "ticker1": t1,
                "ticker2": t2,
                "pval": pval,
                "beta": beta,
                "alpha": alpha,
                "n_obs": len(df)
            })

    out_df = pd.DataFrame(pairs).sort_values(["pval"], ascending=[True])
    save_path = RESULTS_DIR / "pairs.csv"
    out_df.to_csv(save_path, index=False)
    print(f"Saved pairs to {save_path}")

if __name__ == "__main__":
    main()
    