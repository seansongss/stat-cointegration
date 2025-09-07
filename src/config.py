import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

RAW_DIR = Path("data/raw")
META_DIR = Path("data/meta")
RESULTS_DIR = Path("data/results")
for d in (RAW_DIR, META_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

WRDS_USERNAME = os.getenv("WRDS_USERNAME")
WRDS_POSTGRES_HOST = os.getenv("WRDS_POSTGRES_HOST", "wrds-pgdata.wharton.upenn.edu")
WRDS_POSTGRES_PORT = int(os.getenv("WRDS_POSTGRES_PORT", "9737"))

# Exchanges: NYSE(1), AMEX(2), NASDAQ(3)
VALID_EXCHCD = (1, 2, 3)

# Share codes: 10, 11 = common stocks
VALID_SHRCD = (10, 11)

# Backtesting tickers
BACKTEST_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "NFLX", "CRM", "ADBE"
]

# Specific pairs to test (empty to read from pairs.csv)
BACKTEST_PAIRS = [
    # ("AAPL", "MSFT"),
    # ("GOOGL", "AMZN"),
    # ("TSLA", "NVDA"),
]

# Default backtest window
DEFAULT_START = "2024-01-01"
DEFAULT_END   = "2024-12-31"

# Pair selection constraints
MIN_OVERLAP_DAYS = 120

# Signal settings
FORMATION = 60
TRADE     = 10
LOOKBACK  = 60
ENTRY_Z  = 2.0
EXIT_Z   = 0.5
TIME_STOP_DAYS = 10

# Cost model
COST_BPS = 2.0
TOP_PAIRS_FOR_BACKTEST = 25

# Cointegration selection
PVAL_MAX = 0.05
MIN_LOG_CORR = 0.60  # min correlation of log-prices

# Pair quality gates (applied in each formation window)
BETA_MIN, BETA_MAX = 0.20, 5.0     # hedge ratio range
MIN_SIGMA_DIFF = 1e-4              # min std of delta spread (log units) to avoid micro-noise pairs
