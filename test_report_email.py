# test_report_email.py - Test the daily analysis report email
# Run with: python test_report_email.py

from analyzer import run_all_analysis
from emailer import send_analysis_report

def main():
    print("Running analysis...")
    results = run_all_analysis(days=7, include_yahoo_alerts=True)
    
    print(f"\nAnalysis complete:")
    print(f"  Transactions: {results['transaction_count']}")
    print(f"  Total alerts: {results['summary']['total_alerts']}")
    print(f"  High priority: {results['summary']['high_priority']}")
    
    print("\nSending analysis report email...")
    
    # Set dry_run=True to preview without sending
    # Set dry_run=False to actually send the email
    success = send_analysis_report(results, dry_run=False)
    
    if success:
        print("\n✅ Report email sent successfully!")
    else:
        print("\n❌ Failed to send report email")

if __name__ == '__main__':
    main()
