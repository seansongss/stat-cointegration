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

# Backtesting configuration
BACKTEST_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "NFLX", "CRM", "ADBE"
]

# Specific pairs to test
BACKTEST_PAIRS = [
    ("AAPL", "MSFT"),
    ("GOOGL", "AMZN"),
    ("TSLA", "NVDA"),
]
