"""
Congressional Trading Tracker - Configuration
=============================================
Copy this file to config.py and fill in your credentials.

    cp config_example.py config.py

"""

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================
# Use Gmail with an App Password (not your regular password)
# To create an App Password: https://myaccount.google.com/apppasswords

EMAIL_SENDER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password_here"
EMAIL_RECIPIENT = "your_email@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_PATH = "congress_trades.db"

# =============================================================================
# DATA SOURCES
# =============================================================================
HOUSE_API_URL = "https://housestockwatcher.com/api"
SENATE_API_URL = "https://senatestockwatcher.com/api"

USER_AGENT = "CongressTracker/1.0 (your_email@gmail.com)"
REQUEST_DELAY = 1.0

# =============================================================================
# DETECTION THRESHOLDS
# =============================================================================
CLUSTER_WINDOW_DAYS = 14
MIN_CLUSTER_SIZE = 3

AMOUNT_RANGES = {
    "$1,001 - $15,000": (1001, 15000),
    "$15,001 - $50,000": (15001, 50000),
    "$50,001 - $100,000": (50001, 100000),
    "$100,001 - $250,000": (100001, 250000),
    "$250,001 - $500,000": (250001, 500000),
    "$500,001 - $1,000,000": (500001, 1000000),
    "$1,000,001 - $5,000,000": (1000001, 5000000),
    "$5,000,001 - $25,000,000": (5000001, 25000000),
    "$25,000,001 - $50,000,000": (25000001, 50000000),
    "$50,000,001 +": (50000001, 100000000),
}

LARGE_TRADE_THRESHOLD = 100001

# =============================================================================
# SIGNAL SCORING
# =============================================================================
SIGNAL_WEIGHTS = {
    'cluster': 3,
    'bipartisan': 2,
    'committee_relevance': 2,
    'large_trade': 1,
    'leadership': 1,
}

SELL_SCORE_MULTIPLIER = 0.5
ALERT_THRESHOLD = 3

# =============================================================================
# COMMITTEE-SECTOR MAPPING
# =============================================================================
COMMITTEE_SECTOR_MAP = {
    "Financial Services": ["XLF", "banks", "finance", "insurance", "credit"],
    "Banking": ["XLF", "banks", "finance", "insurance", "credit"],
    "Finance": ["XLF", "banks", "finance", "insurance", "credit"],
    "Science, Space, and Technology": ["XLK", "technology", "software", "semiconductor", "AI"],
    "Oversight and Reform": ["XLK", "technology", "software"],
    "Energy and Commerce": ["XLE", "energy", "oil", "gas", "utilities", "renewable"],
    "Energy and Natural Resources": ["XLE", "energy", "oil", "gas", "utilities"],
    "Health": ["XLV", "healthcare", "biotech", "pharma", "medical"],
    "Health, Education, Labor, and Pensions": ["XLV", "healthcare", "biotech", "pharma"],
    "Armed Services": ["XAR", "defense", "aerospace", "military"],
    "Defense": ["XAR", "defense", "aerospace", "military"],
    "Transportation and Infrastructure": ["XLI", "transportation", "airlines", "shipping"],
    "Commerce, Science, and Transportation": ["XLI", "transportation", "airlines"],
    "Agriculture": ["MOO", "agriculture", "farming", "food"],
    "Communications": ["XLC", "telecom", "media", "communications"],
}

LEADERSHIP_TITLES = [
    "Speaker", "Majority Leader", "Minority Leader",
    "Majority Whip", "Minority Whip", "Chair",
    "Ranking Member", "President Pro Tempore",
]

LOOKBACK_DAYS = 7
ALERT_COOLDOWN_HOURS = 24
