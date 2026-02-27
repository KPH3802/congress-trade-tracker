"""
Congressional Trading Tracker - Data Fetcher Module
====================================================
Fetches congressional stock trading data from FMP (Financial Modeling Prep) API.
"""

import requests
import time
import os
from datetime import datetime, timedelta
from config import REQUEST_DELAY
import politicians

# FMP API configuration
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.environ.get('FMP_API_KEY', '')


class CongressionalDataFetcher:
    """Fetches congressional trading data from FMP API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Trading-Tracker/1.0 (Educational Purpose)'
        })
        self.last_request_time = 0
        
        if not FMP_API_KEY:
            print("WARNING: FMP_API_KEY environment variable not set!")
    
    def _rate_limit(self):
        """Simple rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url, params=None):
        """Make HTTP request with rate limiting."""
        self._rate_limit()
        
        # Add API key to params
        if params is None:
            params = {}
        params['apikey'] = FMP_API_KEY
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed for {url}: {e}")
            return None
        except ValueError as e:
            print(f"JSON parsing failed for {url}: {e}")
            return None
    
    def _transform_fmp_transaction(self, item, chamber):
        """Transform FMP API response to our internal format."""
        import hashlib
        
        # Generate unique transaction ID for deduplication
        id_string = f"{item.get('firstName', '')}-{item.get('lastName', '')}-{item.get('symbol', '')}-{item.get('transactionDate', '')}-{item.get('amount', '')}"
        transaction_id = hashlib.md5(id_string.encode()).hexdigest()
        
        # Parse amount range to get low/high values
        amount_str = item.get('amount', '')
        amount_low, amount_high = self._parse_amount_range(amount_str)
        
        # Map FMP fields to our format (matching database.py field names)
        return {
            'transaction_id': transaction_id,
            'politician': f"{item.get('firstName', '')} {item.get('lastName', '')}".strip(),
            'chamber': chamber,
            'party': '',  # FMP doesn't provide party info directly
            'state': item.get('district', ''),
            'ticker': item.get('symbol', ''),
            'company': item.get('assetDescription', ''),
            'trade_type': item.get('type', ''),  # Purchase, Sale, etc.
            'trade_date': item.get('transactionDate', ''),
            'disclosure_date': item.get('disclosureDate', ''),
            'amount_range': amount_str,
            'amount_low': amount_low,
            'amount_high': amount_high,
            'owner': item.get('owner', ''),
            'source_url': item.get('link', ''),
            'committees': '',
            'is_leadership': 0
        }

    def _parse_amount_range(self, amount_str):
        """Parse amount string to get low/high values."""
        from config import AMOUNT_RANGES
        
        if not amount_str:
            return 0, 0
        
        # Try to match against known ranges
        for range_str, (low, high) in AMOUNT_RANGES.items():
            if range_str.lower() in amount_str.lower() or amount_str.lower() in range_str.lower():
                return low, high
        
        # Default if no match
        return 0, 0
    
    def fetch_house_transactions(self, days_back=30):
        """Fetch House representative transactions from FMP."""
        print("Fetching House transactions from FMP...")
        
        url = f"{FMP_BASE_URL}/house-latest"
        
        transactions = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        page = 0
        max_pages = 10  # Limit to prevent infinite loops
        
        while page < max_pages:
            data = self._make_request(url, params={'page': page, 'limit': 100})
            
            if not data:
                print(f"  No data returned for page {page}")
                break
            
            if len(data) == 0:
                print(f"  No more data at page {page}")
                break
            
            print(f"  Page {page}: {len(data)} transactions")
            
            for item in data:
                tx = self._transform_fmp_transaction(item, 'House')
                
                # Filter by date
                tx_date_str = tx.get('trade_date', '')

                if tx_date_str:
                    try:
                        tx_date = datetime.strptime(tx_date_str, '%Y-%m-%d')
                        if tx_date >= cutoff_date:
                            transactions.append(tx)
                    except ValueError:
                        # If date parsing fails, include it anyway
                        transactions.append(tx)
            
            # Check if we got a full page (might have more)
            if len(data) < 100:
                break
            
            page += 1
        
        print(f"  Total House transactions: {len(transactions)}")
        return transactions
    
    def fetch_senate_transactions(self, days_back=30):
        """Fetch Senate transactions from FMP."""
        print("Fetching Senate transactions from FMP...")
        
        url = f"{FMP_BASE_URL}/senate-latest"
        
        transactions = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        page = 0
        max_pages = 10  # Limit to prevent infinite loops
        
        while page < max_pages:
            data = self._make_request(url, params={'page': page, 'limit': 100})
            
            if not data:
                print(f"  No data returned for page {page}")
                break
            
            if len(data) == 0:
                print(f"  No more data at page {page}")
                break
            
            print(f"  Page {page}: {len(data)} transactions")
            
            for item in data:
                tx = self._transform_fmp_transaction(item, 'Senate')
                
                # Filter by date
                tx_date_str = tx.get('trade_date', '')
                if tx_date_str:
                    try:
                        tx_date = datetime.strptime(tx_date_str, '%Y-%m-%d')
                        if tx_date >= cutoff_date:
                            transactions.append(tx)
                    except ValueError:
                        # If date parsing fails, include it anyway
                        transactions.append(tx)
            
            # Check if we got a full page (might have more)
            if len(data) < 100:
                break
            
            page += 1
        
        print(f"  Total Senate transactions: {len(transactions)}")
        return transactions
    
    def fetch_all_transactions(self, days_back=30):
        """Fetch all congressional transactions."""
        print(f"Fetching all congressional transactions (last {days_back} days)...")
        
        all_transactions = []
        
        house_transactions = self.fetch_house_transactions(days_back)
        all_transactions.extend(house_transactions)
        
        senate_transactions = self.fetch_senate_transactions(days_back)
        all_transactions.extend(senate_transactions)
        
        print(f"Total transactions fetched: {len(all_transactions)}")
        return all_transactions

def fetch_and_store_transactions(days_back=None):
    """
    Convenience function to fetch and store transactions.
    Called by main.py and congress_main.py.
    """
    import database
    
    if days_back is None:
        from config import LOOKBACK_DAYS
        days_back = LOOKBACK_DAYS
    
    fetcher = CongressionalDataFetcher()
    transactions = fetcher.fetch_all_transactions(days_back=days_back)
    
    # Store transactions in database
    new_count = 0
    duplicate_count = 0
    
    for tx in transactions:
        # Enrich with politician data (party, committees, etc.)
        tx = politicians.enrich_transaction_with_politician(tx)
        
        if database.save_transaction(tx):
            new_count += 1
        else:
            duplicate_count += 1
    
    print(f"Stored {new_count} new transactions ({duplicate_count} duplicates skipped)")
    
    return {
        'transactions': transactions,
        'new_transactions': new_count,
        'duplicates': duplicate_count,
        'total_fetched': len(transactions)
    }

if __name__ == '__main__':
    fetcher = CongressionalDataFetcher()
    transactions = fetcher.fetch_all_transactions(days_back=7)
    
    print(f"\nSample transactions:")
    for tx in transactions[:5]:
        print(f"  {tx['politician']} ({tx['chamber']}) - {tx['trade_type']} {tx['ticker']} on {tx['trade_date']}")