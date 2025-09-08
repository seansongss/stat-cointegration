# Cointegration-Based Pairs Trading (WRDS/CRSP)

Daily, market-neutral **pairs trading** on U.S. equities using **Engle–Granger** cointegration for pair selection and a **z-score** spread signal for trading.
Data sourced from **CRSP via WRDS**.

> Built for research: clean data pipeline, transparent econometrics, **walk-forward** testing (no look-ahead), and reproducible outputs.

---

## 🔧 Features

* **Data**: Pull daily CRSP bars for tickers (via WRDS), saved as CSV in `data/raw/`.
* **Universe**: Build a liquid universe snapshot (top N by dollar volume) and optional SIC2 labels.
* **Pair Discovery**: `find_pairs.py` (EG test + OLS hedge, optional sector filter).
* **Static Backtest**: `backtest_pairs.py` (in-sample diagnostics for chosen pairs).
* **Walk-Forward**: `daily_walkforward.py` (formation/trade cycles, weighting, costs).
* **Report**: `report.rmd` → HTML/PDF with equity curve, tables, diagnostics.

---

## 📁 Repo Layout

```
.
├─ src/
│  ├─ config.py                 # central settings (dates, thresholds, costs, dirs)
│  ├─ wrds_utils.py             # WRDS connection + helpers
│  ├─ universe_crsp.py          # build/snapshot universe; optional SIC labels
│  ├─ download_daily.py         # pull CRSP daily data for tickers → CSV
│  ├─ labels_crsp.py            # (optional) SIC2 map for sector-within pairing
│  ├─ find_pairs.py             # cointegration triage → results/pairs.csv
│  ├─ backtest_pairs.py         # static per-pair backtest → results/backtest_results.csv
|  ├─ plot_results.py           # plot results from equity_walkforward.csv
│  └─ daily_walkforward.py      # rolling selection & trading → equity_walkforward.csv
├─ data/
│  ├─ raw/                      # input CSVs (per-ticker)
│  ├─ meta/                     # universe snapshots, SIC maps
│  └─ results/                  # pairs.csv, backtests, walk-forward outputs, report
├─ report.rmd                   # knit to HTML/PDF in RStudio
├─ .env.example                 # WRDS credentials template
├─ requirements.txt             # Python deps
├─ Makefile                     # common commands
└─ README.md
```

---

## 🚀 Quickstart

1. **Clone & env**

```bash
git clone <your-repo-url>
cd stat-arbitrage
python -m venv venv && source venv/bin/activate
make install
cp .env.example .env
```

2. **Set WRDS credentials** (`.env`)

```env
WRDS_USERNAME=your_wrds_username
WRDS_POSTGRES_HOST=wrds-pgdata.wharton.upenn.edu
WRDS_POSTGRES_PORT=9737
```

> You must have institutional WRDS access to **CRSP**.

3. **Find cointegrated pairs**

```bash
make find   # writes data/results/pairs.csv (2024 window by default)
```

4. **Static backtest**

```bash
make test   # uses pairs.csv or config BACKTEST_PAIR
```

5. **Walk-forward (main result)**

```bash
make walk
```

Outputs:

* `data/results/equity_walkforward.csv` (daily returns & equity)
* `data/results/wf_summary.csv` (ann. return/vol, Sharpe, cycles)
* `data/results/wf_pairs_stats.csv` (per-pair contribution)

6. **Render the report** (in RStudio)

* Open `docs/report.Rmd` → Knit (HTML recommended).
* The Rmd reads the CSVs in `data/results/` and builds plots/tables automatically.

---

## ⚙️ Configuration (edit `src/config.py`)

| Key                                   | What it does                                                             |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `DEFAULT_START`, `DEFAULT_END`        | Global analysis window (e.g., `"2024-01-01"` → `"2024-12-31"`).          |
| `FORMATION`, `TRADE`                  | Walk-forward cycle lengths (formation/trade days).                       |
| `LOOKBACK`                            | Rolling mean/SD window for z-score.                                      |
| `ENTRY_Z`, `EXIT_Z`, `TIME_STOP_DAYS` | Trading rules (enter on extreme z, exit on mean-reversion or time stop). |
| `COST_BPS`                            | Cost per leg (bps). Open/close is two legs; flips are four.              |
| `MIN_OVERLAP_DAYS`                    | Min shared dates for a pair in selection.                                |
| `PVAL_MAX`                            | Max Engle–Granger p-value to consider a pair cointegrated.               |
| `MIN_LOG_CORR`                        | Min corr of log prices in formation (guards spurious pairs).             |
| `BETA_MIN`, `BETA_MAX`                | Bounds on OLS hedge ratio β.                                             |
| `MIN_SIGMA_DIFF`                      | Floor on spread change volatility (numerical stability).                 |
| `BACKTEST_TICKERS`                    | Convenience list for downloads/backtests.                                |
| `RAW_DIR`, `META_DIR`, `RESULTS_DIR`  | Folder paths; created on import.                                         |

> **Tip:** `daily_walkforward.py` selects pairs **inside each formation window** using the thresholds above; `find_pairs.py`/`backtest_pairs.py` are for **offline triage** and sanity checks.

---

## 📊 Outputs (CSV)

* `results/pairs.csv` — pair candidates with p-value, α, β, obs.
* `results/backtest_results.csv` — static per-pair Sharpe/return/vol/trades.
* `results/equity_walkforward.csv` — daily portfolio return & equity curve.
* `results/wf_summary.csv` — annualized return/vol, Sharpe, days, cycles, params.
* `results/wf_pairs_stats.csv` — sum of daily returns & hit counts per pair.

---

## 🧪 Reproduce the main figure

1. `make walk`
2. Knit `docs/report.Rmd` → the report will show: equity curve, rolling Sharpe, per-pair bars, and top static pairs.

---

## ❗ Troubleshooting

* **WRDS permission errors** (e.g., `permission denied for schema crsp_q_stock`): switch to **annual** CRSP schema (`crsp_a_stock`) — the code does. Make sure your account has CRSP access; contact your WRDS rep if not.
* **Empty CRSP window**: your school’s CRSP feed may end at **2024-12-31**; use `--end 2024-12-31` and a window within 2024, or pull earlier dates.
* **Few/zero trades**: relax thresholds (`ENTRY_Z ↓`, `PVAL_MAX ↑`, `MIN_LOG_CORR ↓`), extend `FORMATION`, or widen the ticker universe.

---

## 📄 License & Use

* Code: **MIT** (adjust if you prefer).
* Data: subject to **WRDS/CRSP terms** — do **not** redistribute raw vendor data.
* For educational/research use; not investment advice.

---

## 📚 References

* Engle, R.F., & Granger, C.W\.J. (1987). *Co-integration and Error Correction*.
* Gatev, E., Goetzmann, W., & Rouwenhorst, K.G. (2006). *Pairs Trading: Performance of a Relative-Value Strategy*.
* Vidyamurthy, G. (2004). *Pairs Trading: Quantitative Methods and Analysis*.
* Elliott, R.J., van der Hoek, J., & Malcolm, W\.P. (2005). *Pairs Trading*.

---

## 🤝 Contributing

Issues and PRs are welcome. If you add data vendors or execution models (e.g., TAQ microstructure costs), please keep configuration centralized in `src/config.py` and write outputs to `data/results/` so the Rmd stays plug-and-play.
