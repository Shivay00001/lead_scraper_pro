"""
Lead Scraper Pro - Yelp Deep Scraper
Deep scraper for Yelp business listings.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Yelp deep scraper - visits each listing page for full details."""
    
    PLATFORM_NAME = "yelp"
    BASE_URL = "https://www.yelp.com"
    
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
        """Deep scrape Yelp business listings."""
        leads = []
        
        if not location:
            location = "Mumbai, India"
        
        try:
            page = self._init_browser(headless)
            
            # Build Yelp search URL
            url = f"{self.BASE_URL}/search?find_desc={query.replace(' ', '+')}&find_loc={location.replace(' ', '+')}"
            page.goto(url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Collect listing URLs
            listing_urls = []
            current_page = 0
            
            while len(listing_urls) < max_results:
                if stop_check and stop_check():
                    break
                
                # Find business links
                links = page.locator('a[href*="/biz/"]').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and '/biz/' in href and '?' not in href:
                            full_url = href if href.startswith('http') else self.BASE_URL + href
                            if full_url not in listing_urls:
                                listing_urls.append(full_url)
                    except:
                        continue
                
                if len(listing_urls) >= max_results:
                    break
                
                # Next page
                try:
                    next_btn = page.locator('a[aria-label="Next"], .next-link').first
                    if next_btn.count() > 0:
                        next_btn.click()
                        time.sleep(2)
                        if rate_limiter:
                            rate_limiter.wait(self.PLATFORM_NAME)
                        current_page += 1
                        if current_page >= 5:  # Limit pages
                            break
                    else:
                        break
                except:
                    break
            
            print(f"[Yelp] Found {len(listing_urls)} listings. Deep scraping...")
            
            # Deep scrape each listing
            for i, listing_url in enumerate(listing_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    # Remove duplicates based on URL
                    if '/biz/' not in listing_url:
                        continue
                    
                    lead = self._deep_scrape_listing(page, listing_url, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        phones = len(lead.get('phone_numbers', []))
                        print(f"  [{i+1}/{min(len(listing_urls), max_results)}] {lead['business_name'][:40]} | Phones: {phones}")
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"[Yelp] Error: {e}")
        
        return leads
    
    def _deep_scrape_listing(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a single Yelp business page."""
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
                'country': '',
                'pincode': '',
                'rating': None,
                'reviews_count': None,
                'opening_hours': '',
                'price_range': '',
                'amenities': [],
                'social_links': {},
                'lead_type': 'B2C',
                'tags': ['yelp', 'deep_scraped'],
                'raw_data': {'url': url}
            }
            
            content = page.content()
            visible_text = page.evaluate('() => document.body.innerText') or ''
            
            # Business name
            try:
                name_elem = page.locator('h1').first
                if name_elem.count() > 0:
                    lead['business_name'] = self.clean_text(name_elem.text_content())
            except:
                pass
            
            if not lead['business_name']:
                return None
            
            # Category
            try:
                cat_elem = page.locator('[class*="category"], .categories-title, a[href*="/c/"]').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())[:100]
            except:
                pass
            
            # Rating
            try:
                rating_elem = page.locator('[aria-label*="rating"], [class*="rating"]').first
                if rating_elem.count() > 0:
                    text = rating_elem.get_attribute('aria-label') or rating_elem.text_content() or ''
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
            except:
                pass
            
            # Reviews count
            try:
                reviews_match = re.search(r'(\d+)\s*reviews?', visible_text, re.I)
                if reviews_match:
                    lead['reviews_count'] = int(reviews_match.group(1))
            except:
                pass
            
            # Address
            try:
                addr_elem = page.locator('address, [class*="address"]').first
                if addr_elem.count() > 0:
                    lead['address'] = self.clean_text(addr_elem.text_content())
                    lead['pincode'] = self.extract_pincode(lead['address'])
            except:
                pass
            
            # Phone
            try:
                phone_patterns = [
                    r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                    r'\+\d{1,3}[-.\s]?\d{10}'
                ]
                for pattern in phone_patterns:
                    phones = re.findall(pattern, visible_text)
                    if phones:
                        lead['phone_numbers'] = list(set(phones))[:3]
                        break
            except:
                pass
            
            # Website
            try:
                website_elem = page.locator('a[href*="biz_redir"]').first
                if website_elem.count() > 0:
                    href = website_elem.get_attribute('href') or ''
                    # Extract actual URL from redirect
                    url_match = re.search(r'url=([^&]+)', href)
                    if url_match:
                        import urllib.parse
                        lead['website'] = urllib.parse.unquote(url_match.group(1))
            except:
                pass
            
            # Opening hours
            try:
                hours_elem = page.locator('[class*="hours"], table[class*="hours"]').first
                if hours_elem.count() > 0:
                    lead['opening_hours'] = self.clean_text(hours_elem.text_content())[:200]
            except:
                pass
            
            # Price range
            try:
                price_elem = page.locator('[class*="price"], [aria-label*="price"]').first
                if price_elem.count() > 0:
                    price_text = price_elem.text_content()
                    if '$' in price_text:
                        lead['price_range'] = price_text.strip()
            except:
                pass
            
            # Amenities
            try:
                amenity_elems = page.locator('[class*="amenity"], [class*="attribute"]').all()
                for elem in amenity_elems[:15]:
                    amenity = self.clean_text(elem.text_content())
                    if amenity and len(amenity) > 2:
                        lead['amenities'].append(amenity)
            except:
                pass
            
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
