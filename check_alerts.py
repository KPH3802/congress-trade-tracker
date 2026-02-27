# check_alerts.py - Diagnostic script to see alert details
# Run with: python check_alerts.py

from analyzer import (
    get_recent_transactions, 
    analyze_against_market,
    analyze_pre_event_timing,
    analyze_leadership_trades,
    is_leadership_member,
    CONGRESSIONAL_LEADERSHIP
)
import json

def main():
    print("=" * 60)
    print("CONGRESS TRACKER - ALERT DIAGNOSTICS")
    print("=" * 60)
    
    # Get recent transactions
    transactions = get_recent_transactions(days=7)
    print(f"\nFound {len(transactions)} transactions in last 7 days:\n")
    
    for i, t in enumerate(transactions, 1):
        print(f"  {i}. {t['politician']} - {t['trade_type'].upper()} {t['ticker']}")
        print(f"     Date: {t['trade_date']} | Amount: {t['amount_range']}")
        print(f"     Company: {t.get('company', 'N/A')}")
        print()
    
    # Check against-market alerts
    print("-" * 60)
    print("AGAINST-MARKET ALERTS (Alert #9)")
    print("-" * 60)
    
    against_market = analyze_against_market(transactions)
    
    if against_market:
        for alert in against_market:
            print(f"\n🚨 {alert['priority']} PRIORITY")
            print(f"   Politician: {alert['politician']}")
            print(f"   Ticker: {alert['ticker']}")
            print(f"   Trade Type: {alert['trade_type']}")
            print(f"   Trade Date: {alert['trade_date']}")
            print(f"   Reason: {alert['reason']}")
            print(f"   Price at trade: ${alert.get('price_at_trade', 'N/A')}")
            print(f"   10-day return: {alert.get('return_10d', 'N/A')}%")
            print(f"   20-day return: {alert.get('return_20d', 'N/A')}%")
    else:
        print("\n  No against-market alerts found.")
    
    # Check pre-earnings alerts
    print("\n" + "-" * 60)
    print("PRE-EARNINGS ALERTS (Alert #8)")
    print("-" * 60)
    
    pre_earnings = analyze_pre_event_timing(transactions)
    
    if pre_earnings:
        for alert in pre_earnings:
            print(f"\n🚨 {alert['priority']} PRIORITY")
            print(f"   Politician: {alert['politician']}")
            print(f"   Ticker: {alert['ticker']}")
            print(f"   Trade Type: {alert['trade_type']}")
            print(f"   Trade Date: {alert['trade_date']}")
            print(f"   Earnings Date: {alert['earnings_date']}")
            print(f"   Days Before Earnings: {alert['days_before_earnings']}")
    else:
        print("\n  No pre-earnings alerts found.")
    
    # Check leadership alerts
    print("\n" + "-" * 60)
    print("LEADERSHIP ALERTS (Alert #3)")
    print("-" * 60)
    
    leadership = analyze_leadership_trades(transactions)
    
    if leadership:
        for alert in leadership:
            print(f"\n🚨 {alert['priority']} PRIORITY")
            print(f"   Politician: {alert['politician']}")
            print(f"   Position: {alert['position']}")
            print(f"   Ticker: {alert['ticker']}")
            print(f"   Trade Type: {alert['trade_type']}")
            print(f"   Amount: {alert['amount_range']}")
    else:
        print("\n  No leadership alerts found.")
        print("\n  Current leadership being tracked:")
        for name, info in CONGRESSIONAL_LEADERSHIP.items():
            print(f"    - {name} ({info['position']})")
    
    # Test leadership matching with current transaction names
    print("\n" + "-" * 60)
    print("LEADERSHIP NAME MATCHING TEST")
    print("-" * 60)
    
    for t in transactions:
        name = t['politician']
        is_leader, info = is_leadership_member(name)
        if is_leader:
            print(f"\n  ✅ MATCH: '{name}' -> {info['name']} ({info['position']})")
        else:
            print(f"\n  ❌ Not leadership: '{name}'")

if __name__ == '__main__':
    main()
