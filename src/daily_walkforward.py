import argparse
from pathlib import Path
from dataclasses import dataclass
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
import statsmodels.api as sm

from .config import (
    RAW_DIR, RESULTS_DIR, META_DIR,
    DEFAULT_START, DEFAULT_END, FORMATION, TRADE,
    LOOKBACK, ENTRY_Z, EXIT_Z, TIME_STOP_DAYS,
    COST_BPS, MIN_OVERLAP_DAYS,
    PVAL_MAX, MIN_LOG_CORR, BETA_MIN, BETA_MAX, MIN_SIGMA_DIFF
)


BPS = 1e-4

def load_log_price(ticker: str, start: str, end: str) -> pd.Series:
    f = RAW_DIR / f"{ticker}_dsf_1y.csv"
    if not f.exists():
        raise FileNotFoundError(f"Missing CSV for {ticker}: {f}")
    df = pd.read_csv(f, parse_dates=["date"]).sort_values("date")
    df = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))]
    s = df.set_index("date")["prc"].astype(float)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return np.log(s)

def eg_beta_alpha(lp1: pd.Series, lp2: pd.Series) -> tuple[float,float,float]:
    """Return (pval, beta, alpha) on aligned formation window."""
    X = sm.add_constant(lp2.values)
    model = sm.OLS(lp1.values, X).fit()
    alpha = float(model.params[0])
    beta = float(model.params[1])
    pval = coint(lp1, lp2)[1]
    return pval, beta, alpha

@dataclass
class PairSpec:
    t1: str
    t2: str
    alpha: float
    beta: float
    sigma_spread: float
    sigma_diff: float
    weight: float = 0.0

def generate_pair_returns(spec: PairSpec,
                          lp1: pd.Series, lp2: pd.Series,
                          start_trade: pd.Timestamp, end_trade: pd.Timestamp,
                          lookback: int, entry_z: float, exit_z: float,
                          time_stop_days: int, cost_bps: float) -> pd.Series:
    df = pd.concat([lp1, lp2], axis=1, keys=["lp1","lp2"]).dropna()
    spread = df["lp1"] - (spec.alpha + spec.beta * df["lp2"])

    mu = spread.rolling(lookback, min_periods=lookback//2).mean().shift(1)
    sd = spread.rolling(lookback, min_periods=lookback//2).std(ddof=1).replace(0, np.nan).shift(1)
    z = ((spread - mu) / sd).dropna()

    z = z.loc[(z.index >= start_trade) & (z.index <= end_trade)]
    if z.empty:
        return pd.Series(dtype=float)

    pos = pd.Series(0.0, index=z.index)
    in_pos = 0
    entry_date = None
    for dt, zval in z.items():
        if in_pos == 0:
            if zval <= -entry_z:
                in_pos = +1; entry_date = dt; pos.loc[dt] = +1
            elif zval >= entry_z:
                in_pos = -1; entry_date = dt; pos.loc[dt] = -1
            else:
                pos.loc[dt] = 0
        else:
            hold_days = (dt - entry_date).days if entry_date else 0
            if abs(zval) <= exit_z or (time_stop_days and hold_days >= time_stop_days):
                in_pos = 0; entry_date = None; pos.loc[dt] = 0
            else:
                pos.loc[dt] = pos.shift(1).loc[dt]

    pos = pos.reindex(spread.index).ffill().fillna(0.0)
    pos = pos.loc[(pos.index >= start_trade) & (pos.index <= end_trade)]

    spread_diff = spread.diff()
    gross = (pos.shift(1) * spread_diff).reindex(pos.index).fillna(0.0)

    pos_change = (pos - pos.shift(1)).fillna(pos)
    transition = pos_change.abs()
    legs = transition.copy()
    legs[(pos.shift(1)==0) & (pos!=0)] = 2.0
    legs[(pos.shift(1)!=0) & (pos==0)] = 2.0
    legs[(pos.shift(1)==1) & (pos==-1)] = 4.0
    legs[(pos.shift(1)==-1) & (pos==1)] = 4.0
    cost = legs * (cost_bps * BPS)

    net = gross - cost
    return net * spec.weight

def main():
    print("Starting walk-forward backtest...")
    p = argparse.ArgumentParser(description="Walk-forward daily pairs backtest")
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end",   default=DEFAULT_END)
    p.add_argument("--formation", type=int, default=FORMATION)
    p.add_argument("--trade",     type=int, default=TRADE)
    p.add_argument("--lookback",  type=int, default=LOOKBACK)
    p.add_argument("--entry",     type=float, default=ENTRY_Z)
    p.add_argument("--exit",      type=float, default=EXIT_Z)
    p.add_argument("--time_stop", type=int, default=TIME_STOP_DAYS)
    p.add_argument("--cost_bps",  type=float, default=COST_BPS)
    p.add_argument("--within_sector", type=int, default=0)
    p.add_argument("--labels_date",   type=str, default=DEFAULT_END)
    args = p.parse_args()

    tickers = [q.stem.split("_")[0] for q in Path(RAW_DIR).glob("*_dsf_1y.csv")]
    print(f"Loaded tickers: {tickers}")
    
    # Whitelist from pairs.csv
    allowed_pairs = None
    try:
        pairs_df = pd.read_csv(RESULTS_DIR / "pairs.csv")
        if {"ticker1","ticker2"}.issubset(pairs_df.columns):
            if "pval" in pairs_df.columns:
                pairs_df = pairs_df[pairs_df["pval"] <= PVAL_MAX].copy()
            allowed_pairs = {
                tuple(sorted((str(r["ticker1"]).upper(), str(r["ticker2"]).upper())))
                for _, r in pairs_df.iterrows()
            }
            print(f"'pairs.csv' whitelist loaded: {len(allowed_pairs)} pairs (p ≤ {PVAL_MAX})")
        else:
            print(f"'pairs.csv' missing ticker1/ticker2; ignoring whitelist")
    except Exception as e:
        print(f"'pairs.csv' failed to read: {e}")

    # sector map
    sic2_map = {}
    if args.within_sector:
        lab_path = META_DIR / f"sic_map_{args.labels_date}.csv"
        if not lab_path.exists():
            raise SystemExit(f"Missing labels file: {lab_path}. Run: python -m src.labels_crsp --on {args.labels_date}")
        lab = pd.read_csv(lab_path)
        sic2_map = {r.ticker: int(r.sic2) if pd.notna(r.sic2) else None for _, r in lab.iterrows()}
    
    # Load log prices for entire period once
    lp = {}
    for t in tickers:
        lp[t] = load_log_price(t, args.start, args.end)

    # union calendar is fine; we align pairs with dropna in formation step
    all_dates = sorted(set().union(*[s.index for s in lp.values()]))
    if len(all_dates) < args.formation + args.trade + 5:
        raise SystemExit("Not enough overlapping dates for selected tickers / period.")
    dates = pd.DatetimeIndex(all_dates)

    # Walk-forward cycles
    equity = []
    per_pair_stats = {}
    cycles = 0

    i = args.formation
    while i + args.trade <= len(dates):
        form_start = dates[i - args.formation]
        form_end   = dates[i - 1]
        trade_start = dates[i]
        trade_end   = dates[i + args.trade - 1]

        # choose pairs in formation window
        candidates = []
        for a in range(len(tickers)):
            for b in range(a+1, len(tickers)):
                t1, t2 = tickers[a], tickers[b]

                if allowed_pairs is not None:
                    if tuple(sorted((t1, t2))) not in allowed_pairs:
                        continue
                    
                if args.within_sector:
                    s1 = sic2_map.get(t1)
                    s2 = sic2_map.get(t2)
                    if (s1 is None) or (s2 is None) or (s1 != s2):
                        continue
                    
                s1 = lp[t1].loc[form_start:form_end]
                s2 = lp[t2].loc[form_start:form_end]
                df = pd.concat([s1, s2], axis=1, keys=["lp1","lp2"]).dropna()
                
                # Require enough overlapping points relative to formation window, and at least the lookback
                required = max(args.lookback, min(MIN_OVERLAP_DAYS, int(0.8 * args.formation)))
                if len(df) < required:
                    continue
                
                corr = df["lp1"].corr(df["lp2"])
                if np.isnan(corr) or corr < MIN_LOG_CORR:
                    continue

                try:
                    pval, beta, alpha = eg_beta_alpha(df["lp1"], df["lp2"])
                except Exception:
                    continue
                
                if pval > PVAL_MAX:
                    continue

                if not (BETA_MIN <= beta <= BETA_MAX):
                    continue
                
                spread_form = df["lp1"] - (alpha + beta*df["lp2"])
                sigma_spread = float(spread_form.std(ddof=1))
                sigma_diff   = float(spread_form.diff().dropna().std(ddof=1))
                if not np.isfinite(sigma_diff) or sigma_diff <= 0:
                    continue

                pre_w = 1.0 / sigma_diff
                candidates.append(PairSpec(t1, t2, alpha, beta, sigma_spread, sigma_diff, pre_w))

        chosen = candidates
        # normalize weights so sum to 1
        if chosen:
            wsum = sum(ps.weight for ps in chosen)
            if wsum > 0:
                for ps in chosen:
                    ps.weight = ps.weight / wsum

        cycles += 1
        print(f"Cycle {cycles}: candidates={len(candidates)}, chosen={len(chosen)} "
              f"[{form_start.date()}→{form_end.date()} | trade {trade_start.date()}→{trade_end.date()}]")

        # trade chosen pairs for trade window
        daily_index = pd.bdate_range(trade_start, trade_end)
        daily_pnl = pd.Series(0.0, index=daily_index)

        for spec in chosen:
            r = generate_pair_returns(spec,
                                      lp[spec.t1], lp[spec.t2],
                                      trade_start, trade_end,
                                      args.lookback, args.entry, args.exit,
                                      args.time_stop, args.cost_bps)
            if r.empty:
                continue
            r = r.reindex(daily_pnl.index).fillna(0.0)
            daily_pnl = daily_pnl.add(r, fill_value=0.0)

            key = (spec.t1, spec.t2)
            if key not in per_pair_stats:
                per_pair_stats[key] = {"ret_sum": 0.0, "ret_cnt": 0, "cycles": 0}
            per_pair_stats[key]["ret_sum"] += float(r.sum())
            per_pair_stats[key]["ret_cnt"] += int((r != 0).sum())
            per_pair_stats[key]["cycles"]  += 1

        equity.extend(list(daily_pnl.values))
        i += args.trade

    pnl = pd.Series(equity, index=pd.bdate_range(start=dates[args.formation], periods=len(equity)))
    ann_ret = pnl.mean() * 252
    ann_vol = pnl.std(ddof=1) * np.sqrt(252)
    sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0.0

    eq = pd.DataFrame({"date": pnl.index, "portfolio_ret": pnl.values})
    eq["equity"] = (1 + eq["portfolio_ret"]).cumprod()
    eq_path = RESULTS_DIR / "equity_walkforward.csv"
    eq.to_csv(eq_path, index=False)

    summary = pd.DataFrame([{
        "start": args.start, "end": args.end,
        "formation": args.formation, "trade": args.trade,
        "lookback": args.lookback, "entry_z": args.entry, "exit_z": args.exit,
        "time_stop": args.time_stop, "cost_bps": args.cost_bps, "within_sector": args.within_sector,
        "ann_return": float(ann_ret), "ann_vol": float(ann_vol), "sharpe": float(sharpe),
        "num_days": int(len(pnl)), "num_cycles": int(cycles)
    }])
    summary_path = RESULTS_DIR / "wf_summary.csv"
    summary.to_csv(summary_path, index=False)

    rows = []
    for (t1, t2), d in per_pair_stats.items():
        rows.append({"t1": t1, "t2": t2, **d})
    pairs_stats = pd.DataFrame(rows)
    pairs_stats_path = RESULTS_DIR / "wf_pairs_stats.csv"
    pairs_stats.to_csv(pairs_stats_path, index=False)

    print(f"Walk-forward saved to:\n  {eq_path}\n  {summary_path}\n  {pairs_stats_path}")
    print(f"Sharpe={sharpe:.2f}, AnnRet={ann_ret:.4f}, AnnVol={ann_vol:.4f}, Days={len(pnl)}, Cycles={cycles}")

if __name__ == "__main__":
    main()
