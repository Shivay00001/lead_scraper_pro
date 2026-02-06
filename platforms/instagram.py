"""
Lead Scraper Pro - Instagram Business Profiles Scraper
Extracts business info from public Instagram business profiles.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Instagram public business profile scraper."""
    
    PLATFORM_NAME = "instagram"
    BASE_URL = "https://www.instagram.com"
    
    def __init__(self):
        super().__init__()
        self._playwright = None
    
    def _init_browser(self, headless: bool = True) -> Page:
        if self._page:
            return self._page
        
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(30000)
        return self._page
    
    def scrape(self, query: str, location: str = None, max_results: int = 50,
               rate_limiter=None, stop_check: Callable = None, headless: bool = True, **kwargs) -> List[Dict]:
        """
        Scrape Instagram business profiles.
        Note: Instagram heavily restricts scraping. This works best with direct profile URLs.
        
        Args:
            query: Username to scrape directly or business type
            max_results: Max profiles to process
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # For Instagram, we need to work with specific profile URLs
            # Direct search is very limited without login
            
            # Check if query is a username
            if query.startswith('@'):
                usernames = [query[1:]]
            elif '/' in query:
                # Could be a URL
                username = query.split('/')[-1].replace('@', '')
                usernames = [username]
            else:
                # Try to use explore/tags endpoint (limited)
                tag_url = f"{self.BASE_URL}/explore/tags/{query.replace(' ', '')}/"
                page.goto(tag_url, wait_until='networkidle', timeout=15000)
                
                if rate_limiter:
                    rate_limiter.wait(self.PLATFORM_NAME)
                
                # This might require login - return gracefully
                usernames = []
                
                # Try to find profile links
                profile_links = page.locator('a[href*="/"][href*="/?"]').all()
                for link in profile_links[:max_results]:
                    href = link.get_attribute('href') or ''
                    if '/p/' not in href and '/explore/' not in href:
                        username = href.strip('/').split('/')[-1]
                        if username and username not in usernames:
                            usernames.append(username)
            
            # Scrape each profile
            for username in usernames[:max_results]:
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._scrape_profile(page, username, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                except:
                    continue
                    
        except Exception as e:
            print(f"[Instagram] Error: {e}")
        
        return leads
    
    def _scrape_profile(self, page: Page, username: str, rate_limiter) -> Optional[Dict]:
        try:
            profile_url = f"{self.BASE_URL}/{username}/"
            page.goto(profile_url, wait_until='domcontentloaded', timeout=15000)
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            lead = {
                'business_name': '',
                'category': '',
                'phone_numbers': [],
                'emails': [],
                'website': '',
                'address': '',
                'lead_type': 'B2C',
                'tags': ['instagram'],
                'social_links': {'instagram': profile_url}
            }
            
            # Get page content
            content = page.content()
            
            # Extract from meta tags
            title_match = re.search(r'<title>([^<]+)</title>', content)
            if title_match:
                title = title_match.group(1)
                # Instagram title format: "Name (@username) • Instagram photos and videos"
                name_match = re.match(r'([^(]+)\s*\(', title)
                if name_match:
                    lead['business_name'] = self.clean_text(name_match.group(1))
            
            if not lead['business_name']:
                lead['business_name'] = username
            
            # Try to get bio
            bio_elem = page.locator('.-vDIg span, header section > div > span').first
            if bio_elem.count() > 0:
                bio = bio_elem.text_content()
                lead['notes'] = self.clean_text(bio)[:300] if bio else ''
                
                # Extract from bio
                emails = self.extract_emails(bio)
                phones = self.extract_phones(bio)
                
                if emails:
                    lead['emails'] = emails
                if phones:
                    lead['phone_numbers'] = phones
            
            # Website link
            website_elem = page.locator('a[href*="l.instagram.com/"]').first
            if website_elem.count() > 0:
                href = website_elem.get_attribute('href') or ''
                # Extract actual URL from Instagram redirect
                if 'u=' in href:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    actual_url = parsed.get('u', [''])[0]
                    if actual_url:
                        lead['website'] = urllib.parse.unquote(actual_url)
            
            # Category (business category if available)
            cat_elem = page.locator('a[href*="/explore/locations/"] span, ._aade').first
            if cat_elem.count() > 0:
                lead['category'] = self.clean_text(cat_elem.text_content())
            
            # Follower count for lead quality
            followers_match = re.search(r'"edge_followed_by":\s*{\s*"count":\s*(\d+)', content)
            if followers_match:
                lead['raw_data'] = {'followers': int(followers_match.group(1))}
            
            # Guess emails if website exists
            if lead['website'] and not lead['emails']:
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:2]]
                lead['tags'].append('emails_guessed')
            
            return lead
            
        except Exception as e:
            return None
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
