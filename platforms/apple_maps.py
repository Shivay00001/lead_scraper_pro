"""
Lead Scraper Pro - Apple Maps Web Scraper
Scrapes business listings from Apple Maps web interface.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Apple Maps web scraper for business listings."""
    
    PLATFORM_NAME = "apple_maps"
    BASE_URL = "https://maps.apple.com"
    
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
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
            locale='en-US'
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(30000)
        return self._page
    
    def scrape(self, query: str, location: str = None, max_results: int = 50,
               rate_limiter=None, stop_check: Callable = None, headless: bool = True, **kwargs) -> List[Dict]:
        """Scrape Apple Maps for business listings."""
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Build search query
            search_query = query
            if location:
                search_query = f"{query} in {location}"
            
            # Apple Maps search URL
            url = f"{self.BASE_URL}/?q={search_query.replace(' ', '%20')}"
            page.goto(url, wait_until='networkidle')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Click on search input if needed
            try:
                search_input = page.locator('input[type="text"], input[name="search"]').first
                if search_input.count() > 0:
                    search_input.fill(search_query)
                    search_input.press('Enter')
                    time.sleep(3)
            except:
                pass
            
            collected = 0
            
            # Scroll to load results
            for scroll in range(10):
                if stop_check and stop_check():
                    break
                
                # Find all result items
                results = page.locator('[data-testid="search-result-item"], .place-card, .search-result').all()
                
                for result in results[collected:]:
                    if stop_check and stop_check():
                        break
                    
                    if collected >= max_results:
                        break
                    
                    try:
                        lead = self._parse_result(result, page)
                        if lead and lead.get('business_name'):
                            leads.append(lead)
                            collected += 1
                    except:
                        continue
                
                if collected >= max_results:
                    break
                
                # Scroll
                page.keyboard.press('End')
                time.sleep(1)
            
            # Deep scrape by clicking into results
            if leads and kwargs.get('deep', True):
                leads = self._deep_scrape_results(page, leads, rate_limiter, stop_check)
            
        except Exception as e:
            print(f"[AppleMaps] Error: {e}")
        
        return leads
    
    def _parse_result(self, result, page: Page) -> Optional[Dict]:
        """Parse a single search result."""
        try:
            lead = {
                'business_name': '',
                'category': '',
                'phone_numbers': [],
                'emails': [],
                'website': '',
                'address': '',
                'rating': None,
                'reviews_count': None,
                'lead_type': 'B2B',
                'tags': ['apple_maps']
            }
            
            # Name
            name_elem = result.locator('h2, h3, .place-name, [data-testid="place-name"]').first
            if name_elem.count() > 0:
                lead['business_name'] = self.clean_text(name_elem.text_content())
            
            if not lead['business_name']:
                return None
            
            # Category
            cat_elem = result.locator('.category, .place-category').first
            if cat_elem.count() > 0:
                lead['category'] = self.clean_text(cat_elem.text_content())
            
            # Address
            addr_elem = result.locator('.address, .place-address').first
            if addr_elem.count() > 0:
                lead['address'] = self.clean_text(addr_elem.text_content())
                lead['pincode'] = self.extract_pincode(lead['address'])
            
            # Rating
            rating_elem = result.locator('.rating, [data-testid="rating"]').first
            if rating_elem.count() > 0:
                text = rating_elem.text_content()
                match = re.search(r'(\d+\.?\d*)', text)
                if match:
                    lead['rating'] = float(match.group(1))
            
            return lead
            
        except:
            return None
    
    def _deep_scrape_results(self, page: Page, leads: List[Dict], rate_limiter, stop_check) -> List[Dict]:
        """Click into each result for more details."""
        enhanced = []
        
        for lead in leads:
            if stop_check and stop_check():
                break
            
            try:
                # Search for this specific business
                search_input = page.locator('input[type="text"]').first
                if search_input.count() > 0:
                    search_input.fill(lead['business_name'])
                    search_input.press('Enter')
                    
                    if rate_limiter:
                        rate_limiter.wait(self.PLATFORM_NAME)
                    
                    time.sleep(2)
                    
                    # Click first result
                    first_result = page.locator('[data-testid="search-result-item"], .search-result').first
                    if first_result.count() > 0:
                        first_result.click()
                        time.sleep(1)
                        
                        # Extract details from expanded view
                        content = page.content()
                        
                        # Phone
                        phones = self.extract_phones(content)
                        if phones:
                            lead['phone_numbers'] = phones[:3]
                        
                        # Website
                        website_match = re.search(r'href="(https?://(?!maps\.apple)[^"]+)"', content)
                        if website_match:
                            lead['website'] = website_match.group(1)
                        
                        lead['tags'].append('deep_scraped')
            except:
                pass
            
            enhanced.append(lead)
            
            # Guess emails if website found
            if lead.get('website') and not lead.get('emails'):
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:2]]
                lead['tags'].append('emails_guessed')
        
        return enhanced
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
