# Congress Trade Tracker

**Automated intelligence system that tracks, analyzes, and alerts on U.S. congressional stock trading activity.**

Members of Congress are required to disclose stock trades within 45 days under the STOCK Act. This tool ingests those disclosures in real time, stores them in a local database, and runs pattern detection algorithms to surface the most notable activity — then delivers a prioritized daily briefing via email.

---

## What It Detects

The analyzer runs **10 detection algorithms** against every new batch of disclosures:

| Signal | Description | Priority |
|--------|-------------|----------|
| **Cluster Detection** | 3+ politicians trading the same stock within 14 days | HIGH |
| **Bipartisan Convergence** | Both parties buying the same stock simultaneously | HIGH |
| **Committee-Relevant Trades** | Trades in sectors overseen by the politician's committee | HIGH |
| **Leadership Activity** | Trades by Speaker, Majority/Minority Leaders, Whips, Committee Chairs | MEDIUM |
| **Large Trades** | Positions exceeding $250K (estimated from disclosure brackets) | MEDIUM |
| **Sector Surges** | Unusual concentration of trades in a single sector | MEDIUM |
| **Repeat Buyers** | Politicians building a position with multiple purchases | LOW |
| **New Positions** | First-ever trade in a ticker by a politician | LOW |
| **Pre-Earnings Trades** | Trades placed shortly before scheduled earnings | LOW |
| **Against-Market Trades** | Buying during selloffs or selling during rallies | LOW |

Signals are scored and combined — a bipartisan cluster of committee-relevant large trades will rank higher than a single new position.

---

## Backtest Results

The system was backtested against **46,154 congressional purchase signals** from July 2012 through January 2026.

| Holding Period | Avg Return | Median Return | Win Rate |
|---------------|------------|---------------|----------|
| 5 days | +0.39% | +0.41% | 54.9% |
| 10 days | +0.67% | +0.73% | 56.2% |
| 20 days | +1.24% | +1.31% | 57.6% |
| 40 days | +2.41% | +2.16% | 58.5% |
| 60 days | +3.76% | +3.32% | 60.5% |

**Key findings:**
- 297 unique politicians tracked across 2,713 tickers
- Party split: 21,857 Republican / 24,245 Democrat trades
- Congressional purchases show consistent positive returns across all holding windows
- Win rates improve with longer holding periods, suggesting informed positioning rather than noise

---

## Architecture

```
congress_main.py          # Orchestrator — runs daily pipeline
├── data_fetcher.py       # Pulls House + Senate disclosures from FMP API
├── database.py           # SQLite storage and query layer
├── analyzer.py           # 10 detection algorithms + scoring engine
├── politicians.py        # Politician metadata, committees, leadership roles
├── emailer.py            # HTML email report builder + SMTP delivery
└── config.py             # Credentials and tunable thresholds (not committed)

congress_backtest.py      # Historical backtesting framework
congress_deep_dive.py     # Ad-hoc analysis and deep dives
check_alerts.py           # Manual alert check utility
```

---

## Setup

```bash
# Clone the repo
git clone https://github.com/KPH3802/congress-trade-tracker.git
cd congress-trade-tracker

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp config_example.py config.py
# Edit config.py with your email and API key

# Set your FMP API key
export FMP_API_KEY="your_key_here"

# Run the tracker
python congress_main.py
```

### Requirements
- Python 3.8+
- Free [FMP API key](https://financialmodelingprep.com/) for congressional disclosure data
- Gmail account with [App Password](https://myaccount.google.com/apppasswords) for email alerts

---

## Daily Email Report

The tracker sends a formatted HTML email containing:
- **Data fetch summary** — new House and Senate transactions ingested
- **Database statistics** — total transactions, party breakdown, date coverage
- **Prioritized alerts** — HIGH and MEDIUM signals with full context
- **Alert breakdown** — counts by detection type

Subject line adapts to content: quiet days get a status update, active days lead with the alert count.

---

## Built With

- **Python** — core language
- **SQLite** — local transaction database
- **FMP API** — congressional disclosure data source
- **SMTP/Gmail** — automated email delivery

---

## Disclaimer

This tool is for **educational and research purposes only**. Congressional trading data is public information under the STOCK Act. This project does not constitute financial advice. Past performance of congressional trades does not guarantee future results.

---

## License

MIT
