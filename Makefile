PY=python

install:
	pip install -r requirements.txt

env:
	cp -n .env.example .env || true

snapshot:
	$(PY) -m src.universe snapshot

addv:
	$(PY) -m src.universe addv --days 60

universe:
	$(PY) -m src.universe finalize --top 300

smoke:
	$(PY) -m src.download_minutes --tickers KO,PEP --days 7

test:
	pytest -q
