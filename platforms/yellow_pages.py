"""
Lead Scraper Pro - Yellow Pages Deep Scraper
Deep scraper for Yellow Pages (global + India).
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Yellow Pages deep scraper - clicks into each listing for full details."""
    
    PLATFORM_NAME = "yellow_pages"
    
    # Multiple Yellow Pages domains
    DOMAINS = {
        'us': 'https://www.yellowpages.com',
        'india': 'https://www.yellowpages.co.in',
        'uk': 'https://www.yell.com',
        'au': 'https://www.yellowpages.com.au'
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
               rate_limiter=None, stop_check: Callable = None, headless: bool = True,
               region: str = 'us', **kwargs) -> List[Dict]:
        """Deep scrape Yellow Pages business listings."""
        leads = []
        
        if not location:
            location = 'Mumbai' if region == 'india' else 'New York, NY'
        
        base_url = self.DOMAINS.get(region, self.DOMAINS['us'])
        
        try:
            page = self._init_browser(headless)
            
            # Build search URL
            if region == 'india':
                url = f"{base_url}/search/?what={query.replace(' ', '+')}&where={location.replace(' ', '+')}"
            else:
                url = f"{base_url}/search?search_terms={query.replace(' ', '+')}&geo_location_terms={location.replace(' ', '+')}"
            
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
                links = page.locator('a.business-name, a[href*="/listing-"], a[class*="listing-link"]').all()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href:
                            full_url = href if href.startswith('http') else base_url + href
                            if full_url not in listing_urls:
                                listing_urls.append(full_url)
                    except:
                        continue
                
                if len(listing_urls) >= max_results:
                    break
                
                # Next page
                try:
                    next_btn = page.locator('a.next, [rel="next"], a:has-text("Next")').first
                    if next_btn.count() > 0:
                        next_btn.click()
                        time.sleep(2)
                        if rate_limiter:
                            rate_limiter.wait(self.PLATFORM_NAME)
                        current_page += 1
                        if current_page >= 5:
                            break
                    else:
                        break
                except:
                    break
            
            print(f"[YellowPages] Found {len(listing_urls)} listings. Deep scraping...")
            
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
            print(f"[YellowPages] Error: {e}")
        
        return leads
    
    def _deep_scrape_listing(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a single Yellow Pages listing."""
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
                'services': [],
                'year_established': '',
                'social_links': {},
                'lead_type': 'B2B',
                'tags': ['yellow_pages', 'deep_scraped'],
                'raw_data': {'url': url}
            }
            
            content = page.content()
            visible_text = page.evaluate('() => document.body.innerText') or ''
            
            # Business name
            name_selectors = ['h1.business-name', 'h1', '.dockable-business-name']
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
                cat_elem = page.locator('.categories, .category-links a').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())[:100]
            except:
                pass
            
            # Rating
            try:
                rating_elem = page.locator('.rating, [class*="star-rating"]').first
                if rating_elem.count() > 0:
                    text = rating_elem.get_attribute('aria-label') or rating_elem.text_content() or ''
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
            except:
                pass
            
            # Reviews count  
            try:
                reviews_elem = page.locator('.review-count, .count').first
                if reviews_elem.count() > 0:
                    text = reviews_elem.text_content()
                    match = re.search(r'(\d+)', text)
                    if match:
                        lead['reviews_count'] = int(match.group(1))
            except:
                pass
            
            # Address
            try:
                addr_elem = page.locator('.address, .street-address, [class*="address"]').first
                if addr_elem.count() > 0:
                    lead['address'] = self.clean_text(addr_elem.text_content())
                    lead['pincode'] = self.extract_pincode(lead['address'])
            except:
                pass
            
            # Phone - primary method
            try:
                phone_elem = page.locator('a[href^="tel:"], .phone, .primary-phone').first
                if phone_elem.count() > 0:
                    text = phone_elem.get_attribute('href') or phone_elem.text_content() or ''
                    phones = self.extract_phones(text)
                    lead['phone_numbers'] = phones
            except:
                pass
            
            # Phone - from content
            if not lead['phone_numbers']:
                phones = self.extract_phones(visible_text)
                lead['phone_numbers'] = phones[:5]
            
            lead['phone_numbers'] = list(set(lead['phone_numbers']))[:5]
            
            # Website
            try:
                website_elem = page.locator('a.website-link, a[href*="http"]:not([href*="yellowpages"])').first
                if website_elem.count() > 0:
                    href = website_elem.get_attribute('href') or ''
                    if 'yellowpages' not in href and 'yell' not in href:
                        lead['website'] = href
            except:
                pass
            
            # Opening hours
            try:
                hours_elem = page.locator('.open-hours, .hours-table, [class*="hours"]').first
                if hours_elem.count() > 0:
                    lead['opening_hours'] = self.clean_text(hours_elem.text_content())[:200]
            except:
                pass
            
            # Year established
            try:
                year_match = re.search(r'(?:established|since|founded)[:\s]*(\d{4})', visible_text, re.I)
                if year_match:
                    lead['year_established'] = year_match.group(1)
            except:
                pass
            
            # Services
            try:
                services_elems = page.locator('.services li, .service-list span').all()
                for elem in services_elems[:10]:
                    service = self.clean_text(elem.text_content())
                    if service and len(service) > 2:
                        lead['services'].append(service)
            except:
                pass
            
            # Email extraction
            try:
                emails = self.extract_emails(content)
                lead['emails'] = [e for e in emails if 'yellowpages' not in e and 'yell' not in e][:5]
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
