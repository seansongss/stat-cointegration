PY=python

install:
	pip install -r requirements.txt

# Download data for config tickers
download:
	$(PY) -m src.download_daily --tickers $(shell python -c "from src.config import BACKTEST_TICKERS; print(','.join(BACKTEST_TICKERS))") --years_back 1

# Download daily data for specific tickers
download-specific:
	$(PY) -m src.download_daily --tickers $(word 2, $(MAKECMDGOALS)) --years_back 1

# Find pairs with default config
find:
	$(PY) -m src.find_pairs --start 2024-01-01 --end 2024-12-31

# Run backtest with default config
test:
	$(PY) -m src.backtest_pairs

# Run backtest with specific tickers
test-tickers:
	$(PY) -m src.backtest_pairs --tickers $(word 2, $(MAKECMDGOALS))

# Run backtest with specific pairs
test-pairs:
	$(PY) -m src.backtest_pairs --pairs $(word 2, $(MAKECMDGOALS))

pipeline:
	$(PY) -m src.download_daily --tickers $(shell python -c "from src.config import BACKTEST_TICKERS; print(','.join(BACKTEST_TICKERS))") --years_back 1
	$(PY) -m src.find_pairs --start 2024-01-01 --end 2024-12-31
	$(PY) -m src.backtest_pairs
