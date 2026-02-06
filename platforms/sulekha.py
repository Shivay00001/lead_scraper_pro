"""
Lead Scraper Pro - Sulekha Deep Scraper
Deep scraper for Sulekha business listings.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Sulekha deep scraper - visits each listing for full details."""
    
    PLATFORM_NAME = "sulekha"
    BASE_URL = "https://www.sulekha.com"
    
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
        """Deep scrape Sulekha business listings."""
        leads = []
        
        if not location:
            location = "mumbai"
        
        try:
            page = self._init_browser(headless)
            
            # Build Sulekha URL
            city_slug = location.lower().replace(' ', '-')
            category_slug = query.lower().replace(' ', '-')
            
            url = f"{self.BASE_URL}/{category_slug}/{city_slug}"
            page.goto(url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Close popups
            try:
                page.click('.fa-times, .close-btn, button[class*="close"]', timeout=2000)
            except:
                pass
            
            # Collect listing URLs
            listing_urls = []
            
            for scroll in range(5):
                if stop_check and stop_check():
                    break
                
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)
                
                # Find listing links
                links = page.locator('a.name, a[href*="/view-"], .bus-name a').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in listing_urls:
                            if href.startswith('/'):
                                href = self.BASE_URL + href
                            listing_urls.append(href)
                    except:
                        continue
                
                if len(listing_urls) >= max_results:
                    break
            
            print(f"[Sulekha] Found {len(listing_urls)} listings. Deep scraping...")
            
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
                    continue
            
        except Exception as e:
            print(f"[Sulekha] Error: {e}")
        
        return leads
    
    def _deep_scrape_listing(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a single Sulekha listing page."""
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
                'experience_years': '',
                'tags': ['sulekha', 'deep_scraped'],
                'is_verified': False,
                'raw_data': {'url': url}
            }
            
            content = page.content()
            visible_text = page.evaluate('() => document.body.innerText') or ''
            
            # Business name
            name_selectors = ['h1.name', 'h1.bus-name', '.company-name h1', 'h1']
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
                cat_elem = page.locator('.category, .service-type, .bus-category').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())[:100]
            except:
                pass
            
            # Rating
            try:
                rating_elem = page.locator('.rating-star, .avg-rating, [class*="rating"]').first
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
                addr_selectors = ['.address, .adr, .location-info']
                for selector in addr_selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        lead['address'] = self.clean_text(elem.text_content())
                        lead['pincode'] = self.extract_pincode(lead['address'])
                        break
            except:
                pass
            
            # Phone numbers - click to reveal if needed
            try:
                # Try visible phones first
                phone_btns = page.locator('a[href^="tel:"], .phone-num, .contact-phone').all()
                for btn in phone_btns:
                    text = btn.get_attribute('href') or btn.text_content() or ''
                    phones = self.extract_phones(text)
                    lead['phone_numbers'].extend(phones)
                
                # Click "Show Number" button if available
                if not lead['phone_numbers']:
                    try:
                        show_btn = page.locator('button:has-text("Show"), a:has-text("Call"), .show-phone').first
                        if show_btn.count() > 0:
                            show_btn.click(timeout=3000)
                            time.sleep(1)
                            
                            # Get revealed phone
                            phone_containers = page.locator('.phone-revealed, .shown-number, [class*="phone"]').all()
                            for container in phone_containers:
                                text = container.text_content() or ''
                                phones = self.extract_phones(text)
                                lead['phone_numbers'].extend(phones)
                    except:
                        pass
                
                # Also check page content
                if not lead['phone_numbers']:
                    phones = self.extract_phones(visible_text)
                    lead['phone_numbers'] = phones[:5]
            except:
                pass
            
            lead['phone_numbers'] = list(set(lead['phone_numbers']))[:5]
            
            # Website
            try:
                website_elem = page.locator('a[href*="http"]:not([href*="sulekha"])').first
                if website_elem.count() > 0:
                    href = website_elem.get_attribute('href') or ''
                    if href and 'sulekha' not in href and not href.endswith('.jpg'):
                        lead['website'] = href
            except:
                pass
            
            # Experience/years in business
            try:
                exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:experience|exp)?', visible_text, re.I)
                if exp_match:
                    lead['experience_years'] = f"{exp_match.group(1)} years"
            except:
                pass
            
            # Services offered
            try:
                service_elems = page.locator('.service-list li, .services-offered span').all()
                for elem in service_elems[:10]:
                    service = self.clean_text(elem.text_content())
                    if service and len(service) > 2:
                        lead['services'].append(service)
            except:
                pass
            
            # Verified badge
            try:
                verified = page.locator('[class*="verified"], [class*="trusted"]')
                if verified.count() > 0:
                    lead['is_verified'] = True
                    lead['tags'].append('verified')
            except:
                pass
            
            # Extract emails
            try:
                emails = self.extract_emails(content)
                lead['emails'] = [e for e in emails if 'sulekha' not in e][:5]
            except:
                pass
            
            # Guess emails if website exists
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
