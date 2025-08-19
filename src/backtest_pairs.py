import pandas as pd
import numpy as np
import argparse
import statsmodels.api as sm

from .config import (
    RAW_DIR, RESULTS_DIR,
    DEFAULT_START, DEFAULT_END,
    LOOKBACK, ENTRY_Z, EXIT_Z, TIME_STOP_DAYS,
    COST_BPS, TOP_PAIRS_FOR_BACKTEST,
    BACKTEST_PAIRS
)

# 1 bps = 0.01%
BPS = 1e-4

def load_log_price(ticker: str, start: str, end: str) -> pd.Series:
    f = RAW_DIR / f"{ticker}_dsf_1y.csv"
    df = pd.read_csv(f, parse_dates=["date"]).sort_values("date")
    df = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))]
    s = df.set_index("date")["prc"].astype(float)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return np.log(s)

def backtest_pair_row(row: pd.Series,
                      start: str, end: str,
                      lookback: int, entry_z: float, exit_z: float,
                      time_stop_days: int, cost_bps: float) -> dict:
    t1, t2 = row.ticker1, row.ticker2
    beta, alpha = float(row.beta), float(row.alpha)

    lp1 = load_log_price(t1, start, end)
    lp2 = load_log_price(t2, start, end)
    df = pd.concat([lp1, lp2], axis=1, keys=["lp1","lp2"]).dropna()
    if len(df) < lookback + 5:
        raise ValueError("not enough data")

    # cointegration spread residual: x_t = logP1 - (alpha + beta*logP2)
    spread = df["lp1"] - (alpha + beta * df["lp2"])

    mu = spread.rolling(lookback, min_periods=lookback//2).mean()
    sd = spread.rolling(lookback, min_periods=lookback//2).std(ddof=1).replace(0, np.nan)
    z = (spread - mu) / sd
    z = z.dropna()

    # positions: +1 = long spread (long t1, short beta*t2), -1 = short spread
    pos = pd.Series(0, index=z.index, dtype=float)

    in_pos = 0
    entry_date = None
    for dt, zval in z.items():
        if in_pos == 0:
            if zval <= -entry_z:
                in_pos = +1
                entry_date = dt
                pos.loc[dt] = +1
            elif zval >= entry_z:
                in_pos = -1
                entry_date = dt
                pos.loc[dt] = -1
        else:
            # exit rules
            hold_days = (dt - entry_date).days if entry_date else 0
            if abs(zval) <= exit_z or (time_stop_days and hold_days >= time_stop_days):
                in_pos = 0
                entry_date = None
                pos.loc[dt] = 0
            else:
                pos.loc[dt] = pos.loc[pos.index[pos.index.get_loc(dt)-1]]  # carry

    pos = pos.ffill().reindex(df.index).fillna(0.0)

    # daily PnL approximation: change in spread * position_{t-1}
    spread_diff = spread.diff()
    gross_ret = (pos.shift(1) * spread_diff).fillna(0.0)

    # trading cost: whenever |pos_t - pos_{t-1}| > 0
    # cost per transition (per leg) ~ cost_bps; two legs (long+short). Flip = close+open = 4 legs.
    pos_change = (pos - pos.shift(1)).fillna(pos)  # first day = opening if not zero
    transition = pos_change.abs()
    # 0->+1/-1 or +1/-1->0 => 2 legs; +1->-1 or -1->+1 => 4 legs
    legs = transition.copy()
    legs[(pos.shift(1)==0) & (pos!=0)] = 2.0
    legs[(pos.shift(1)!=0) & (pos==0)] = 2.0
    legs[(pos.shift(1)==1) & (pos==-1)] = 4.0
    legs[(pos.shift(1)==-1) & (pos==1)] = 4.0
    cost = legs * (cost_bps * BPS)

    net_ret = gross_ret - cost

    ann_ret = net_ret.mean() * 252
    ann_vol = net_ret.std(ddof=1) * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    trades = int((transition > 0).sum())

    return {
        "t1": t1, "t2": t2,
        "beta": beta, "alpha": alpha,
        "n_obs": int(len(df)),
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "trades": trades
    }

def main():
    parser = argparse.ArgumentParser(description='Daily pairs backtest (cointegration spread)')
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end",   default=DEFAULT_END)
    parser.add_argument("--lookback", type=int, default=LOOKBACK)
    parser.add_argument("--entry", type=float, default=ENTRY_Z)
    parser.add_argument("--exit",  type=float, default=EXIT_Z)
    parser.add_argument("--time_stop", type=int, default=TIME_STOP_DAYS)
    parser.add_argument("--cost_bps", type=float, default=COST_BPS)
    parser.add_argument("--max_pairs", type=int, default=TOP_PAIRS_FOR_BACKTEST)
    parser.add_argument("--tickers", type=str, default="")
    parser.add_argument("--pairs", type=str, default="")
    args = parser.parse_args()
    
    pairs_df = None
    pairs = []
    
    if args.pairs:
        pairs = [tuple(x.split(",")) for x in args.pairs.split(";") if x]
    elif args.tickers:
        T = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        for i in range(len(T)):
            for j in range(i+1, len(T)):
                pairs.append((T[i], T[j]))
    elif BACKTEST_PAIRS:
        pairs = BACKTEST_PAIRS
    else:
        # default: use top pairs from results/pairs.csv (lowest pval)
        pairs_df = pd.read_csv(RESULTS_DIR / "pairs.csv")
        pairs_df = pairs_df.sort_values("pval").head(args.max_pairs)

    rows = []
    if pairs_df is not None:
        for _, r in pairs_df.iterrows():
            try:
                res = backtest_pair_row(r, args.start, args.end, args.lookback, args.entry, args.exit, args.time_stop, args.cost_bps)
                rows.append(res)
                print(f"{r.ticker1}-{r.ticker2}: Sharpe {res['sharpe']:.2f}, trades {res['trades']}")
            except Exception as e:
                print(f"[WARN] backtest failed for {r.ticker1}-{r.ticker2}: {e}")
    else:
        # Estimate beta/alpha
        # quick OLS on the whole period for these specific pairs
        for (t1, t2) in pairs[:args.max_pairs]:
            try:
                # estimate beta/alpha
                lp1 = load_log_price(t1, args.start, args.end)
                lp2 = load_log_price(t2, args.start, args.end)
                df = pd.concat([lp1, lp2], axis=1, keys=["lp1","lp2"]).dropna()
                if len(df) < LOOKBACK + 5:
                    raise ValueError("not enough data")
                X = sm.add_constant(df["lp2"].values)
                model = sm.OLS(df["lp1"].values, X).fit()
                alpha = float(model.params[0]); beta = float(model.params[1])
                r = pd.Series({"ticker1": t1, "ticker2": t2, "alpha": alpha, "beta": beta})
                res = backtest_pair_row(r, args.start, args.end, args.lookback, args.entry, args.exit, args.time_stop, args.cost_bps)
                rows.append(res)
                print(f"{t1}-{t2}: Sharpe {res['sharpe']:.2f}, trades {res['trades']}")
            except Exception as e:
                print(f"[WARN] backtest failed for {t1}-{t2}: {e}")

    out_df = pd.DataFrame(rows)
    save_path = RESULTS_DIR / "backtest_results.csv"
    out_df.to_csv(save_path, index=False)
    if not out_df.empty:
        print(f"Saved backtest results → {save_path}")
        print(f"Tested {len(out_df)} pairs, avg sharpe: {out_df['sharpe'].mean():.4f}")

if __name__ == "__main__":
    main()
