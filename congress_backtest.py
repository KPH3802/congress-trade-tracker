#!/usr/bin/env python3
"""
CONGRESSIONAL TRADING BACKTEST
================================
Signal #2: Do congressional trades predict stock moves?

Data: Quiver Quant congress-trading-all.xlsx (109K records, 2012-2026)
Location: ~/Desktop/Claude_Programs/Trading_Programs/congress_tracker/

Methodology mirrors the insider cluster backtest:
- Load data, filter to purchases
- Fetch forward returns via yfinance + SPY benchmark
- Analyze across multiple dimensions (party, size, politician, chamber, clusters, timing)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import os
import sys
import time
import json

# ─── Configuration ───────────────────────────────────────────────────────────
DATA_DIR = os.path.expanduser("~/Desktop/Claude_Programs/Trading_Programs/congress_tracker")
DATA_FILE = os.path.join(DATA_DIR, "congress-trading-all.xlsx")
RESULTS_FILE = os.path.join(DATA_DIR, "congress_backtest_results.csv")
REPORT_FILE = os.path.join(DATA_DIR, "congress_backtest_report.txt")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "congress_backtest_checkpoint.json")

# Forward return windows (trading days)
RETURN_WINDOWS = [5, 10, 20, 40, 60]

# Minimum signals for statistical relevance
MIN_SIGNALS = 20


# ─── STEP 1: Load and Inspect Data ──────────────────────────────────────────
def load_data():
    """Load the Quiver Quant congress trading data."""
    print("=" * 70)
    print("STEP 1: LOADING DATA")
    print("=" * 70)
    
    if not os.path.exists(DATA_FILE):
        print(f"ERROR: File not found: {DATA_FILE}")
        print("Make sure congress-trading-all.xlsx is in your congress_tracker folder.")
        sys.exit(1)
    
    df = pd.read_excel(DATA_FILE)
    print(f"Loaded {len(df):,} total records")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nColumn types:")
    for col in df.columns:
        print(f"  {col}: {df[col].dtype} | non-null: {df[col].notna().sum():,} | sample: {df[col].dropna().iloc[0] if df[col].notna().any() else 'ALL NULL'}")
    
    print(f"\nDate range: {df['Traded'].min()} to {df['Traded'].max()}")
    print(f"Unique politicians: {df['Name'].nunique()}")
    print(f"Unique tickers: {df['Ticker'].nunique()}")
    
    # Transaction type breakdown
    print(f"\nTransaction types:")
    for tx_type, count in df['Transaction'].value_counts().items():
        print(f"  {tx_type}: {count:,}")
    
    # Party breakdown
    if 'Party' in df.columns:
        print(f"\nParty breakdown:")
        for party, count in df['Party'].value_counts().items():
            print(f"  {party}: {count:,}")
    
    # Check if excess_return is usable
    if 'excess_return' in df.columns:
        valid_er = df['excess_return'].notna().sum()
        print(f"\nexcess_return column: {valid_er:,} non-null values ({valid_er/len(df)*100:.1f}%)")
        if valid_er > 0:
            print(f"  Mean: {df['excess_return'].mean():.4f}")
            print(f"  Median: {df['excess_return'].median():.4f}")
            print(f"  NOTE: We'll examine this but also calculate our own returns for verification")
    
    # Trade size breakdown
    if 'Trade_Size_USD' in df.columns:
        print(f"\nTrade size distribution:")
        for size, count in df['Trade_Size_USD'].value_counts().head(10).items():
            print(f"  {size}: {count:,}")
    
    return df


# ─── STEP 2: Filter to Purchases ────────────────────────────────────────────
def filter_purchases(df):
    """Filter to stock purchases only."""
    print("\n" + "=" * 70)
    print("STEP 2: FILTERING TO PURCHASES")
    print("=" * 70)
    
    # Identify purchase transactions
    # Quiver Quant uses various labels - check what's in the data
    purchase_keywords = ['Purchase', 'Buy', 'purchase', 'buy']
    
    # First show all transaction types
    print("All transaction types found:")
    for tx, count in df['Transaction'].value_counts().items():
        print(f"  '{tx}': {count:,}")
    
    # Filter to purchases
    purchases = df[df['Transaction'].str.contains('Purchase|Buy|purchase|buy', case=False, na=False)].copy()
    
    if len(purchases) == 0:
        print("\nWARNING: No purchases found with keyword matching.")
        print("Trying exact match on common values...")
        # Try the most common transaction type that looks like a purchase
        for tx in df['Transaction'].unique():
            if any(kw in str(tx).lower() for kw in ['purchase', 'buy']):
                purchases = df[df['Transaction'] == tx].copy()
                print(f"Found {len(purchases):,} records matching '{tx}'")
                break
    
    print(f"\nFiltered to {len(purchases):,} purchase transactions")
    
    # Clean dates
    purchases['Traded'] = pd.to_datetime(purchases['Traded'], errors='coerce')
    purchases = purchases.dropna(subset=['Traded', 'Ticker'])
    
    # Remove non-stock tickers (options, bonds, etc.)
    # Filter out tickers with special characters or that are too long
    purchases = purchases[purchases['Ticker'].str.match(r'^[A-Z]{1,5}$', na=False)]
    
    print(f"After cleaning: {len(purchases):,} valid stock purchases")
    print(f"Date range: {purchases['Traded'].min().date()} to {purchases['Traded'].max().date()}")
    print(f"Unique politicians: {purchases['Name'].nunique()}")
    print(f"Unique tickers: {purchases['Ticker'].nunique()}")
    
    return purchases


# ─── STEP 3: Parse Trade Sizes ───────────────────────────────────────────────
def parse_trade_sizes(purchases):
    """Convert trade size ranges to numeric estimates."""
    print("\n" + "=" * 70)
    print("STEP 3: PARSING TRADE SIZES")
    print("=" * 70)
    
    # Quiver Quant typically provides ranges like "$1,001 - $15,000"
    # Map them to midpoint estimates
    size_map = {
        '$1,001 - $15,000': 8000,
        '$15,001 - $50,000': 32500,
        '$50,001 - $100,000': 75000,
        '$100,001 - $250,000': 175000,
        '$250,001 - $500,000': 375000,
        '$500,001 - $1,000,000': 750000,
        '$1,000,001 - $5,000,000': 3000000,
        '$5,000,001 - $25,000,000': 15000000,
        '$25,000,001 - $50,000,000': 37500000,
        'Over $50,000,000': 50000000,
    }
    
    if 'Trade_Size_USD' in purchases.columns:
        purchases['size_estimate'] = purchases['Trade_Size_USD'].map(size_map)
        mapped = purchases['size_estimate'].notna().sum()
        unmapped = purchases['size_estimate'].isna().sum()
        print(f"Mapped {mapped:,} trade sizes, {unmapped:,} unmapped")
        
        if unmapped > 0:
            unmapped_vals = purchases[purchases['size_estimate'].isna()]['Trade_Size_USD'].value_counts().head(10)
            print("Unmapped values:")
            for val, count in unmapped_vals.items():
                print(f"  '{val}': {count:,}")
    else:
        print("No Trade_Size_USD column found - skipping size analysis")
        purchases['size_estimate'] = np.nan
    
    return purchases


# ─── STEP 4: Fetch Forward Returns ──────────────────────────────────────────
def fetch_returns(purchases):
    """Fetch forward returns for each purchase signal using yfinance."""
    print("\n" + "=" * 70)
    print("STEP 4: FETCHING FORWARD RETURNS")
    print("=" * 70)
    
    # Check for existing checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            checkpoint = json.load(f)
        completed_indices = set(checkpoint.get('completed', []))
        print(f"Resuming from checkpoint: {len(completed_indices):,} already completed")
    else:
        completed_indices = set()
    
    # Load existing results if any
    if os.path.exists(RESULTS_FILE) and len(completed_indices) > 0:
        results_df = pd.read_csv(RESULTS_FILE)
        results = results_df.to_dict('records')
        print(f"Loaded {len(results):,} existing results")
    else:
        results = []
    
    # Get unique tickers to minimize API calls
    # Strategy: download price data per ticker, then look up each trade date
    unique_tickers = sorted(purchases['Ticker'].unique())
    print(f"\nNeed price data for {len(unique_tickers):,} unique tickers")
    
    # Also need SPY for benchmark
    if 'SPY' not in unique_tickers:
        unique_tickers.append('SPY')
    
    # Download price data in batches
    # First, determine date range needed
    min_date = purchases['Traded'].min() - timedelta(days=10)
    max_date = purchases['Traded'].max() + timedelta(days=90)  # Need forward returns
    today = datetime.now()
    if max_date > today:
        max_date = today
    
    print(f"Price data range: {min_date.date()} to {max_date.date()}")
    
    # Cache price data per ticker
    price_cache = {}
    spy_data = None
    
    # Download SPY first
    print("\nDownloading SPY benchmark data...")
    try:
        spy = yf.download('SPY', start=min_date.strftime('%Y-%m-%d'), end=max_date.strftime('%Y-%m-%d'), progress=False)
        if len(spy) > 0:
            spy_close = spy['Close']
            if isinstance(spy_close, pd.DataFrame):
                spy_close = spy_close.iloc[:, 0]
            # Ensure index is DatetimeIndex
            spy_close.index = pd.to_datetime(spy_close.index)
            spy_data = spy_close  # Keep as Series, not dict
            print(f"SPY: {len(spy_data):,} trading days loaded")
        else:
            print("WARNING: Could not download SPY data")
    except Exception as e:
        print(f"ERROR downloading SPY: {e}")
    
    # Process each trade
    total = len(purchases)
    batch_size = 50  # Save checkpoint every N trades
    skipped_tickers = set()
    
    print(f"\nProcessing {total:,} trades...")
    print(f"Progress updates every {batch_size} trades")
    print("-" * 50)
    
    for i, (idx, row) in enumerate(purchases.iterrows()):
        # Skip if already done
        if str(idx) in completed_indices:
            continue
        
        ticker = row['Ticker']
        trade_date = pd.Timestamp(row['Traded'])
        
        # Get price data for this ticker (with caching)
        if ticker not in price_cache:
            if ticker in skipped_tickers:
                continue
            try:
                data = yf.download(ticker, start=min_date, end=max_date, progress=False)
                if len(data) > 0:
                    # Handle potential MultiIndex columns
                    close = data['Close']
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    price_cache[ticker] = close
                else:
                    skipped_tickers.add(ticker)
                    continue
                # Rate limiting
                time.sleep(0.1)
            except Exception as e:
                skipped_tickers.add(ticker)
                continue
        
        prices = price_cache[ticker]
        
        # Find the entry price (first available close on or after trade date)
        available_dates = prices.index[prices.index >= trade_date]
        if len(available_dates) == 0:
            continue
        
        entry_date = available_dates[0]
        entry_price = float(prices[entry_date])
        
        # Calculate forward returns at each window
        result = {
            'idx': idx,
            'ticker': ticker,
            'trade_date': str(trade_date.date()),
            'entry_date': str(entry_date.date()),
            'entry_price': entry_price,
            'politician': row['Name'],
            'party': row.get('Party', ''),
            'size_estimate': row.get('size_estimate', np.nan),
            'trade_size_raw': row.get('Trade_Size_USD', ''),
        }
        
        # Add any extra columns that might be useful
        for col in ['Chamber', 'chamber', 'House', 'Senate', 'excess_return']:
            if col in row.index and pd.notna(row[col]):
                result[col.lower()] = row[col]
        
        # Forward returns
        for window in RETURN_WINDOWS:
            # Find trading day N days after entry
            future_dates = prices.index[prices.index > entry_date]
            if len(future_dates) >= window:
                future_date = future_dates[window - 1]
                future_price = float(prices[future_date])
                ret = ((future_price - entry_price) / entry_price) * 100
                result[f'ret_{window}d'] = round(ret, 4)
                
                # SPY benchmark return over same period
                if spy_data is not None:
                    spy_entry_dates = spy_data.index[spy_data.index >= entry_date]
                    if len(spy_entry_dates) > 0:
                        spy_entry_d = spy_entry_dates[0]
                        spy_entry_p = float(spy_data[spy_entry_d])
                        spy_future_dates = spy_data.index[spy_data.index > spy_entry_d]
                        if len(spy_future_dates) >= window:
                            spy_future_d = spy_future_dates[window - 1]
                            spy_future_p = float(spy_data[spy_future_d])
                            spy_ret = ((spy_future_p - spy_entry_p) / spy_entry_p) * 100
                            result[f'spy_{window}d'] = round(spy_ret, 4)
                            result[f'alpha_{window}d'] = round(ret - spy_ret, 4)
            else:
                result[f'ret_{window}d'] = np.nan
                result[f'spy_{window}d'] = np.nan
                result[f'alpha_{window}d'] = np.nan
        
        results.append(result)
        completed_indices.add(str(idx))
        
        # Progress and checkpoint
        done = len(results)
        if done % batch_size == 0:
            pct = done / total * 100
            elapsed_tickers = len(price_cache) + len(skipped_tickers)
            print(f"  [{done:,}/{total:,}] {pct:.1f}% | {len(price_cache):,} tickers cached | {len(skipped_tickers):,} skipped")
            
            # Save checkpoint
            results_df = pd.DataFrame(results)
            results_df.to_csv(RESULTS_FILE, index=False)
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump({'completed': list(completed_indices)}, f)
    
    # Final save
    results_df = pd.DataFrame(results)
    results_df.to_csv(RESULTS_FILE, index=False)
    
    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
    
    print(f"\n{'=' * 50}")
    print(f"DONE: {len(results):,} trades with return data")
    print(f"Tickers downloaded: {len(price_cache):,}")
    print(f"Tickers skipped (no data): {len(skipped_tickers):,}")
    print(f"Results saved to: {RESULTS_FILE}")
    
    return results_df


# ─── STEP 5: Analysis ───────────────────────────────────────────────────────
def analyze(results_df):
    """Run the full multi-dimensional analysis."""
    print("\n" + "=" * 70)
    print("STEP 5: ANALYSIS")
    print("=" * 70)
    
    report_lines = []
    
    def log(text=""):
        print(text)
        report_lines.append(text)
    
    def stats_table(subset, label):
        """Print stats for a subset of results."""
        n = len(subset)
        if n < MIN_SIGNALS:
            log(f"\n  {label}: n={n} (below minimum {MIN_SIGNALS}, skipping)")
            return
        
        log(f"\n  {label} (n={n:,})")
        log(f"  {'─' * 60}")
        
        # Header
        log(f"  {'Window':<10} {'Avg Ret':>10} {'Med Ret':>10} {'Alpha':>10} {'Win%':>8} {'Alpha Win%':>12}")
        log(f"  {'─' * 60}")
        
        for w in RETURN_WINDOWS:
            ret_col = f'ret_{w}d'
            spy_col = f'spy_{w}d'
            alpha_col = f'alpha_{w}d'
            
            if ret_col not in subset.columns:
                continue
            
            valid = subset[ret_col].dropna()
            if len(valid) < MIN_SIGNALS:
                continue
            
            avg_ret = valid.mean()
            med_ret = valid.median()
            win_pct = (valid > 0).mean() * 100
            
            if alpha_col in subset.columns:
                alpha_valid = subset[alpha_col].dropna()
                avg_alpha = alpha_valid.mean() if len(alpha_valid) > 0 else np.nan
                alpha_win = (alpha_valid > 0).mean() * 100 if len(alpha_valid) > 0 else np.nan
            else:
                avg_alpha = np.nan
                alpha_win = np.nan
            
            log(f"  {w:>3}d       {avg_ret:>+9.2f}% {med_ret:>+9.2f}% {avg_alpha:>+9.2f}% {win_pct:>7.1f}% {alpha_win:>11.1f}%")
    
    def section(title):
        log(f"\n{'━' * 70}")
        log(f"  {title}")
        log(f"{'━' * 70}")
    
    # ── Header ──
    log("=" * 70)
    log("CONGRESSIONAL TRADING BACKTEST - FULL REPORT")
    log(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log("=" * 70)
    log(f"\nTotal signals analyzed: {len(results_df):,}")
    log(f"Unique politicians: {results_df['politician'].nunique():,}")
    log(f"Unique tickers: {results_df['ticker'].nunique():,}")
    
    if 'party' in results_df.columns:
        log(f"Party split: {(results_df['party'] == 'R').sum():,} R / {(results_df['party'] == 'D').sum():,} D")
    
    date_range = f"{results_df['trade_date'].min()} to {results_df['trade_date'].max()}"
    log(f"Date range: {date_range}")
    
    # ── A. Overall Performance ──
    section("A. OVERALL PERFORMANCE (All Congressional Purchases)")
    stats_table(results_df, "All Congressional Purchases")
    
    # ── B. By Party ──
    section("B. BY PARTY")
    if 'party' in results_df.columns:
        for party in ['R', 'D']:
            subset = results_df[results_df['party'] == party]
            party_name = "Republican" if party == 'R' else "Democrat"
            stats_table(subset, f"{party_name} ({party})")
    
    # ── C. By Trade Size ──
    section("C. BY TRADE SIZE")
    if 'size_estimate' in results_df.columns:
        size_bins = [
            (0, 15001, "Under $15K"),
            (15001, 50001, "$15K - $50K"),
            (50001, 100001, "$50K - $100K"),
            (100001, 250001, "$100K - $250K"),
            (250001, 500001, "$250K - $500K"),
            (500001, 1000001, "$500K - $1M"),
            (1000001, float('inf'), "$1M+"),
        ]
        for low, high, label in size_bins:
            subset = results_df[
                (results_df['size_estimate'] >= low) &
                (results_df['size_estimate'] < high)
            ]
            stats_table(subset, label)
    
    # ── D. By Chamber ──
    section("D. BY CHAMBER (House vs Senate)")
    # Try various column names
    chamber_col = None
    for col in ['chamber', 'Chamber', 'House', 'house']:
        if col in results_df.columns:
            chamber_col = col
            break
    
    if chamber_col:
        for chamber in results_df[chamber_col].dropna().unique():
            subset = results_df[results_df[chamber_col] == chamber]
            stats_table(subset, str(chamber))
    else:
        log("  (Chamber data not available)")
    
    # ── E. By Year ──
    section("E. BY YEAR")
    results_df['year'] = pd.to_datetime(results_df['trade_date']).dt.year
    for year in sorted(results_df['year'].unique()):
        subset = results_df[results_df['year'] == year]
        stats_table(subset, str(year))
    
    # ── F. Clusters (Multiple Politicians, Same Stock, Same Week) ──
    section("F. CLUSTER ANALYSIS (2+ Politicians Same Stock Within 14 Days)")
    
    results_df['trade_dt'] = pd.to_datetime(results_df['trade_date'])
    
    # Find clusters: group by ticker, then check for trades within 14 days by different politicians
    cluster_signals = []
    for ticker, group in results_df.groupby('ticker'):
        group = group.sort_values('trade_dt')
        for i, (idx, row) in enumerate(group.iterrows()):
            # Look at trades within 14 days
            window_start = row['trade_dt']
            window_end = window_start + timedelta(days=14)
            window = group[
                (group['trade_dt'] >= window_start) &
                (group['trade_dt'] <= window_end)
            ]
            unique_pols = window['politician'].nunique()
            if unique_pols >= 2:
                cluster_signals.append({
                    **row.to_dict(),
                    'cluster_size': unique_pols
                })
    
    if cluster_signals:
        cluster_df = pd.DataFrame(cluster_signals).drop_duplicates(subset=['ticker', 'trade_date', 'politician'])
        log(f"\n  Found {len(cluster_df):,} trades that are part of clusters")
        stats_table(cluster_df, "All Cluster Trades (2+ politicians)")
        
        # By cluster size
        for size in sorted(cluster_df['cluster_size'].unique()):
            if size >= 3:
                subset = cluster_df[cluster_df['cluster_size'] >= size]
                stats_table(subset, f"{size}+ politicians in cluster")
    else:
        log("  No clusters found")
    
    # Non-cluster for comparison
    non_cluster_tickers = set()
    if cluster_signals:
        cluster_ticker_dates = set()
        for cs in cluster_signals:
            cluster_ticker_dates.add((cs['ticker'], cs['trade_date']))
        non_cluster = results_df[
            ~results_df.apply(lambda r: (r['ticker'], r['trade_date']) in cluster_ticker_dates, axis=1)
        ]
        stats_table(non_cluster, "Non-Cluster (solo politician trades)")
    
    # ── G. Top Individual Politicians ──
    section("G. TOP POLITICIANS BY TRADE COUNT")
    
    politician_counts = results_df['politician'].value_counts()
    top_pols = politician_counts[politician_counts >= 50].index  # At least 50 trades
    
    if len(top_pols) > 0:
        log(f"\n  Politicians with 50+ purchase trades: {len(top_pols)}")
        
        pol_results = []
        for pol in top_pols:
            subset = results_df[results_df['politician'] == pol]
            n = len(subset)
            avg_alpha_20 = subset['alpha_20d'].dropna().mean() if 'alpha_20d' in subset.columns else np.nan
            win_rate_20 = (subset['alpha_20d'].dropna() > 0).mean() * 100 if 'alpha_20d' in subset.columns else np.nan
            pol_results.append({
                'politician': pol,
                'n_trades': n,
                'avg_alpha_20d': avg_alpha_20,
                'win_rate_20d': win_rate_20,
                'party': subset['party'].mode().iloc[0] if 'party' in subset.columns and len(subset['party'].mode()) > 0 else '?'
            })
        
        pol_df = pd.DataFrame(pol_results).sort_values('avg_alpha_20d', ascending=False)
        
        log(f"\n  {'Politician':<30} {'Party':>5} {'Trades':>7} {'20d Alpha':>10} {'Win%':>8}")
        log(f"  {'─' * 65}")
        for _, row in pol_df.iterrows():
            log(f"  {row['politician']:<30} {row['party']:>5} {row['n_trades']:>7} {row['avg_alpha_20d']:>+9.2f}% {row['win_rate_20d']:>7.1f}%")
    else:
        log("  No politicians with 50+ trades")
        # Try lower threshold
        top_pols_20 = politician_counts[politician_counts >= 20].index
        if len(top_pols_20) > 0:
            log(f"\n  Politicians with 20+ trades: {len(top_pols_20)}")
            for pol in top_pols_20[:15]:
                subset = results_df[results_df['politician'] == pol]
                stats_table(subset, f"{pol} ({subset['party'].mode().iloc[0] if 'party' in subset.columns and len(subset['party'].mode()) > 0 else '?'})")
    
    # ── H. Verdict ──
    section("H. VERDICT")
    
    if 'alpha_5d' in results_df.columns:
        overall_alpha_5 = results_df['alpha_5d'].dropna().mean()
        overall_alpha_20 = results_df['alpha_20d'].dropna().mean()
        overall_alpha_60 = results_df['alpha_60d'].dropna().mean() if 'alpha_60d' in results_df.columns else np.nan
        
        log(f"\n  Overall 5-day alpha:  {overall_alpha_5:+.2f}%")
        log(f"  Overall 20-day alpha: {overall_alpha_20:+.2f}%")
        if not np.isnan(overall_alpha_60):
            log(f"  Overall 60-day alpha: {overall_alpha_60:+.2f}%")
        
        if overall_alpha_20 > 0.5:
            log(f"\n  SIGNAL STRENGTH: MODERATE TO STRONG")
            log(f"  Congressional purchases show meaningful alpha.")
        elif overall_alpha_20 > 0:
            log(f"\n  SIGNAL STRENGTH: WEAK")
            log(f"  Some alpha but may not be tradeable after costs.")
        else:
            log(f"\n  SIGNAL STRENGTH: NO SIGNAL")
            log(f"  Congressional purchases do not predict outperformance.")
        
        log(f"\n  Look for stronger sub-signals in the dimensional analysis above.")
        log(f"  The best edge may be in specific slices (e.g., large trades, clusters, specific politicians).")
    
    # Save report
    with open(REPORT_FILE, 'w') as f:
        f.write('\n'.join(report_lines))
    
    log(f"\n  Report saved to: {REPORT_FILE}")
    
    return report_lines


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    start_time = datetime.now()
    
    # Step 1: Load
    df = load_data()
    
    input("\n>>> Press Enter to continue to Step 2 (filter purchases)...")
    
    # Step 2: Filter
    purchases = filter_purchases(df)
    
    # Step 3: Parse sizes
    purchases = parse_trade_sizes(purchases)
    
    input(f"\n>>> {len(purchases):,} purchases ready. Press Enter to start fetching returns (this is the slow part)...")
    
    # Step 4: Fetch returns
    results_df = fetch_returns(purchases)
    
    input("\n>>> Returns fetched. Press Enter to run analysis...")
    
    # Step 5: Analyze
    analyze(results_df)
    
    elapsed = datetime.now() - start_time
    print(f"\n{'=' * 70}")
    print(f"TOTAL TIME: {elapsed}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()