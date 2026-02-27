"""
Congressional Trading Tracker - Database Module
================================================
SQLite storage for transactions, politicians, and alert tracking.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import config


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Main transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT UNIQUE,  -- Unique ID to prevent duplicates
            politician TEXT NOT NULL,
            chamber TEXT,                 -- 'House' or 'Senate'
            party TEXT,                   -- 'D', 'R', 'I'
            state TEXT,
            ticker TEXT NOT NULL,
            company TEXT,
            trade_type TEXT,              -- 'buy', 'sell', 'exchange'
            trade_date DATE,
            disclosure_date DATE,
            amount_range TEXT,
            amount_low INTEGER,
            amount_high INTEGER,
            committees TEXT,              -- JSON list of committees
            is_leadership INTEGER DEFAULT 0,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Indexes for faster queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON transactions(ticker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_date ON transactions(trade_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_politician ON transactions(politician)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_disclosure_date ON transactions(disclosure_date)")
    
    # Table to track sent alerts (prevent duplicates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT,              -- 'cluster', 'single', etc.
            ticker TEXT,
            alert_hash TEXT UNIQUE,       -- Hash of alert content for deduplication
            politicians TEXT,             -- JSON list of politicians in alert
            score REAL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table to cache politician metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS politicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            chamber TEXT,
            party TEXT,
            state TEXT,
            district TEXT,
            committees TEXT,              -- JSON list
            leadership_position TEXT,
            is_leadership INTEGER DEFAULT 0,
            last_updated TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def transaction_exists(transaction_id: str) -> bool:
    """Check if a transaction already exists in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM transactions WHERE transaction_id = ?", (transaction_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def save_transaction(txn: Dict) -> bool:
    """
    Save a transaction to the database.
    Returns True if new transaction was saved, False if duplicate.
    """
    if transaction_exists(txn.get('transaction_id', '')):
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO transactions (
                transaction_id, politician, chamber, party, state, ticker, company,
                trade_type, trade_date, disclosure_date, amount_range,
                amount_low, amount_high, committees, is_leadership, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn.get('transaction_id'),
            txn.get('politician'),
            txn.get('chamber'),
            txn.get('party'),
            txn.get('state'),
            txn.get('ticker'),
            txn.get('company'),
            txn.get('trade_type'),
            txn.get('trade_date'),
            txn.get('disclosure_date'),
            txn.get('amount_range'),
            txn.get('amount_low'),
            txn.get('amount_high'),
            txn.get('committees'),
            txn.get('is_leadership', 0),
            txn.get('source_url')
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_recent_transactions(days: int = 14, ticker: str = None) -> List[Dict]:
    """
    Get transactions from the last N days.
    Optionally filter by ticker.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    if ticker:
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE trade_date >= ? AND ticker = ?
            ORDER BY trade_date DESC
        """, (cutoff_date, ticker.upper()))
    else:
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE trade_date >= ?
            ORDER BY trade_date DESC
        """, (cutoff_date,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_transactions_by_ticker(ticker: str, days: int = 14) -> List[Dict]:
    """Get all transactions for a specific ticker within the window."""
    return get_recent_transactions(days=days, ticker=ticker)


def get_unique_tickers_recent(days: int = 14) -> List[str]:
    """Get list of unique tickers traded in the last N days."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT DISTINCT ticker FROM transactions 
        WHERE trade_date >= ? AND ticker IS NOT NULL AND ticker != ''
        ORDER BY ticker
    """, (cutoff_date,))
    
    results = [row['ticker'] for row in cursor.fetchall()]
    conn.close()
    return results


def alert_already_sent(alert_hash: str) -> bool:
    """Check if an alert with this hash was already sent."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if sent within cooldown period
    cooldown = datetime.now() - timedelta(hours=config.ALERT_COOLDOWN_HOURS)
    
    cursor.execute("""
        SELECT 1 FROM alerts_sent 
        WHERE alert_hash = ? AND sent_at > ?
    """, (alert_hash, cooldown.strftime('%Y-%m-%d %H:%M:%S')))
    
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def record_alert_sent(alert_type: str, ticker: str, alert_hash: str, 
                      politicians: str, score: float):
    """Record that an alert was sent."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO alerts_sent 
        (alert_type, ticker, alert_hash, politicians, score, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alert_type, ticker, alert_hash, politicians, score, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()


def get_database_stats() -> Dict:
    """Get statistics about the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Total transactions
    cursor.execute("SELECT COUNT(*) as count FROM transactions")
    stats['total_transactions'] = cursor.fetchone()['count']
    
    # Unique politicians
    cursor.execute("SELECT COUNT(DISTINCT politician) as count FROM transactions")
    stats['unique_politicians'] = cursor.fetchone()['count']
    
    # Unique tickers
    cursor.execute("SELECT COUNT(DISTINCT ticker) as count FROM transactions WHERE ticker IS NOT NULL")
    stats['unique_tickers'] = cursor.fetchone()['count']
    
    # Date range
    cursor.execute("SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date FROM transactions")
    row = cursor.fetchone()
    stats['earliest_trade'] = row['min_date']
    stats['latest_trade'] = row['max_date']
    
    # Transactions by chamber
    cursor.execute("""
        SELECT chamber, COUNT(*) as count 
        FROM transactions 
        GROUP BY chamber
    """)
    stats['by_chamber'] = {row['chamber']: row['count'] for row in cursor.fetchall()}
    
    # Recent transactions (last 7 days)
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE disclosure_date >= ?", (cutoff,))
    stats['transactions_last_7_days'] = cursor.fetchone()['count']
    
    # Alerts sent
    cursor.execute("SELECT COUNT(*) as count FROM alerts_sent")
    stats['alerts_sent'] = cursor.fetchone()['count']
    
    conn.close()
    return stats


def get_top_traded_tickers(days: int = 14, limit: int = 10) -> List[Dict]:
    """Get most frequently traded tickers."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT ticker, 
               COUNT(*) as trade_count,
               COUNT(DISTINCT politician) as politician_count,
               GROUP_CONCAT(DISTINCT party) as parties
        FROM transactions 
        WHERE trade_date >= ? AND ticker IS NOT NULL AND ticker != ''
        GROUP BY ticker
        HAVING trade_count >= 2
        ORDER BY politician_count DESC, trade_count DESC
        LIMIT ?
    """, (cutoff_date, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


if __name__ == "__main__":
    init_database()
    stats = get_database_stats()
    print(f"\nDatabase Stats:")
    print(f"  Total transactions: {stats['total_transactions']}")
    print(f"  Unique politicians: {stats['unique_politicians']}")
    print(f"  Unique tickers: {stats['unique_tickers']}")
    print(f"\nDatabase test complete.")
