"""
Lead Scraper Pro - Justdial Deep Scraper
Playwright-based deep scraper for Justdial - clicks into listings for full details.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Justdial deep scraper - extracts all available business info."""
    
    PLATFORM_NAME = "justdial"
    BASE_URL = "https://www.justdial.com"
    
    # Justdial uses CSS-based number encoding - this is the mapping
    JD_NUMBER_MAP = {
        'icon-acb': '0', 'icon-ber': '1', 'icon-cdc': '2', 'icon-dede': '3', 'icon-edfe': '4',
        'icon-fgh': '5', 'icon-ghi': '6', 'icon-hij': '7', 'icon-ijk': '8', 'icon-jkl': '9',
        'acb': '0', 'ber': '1', 'cdc': '2', 'dede': '3', 'edfe': '4',
        'fgh': '5', 'ghi': '6', 'hij': '7', 'ijk': '8', 'jkl': '9'
    }
    
    def __init__(self):
        super().__init__()
        self._playwright = None
    
    def _init_browser(self, headless: bool = True) -> Page:
        if self._page:
            return self._page
        
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-IN'
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(30000)
        
        return self._page
    
    def scrape(self,
               query: str,
               location: str = None,
               max_results: int = 50,
               rate_limiter = None,
               stop_check: Callable = None,
               headless: bool = True,
               **kwargs) -> List[Dict]:
        """
        Deep scrape Justdial - clicks into each listing for full details.
        """
        leads = []
        
        if not location:
            location = "Mumbai"
        
        try:
            page = self._init_browser(headless)
            
            # Build Justdial URL
            city_slug = location.lower().replace(' ', '-')
            category_slug = query.lower().replace(' ', '-')
            
            url = f"{self.BASE_URL}/{city_slug}/{category_slug}"
            page.goto(url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Close popups
            try:
                page.click('.jdCloseBtn, .close-btn, [class*="close"]', timeout=2000)
            except:
                pass
            
            # Collect listing URLs
            listing_urls = []
            
            # Scroll to load more listings
            for scroll in range(5):
                if stop_check and stop_check():
                    break
                
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)
                
                # Find all listing links
                links = page.locator('a.lng_cont_name, a.store-name, li.cntanr a[title]').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in listing_urls and '/c-' not in href:
                            if href.startswith('/'):
                                href = self.BASE_URL + href
                            listing_urls.append(href)
                    except:
                        continue
                
                if len(listing_urls) >= max_results:
                    break
            
            print(f"[Justdial] Found {len(listing_urls)} listings. Deep scraping...")
            
            # Deep scrape each listing
            for i, listing_url in enumerate(listing_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._deep_scrape_listing(page, listing_url, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        phones = len(lead.get('phone_numbers', []))
                        print(f"  [{i+1}/{min(len(listing_urls), max_results)}] {lead['business_name'][:40]} | Phones: {phones}")
                except Exception as e:
                    print(f"  [{i+1}] Error: {str(e)[:40]}")
                    continue
            
        except Exception as e:
            print(f"[Justdial] Error: {e}")
        
        return leads
    
    def _deep_scrape_listing(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a single Justdial listing page."""
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
                'opening_hours': '',
                'services': [],
                'social_links': {},
                'lead_type': 'B2B',
                'tags': ['justdial', 'deep_scraped'],
                'raw_data': {'url': url}
            }
            
            # Business name
            name_selectors = ['h1 span.fn', 'h1.store-name', '.company-name h1', 'h1']
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
            
            # Category
            try:
                cat_selectors = ['.primary-tname', '.category-list', '.tagline']
                for selector in cat_selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        lead['category'] = self.clean_text(elem.text_content())
                        break
            except:
                pass
            
            # Rating
            try:
                rating_elem = page.locator('.star-m, .rating-count, .green-box').first
                if rating_elem.count() > 0:
                    text = rating_elem.text_content()
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
            except:
                pass
            
            # Reviews count
            try:
                reviews_elem = page.locator('.review-count, .total-reviews').first
                if reviews_elem.count() > 0:
                    text = reviews_elem.text_content()
                    match = re.search(r'(\d+)', text)
                    if match:
                        lead['reviews_count'] = int(match.group(1))
            except:
                pass
            
            # Address
            try:
                addr_selectors = ['.address-info', '.cont_fl_addr', '.address', '.adr']
                for selector in addr_selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        lead['address'] = self.clean_text(elem.text_content())
                        lead['pincode'] = self.extract_pincode(lead['address'])
                        break
            except:
                pass
            
            # PHONE NUMBERS - Critical for Justdial
            # Method 1: Try to decode from CSS classes
            phones = self._decode_jd_phones(page)
            if phones:
                lead['phone_numbers'] = phones
            
            # Method 2: Click "Call" button if available
            if not lead['phone_numbers']:
                try:
                    call_btn = page.locator('a[href^="tel:"], .callcontent, .contact-number').first
                    if call_btn.count() > 0:
                        href = call_btn.get_attribute('href') or ''
                        text = call_btn.text_content() or ''
                        phones = self.extract_phones(href + ' ' + text)
                        if phones:
                            lead['phone_numbers'] = phones
                except:
                    pass
            
            # Method 3: Check visible phone numbers
            if not lead['phone_numbers']:
                try:
                    content = page.content()
                    # Look for phone patterns in content
                    phone_pattern = r'(?:\+91|0)?\s*[789]\d{9}'
                    phones = re.findall(phone_pattern, content)
                    if phones:
                        lead['phone_numbers'] = list(set(phones))[:5]
                except:
                    pass
            
            # Website
            try:
                website_selectors = ['a.website-link', 'a[data-type="website"]', 'a.primary-action-w']
                for selector in website_selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        href = elem.get_attribute('href')
                        if href and 'justdial' not in href:
                            lead['website'] = href
                            break
            except:
                pass
            
            # Opening hours
            try:
                hours_elem = page.locator('.timing-sec, .open-hours, .working-hours').first
                if hours_elem.count() > 0:
                    lead['opening_hours'] = self.clean_text(hours_elem.text_content())[:200]
            except:
                pass
            
            # Services offered
            try:
                services_elem = page.locator('.services-list li, .tags-list span').all()
                for elem in services_elem[:10]:
                    service = self.clean_text(elem.text_content())
                    if service:
                        lead['services'].append(service)
            except:
                pass
            
            # Extract emails from page content
            try:
                content = page.content()
                emails = self.extract_emails(content)
                lead['emails'] = list(set(emails))[:5]
            except:
                pass
            
            # Guess emails if website but no email
            if lead['website'] and not lead['emails']:
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:3]]
                lead['tags'].append('emails_guessed')
            
            return lead
            
        except Exception as e:
            return None
    
    def _decode_jd_phones(self, page: Page) -> List[str]:
        """
        Decode Justdial's obfuscated phone numbers.
        Justdial uses CSS classes to render phone digits as background images.
        """
        phones = []
        
        try:
            # Find phone containers
            phone_containers = page.locator('.mobilesv, .contact-phone, .telnumcr').all()
            
            for container in phone_containers:
                phone_number = ''
                
                # Get all span elements with number classes
                spans = container.locator('span[class*="icon-"]').all()
                
                if not spans:
                    # Try alternate format
                    spans = container.locator('span[class]').all()
                
                for span in spans:
                    try:
                        classes = span.get_attribute('class') or ''
                        
                        for class_name in classes.split():
                            # Check against our mapping
                            for key, digit in self.JD_NUMBER_MAP.items():
                                if key in class_name:
                                    phone_number += digit
                                    break
                    except:
                        continue
                
                if len(phone_number) >= 10:
                    # Add country code if not present
                    if not phone_number.startswith('+'):
                        phone_number = '+91' + phone_number[-10:]
                    phones.append(phone_number)
            
        except Exception as e:
            pass
        
        return list(set(phones))[:3]
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
