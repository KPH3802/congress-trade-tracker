#!/usr/bin/env python3
"""
Congressional Trading Tracker - Main Script
============================================
Monitors congressional stock trades and sends daily analysis reports.

Usage:
    python main.py              # Full scan: fetch, analyze, send report
    python main.py --dry-run    # Test without sending emails
    python main.py --fetch-only # Only fetch new data
    python main.py --analyze-only # Only analyze (no fetch)
    python main.py --status     # Show database status
    python main.py --test-email # Send test email
"""

import sys
from datetime import datetime, timezone

import config
import database
import data_fetcher
import analyzer
import emailer


def run_full_scan(dry_run: bool = False) -> dict:
    """
    Run the complete scan workflow:
    1. Fetch new transactions from FMP API
    2. Analyze for all 9 alert types
    3. Send daily analysis report
    
    Returns:
        Dict with results summary
    """
    print(f"\n{'#'*60}")
    print(f"# CONGRESSIONAL TRADING TRACKER")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")
    
    if dry_run:
        print("\n*** DRY RUN MODE - No emails will be sent ***")
    
    results = {
        'fetch': None,
        'analysis': None,
        'emails_sent': 0,
        'status': 'complete'
    }
    
    # Step 1: Fetch new transactions
    print("\n" + "="*60)
    print("STEP 1: FETCHING DATA")
    print("="*60)
    
    fetch_results = data_fetcher.fetch_and_store_transactions()
    results['fetch'] = fetch_results
    
    # Step 2: Analyze for all 9 alert types
    print("\n" + "="*60)
    print("STEP 2: ANALYZING PATTERNS (9 Alert Types)")
    print("="*60)
    
    analysis_results = analyzer.run_all_analysis(days=7, include_yahoo_alerts=True)
    results['analysis'] = analysis_results
    
    summary = analysis_results.get('summary', {})
    print(f"\nAnalysis Summary:")
    print(f"  Transactions analyzed: {analysis_results.get('transaction_count', 0)}")
    print(f"  Total alerts: {summary.get('total_alerts', 0)}")
    print(f"  HIGH priority: {summary.get('high_priority', 0)}")
    print(f"  MEDIUM priority: {summary.get('medium_priority', 0)}")
    print(f"  LOW priority: {summary.get('low_priority', 0)}")
    
    # Step 3: Send daily analysis report
    print("\n" + "="*60)
    print("STEP 3: SENDING DAILY REPORT")
    print("="*60)
    
    if emailer.send_analysis_report(analysis_results, dry_run=dry_run):
        results['emails_sent'] = 1
        print(f"✓ Daily analysis report sent")
    else:
        print("✗ Failed to send report email")
        results['status'] = 'email_failed'
    
    # Summary
    print("\n" + "#"*60)
    print("# SCAN COMPLETE")
    print("#"*60)
    print(f"  New transactions: {fetch_results.get('new_transactions', 0)}")
    print(f"  Total alerts: {summary.get('total_alerts', 0)}")
    print(f"  High priority: {summary.get('high_priority', 0)}")
    print(f"  Report sent: {'Yes' if results['emails_sent'] else 'No'}")
    
    return results


def show_status():
    """Display current database status."""
    database.init_database()
    stats = database.get_database_stats()
    
    print(f"\n{'='*60}")
    print("CONGRESSIONAL TRADING TRACKER - STATUS")
    print(f"{'='*60}")
    print(f"\nDatabase: {config.DATABASE_PATH}")
    print(f"\nTransactions:")
    print(f"  Total: {stats['total_transactions']:,}")
    print(f"  Unique politicians: {stats['unique_politicians']}")
    print(f"  Unique tickers: {stats['unique_tickers']}")
    
    if stats['earliest_trade']:
        print(f"  Date range: {stats['earliest_trade']} to {stats['latest_trade']}")
    
    print(f"\nRecent Activity:")
    print(f"  Last 7 days: {stats['transactions_last_7_days']} transactions")
    print(f"  Alerts sent: {stats['alerts_sent']}")
    
    if stats.get('by_chamber'):
        print(f"\nBy Chamber:")
        for chamber, count in stats['by_chamber'].items():
            print(f"  {chamber}: {count}")
    
    # Show top traded tickers
    top_tickers = database.get_top_traded_tickers(days=14, limit=5)
    if top_tickers:
        print(f"\nMost Active Tickers (14 days):")
        for t in top_tickers:
            parties = t.get('parties', '')
            print(f"  {t['ticker']}: {t['politician_count']} politicians, {t['trade_count']} trades ({parties})")
    
    # Run quick analysis
    print(f"\n{'='*60}")
    print("CURRENT ALERTS")
    print(f"{'='*60}")
    
    analysis = analyzer.run_all_analysis(days=7, include_yahoo_alerts=False)
    summary = analysis.get('summary', {})
    
    print(f"\nAlert Summary (last 7 days):")
    print(f"  Clusters: {summary.get('clusters', 0)}")
    print(f"  Committee-relevant: {summary.get('committee_relevant', 0)}")
    print(f"  Leadership: {summary.get('leadership', 0)}")
    print(f"  Large trades: {summary.get('large_trades', 0)}")
    print(f"  Sector surges: {summary.get('sector_surges', 0)}")
    print(f"  Repeat buyers: {summary.get('repeat_buyers', 0)}")
    print(f"  New positions: {summary.get('new_positions', 0)}")
    
    if summary.get('high_priority', 0) > 0:
        print(f"\n⚠️  {summary['high_priority']} HIGH PRIORITY alert(s)!")


def main():
    """Main entry point."""

    # Parse arguments
    args = sys.argv[1:]
    
    dry_run = '--dry-run' in args
    fetch_only = '--fetch-only' in args
    analyze_only = '--analyze-only' in args
    status_only = '--status' in args
    test_email = '--test-email' in args
    
    # Initialize database
    database.init_database()
    
    # Handle different modes
    if test_email:
        print("Sending test email...")
        if emailer.send_test_email():
            print("✅ Test email sent!")
        else:
            print("❌ Failed to send test email")
        return
    
    if status_only:
        show_status()
        return
    
    if fetch_only:
        print("Fetching data only...")
        data_fetcher.fetch_and_store_transactions()
        return
    
    if analyze_only:
        print("Analyzing only (no fetch)...")
        analysis_results = analyzer.run_all_analysis(days=7, include_yahoo_alerts=True)
        
        if not dry_run:
            emailer.send_analysis_report(analysis_results, dry_run=False)
        else:
            emailer.send_analysis_report(analysis_results, dry_run=True)
        return
    
    # Default: full scan
    run_full_scan(dry_run=dry_run)


if __name__ == '__main__':
    main()
