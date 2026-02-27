"""
Congressional Trading Tracker - Politicians Database
=====================================================
Fetches and stores comprehensive data on members of Congress.
Uses ProPublica Congress API.
"""

import requests
import sqlite3
import time
from datetime import datetime
import config

# ProPublica Congress API (free, requires API key)
PROPUBLICA_API_KEY = ""  # We'll set this up
PROPUBLICA_BASE_URL = "https://api.propublica.org/congress/v1"

# Fallback: Basic party lookup for known politicians
# This ensures we have SOME data even without API
PARTY_LOOKUP = {
    # House Leadership
    "Mike Johnson": {"party": "R", "state": "LA", "leadership": "Speaker of the House"},
    "Hakeem Jeffries": {"party": "D", "state": "NY", "leadership": "House Minority Leader"},
    "Steve Scalise": {"party": "R", "state": "LA", "leadership": "House Majority Leader"},
    "Katherine Clark": {"party": "D", "state": "MA", "leadership": "House Minority Whip"},
    "Tom Emmer": {"party": "R", "state": "MN", "leadership": "House Majority Whip"},
    
    # Senate Leadership
    "Chuck Schumer": {"party": "D", "state": "NY", "leadership": "Senate Majority Leader"},
    "Mitch McConnell": {"party": "R", "state": "KY", "leadership": "Senate Minority Leader"},
    "John Thune": {"party": "R", "state": "SD", "leadership": "Senate Minority Whip"},
    "Dick Durbin": {"party": "D", "state": "IL", "leadership": "Senate Majority Whip"},
    
    # Notable traders (frequently appear in disclosures)
    "Nancy Pelosi": {"party": "D", "state": "CA", "leadership": "Former Speaker"},
    "Dan Crenshaw": {"party": "R", "state": "TX", "leadership": ""},
    "Josh Gottheimer": {"party": "D", "state": "NJ", "leadership": ""},
    "Marjorie Taylor Greene": {"party": "R", "state": "GA", "leadership": ""},
    "Tommy Tuberville": {"party": "R", "state": "AL", "leadership": ""},
    "Mark Green": {"party": "R", "state": "TN", "leadership": ""},
    "Michael McCaul": {"party": "R", "state": "TX", "leadership": "Chair, Foreign Affairs"},
    "Ro Khanna": {"party": "D", "state": "CA", "leadership": ""},
    "Alexandria Ocasio-Cortez": {"party": "D", "state": "NY", "leadership": ""},
    "Katie Porter": {"party": "D", "state": "CA", "leadership": ""},
    "Rick Scott": {"party": "R", "state": "FL", "leadership": ""},
    "Ted Cruz": {"party": "R", "state": "TX", "leadership": ""},
    
    # From your test data
    "Dale Strong": {"party": "R", "state": "AL", "leadership": ""},
    "Katie Britt": {"party": "R", "state": "AL", "leadership": ""},
}


def init_politicians_table():
    """Create the politicians table with comprehensive fields."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS politicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Basic Info
            full_name TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            
            -- Political Info
            party TEXT,                    -- D, R, I
            chamber TEXT,                  -- House, Senate
            state TEXT,                    -- Two-letter code
            district TEXT,                 -- House district number (null for Senate)
            
            -- Leadership & Committees
            leadership_position TEXT,      -- Speaker, Majority Leader, etc.
            is_leadership INTEGER DEFAULT 0,
            committees TEXT,               -- JSON list of committees
            committee_chairs TEXT,         -- JSON list of committees they chair
            
            -- Career Info
            years_in_congress INTEGER,
            first_elected_year INTEGER,
            term_start DATE,
            term_end DATE,
            
            -- Personal Info
            birth_date DATE,
            age INTEGER,
            gender TEXT,
            prior_profession TEXT,         -- Lawyer, Doctor, Business, Military, etc.
            
            -- IDs for cross-referencing
            bioguide_id TEXT,              -- Official Congress ID
            propublica_id TEXT,
            fec_id TEXT,
            
            -- Social Media
            twitter_handle TEXT,
            
            -- Tracking
            data_source TEXT,              -- 'propublica', 'manual', 'fallback'
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Index for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_politician_name ON politicians(full_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_politician_party ON politicians(party)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_politician_state ON politicians(state)")
    
    conn.commit()
    conn.close()
    print("Politicians table initialized.")


def get_politician_by_name(name):
    """Look up a politician by name. Returns dict or None."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Try exact match first
    cursor.execute("SELECT * FROM politicians WHERE full_name = ?", (name,))
    row = cursor.fetchone()
    
    if not row:
        # Try partial match (last name)
        parts = name.split()
        if parts:
            last_name = parts[-1]
            cursor.execute("SELECT * FROM politicians WHERE last_name = ?", (last_name,))
            row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return dict(row)
    
    # Fallback to hardcoded lookup
    if name in PARTY_LOOKUP:
        return {
            'full_name': name,
            'party': PARTY_LOOKUP[name]['party'],
            'state': PARTY_LOOKUP[name]['state'],
            'leadership_position': PARTY_LOOKUP[name]['leadership'],
            'is_leadership': 1 if PARTY_LOOKUP[name]['leadership'] else 0,
            'data_source': 'fallback'
        }
    
    return None


def save_politician(data):
    """Save or update a politician record."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO politicians (
            full_name, first_name, last_name, party, chamber, state, district,
            leadership_position, is_leadership, committees, committee_chairs,
            years_in_congress, first_elected_year, term_start, term_end,
            birth_date, age, gender, prior_profession,
            bioguide_id, propublica_id, fec_id, twitter_handle,
            data_source, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('full_name'),
        data.get('first_name'),
        data.get('last_name'),
        data.get('party'),
        data.get('chamber'),
        data.get('state'),
        data.get('district'),
        data.get('leadership_position'),
        data.get('is_leadership', 0),
        data.get('committees'),
        data.get('committee_chairs'),
        data.get('years_in_congress'),
        data.get('first_elected_year'),
        data.get('term_start'),
        data.get('term_end'),
        data.get('birth_date'),
        data.get('age'),
        data.get('gender'),
        data.get('prior_profession'),
        data.get('bioguide_id'),
        data.get('propublica_id'),
        data.get('fec_id'),
        data.get('twitter_handle'),
        data.get('data_source', 'manual'),
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()


def enrich_transaction_with_politician(transaction):
    """Add politician data to a transaction dict."""
    name = transaction.get('politician', '')
    
    politician = get_politician_by_name(name)
    
    if politician:
        transaction['party'] = politician.get('party', '')
        transaction['is_leadership'] = politician.get('is_leadership', 0)
        transaction['committees'] = politician.get('committees', '')
        transaction['leadership_position'] = politician.get('leadership_position', '')
    
    return transaction


def get_politician_stats():
    """Get statistics about the politicians database."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM politicians")
    stats['total'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM politicians WHERE party = 'D'")
    stats['democrats'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM politicians WHERE party = 'R'")
    stats['republicans'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM politicians WHERE chamber = 'House'")
    stats['house'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM politicians WHERE chamber = 'Senate'")
    stats['senate'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM politicians WHERE is_leadership = 1")
    stats['leadership'] = cursor.fetchone()[0]
    
    conn.close()
    return stats


if __name__ == "__main__":
    print("Initializing politicians database...")
    init_politicians_table()
    
    # Load fallback data
    print(f"Loading {len(PARTY_LOOKUP)} known politicians from fallback...")
    for name, data in PARTY_LOOKUP.items():
        parts = name.split()
        save_politician({
            'full_name': name,
            'first_name': parts[0] if parts else '',
            'last_name': parts[-1] if parts else '',
            'party': data['party'],
            'leadership_position': data['leadership'],
            'is_leadership': 1 if data['leadership'] else 0,
            'state': data['state'],
            'data_source': 'fallback'
        })
    
    stats = get_politician_stats()
    print(f"\nPoliticians database stats:")
    print(f"  Total: {stats['total']}")
    print(f"  Democrats: {stats['democrats']}")
    print(f"  Republicans: {stats['republicans']}")