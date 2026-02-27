# congress_main.py - Congressional Trading Tracker Main Script
# Fetches data, runs analysis, sends daily status email

import os
import sys
from datetime import datetime, timedelta

from config import EMAIL_RECIPIENT
from data_fetcher import CongressionalDataFetcher
from database import init_database, get_connection
from analyzer import run_all_analysis
from emailer import send_email


def get_database_stats():
    """Get current database statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total transactions
    cursor.execute('SELECT COUNT(*) FROM transactions')
    total = cursor.fetchone()[0]
    
    # Transactions by party
    cursor.execute('''
        SELECT party, COUNT(*) as count 
        FROM transactions 
        GROUP BY party
    ''')
    party_counts = {row['party']: row['count'] for row in cursor.fetchall()}
    
    # Unique politicians
    cursor.execute('SELECT COUNT(DISTINCT politician) FROM transactions')
    unique_politicians = cursor.fetchone()[0]
    
    # Unique tickers
    cursor.execute('SELECT COUNT(DISTINCT ticker) FROM transactions')
    unique_tickers = cursor.fetchone()[0]
    
    # Date range
    cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM transactions')
    date_range = cursor.fetchone()
    
    # Today's new transactions
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM transactions WHERE DATE(created_at) = ?', (today,))
    new_today = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'party_counts': party_counts,
        'unique_politicians': unique_politicians,
        'unique_tickers': unique_tickers,
        'earliest_date': date_range[0],
        'latest_date': date_range[1],
        'new_today': new_today
    }


def format_alert_html(alert):
    """Format a single alert as HTML."""
    alert_type = alert.get('type', 'UNKNOWN')
    priority = alert.get('priority', 'LOW')
    
    # Priority colors
    priority_colors = {
        'HIGH': '#dc3545',
        'MEDIUM': '#fd7e14', 
        'LOW': '#6c757d'
    }
    priority_color = priority_colors.get(priority, '#6c757d')
    
    html = f'<div style="border-left: 4px solid {priority_color}; padding: 10px; margin: 10px 0; background: #f8f9fa;">'
    html += f'<strong style="color: {priority_color};">[{priority}] {alert_type}</strong><br>'
    
    if alert_type == 'CLUSTER':
        bipartisan_badge = ' <span style="background: #9b59b6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">BIPARTISAN</span>' if alert.get('bipartisan') else ''
        html += f'<strong>{alert["ticker"]}</strong>{bipartisan_badge}<br>'
        html += f'{alert["politician_count"]} politicians: {", ".join(alert["politicians"][:5])}'
        if len(alert["politicians"]) > 5:
            html += f' (+{len(alert["politicians"]) - 5} more)'
        html += f'<br>Party breakdown: R: {alert["party_breakdown"].get("Republican", 0)}, D: {alert["party_breakdown"].get("Democrat", 0)}'
    
    elif alert_type == 'COMMITTEE_RELEVANT':
        html += f'<strong>{alert["politician"]}</strong> traded <strong>{alert["ticker"]}</strong> ({alert["sector"]})<br>'
        html += f'Committee: {alert["committee"]}'
    
    elif alert_type == 'LEADERSHIP':
        t = alert['transaction']
        html += f'<strong>{alert["politician"]}</strong> ({alert.get("position", "Leadership")})<br>'
        html += f'{t["transaction_type"].upper()} {t["ticker"]} - {t["amount"]}'
    
    elif alert_type == 'LARGE_TRADE':
        t = alert['transaction']
        html += f'<strong>{alert["politician"]}</strong> - ${alert["estimated_amount"]:,.0f} (est.)<br>'
        html += f'{t["transaction_type"].upper()} {t["ticker"]} - {t["amount"]}'
    
    elif alert_type == 'SECTOR_SURGE':
        bipartisan_badge = ' <span style="background: #9b59b6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">BIPARTISAN</span>' if alert.get('bipartisan') else ''
        html += f'<strong>{alert["sector"]}</strong> sector{bipartisan_badge}<br>'
        html += f'{alert["politician_count"]} politicians trading {len(alert["tickers"])} stocks<br>'
        html += f'Tickers: {", ".join(alert["tickers"][:8])}'
        if len(alert["tickers"]) > 8:
            html += f' (+{len(alert["tickers"]) - 8} more)'
    
    elif alert_type == 'REPEAT_BUYER':
        html += f'<strong>{alert["politician"]}</strong> bought <strong>{alert["ticker"]}</strong> again<br>'
        html += f'This is purchase #{alert["total_purchases"]} of this stock'
    
    elif alert_type == 'NEW_POSITION':
        t = alert['transaction']
        html += f'<strong>{alert["politician"]}</strong> - first trade in <strong>{alert["ticker"]}</strong><br>'
        html += f'{t["transaction_type"].upper()} - {t["amount"]}'
    
    elif alert_type == 'AGAINST_MARKET':
        price = alert.get('price_at_trade', 'N/A')
        if isinstance(price, float):
            price = f'${price:.2f}'
        html += f'<strong>{alert.get("politician", "Unknown")}</strong> traded <strong>{alert.get("ticker", "N/A")}</strong><br>'
        html += f'{alert.get("trade_type", "N/A").upper()} - {alert.get("reason", "Price movement detected")}<br>'
        html += f'Price: {price}'
    
    elif alert_type == 'PRE_EARNINGS':
        html += f'<strong>{alert.get("politician", "Unknown")}</strong> traded <strong>{alert.get("ticker", "N/A")}</strong><br>'
        html += f'{alert.get("trade_type", "N/A").upper()} - {alert.get("days_before_earnings", "?")} days before earnings<br>'
        html += f'Earnings date: {alert.get("earnings_date", "N/A")}'
    
    elif alert_type == 'BIPARTISAN':
        html += f'<strong>{alert.get("ticker", "N/A")}</strong> - Both parties buying<br>'
        html += f'Republicans: {", ".join(alert.get("republican_politicians", [])[:3])}<br>'
        html += f'Democrats: {", ".join(alert.get("democrat_politicians", [])[:3])}'
    
    elif alert_type == 'LEADERSHIP_TRADE':
        html += f'<strong>{alert.get("politician", "Unknown")}</strong> ({alert.get("position", "Leadership")})<br>'
        html += f'{alert.get("trade_type", "N/A").upper()} {alert.get("ticker", "N/A")} - {alert.get("amount_range", "N/A")}'
    
    else:
        html += f'{alert_type}: {alert.get("ticker", "N/A")} - {alert.get("politician", "Unknown")}'
    
    html += '</div>'
    return html


def build_status_email(db_stats, analysis_results, fetch_results):
    """Build the daily status email HTML."""
    now = datetime.now()
    
    # Determine if we have alerts
    has_alerts = analysis_results['summary']['total_alerts'] > 0
    high_priority = analysis_results['summary'].get('high_priority', 0)
    
    if high_priority > 0:
        subject = f"Congress Tracker: {high_priority} HIGH Priority Alerts - {now.strftime('%Y-%m-%d')}"
    elif has_alerts:
        subject = f"Congress Tracker: {analysis_results['summary']['total_alerts']} Alerts - {now.strftime('%Y-%m-%d')}"
    else:
        subject = f"Congress Tracker: Daily Status - {now.strftime('%Y-%m-%d')}"
    
    html = f'''
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            Congressional Trading Tracker - Daily Report
        </h2>
        <p style="color: #7f8c8d;">Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        
        <h3 style="color: #2c3e50;">Data Fetch Results</h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>House Transactions</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{fetch_results.get('house', 0)}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Senate Transactions</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{fetch_results.get('senate', 0)}</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>New Today</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>{db_stats['new_today']}</strong></td>
            </tr>
        </table>
        
        <h3 style="color: #2c3e50;">Database Statistics</h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Total Transactions</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['total']:,}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Republican</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['party_counts'].get('Republican', 0):,}</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Democrat</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['party_counts'].get('Democrat', 0):,}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Unique Politicians</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['unique_politicians']}</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Unique Tickers</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['unique_tickers']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Date Range</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{db_stats['earliest_date']} to {db_stats['latest_date']}</td>
            </tr>
        </table>
        
        <h3 style="color: #2c3e50;">Analysis Summary (Last 7 Days)</h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Transactions Analyzed</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{analysis_results['transaction_count']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Total Alerts</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{analysis_results['summary']['total_alerts']}</td>
            </tr>
            <tr style="background: #dc3545; color: white;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>HIGH Priority</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>{analysis_results['summary']['high_priority']}</strong></td>
            </tr>
            <tr style="background: #fd7e14; color: white;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>MEDIUM Priority</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>{analysis_results['summary']['medium_priority']}</strong></td>
            </tr>
            <tr style="background: #6c757d; color: white;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>LOW Priority</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>{analysis_results['summary']['low_priority']}</strong></td>
            </tr>
        </table>
        
        <h4>Alert Breakdown by Type:</h4>
        <ul>
            <li>Clusters (2+ politicians same stock): {analysis_results['summary']['clusters']}</li>
            <li>Committee-Relevant Trades: {analysis_results['summary']['committee_relevant']}</li>
            <li>Leadership Trades: {analysis_results['summary']['leadership']}</li>
            <li>Large Trades (>$250K): {analysis_results['summary']['large_trades']}</li>
            <li>Sector Surges: {analysis_results['summary']['sector_surges']}</li>
            <li>Repeat Buyers: {analysis_results['summary']['repeat_buyers']}</li>
            <li>New Positions: {analysis_results['summary']['new_positions']}</li>
        </ul>
    '''
    
    # Add alert details if we have any HIGH or MEDIUM priority alerts
    important_alerts = [a for a in analysis_results['alerts'] if a.get('priority') in ['HIGH', 'MEDIUM']]
    
    if important_alerts:
        html += '<h3 style="color: #2c3e50;">Alert Details</h3>'
        for alert in important_alerts[:20]:  # Limit to 20 alerts
            html += format_alert_html(alert)
        
        if len(important_alerts) > 20:
            html += f'<p style="color: #7f8c8d;">... and {len(important_alerts) - 20} more alerts</p>'
    
    html += '''
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #bdc3c7;">
        <p style="color: #7f8c8d; font-size: 12px;">
            Congressional Trading Tracker | Scheduled Task Running at 22:30 UTC
        </p>
    </body>
    </html>
    '''
    
    return subject, html


def main():
    """Main execution function."""
    print("=" * 60)
    print("CONGRESSIONAL TRADING TRACKER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize database
    print("\n[1/4] Initializing database...")
    init_database()
    
    # Fetch new data
    print("\n[2/4] Fetching congressional trading data...")
    fetcher = CongressionalDataFetcher()
    
    fetch_results = {'house': 0, 'senate': 0}
    
    try:
        house_data = fetcher.fetch_house_transactions()
        fetch_results['house'] = len(house_data) if house_data else 0
        print(f"  House: {fetch_results['house']} transactions")
    except Exception as e:
        print(f"  House fetch error: {e}")
    
    try:
        senate_data = fetcher.fetch_senate_transactions()
        fetch_results['senate'] = len(senate_data) if senate_data else 0
        print(f"  Senate: {fetch_results['senate']} transactions")
    except Exception as e:
        print(f"  Senate fetch error: {e}")
    
    # Run analysis
    print("\n[3/4] Running analysis...")
    analysis_results = run_all_analysis(days=7)
    print(f"  Analyzed {analysis_results['transaction_count']} transactions")
    print(f"  Found {analysis_results['summary']['total_alerts']} alerts")
    print(f"    HIGH: {analysis_results['summary']['high_priority']}")
    print(f"    MEDIUM: {analysis_results['summary']['medium_priority']}")
    print(f"    LOW: {analysis_results['summary']['low_priority']}")
    
    # Get database stats
    db_stats = get_database_stats()
    print(f"\n  Database now has {db_stats['total']:,} total transactions")
    print(f"  New today: {db_stats['new_today']}")
    
    # Send status email
    print("\n[4/4] Sending status email...")
    subject, html_body = build_status_email(db_stats, analysis_results, fetch_results)
    
    try:
        send_email(
            subject=subject,
            body="See HTML version",
            html_body=html_body
        )
        print(f"  Email sent to {EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"  Email error: {e}")
    
    print("\n" + "=" * 60)
    print(f"COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == '__main__':
    main()