install:
	pip install -r requirements.txt

# Download data for config tickers
download:
	python -m src.download_daily

# Download daily data for specific tickers (comma separated)
download-specific:
	python -m src.download_daily --tickers $(word 2, $(MAKECMDGOALS))

# Find pairs with config
find:
	python -m src.find_pairs

# Find pairs WITHIN sector (requires labels)
find-sector:
	python -m src.find_pairs --within_sector 1

# Run backtest with config
test:
	python -m src.backtest_pairs

# Run backtest with specific tickers
test-tickers:
	python -m src.backtest_pairs --tickers $(word 2, $(MAKECMDGOALS))

# Run backtest with specific pairs
test-pairs:
	python -m src.backtest_pairs --pairs $(word 2, $(MAKECMDGOALS))

# Fetch sector labels at snapshot date
sic:
	python -m src.labels_crsp

# Walk-forward backtest (formation -> trade cycles)
walk:
	python -m src.daily_walkforward

# Plot equity and rolling Sharpe from walk-forward
plot:
	python -m src.plot_results

# Run pipeline
pipeline:
	python -m src.download_daily
	python -m src.find_pairs
	python -m src.backtest_pairs
	python -m src.daily_walkforward
	python -m src.plot_results

# Run pipeline within sector
pipeline-sector:
	python -m src.download_daily
	python -m src.find_pairs --within_sector 1
	python -m src.backtest_pairs
	python -m src.daily_walkforward --within_sector 1
	python -m src.plot_results
