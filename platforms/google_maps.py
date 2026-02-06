"""
Lead Scraper Pro - Google Maps Deep Scraper
Playwright-based deep scraper for Google Maps - clicks into each listing for full details.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Google Maps deep scraper - extracts full business details."""
    
    PLATFORM_NAME = "google_maps"
    BASE_URL = "https://www.google.com/maps"
    
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
                '--no-sandbox',
                '--disable-web-security'
            ]
        )
        
        context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            geolocation={'latitude': 19.0760, 'longitude': 72.8777},  # Mumbai
            permissions=['geolocation']
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
        Deep scrape Google Maps - clicks into each listing for full details.
        
        Args:
            query: Search query (e.g., "restaurants", "IT companies")
            location: Location (e.g., "Mumbai", "Delhi NCR")
            max_results: Maximum number of results
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Build search query
            search_query = query
            if location:
                search_query = f"{query} in {location}"
            
            # Navigate to Google Maps
            page.goto(self.BASE_URL, wait_until='networkidle')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Search
            search_box = page.locator('#searchboxinput')
            search_box.fill(search_query)
            search_box.press('Enter')
            
            # Wait for results
            time.sleep(4)
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Find results panel and scroll to load more
            results_panel = page.locator('div[role="feed"]').first
            
            # Collect listing URLs first
            listing_urls = []
            last_count = 0
            no_new_count = 0
            
            while len(listing_urls) < max_results:
                if stop_check and stop_check():
                    break
                
                # Scroll
                try:
                    results_panel.evaluate('el => el.scrollBy(0, 800)')
                except:
                    page.keyboard.press('End')
                
                time.sleep(1)
                
                # Get all listing links
                links = page.locator('a[href*="/maps/place/"]').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in listing_urls:
                            listing_urls.append(href)
                    except:
                        continue
                
                if len(listing_urls) == last_count:
                    no_new_count += 1
                    if no_new_count >= 3:
                        break
                else:
                    no_new_count = 0
                
                last_count = len(listing_urls)
                
                if len(listing_urls) >= max_results:
                    break
            
            # Deep scrape each listing
            print(f"[GoogleMaps] Found {len(listing_urls)} listings. Deep scraping...")
            
            for i, url in enumerate(listing_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._deep_scrape_listing(page, url, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        print(f"  [{i+1}/{min(len(listing_urls), max_results)}] {lead['business_name'][:50]}")
                except Exception as e:
                    print(f"  [{i+1}] Error: {str(e)[:50]}")
                    continue
            
        except Exception as e:
            print(f"[GoogleMaps] Error: {e}")
        
        return leads
    
    def _deep_scrape_listing(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a single listing by navigating to its page."""
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
                'social_links': {},
                'lead_type': 'B2B',
                'tags': ['google_maps', 'deep_scraped'],
                'is_verified': False,
                'raw_data': {'url': url}
            }
            
            # Business name
            name_selectors = ['h1.DUwDvf', 'h1[data-attrid="title"]', 'div.fontHeadlineLarge']
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
                cat_elem = page.locator('button[jsaction*="category"]').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())
            except:
                pass
            
            # Rating and reviews
            try:
                rating_elem = page.locator('div.F7nice span[aria-hidden="true"]').first
                if rating_elem.count() > 0:
                    text = rating_elem.text_content()
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
                
                reviews_elem = page.locator('span[aria-label*="reviews"]').first
                if reviews_elem.count() > 0:
                    text = reviews_elem.get_attribute('aria-label') or reviews_elem.text_content()
                    match = re.search(r'([\d,]+)', text)
                    if match:
                        lead['reviews_count'] = int(match.group(1).replace(',', ''))
            except:
                pass
            
            # Address - multiple attempts
            try:
                # Method 1: Button with address
                addr_btn = page.locator('button[data-item-id*="address"]').first
                if addr_btn.count() > 0:
                    lead['address'] = self.clean_text(addr_btn.get_attribute('aria-label') or addr_btn.text_content())
                    lead['address'] = lead['address'].replace('Address:', '').strip()
            except:
                pass
            
            if not lead['address']:
                try:
                    # Method 2: Look for address in info container
                    addr_elem = page.locator('[data-tooltip="Copy address"]').first
                    if addr_elem.count() > 0:
                        lead['address'] = self.clean_text(addr_elem.text_content())
                except:
                    pass
            
            # Extract pincode and city from address
            if lead['address']:
                lead['pincode'] = self.extract_pincode(lead['address'])
                
                # Parse city from address
                parts = lead['address'].split(',')
                if len(parts) >= 2:
                    lead['city'] = parts[-2].strip()
                    lead['state'] = parts[-1].strip() if len(parts) > 2 else ''
            
            # Phone numbers - CRITICAL
            phone_found = False
            phone_selectors = [
                'button[data-item-id*="phone"]',
                'a[data-item-id*="phone"]',
                'button[aria-label*="Phone"]',
                '[data-tooltip="Copy phone number"]'
            ]
            
            for selector in phone_selectors:
                try:
                    elems = page.locator(selector).all()
                    for elem in elems:
                        text = elem.get_attribute('aria-label') or elem.text_content() or ''
                        phones = self.extract_phones(text)
                        if phones:
                            lead['phone_numbers'].extend(phones)
                            phone_found = True
                except:
                    continue
            
            # Also check page content for phone patterns
            if not phone_found:
                try:
                    content = page.content()
                    phones = self.extract_phones(content)
                    if phones:
                        lead['phone_numbers'] = phones[:3]  # Limit to 3
                except:
                    pass
            
            lead['phone_numbers'] = list(set(lead['phone_numbers']))
            
            # Website - CRITICAL
            website_selectors = [
                'a[data-item-id="authority"]',
                'a[data-tooltip="Open website"]',
                'a[aria-label*="website"]'
            ]
            
            for selector in website_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        href = elem.get_attribute('href')
                        if href and 'google' not in href:
                            lead['website'] = href
                            break
                except:
                    continue
            
            # Opening hours
            try:
                hours_btn = page.locator('button[data-item-id*="oh"]').first
                if hours_btn.count() > 0:
                    hours_text = hours_btn.get_attribute('aria-label') or hours_btn.text_content() or ''
                    lead['opening_hours'] = self.clean_text(hours_text)[:200]
            except:
                pass
            
            # Check for verified badge
            try:
                verified = page.locator('[aria-label*="verified"], [data-value*="verified"]')
                if verified.count() > 0:
                    lead['is_verified'] = True
                    lead['tags'].append('verified')
            except:
                pass
            
            # Extract emails from page content
            try:
                content = page.content()
                emails = self.extract_emails(content)
                lead['emails'] = list(set(emails))[:5]
            except:
                pass
            
            # Guess emails if website exists but no emails found
            if lead['website'] and not lead['emails']:
                guessed = self.guess_emails(lead['website'])
                lead['emails'] = [g['email'] for g in guessed[:3]]
                lead['tags'].append('emails_guessed')
            
            # Check for social links
            social_patterns = {
                'facebook': r'facebook\.com/[^"\s]+',
                'instagram': r'instagram\.com/[^"\s]+',
                'twitter': r'twitter\.com/[^"\s]+|x\.com/[^"\s]+',
                'linkedin': r'linkedin\.com/[^"\s]+',
                'youtube': r'youtube\.com/[^"\s]+'
            }
            
            try:
                content = page.content()
                for platform, pattern in social_patterns.items():
                    match = re.search(pattern, content, re.I)
                    if match:
                        lead['social_links'][platform] = 'https://' + match.group(0)
            except:
                pass
            
            # Determine lead type based on category
            b2c_keywords = ['restaurant', 'cafe', 'salon', 'spa', 'gym', 'hotel', 'clinic', 'hospital', 'school']
            if any(kw in (lead['category'] or '').lower() for kw in b2c_keywords):
                lead['lead_type'] = 'B2C'
            
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
