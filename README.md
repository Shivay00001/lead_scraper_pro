# Lead Scraper Pro

A production-ready, commercial B2B/B2C lead scraping system with built-in license validation and usage limits.

## Features

- 12+ platform scrapers (Google Maps, Justdial, IndiaMART, etc.)
- License-based monetization with daily/monthly limits
- Encrypted SQLite storage for leads
- Deduplication using phone, email, and domain
- CSV, Excel, and JSON export
- Command-line interface

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

```bash
# Show status
python main.py status

# List available platforms
python main.py platforms

# Scrape leads
python main.py scrape google_maps "restaurants" -l "Mumbai" -m 50

# Export to CSV
python main.py export leads.csv -f csv

# Activate license
python main.py activate -k YOUR_LICENSE_KEY
```

## Supported Platforms

| Platform | Type | Status |
|----------|------|--------|
| Google Maps | PRIMARY | ✅ |
| Google Search | PRIMARY | ✅ |
| Justdial | PRIMARY | ✅ |
| Sulekha | PRIMARY | ✅ |
| IndiaMART | SECONDARY | ✅ |
| Bing Maps | SECONDARY | ✅ |
| Yelp | SECONDARY | ✅ |
| Yellow Pages | SECONDARY | ✅ |
| YouTube | SIGNAL | ✅ |
| Instagram | SIGNAL | ✅ |
| Twitter/X | SIGNAL | ✅ |
| Job Portals | INDIRECT | ✅ |

## License Plans

| Plan | Daily Limit | Monthly Limit | Platforms | Export |
|------|-------------|---------------|-----------|--------|
| Trial | 10 | 50 | Google Search only | ❌ |
| Starter | 50 | 500 | 3 platforms | ✅ |
| Pro | 200 | 2,000 | 8 platforms | ✅ |
| Agency | 1,000 | 10,000 | All platforms | ✅ |

## Disclaimer

This software collects ONLY publicly available business information. Users are responsible for compliance with applicable laws and platform Terms of Service.
