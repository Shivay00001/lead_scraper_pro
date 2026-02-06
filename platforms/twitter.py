"""
Lead Scraper Pro - Twitter/X Business Profiles Scraper
Extracts business info from public X (Twitter) profiles.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Twitter/X public profile scraper."""
    
    PLATFORM_NAME = "twitter"
    BASE_URL = "https://x.com"
    
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
        Scrape X/Twitter business profiles.
        
        Args:
            query: @username or search term
            max_results: Max profiles
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Direct username
            if query.startswith('@'):
                usernames = [query[1:]]
            else:
                # Search for profiles
                search_url = f"{self.BASE_URL}/search?q={query.replace(' ', '%20')}&f=user"
                page.goto(search_url, wait_until='networkidle', timeout=15000)
                
                if rate_limiter:
                    rate_limiter.wait(self.PLATFORM_NAME)
                
                time.sleep(3)
                
                # Extract usernames from search
                usernames = []
                user_links = page.locator('a[href*="/"]:has-text("@")').all()
                
                for link in user_links[:max_results * 2]:
                    href = link.get_attribute('href') or ''
                    text = link.text_content() or ''
                    
                    if text.startswith('@'):
                        username = text[1:]
                        if username and username not in usernames:
                            usernames.append(username)
            
            # Scrape profiles
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
            print(f"[Twitter] Error: {e}")
        
        return leads
    
    def _scrape_profile(self, page: Page, username: str, rate_limiter) -> Optional[Dict]:
        try:
            profile_url = f"{self.BASE_URL}/{username}"
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
                'tags': ['twitter', 'x'],
                'social_links': {'twitter': profile_url}
            }
            
            content = page.content()
            
            # Name
            name_elem = page.locator('[data-testid="UserName"] span:first-child').first
            if name_elem.count() > 0:
                lead['business_name'] = self.clean_text(name_elem.text_content())
            
            if not lead['business_name']:
                lead['business_name'] = username
            
            # Bio
            bio_elem = page.locator('[data-testid="UserDescription"]').first
            if bio_elem.count() > 0:
                bio = bio_elem.text_content()
                lead['notes'] = self.clean_text(bio)[:300] if bio else ''
                
                # Extract contact info
                emails = self.extract_emails(bio)
                phones = self.extract_phones(bio)
                
                if emails:
                    lead['emails'] = emails
                if phones:
                    lead['phone_numbers'] = phones
            
            # Website
            website_elem = page.locator('[data-testid="UserUrl"] a').first
            if website_elem.count() > 0:
                href = website_elem.get_attribute('href') or website_elem.text_content() or ''
                if href and 'twitter' not in href and 'x.com' not in href:
                    if not href.startswith('http'):
                        href = 'https://' + href
                    lead['website'] = href
            
            # Location
            loc_elem = page.locator('[data-testid="UserLocation"]').first
            if loc_elem.count() > 0:
                lead['address'] = self.clean_text(loc_elem.text_content())
            
            # Category (from profile)
            cat_elem = page.locator('[data-testid="UserProfessionalCategory"]').first
            if cat_elem.count() > 0:
                lead['category'] = self.clean_text(cat_elem.text_content())
            
            # Followers
            followers_match = re.search(r'"followers_count":(\d+)', content)
            if followers_match:
                lead['raw_data'] = {'followers': int(followers_match.group(1))}
            
            # Verified badge
            if 'verified' in content.lower() or page.locator('[data-testid="icon-verified"]').count() > 0:
                lead['is_verified'] = True
                lead['tags'].append('verified')
            
            # Guess emails
            if lead['website'] and not lead['emails']:
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:2]]
                lead['tags'].append('emails_guessed')
            
            return lead
            
        except:
            return None
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
