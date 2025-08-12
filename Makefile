PY=python

install:
	pip install -r requirements.txt

env:
	cp -n .env.example .env || true

universe:
	$(PY) -m src.universe_crsp build --end 2024-12-31 --days 60 --top 300

smoke:
	$(PY) -m src.universe_crsp build --end 2024-12-31 --days 60 --top 50
	$(PY) -m src.download_daily --tickers AAPL,MSFT --years_back 1

test:
	pytest -q
