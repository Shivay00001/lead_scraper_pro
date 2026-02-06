"""
Lead Scraper Pro - IndiaMART Deep Scraper
Deep scraper for IndiaMART supplier listings and product pages.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """IndiaMART deep scraper - visits supplier profiles for full details."""
    
    PLATFORM_NAME = "indiamart"
    BASE_URL = "https://dir.indiamart.com"
    
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
            locale='en-IN'
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(30000)
        return self._page
    
    def scrape(self, query: str, location: str = None, max_results: int = 50,
               rate_limiter=None, stop_check: Callable = None, headless: bool = True, **kwargs) -> List[Dict]:
        """Deep scrape IndiaMART supplier listings."""
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Build search URL
            url = f"{self.BASE_URL}/search.mp?ss={query.replace(' ', '+')}"
            if location:
                url += f"&cq={location.replace(' ', '+')}"
            
            page.goto(url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Close popups
            try:
                page.click('.close-icon, .popup-close, [class*="close"]', timeout=2000)
            except:
                pass
            
            # Collect supplier profile URLs
            profile_urls = []
            
            for scroll in range(5):
                if stop_check and stop_check():
                    break
                
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)
                
                # Find company profile links
                links = page.locator('a[href*="/company/"], a.lcname, a[href*="indiamart.com/"][href*="/"]').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and '/company/' in href and href not in profile_urls:
                            if not href.startswith('http'):
                                href = 'https://www.indiamart.com' + href
                            profile_urls.append(href)
                    except:
                        continue
                
                if len(profile_urls) >= max_results:
                    break
            
            print(f"[IndiaMART] Found {len(profile_urls)} suppliers. Deep scraping...")
            
            # Deep scrape each supplier profile
            for i, profile_url in enumerate(profile_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._deep_scrape_profile(page, profile_url, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        print(f"  [{i+1}/{min(len(profile_urls), max_results)}] {lead['business_name'][:40]}")
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"[IndiaMART] Error: {e}")
        
        return leads
    
    def _deep_scrape_profile(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a supplier profile page."""
        try:
            page.goto(url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(2)
            
            lead = {
                'business_name': '',
                'category': '',
                'phone_numbers': [],
                'emails': [],
                'website': '',
                'address': '',
                'city': '',
                'state': '',
                'country': 'India',
                'pincode': '',
                'rating': None,
                'reviews_count': None,
                'products': [],
                'gst_number': '',
                'year_established': '',
                'employee_count': '',
                'annual_turnover': '',
                'social_links': {},
                'lead_type': 'B2B',
                'industry': '',
                'tags': ['indiamart', 'supplier', 'deep_scraped'],
                'is_verified': False,
                'raw_data': {'url': url}
            }
            
            # Company name
            name_selectors = ['h1.cmp-name', '.company-name h1', 'h1[itemprop="name"]', 'h1']
            for selector in name_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        lead['business_name'] = self.clean_text(elem.text_content())
                        break
                except:
                    continue
            
            if not lead['business_name']:
                return None
            
            # Business type/category
            try:
                cat_elem = page.locator('.nature-of-bus, .business-type, [itemprop="description"]').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())[:100]
            except:
                pass
            
            # Address
            try:
                addr_elem = page.locator('.addr, address, .company-address, [itemprop="address"]').first
                if addr_elem.count() > 0:
                    lead['address'] = self.clean_text(addr_elem.text_content())
                    lead['pincode'] = self.extract_pincode(lead['address'])
                    
                    # Parse city/state
                    parts = lead['address'].split(',')
                    if len(parts) >= 2:
                        lead['city'] = parts[-2].strip()
                        lead['state'] = parts[-1].strip()
            except:
                pass
            
            # Phone numbers - click to reveal if needed
            try:
                # First try visible phones
                phone_elems = page.locator('a[href^="tel:"], .phone-number, .contact-no').all()
                for elem in phone_elems:
                    text = elem.get_attribute('href') or elem.text_content() or ''
                    phones = self.extract_phones(text)
                    lead['phone_numbers'].extend(phones)
                
                # Click "Call" button if phones not found
                if not lead['phone_numbers']:
                    try:
                        call_btn = page.locator('button:has-text("Call"), .call-btn, a.call-link').first
                        if call_btn.count() > 0:
                            call_btn.click(timeout=3000)
                            time.sleep(1)
                            
                            # Try to extract revealed phone
                            content = page.content()
                            phones = self.extract_phones(content)
                            lead['phone_numbers'] = phones[:3]
                    except:
                        pass
            except:
                pass
            
            lead['phone_numbers'] = list(set(lead['phone_numbers']))[:5]
            
            # Website
            try:
                website_elem = page.locator('a[href*="http"]:not([href*="indiamart"])').all()
                for elem in website_elem[:5]:
                    href = elem.get_attribute('href') or ''
                    if href and 'indiamart' not in href and not href.endswith('.jpg') and not href.endswith('.png'):
                        lead['website'] = href
                        break
            except:
                pass
            
            # GST Number (important for B2B)
            try:
                gst_elem = page.locator('[class*="gst"], [data-gst]').first
                if gst_elem.count() > 0:
                    text = gst_elem.text_content()
                    gst_match = re.search(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}[Z]{1}[0-9A-Z]{1}', text)
                    if gst_match:
                        lead['gst_number'] = gst_match.group(0)
                        lead['is_verified'] = True
                        lead['tags'].append('gst_verified')
            except:
                pass
            
            # Year established
            try:
                year_elem = page.locator('[class*="established"], [class*="year"]').first
                if year_elem.count() > 0:
                    text = year_elem.text_content()
                    year_match = re.search(r'(19|20)\d{2}', text)
                    if year_match:
                        lead['year_established'] = year_match.group(0)
            except:
                pass
            
            # Employee count and turnover
            try:
                info_items = page.locator('.info-list li, .company-info-row').all()
                for item in info_items:
                    text = (item.text_content() or '').lower()
                    if 'employee' in text:
                        lead['employee_count'] = self.clean_text(item.text_content())
                    elif 'turnover' in text:
                        lead['annual_turnover'] = self.clean_text(item.text_content())
            except:
                pass
            
            # Products list
            try:
                product_elems = page.locator('.product-list a, .main-products li').all()
                for elem in product_elems[:10]:
                    product = self.clean_text(elem.text_content())
                    if product:
                        lead['products'].append(product)
            except:
                pass
            
            # Trust seal/rating
            try:
                trust_elem = page.locator('.trust-score, .im-seal').first
                if trust_elem.count() > 0:
                    text = trust_elem.text_content()
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
            except:
                pass
            
            # Extract emails from page
            try:
                content = page.content()
                emails = self.extract_emails(content)
                lead['emails'] = list(set(emails))[:5]
            except:
                pass
            
            # Guess emails if none found
            if lead['website'] and not lead['emails']:
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:3]]
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
