import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

from .config import RESULTS_DIR

def plot_equity(eq_path: Path, out_path: Path):
    df = pd.read_csv(eq_path, parse_dates=["date"])
    plt.figure()
    plt.plot(df["date"], df["equity"])
    plt.title("Equity Curve (Walk-Forward)")
    plt.xlabel("Date"); plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_rolling_sharpe(eq_path: Path, out_path: Path, window_days: int = 63):
    df = pd.read_csv(eq_path, parse_dates=["date"])
    r = df["portfolio_ret"].astype(float)
    roll_mean = r.rolling(window_days).mean()
    roll_std  = r.rolling(window_days).std(ddof=1)
    roll_sharpe = (roll_mean / roll_std) * np.sqrt(252)
    plt.figure()
    plt.plot(df["date"], roll_sharpe)
    plt.title(f"Rolling Sharpe ({window_days}d window)")
    plt.xlabel("Date"); plt.ylabel("Sharpe")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def main():
    eq_path = RESULTS_DIR / "equity_walkforward.csv"
    if not eq_path.exists():
        raise SystemExit(f"Missing {eq_path} — run daily_walkforward.py first.")
    plot_equity(eq_path, RESULTS_DIR / "equity_walkforward.png")
    plot_rolling_sharpe(eq_path, RESULTS_DIR / "rolling_sharpe.png")
    print(f"Plots saved to {RESULTS_DIR / 'equity_walkforward.png'}, {RESULTS_DIR / 'rolling_sharpe.png'}")

if __name__ == "__main__":
    main()
