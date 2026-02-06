"""
Lead Scraper Pro - Bing Maps Deep Scraper
Deep scraper for Bing Maps business listings.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Bing Maps deep scraper - clicks into each listing for details."""
    
    PLATFORM_NAME = "bing_maps"
    BASE_URL = "https://www.bing.com/maps"
    
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
        """Deep scrape Bing Maps business listings."""
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Build search query
            search_query = query
            if location:
                search_query = f"{query} in {location}"
            
            page.goto(self.BASE_URL, wait_until='networkidle')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Search
            search_box = page.locator('#maps_sb, #sb_form_q').first
            search_box.fill(search_query)
            search_box.press('Enter')
            
            time.sleep(4)
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Find all listing cards
            listing_count = 0
            
            for scroll in range(8):
                if stop_check and stop_check():
                    break
                
                # Get listings from results panel
                listings = page.locator('.taskCard, .entity, .b_algo').all()
                
                for listing in listings[listing_count:]:
                    if stop_check and stop_check():
                        break
                    
                    if len(leads) >= max_results:
                        break
                    
                    try:
                        # Click on listing to expand
                        listing.click()
                        time.sleep(1)
                        
                        lead = self._extract_listing_details(page)
                        if lead and lead.get('business_name'):
                            leads.append(lead)
                            print(f"  [{len(leads)}/{max_results}] {lead['business_name'][:40]}")
                    except:
                        continue
                
                listing_count = len(listings)
                
                if len(leads) >= max_results:
                    break
                
                # Scroll
                page.keyboard.press('End')
                time.sleep(1)
            
        except Exception as e:
            print(f"[BingMaps] Error: {e}")
        
        return leads
    
    def _extract_listing_details(self, page: Page) -> Optional[Dict]:
        """Extract details from expanded listing view."""
        try:
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
                'social_links': {},
                'lead_type': 'B2B',
                'tags': ['bing_maps', 'deep_scraped'],
                'raw_data': {}
            }
            
            content = page.content()
            
            # Business name
            name_selectors = ['.title, .entityName, h2.taskName', '.b_promText']
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
                cat_elem = page.locator('.category, .taskType, .entityType').first
                if cat_elem.count() > 0:
                    lead['category'] = self.clean_text(cat_elem.text_content())
            except:
                pass
            
            # Address
            try:
                addr_elem = page.locator('.address, .taskAddress, .locAddr').first
                if addr_elem.count() > 0:
                    lead['address'] = self.clean_text(addr_elem.text_content())
                    lead['pincode'] = self.extract_pincode(lead['address'])
            except:
                pass
            
            # Phone
            try:
                phone_elem = page.locator('a[href^="tel:"], .phone, .taskPhone').first
                if phone_elem.count() > 0:
                    text = phone_elem.get_attribute('href') or phone_elem.text_content() or ''
                    phones = self.extract_phones(text)
                    lead['phone_numbers'] = phones
            except:
                pass
            
            # Also check in content
            if not lead['phone_numbers']:
                phones = self.extract_phones(content)
                lead['phone_numbers'] = phones[:3]
            
            # Website
            try:
                website_elem = page.locator('a[href*="http"]:not([href*="bing"])').first
                if website_elem.count() > 0:
                    href = website_elem.get_attribute('href')
                    if href and 'bing' not in href:
                        lead['website'] = href
            except:
                pass
            
            # Rating
            try:
                rating_elem = page.locator('.rating, .starRating').first
                if rating_elem.count() > 0:
                    text = rating_elem.text_content() or rating_elem.get_attribute('aria-label') or ''
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        lead['rating'] = float(match.group(1))
            except:
                pass
            
            # Reviews count
            try:
                reviews_elem = page.locator('.reviewCount, .numReviews').first
                if reviews_elem.count() > 0:
                    text = reviews_elem.text_content()
                    match = re.search(r'(\d+)', text)
                    if match:
                        lead['reviews_count'] = int(match.group(1))
            except:
                pass
            
            # Opening hours
            try:
                hours_elem = page.locator('.hours, .openHours').first
                if hours_elem.count() > 0:
                    lead['opening_hours'] = self.clean_text(hours_elem.text_content())[:150]
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
