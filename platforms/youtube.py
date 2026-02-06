"""
Lead Scraper Pro - YouTube Channel Scraper
Extracts business info from YouTube channel About pages.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """YouTube channel About page scraper."""
    
    PLATFORM_NAME = "youtube"
    BASE_URL = "https://www.youtube.com"
    
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
        Scrape YouTube channel About pages for business info.
        
        Args:
            query: Search query for business/company channels
            location: Not used for YouTube
            max_results: Max channels to scrape
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Search for channels
            search_url = f"{self.BASE_URL}/results?search_query={query.replace(' ', '+')}&sp=EgIQAg%253D%253D"  # Channels filter
            page.goto(search_url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Get channel links
            channel_links = page.locator('a#main-link[href*="/@"], a[href*="/channel/"]').all()
            
            collected = 0
            seen_channels = set()
            
            for link in channel_links:
                if stop_check and stop_check():
                    break
                
                if collected >= max_results:
                    break
                
                try:
                    href = link.get_attribute('href')
                    if not href or href in seen_channels:
                        continue
                    
                    seen_channels.add(href)
                    
                    # Navigate to About page
                    about_url = href + '/about' if not href.endswith('/') else href + 'about'
                    if not about_url.startswith('http'):
                        about_url = self.BASE_URL + about_url
                    
                    page.goto(about_url, wait_until='domcontentloaded')
                    
                    if rate_limiter:
                        rate_limiter.wait(self.PLATFORM_NAME)
                    
                    time.sleep(2)
                    
                    lead = self._extract_channel_info(page)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        collected += 1
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"[YouTube] Error: {e}")
        
        return leads
    
    def _extract_channel_info(self, page: Page) -> Optional[Dict]:
        try:
            # Channel name
            name_elem = page.locator('#channel-name, .ytd-channel-name').first
            name = name_elem.text_content() if name_elem.count() > 0 else ''
            
            if not name:
                return None
            
            lead = {
                'business_name': self.clean_text(name),
                'category': '',
                'phone_numbers': [],
                'emails': [],
                'website': '',
                'address': '',
                'lead_type': 'B2C',  # YouTube-based leads are often D2C/B2C
                'tags': ['youtube', 'content_creator'],
                'social_links': {'youtube': page.url}
            }
            
            # Get page content for extraction
            content = page.content()
            
            # Extract emails
            emails = self.extract_emails(content)
            if emails:
                lead['emails'] = emails
            
            # Description/about
            desc_elem = page.locator('#description, .ytd-about-channel-content').first
            if desc_elem.count() > 0:
                description = desc_elem.text_content()
                lead['notes'] = self.clean_text(description)[:300] if description else ''
                
                # Extract phones from description
                phones = self.extract_phones(description)
                if phones:
                    lead['phone_numbers'] = phones
            
            # Links section
            links = page.locator('a[href*="redirect"]').all()
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    text = link.text_content() or ''
                    
                    # Extract actual URL from redirect
                    if 'q=' in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        actual_url = parsed.get('q', [''])[0]
                        
                        if actual_url:
                            if 'instagram' in actual_url.lower():
                                lead['social_links']['instagram'] = actual_url
                            elif 'twitter' in actual_url.lower() or 'x.com' in actual_url.lower():
                                lead['social_links']['twitter'] = actual_url
                            elif 'facebook' in actual_url.lower():
                                lead['social_links']['facebook'] = actual_url
                            elif not lead['website']:
                                lead['website'] = actual_url
                except:
                    continue
            
            # Subscriber count (for lead quality)
            subs_elem = page.locator('#subscriber-count').first
            if subs_elem.count() > 0:
                subs_text = subs_elem.text_content()
                lead['raw_data'] = {'subscribers': subs_text}
            
            # Guess emails if website but no email
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
