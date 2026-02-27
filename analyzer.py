# analyzer.py - Congress Trading Analyzer
# Detects 10 types of notable trading patterns

from datetime import datetime, timedelta
from database import get_connection
from politicians import get_politician_by_name

# Amount ranges (FMP provides ranges, not exact amounts)
AMOUNT_THRESHOLDS = {
    '$1,001 - $15,000': 8000,
    '$15,001 - $50,000': 32500,
    '$50,001 - $100,000': 75000,
    '$100,001 - $250,000': 175000,
    '$250,001 - $500,000': 375000,
    '$500,001 - $1,000,000': 750000,
    '$1,000,001 - $5,000,000': 3000000,
    '$5,000,001 - $25,000,000': 15000000,
    '$25,000,001 - $50,000,000': 37500000,
    'Over $50,000,000': 50000000
}

# =============================================================================
# CONGRESSIONAL LEADERSHIP (Alert #3)
# Updated: January 2025 - 119th Congress
# =============================================================================
CONGRESSIONAL_LEADERSHIP = {
    # House Leadership
    'Mike Johnson': {'position': 'Speaker of the House', 'chamber': 'House', 'party': 'R'},
    'Steve Scalise': {'position': 'House Majority Leader', 'chamber': 'House', 'party': 'R'},
    'Tom Emmer': {'position': 'House Majority Whip', 'chamber': 'House', 'party': 'R'},
    'Hakeem Jeffries': {'position': 'House Minority Leader', 'chamber': 'House', 'party': 'D'},
    'Katherine Clark': {'position': 'House Minority Whip', 'chamber': 'House', 'party': 'D'},
    'Pete Aguilar': {'position': 'House Democratic Caucus Chair', 'chamber': 'House', 'party': 'D'},
    
    # Senate Leadership
    'John Thune': {'position': 'Senate Majority Leader', 'chamber': 'Senate', 'party': 'R'},
    'Chuck Schumer': {'position': 'Senate Minority Leader', 'chamber': 'Senate', 'party': 'D'},
    'John Barrasso': {'position': 'Senate Majority Whip', 'chamber': 'Senate', 'party': 'R'},
    'Dick Durbin': {'position': 'Senate Minority Whip', 'chamber': 'Senate', 'party': 'D'},
    'Shelley Moore Capito': {'position': 'Senate Republican Conference Chair', 'chamber': 'Senate', 'party': 'R'},
    
    # Key Committee Chairs (often have significant market-moving info)
    'Jason Smith': {'position': 'House Ways & Means Chair', 'chamber': 'House', 'party': 'R'},
    'Patrick McHenry': {'position': 'House Financial Services Chair', 'chamber': 'House', 'party': 'R'},
    'Mike Crapo': {'position': 'Senate Finance Chair', 'chamber': 'Senate', 'party': 'R'},
    'Tim Scott': {'position': 'Senate Banking Chair', 'chamber': 'Senate', 'party': 'R'},
}

# Normalized names for fuzzy matching (handles variations in how names appear)
LEADERSHIP_NAME_VARIANTS = {
    'michael johnson': 'Mike Johnson',
    'steven scalise': 'Steve Scalise',
    'thomas emmer': 'Tom Emmer',
    'katherine m clark': 'Katherine Clark',
    'katherine m. clark': 'Katherine Clark',
    'charles schumer': 'Chuck Schumer',
    'charles e schumer': 'Chuck Schumer',
    'richard durbin': 'Dick Durbin',
    'richard j durbin': 'Dick Durbin',
    'shelley capito': 'Shelley Moore Capito',
}

# Sector mappings for common tickers (expandable)
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
    'META': 'Technology', 'NVDA': 'Technology', 'AMD': 'Technology', 'INTC': 'Technology',
    'CRM': 'Technology', 'ORCL': 'Technology', 'IBM': 'Technology', 'CSCO': 'Technology',
    'ADBE': 'Technology', 'NOW': 'Technology', 'SNOW': 'Technology', 'PLTR': 'Technology',
    # Defense
    'LMT': 'Defense', 'RTX': 'Defense', 'NOC': 'Defense', 'GD': 'Defense', 'BA': 'Defense',
    'HII': 'Defense', 'LHX': 'Defense',
    # Healthcare/Pharma
    'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'UNH': 'Healthcare', 'MRK': 'Healthcare',
    'ABBV': 'Healthcare', 'LLY': 'Healthcare', 'BMY': 'Healthcare', 'AMGN': 'Healthcare',
    'GILD': 'Healthcare', 'MRNA': 'Healthcare', 'BNTX': 'Healthcare',
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy', 'OXY': 'Energy',
    'EOG': 'Energy', 'PSX': 'Energy', 'VLO': 'Energy', 'MPC': 'Energy',
    # Financials
    'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',
    'MS': 'Financials', 'C': 'Financials', 'BLK': 'Financials', 'SCHW': 'Financials',
    # Telecom
    'VZ': 'Telecom', 'T': 'Telecom', 'TMUS': 'Telecom',
    # Retail/Consumer
    'AMZN': 'Retail', 'WMT': 'Retail', 'COST': 'Retail', 'TGT': 'Retail', 'HD': 'Retail',
    # Automotive
    'TSLA': 'Automotive', 'F': 'Automotive', 'GM': 'Automotive', 'RIVN': 'Automotive',
}

# Committee relevance mappings
COMMITTEE_SECTOR_RELEVANCE = {
    'Armed Services': ['Defense'],
    'Defense': ['Defense'],
    'Intelligence': ['Defense', 'Technology'],
    'Energy': ['Energy'],
    'Finance': ['Financials'],
    'Banking': ['Financials'],
    'Health': ['Healthcare'],
    'Commerce': ['Technology', 'Telecom', 'Retail'],
    'Transportation': ['Automotive'],
}


def estimate_amount(amount_range):
    """Convert amount range string to estimated dollar value."""
    if amount_range is None:
        return 0
    return AMOUNT_THRESHOLDS.get(amount_range, 0)


def get_sector(ticker):
    """Get sector for a ticker, or 'Unknown' if not mapped."""
    if ticker is None:
        return 'Unknown'
    return SECTOR_MAP.get(ticker.upper(), 'Unknown')


def normalize_name(name):
    """Normalize a politician name for comparison."""
    if not name:
        return ''
    # Remove titles, extra spaces, convert to lowercase
    normalized = name.lower().strip()
    # Remove common prefixes
    for prefix in ['rep.', 'rep ', 'sen.', 'sen ', 'representative ', 'senator ']:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return normalized.strip()


def is_leadership_member(politician_name):
    """
    Check if a politician is in congressional leadership.
    Returns (is_leader: bool, leadership_info: dict or None)
    """
    if not politician_name:
        return False, None
    
    normalized = normalize_name(politician_name)
    
    # Check direct match first
    for leader_name, info in CONGRESSIONAL_LEADERSHIP.items():
        if normalize_name(leader_name) == normalized:
            return True, {'name': leader_name, **info}
    
    # Check name variants
    if normalized in LEADERSHIP_NAME_VARIANTS:
        canonical_name = LEADERSHIP_NAME_VARIANTS[normalized]
        if canonical_name in CONGRESSIONAL_LEADERSHIP:
            return True, {'name': canonical_name, **CONGRESSIONAL_LEADERSHIP[canonical_name]}
    
    # Partial match (last name + first initial)
    for leader_name, info in CONGRESSIONAL_LEADERSHIP.items():
        leader_parts = leader_name.lower().split()
        name_parts = normalized.split()
        if len(leader_parts) >= 2 and len(name_parts) >= 2:
            # Match last name and first letter of first name
            if leader_parts[-1] == name_parts[-1] and leader_parts[0][0] == name_parts[0][0]:
                return True, {'name': leader_name, **info}
    
    return False, None


def get_recent_transactions(days=7):
    """Fetch transactions from the last N days."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT politician, ticker, trade_date, trade_type, 
               amount_range, company, party
        FROM transactions
        WHERE trade_date >= ?
        ORDER BY trade_date DESC
    ''', (cutoff_date,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    return [dict(t) for t in transactions]


def get_all_historical_transactions():
    """Fetch all transactions for historical analysis."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT politician, ticker, trade_date, trade_type, 
               amount_range, company, party
        FROM transactions
        ORDER BY trade_date DESC
    ''')
    
    transactions = cursor.fetchall()
    conn.close()
    
    return [dict(t) for t in transactions]


# =============================================================================
# YAHOO FINANCE HELPERS (for Alerts #8 and #9)
# =============================================================================

def get_yahoo_earnings_calendar(ticker, trade_date_str):
    """
    Get earnings date for a ticker around a trade date.
    Returns dict with 'next_earnings_date' and 'days_until_earnings' or None.
    
    Requires: pip install yfinance
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
        
        # Get earnings calendar
        calendar = stock.calendar
        if calendar is None or calendar.empty:
            return None
        
        # Look for earnings date
        earnings_date = None
        if 'Earnings Date' in calendar.index:
            earnings_dates = calendar.loc['Earnings Date']
            if hasattr(earnings_dates, '__iter__') and not isinstance(earnings_dates, str):
                # Multiple dates - get the first one
                for ed in earnings_dates:
                    if ed is not None:
                        earnings_date = ed
                        break
            else:
                earnings_date = earnings_dates
        
        if earnings_date is None:
            return None
        
        # Convert to datetime if needed
        if hasattr(earnings_date, 'to_pydatetime'):
            earnings_date = earnings_date.to_pydatetime()
        elif isinstance(earnings_date, str):
            earnings_date = datetime.strptime(earnings_date, '%Y-%m-%d')
        
        days_until = (earnings_date - trade_date).days
        
        return {
            'next_earnings_date': earnings_date.strftime('%Y-%m-%d'),
            'days_until_earnings': days_until
        }
        
    except ImportError:
        print("Warning: yfinance not installed. Pre-event timing alerts disabled.")
        return None
    except Exception as e:
        # Silently fail for individual ticker lookups
        return None


def get_yahoo_price_history(ticker, trade_date_str, lookback_days=30):
    """
    Get price history for a ticker to analyze recent movement.
    Returns dict with price change metrics or None.
    
    Requires: pip install yfinance
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
        
        # Get history for lookback period before trade
        start_date = trade_date - timedelta(days=lookback_days + 5)  # Buffer for weekends
        end_date = trade_date + timedelta(days=1)
        
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty or len(hist) < 5:
            return None
        
        # Get prices
        # Find the closest trading day to trade_date
        hist.index = hist.index.tz_localize(None)  # Remove timezone
        
        # Get price on or before trade date
        valid_dates = hist.index[hist.index <= trade_date]
        if len(valid_dates) == 0:
            return None
        
        trade_day_price = hist.loc[valid_dates[-1], 'Close']
        
        # Calculate various lookback returns
        results = {
            'trade_date_price': round(trade_day_price, 2),
        }
        
        for days in [5, 10, 20, 30]:
            lookback_date = trade_date - timedelta(days=days)
            valid_lookback = hist.index[hist.index <= lookback_date]
            if len(valid_lookback) > 0:
                lookback_price = hist.loc[valid_lookback[-1], 'Close']
                pct_change = ((trade_day_price - lookback_price) / lookback_price) * 100
                results[f'return_{days}d'] = round(pct_change, 2)
        
        return results
        
    except ImportError:
        print("Warning: yfinance not installed. Against-the-market alerts disabled.")
        return None
    except Exception as e:
        return None


# =============================================================================
# ALERT ANALYZERS
# =============================================================================

def analyze_clusters(transactions, days=7):
    """
    ALERT TYPE 1: Cluster Detection
    Find 2+ politicians trading the same stock within the time window.
    """
    alerts = []
    
    # Group by ticker
    ticker_trades = {}
    for t in transactions:
        ticker = t['ticker']
        if not ticker:
            continue
        if ticker not in ticker_trades:
            ticker_trades[ticker] = []
        ticker_trades[ticker].append(t)
    
    # Find clusters
    for ticker, trades in ticker_trades.items():
        politicians = set(t['politician'] for t in trades if t['politician'])
        if len(politicians) >= 2:
            # Get party breakdown
            parties = [t['party'] for t in trades if t['party']]
            party_counts = {'Republican': parties.count('Republican'), 
                          'Democrat': parties.count('Democrat')}
            
            bipartisan = party_counts['Republican'] > 0 and party_counts['Democrat'] > 0
            
            alerts.append({
                'type': 'CLUSTER',
                'ticker': ticker,
                'politician_count': len(politicians),
                'politicians': list(politicians),
                'trades': trades,
                'bipartisan': bipartisan,
                'party_breakdown': party_counts,
                'priority': 'HIGH' if bipartisan else 'MEDIUM'
            })
    
    return alerts


def analyze_bipartisan(transactions):
    """
    ALERT TYPE 10: Bipartisan Trading
    Specifically flag when BOTH Republicans AND Democrats are buying the same stock.
    This is a strong signal - when opposing parties agree on a trade, pay attention.
    """
    alerts = []
    
    # Group by ticker and filter for purchases only
    ticker_buys = {}
    for t in transactions:
        ticker = t['ticker']
        trade_type = t.get('trade_type', '').lower()
        
        if not ticker or trade_type not in ['purchase', 'buy']:
            continue
        
        if ticker not in ticker_buys:
            ticker_buys[ticker] = {'Republican': [], 'Democrat': []}
        
        party = t.get('party', '')
        if party == 'Republican':
            ticker_buys[ticker]['Republican'].append(t)
        elif party == 'Democrat':
            ticker_buys[ticker]['Democrat'].append(t)
    
    # Find bipartisan buys
    for ticker, party_trades in ticker_buys.items():
        rep_trades = party_trades['Republican']
        dem_trades = party_trades['Democrat']
        
        # Must have at least 1 from each party
        if len(rep_trades) >= 1 and len(dem_trades) >= 1:
            rep_politicians = list(set(t['politician'] for t in rep_trades))
            dem_politicians = list(set(t['politician'] for t in dem_trades))
            
            total_amount = sum(estimate_amount(t.get('amount_range')) for t in rep_trades + dem_trades)
            
            # Higher priority if multiple from each party, or large amounts
            politician_count = len(rep_politicians) + len(dem_politicians)
            if politician_count >= 4 or total_amount >= 500000:
                priority = 'HIGH'
            elif politician_count >= 3 or total_amount >= 250000:
                priority = 'HIGH'
            else:
                priority = 'MEDIUM'
            
            alerts.append({
                'type': 'BIPARTISAN',
                'ticker': ticker,
                'republican_politicians': rep_politicians,
                'democrat_politicians': dem_politicians,
                'republican_count': len(rep_politicians),
                'democrat_count': len(dem_politicians),
                'total_politicians': politician_count,
                'republican_trades': rep_trades,
                'democrat_trades': dem_trades,
                'estimated_total_amount': total_amount,
                'priority': priority
            })
    
    return alerts


def analyze_committee_relevant(transactions):
    """
    ALERT TYPE 2: Committee-Relevant Trades
    Flag trades where politician's committee oversees the sector.
    """
    alerts = []
    
    for t in transactions:
        politician_info = get_politician_by_name(t['politician'])
        if not politician_info or not politician_info.get('committees'):
            continue
        
        ticker_sector = get_sector(t['ticker'])
        if ticker_sector == 'Unknown':
            continue
        
        # Check committee relevance
        for committee in politician_info['committees']:
            for committee_key, relevant_sectors in COMMITTEE_SECTOR_RELEVANCE.items():
                if committee_key.lower() in committee.lower():
                    if ticker_sector in relevant_sectors:
                        alerts.append({
                            'type': 'COMMITTEE_RELEVANT',
                            'politician': t['politician'],
                            'ticker': t['ticker'],
                            'sector': ticker_sector,
                            'committee': committee,
                            'transaction': t,
                            'priority': 'HIGH'
                        })
                        break
    
    return alerts


def analyze_leadership_trades(transactions):
    """
    ALERT TYPE 3: Leadership Trades
    Flag any trade by a congressional leadership member.
    These individuals have access to sensitive legislative information.
    """
    alerts = []
    
    for t in transactions:
        is_leader, leader_info = is_leadership_member(t['politician'])
        
        if is_leader:
            estimated_amount = estimate_amount(t['amount_range'])
            
            # Higher priority for top leadership (Speaker, Majority/Minority Leaders)
            top_positions = ['Speaker', 'Majority Leader', 'Minority Leader']
            is_top_leader = any(pos in leader_info['position'] for pos in top_positions)
            
            alerts.append({
                'type': 'LEADERSHIP_TRADE',
                'politician': t['politician'],
                'position': leader_info['position'],
                'chamber': leader_info['chamber'],
                'ticker': t['ticker'],
                'company': t.get('company', ''),
                'trade_type': t['trade_type'],
                'amount_range': t['amount_range'],
                'estimated_amount': estimated_amount,
                'transaction': t,
                'priority': 'HIGH' if is_top_leader else 'MEDIUM'
            })
    
    return alerts


def analyze_large_trades(transactions, threshold=250000):
    """
    ALERT TYPE 4: Large Trades
    Flag trades over the threshold amount.
    """
    alerts = []
    
    for t in transactions:
        estimated = estimate_amount(t['amount_range'])
        if estimated >= threshold:
            alerts.append({
                'type': 'LARGE_TRADE',
                'politician': t['politician'],
                'ticker': t['ticker'],
                'amount_range': t['amount_range'],
                'estimated_amount': estimated,
                'transaction': t,
                'priority': 'HIGH' if estimated >= 500000 else 'MEDIUM'
            })
    
    return alerts


def analyze_sector_surge(transactions, min_politicians=3):
    """
    ALERT TYPE 5: Sector Surge
    Find 3+ politicians trading different stocks in the same sector.
    """
    alerts = []
    
    # Group by sector
    sector_trades = {}
    for t in transactions:
        sector = get_sector(t['ticker'])
        if sector == 'Unknown':
            continue
        if sector not in sector_trades:
            sector_trades[sector] = []
        sector_trades[sector].append(t)
    
    # Find surges
    for sector, trades in sector_trades.items():
        politicians = set(t['politician'] for t in trades if t['politician'])
        tickers = set(t['ticker'] for t in trades if t['ticker'])
        
        # Need 3+ politicians AND different stocks
        if len(politicians) >= min_politicians and len(tickers) > 1:
            parties = [t['party'] for t in trades if t['party']]
            party_counts = {'Republican': parties.count('Republican'), 
                          'Democrat': parties.count('Democrat')}
            bipartisan = party_counts['Republican'] > 0 and party_counts['Democrat'] > 0
            
            alerts.append({
                'type': 'SECTOR_SURGE',
                'sector': sector,
                'politician_count': len(politicians),
                'politicians': list(politicians),
                'tickers': list(tickers),
                'trades': trades,
                'bipartisan': bipartisan,
                'priority': 'HIGH' if bipartisan else 'MEDIUM'
            })
    
    return alerts


def analyze_repeat_buyers(transactions, all_transactions=None):
    """
    ALERT TYPE 6: Repeat Buyer
    Same politician buying the same stock multiple times.
    """
    alerts = []
    
    if all_transactions is None:
        all_transactions = get_all_historical_transactions()
    
    # For each recent transaction, check history
    for t in transactions:
        if t['trade_type'] not in ['purchase', 'buy']:
            continue
        
        # Count previous purchases of same ticker by same politician
        previous = [
            h for h in all_transactions 
            if h['politician'] == t['politician'] 
            and h['ticker'] == t['ticker']
            and h['trade_date'] < t['trade_date']
            and h['trade_type'] in ['purchase', 'buy']
        ]
        
        if len(previous) >= 1:  # At least 1 previous purchase
            alerts.append({
                'type': 'REPEAT_BUYER',
                'politician': t['politician'],
                'ticker': t['ticker'],
                'current_transaction': t,
                'previous_count': len(previous),
                'total_purchases': len(previous) + 1,
                'priority': 'MEDIUM' if len(previous) == 1 else 'HIGH'
            })
    
    return alerts


def analyze_new_positions(transactions, all_transactions=None):
    """
    ALERT TYPE 7: New Position
    First-ever trade in a ticker by this politician.
    """
    alerts = []
    
    if all_transactions is None:
        all_transactions = get_all_historical_transactions()
    
    for t in transactions:
        # Check if politician has any previous trades in this ticker
        previous = [
            h for h in all_transactions
            if h['politician'] == t['politician']
            and h['ticker'] == t['ticker']
            and h['trade_date'] < t['trade_date']
        ]
        
        if len(previous) == 0:
            alerts.append({
                'type': 'NEW_POSITION',
                'politician': t['politician'],
                'ticker': t['ticker'],
                'transaction': t,
                'priority': 'LOW'
            })
    
    return alerts


def analyze_pre_event_timing(transactions, days_before_earnings=14):
    """
    ALERT TYPE 8: Pre-Event Timing
    Flag trades made shortly before earnings announcements.
    Requires yfinance for earnings calendar data.
    """
    alerts = []
    
    # Cache earnings lookups to avoid repeated API calls
    earnings_cache = {}
    
    for t in transactions:
        ticker = t['ticker']
        if not ticker:
            continue
        
        # Check cache first
        cache_key = f"{ticker}_{t['trade_date']}"
        if cache_key in earnings_cache:
            earnings_info = earnings_cache[cache_key]
        else:
            earnings_info = get_yahoo_earnings_calendar(ticker, t['trade_date'])
            earnings_cache[cache_key] = earnings_info
        
        if earnings_info is None:
            continue
        
        days_until = earnings_info['days_until_earnings']
        
        # Flag if trade is 1-14 days before earnings (configurable)
        # Negative days means earnings already passed
        if 0 < days_until <= days_before_earnings:
            # Higher priority if very close to earnings
            if days_until <= 5:
                priority = 'HIGH'
            elif days_until <= 10:
                priority = 'MEDIUM'
            else:
                priority = 'LOW'
            
            alerts.append({
                'type': 'PRE_EARNINGS',
                'politician': t['politician'],
                'ticker': ticker,
                'trade_date': t['trade_date'],
                'trade_type': t['trade_type'],
                'earnings_date': earnings_info['next_earnings_date'],
                'days_before_earnings': days_until,
                'transaction': t,
                'priority': priority
            })
    
    return alerts


def analyze_against_market(transactions, threshold_pct=10.0):
    """
    ALERT TYPE 9: Against-the-Market Trades
    Flag trades that go opposite to recent strong price movement.
    
    - BUY after stock rose significantly (chasing momentum, or insider knowledge of more upside?)
    - SELL after stock dropped significantly (cutting losses, or insider knowledge of more downside?)
    
    The suspicious pattern is buying into strength or selling into weakness
    when most retail would do the opposite.
    
    Requires yfinance for price history.
    """
    alerts = []
    
    # Cache price lookups
    price_cache = {}
    
    for t in transactions:
        ticker = t['ticker']
        if not ticker:
            continue
        
        trade_type = t.get('trade_type', '').lower()
        if trade_type not in ['purchase', 'buy', 'sale', 'sell']:
            continue
        
        is_buy = trade_type in ['purchase', 'buy']
        
        # Check cache first
        cache_key = f"{ticker}_{t['trade_date']}"
        if cache_key in price_cache:
            price_info = price_cache[cache_key]
        else:
            price_info = get_yahoo_price_history(ticker, t['trade_date'])
            price_cache[cache_key] = price_info
        
        if price_info is None:
            continue
        
        # Check 10-day and 20-day returns
        return_10d = price_info.get('return_10d')
        return_20d = price_info.get('return_20d')
        
        if return_10d is None:
            continue
        
        alert_reason = None
        
        # BUY after significant rise (>threshold%)
        if is_buy and return_10d >= threshold_pct:
            alert_reason = f"Bought after {return_10d:+.1f}% gain (10d)"
        
        # SELL after significant drop (< -threshold%)
        elif not is_buy and return_10d <= -threshold_pct:
            alert_reason = f"Sold after {return_10d:+.1f}% drop (10d)"
        
        # Also check 20-day for larger moves
        elif return_20d is not None:
            if is_buy and return_20d >= threshold_pct * 1.5:
                alert_reason = f"Bought after {return_20d:+.1f}% gain (20d)"
            elif not is_buy and return_20d <= -threshold_pct * 1.5:
                alert_reason = f"Sold after {return_20d:+.1f}% drop (20d)"
        
        if alert_reason:
            # More extreme moves = higher priority
            extreme_move = abs(return_10d) >= threshold_pct * 2
            
            alerts.append({
                'type': 'AGAINST_MARKET',
                'politician': t['politician'],
                'ticker': ticker,
                'trade_type': t['trade_type'],
                'trade_date': t['trade_date'],
                'reason': alert_reason,
                'price_at_trade': price_info.get('trade_date_price'),
                'return_10d': return_10d,
                'return_20d': return_20d,
                'transaction': t,
                'priority': 'HIGH' if extreme_move else 'MEDIUM'
            })
    
    return alerts


def run_all_analysis(days=7, include_yahoo_alerts=True):
    """
    Run all alert types and return consolidated results.
    
    Args:
        days: Number of days to look back for recent transactions
        include_yahoo_alerts: If True, run alerts #8 and #9 (requires yfinance + internet)
    """
    print(f"Running analysis for last {days} days...")
    
    transactions = get_recent_transactions(days)
    print(f"Found {len(transactions)} recent transactions")
    
    if not transactions:
        return {
            'transaction_count': 0,
            'alerts': [],
            'summary': {
                'clusters': 0,
                'bipartisan': 0,
                'committee_relevant': 0,
                'leadership': 0,
                'large_trades': 0,
                'sector_surges': 0,
                'repeat_buyers': 0,
                'new_positions': 0,
                'pre_earnings': 0,
                'against_market': 0,
                'total_alerts': 0,
                'high_priority': 0,
                'medium_priority': 0,
                'low_priority': 0
            }
        }
    
    # Get historical data once for efficiency
    all_transactions = get_all_historical_transactions()
    
    # Run all analyzers
    all_alerts = []
    
    clusters = analyze_clusters(transactions, days)
    all_alerts.extend(clusters)
    print(f"  Clusters: {len(clusters)}")
    
    bipartisan = analyze_bipartisan(transactions)
    all_alerts.extend(bipartisan)
    print(f"  Bipartisan: {len(bipartisan)}")
    
    committee = analyze_committee_relevant(transactions)
    all_alerts.extend(committee)
    print(f"  Committee-relevant: {len(committee)}")
    
    leadership = analyze_leadership_trades(transactions)
    all_alerts.extend(leadership)
    print(f"  Leadership trades: {len(leadership)}")
    
    large = analyze_large_trades(transactions)
    all_alerts.extend(large)
    print(f"  Large trades: {len(large)}")
    
    sector = analyze_sector_surge(transactions)
    all_alerts.extend(sector)
    print(f"  Sector surges: {len(sector)}")
    
    repeat = analyze_repeat_buyers(transactions, all_transactions)
    all_alerts.extend(repeat)
    print(f"  Repeat buyers: {len(repeat)}")
    
    new_pos = analyze_new_positions(transactions, all_transactions)
    all_alerts.extend(new_pos)
    print(f"  New positions: {len(new_pos)}")
    
    # Yahoo Finance alerts (optional - require internet + yfinance)
    pre_earnings = []
    against_market = []
    
    if include_yahoo_alerts:
        try:
            print("  Checking pre-earnings timing (requires yfinance)...")
            pre_earnings = analyze_pre_event_timing(transactions)
            all_alerts.extend(pre_earnings)
            print(f"  Pre-earnings: {len(pre_earnings)}")
            
            print("  Checking against-market trades (requires yfinance)...")
            against_market = analyze_against_market(transactions)
            all_alerts.extend(against_market)
            print(f"  Against-market: {len(against_market)}")
        except Exception as e:
            print(f"  Warning: Yahoo Finance alerts skipped - {e}")
    
    # Sort by priority
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    all_alerts.sort(key=lambda x: priority_order.get(x.get('priority', 'LOW'), 3))
    
    return {
        'transaction_count': len(transactions),
        'alerts': all_alerts,
        'summary': {
            'clusters': len(clusters),
            'bipartisan': len(bipartisan),
            'committee_relevant': len(committee),
            'leadership': len(leadership),
            'large_trades': len(large),
            'sector_surges': len(sector),
            'repeat_buyers': len(repeat),
            'new_positions': len(new_pos),
            'pre_earnings': len(pre_earnings),
            'against_market': len(against_market),
            'total_alerts': len(all_alerts),
            'high_priority': len([a for a in all_alerts if a.get('priority') == 'HIGH']),
            'medium_priority': len([a for a in all_alerts if a.get('priority') == 'MEDIUM']),
            'low_priority': len([a for a in all_alerts if a.get('priority') == 'LOW'])
        }
    }


if __name__ == '__main__':
    results = run_all_analysis(days=7, include_yahoo_alerts=True)
    print(f"\n=== ANALYSIS COMPLETE ===")
    print(f"Transactions analyzed: {results['transaction_count']}")
    print(f"Total alerts: {results['summary']['total_alerts']}")
    print(f"  HIGH priority: {results['summary']['high_priority']}")
    print(f"  MEDIUM priority: {results['summary']['medium_priority']}")
    print(f"  LOW priority: {results['summary']['low_priority']}")
    print(f"\nAlert breakdown:")
    print(f"  Clusters: {results['summary']['clusters']}")
    print(f"  Bipartisan: {results['summary']['bipartisan']}")
    print(f"  Committee-relevant: {results['summary']['committee_relevant']}")
    print(f"  Leadership: {results['summary']['leadership']}")
    print(f"  Large trades: {results['summary']['large_trades']}")
    print(f"  Sector surges: {results['summary']['sector_surges']}")
    print(f"  Repeat buyers: {results['summary']['repeat_buyers']}")
    print(f"  New positions: {results['summary']['new_positions']}")
    print(f"  Pre-earnings: {results['summary']['pre_earnings']}")
    print(f"  Against-market: {results['summary']['against_market']}")
