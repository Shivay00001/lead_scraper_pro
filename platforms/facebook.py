"""
Lead Scraper Pro - Facebook Business Pages Scraper
Scrapes business info from public Facebook business/page About sections.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Facebook public business page scraper - About section only."""
    
    PLATFORM_NAME = "facebook"
    BASE_URL = "https://www.facebook.com"
    
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
        Scrape Facebook business pages.
        Note: Facebook restricts scraping heavily. Works best with direct page URLs.
        
        Args:
            query: Page name/URL or search term
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Check if query is a direct URL or page name
            if 'facebook.com' in query:
                # Direct page URL
                page_urls = [query]
            elif query.startswith('/'):
                page_urls = [self.BASE_URL + query]
            else:
                # Try to search (limited without login)
                page_urls = self._search_pages(page, query, max_results, rate_limiter)
            
            print(f"[Facebook] Found {len(page_urls)} pages. Scraping About sections...")
            
            for i, page_url in enumerate(page_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._scrape_page_about(page, page_url, rate_limiter)
                    if lead and lead.get('business_name'):
                        leads.append(lead)
                        print(f"  [{i+1}] {lead['business_name'][:40]}")
                except:
                    continue
            
        except Exception as e:
            print(f"[Facebook] Error: {e}")
        
        return leads
    
    def _search_pages(self, page: Page, query: str, max_results: int, rate_limiter) -> List[str]:
        """Search for Facebook pages (limited without login)."""
        page_urls = []
        
        try:
            # Facebook pages search URL
            search_url = f"{self.BASE_URL}/public/{query.replace(' ', '%20')}"
            page.goto(search_url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Look for page links
            links = page.locator('a[href*="/pages/"], a[href*="facebook.com/"][role="link"]').all()
            
            for link in links[:max_results * 2]:
                try:
                    href = link.get_attribute('href')
                    if href and '/pages/' in href or (href and 'facebook.com/' in href and '/posts/' not in href):
                        if href not in page_urls:
                            page_urls.append(href)
                except:
                    continue
            
        except:
            pass
        
        return page_urls
    
    def _scrape_page_about(self, page: Page, page_url: str, rate_limiter) -> Optional[Dict]:
        """Scrape the About section of a Facebook page."""
        try:
            # Navigate to About tab
            about_url = page_url.rstrip('/') + '/about'
            if '?' in about_url:
                about_url = page_url.split('?')[0].rstrip('/') + '/about'
            
            page.goto(about_url, wait_until='domcontentloaded')
            
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
                'city': '',
                'state': '',
                'country': '',
                'opening_hours': '',
                'social_links': {'facebook': page_url},
                'lead_type': 'B2C',
                'tags': ['facebook', 'business_page'],
                'notes': '',
                'raw_data': {'url': page_url}
            }
            
            content = page.content()
            visible_text = page.evaluate('() => document.body.innerText') or ''
            
            # Page name
            try:
                name_selectors = ['h1', '[role="heading"][aria-level="1"]', '.x1heor9g']
                for selector in name_selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        lead['business_name'] = self.clean_text(elem.text_content())
                        if lead['business_name']:
                            break
            except:
                pass
            
            if not lead['business_name']:
                # Try from title
                try:
                    title = page.title()
                    if title:
                        lead['business_name'] = title.split('|')[0].split('-')[0].strip()
                except:
                    pass
            
            if not lead['business_name']:
                return None
            
            # Category
            try:
                cat_patterns = [r'Category[:\s]+([^\n]+)', r'Page[:\s]+·[:\s]+([^\n]+)']
                for pattern in cat_patterns:
                    match = re.search(pattern, visible_text, re.I)
                    if match:
                        lead['category'] = self.clean_text(match.group(1))[:50]
                        break
            except:
                pass
            
            # Phone number
            try:
                phone_pattern = r'(?:Phone|Call|Mobile)[:\s]*([+\d\s()-]{10,})'
                phone_match = re.search(phone_pattern, visible_text, re.I)
                if phone_match:
                    phones = self.extract_phones(phone_match.group(1))
                    lead['phone_numbers'] = phones
                else:
                    # Try general extraction
                    phones = self.extract_phones(visible_text)
                    lead['phone_numbers'] = phones[:3]
            except:
                pass
            
            # Email
            try:
                email_pattern = r'(?:Email|Mail)[:\s]*([^\s\n]+@[^\s\n]+)'
                email_match = re.search(email_pattern, visible_text, re.I)
                if email_match:
                    lead['emails'] = [email_match.group(1)]
                else:
                    emails = self.extract_emails(content)
                    # Filter out Facebook emails
                    lead['emails'] = [e for e in emails if 'facebook.com' not in e][:5]
            except:
                pass
            
            # Website
            try:
                website_patterns = [
                    r'Website[:\s]*(https?://[^\s\n]+)',
                    r'(?:Visit|Our Site)[:\s]*(https?://[^\s\n]+)',
                    r'href="(https?://(?!facebook\.com)[^"]+)"'
                ]
                for pattern in website_patterns:
                    match = re.search(pattern, content, re.I)
                    if match:
                        url = match.group(1)
                        if 'facebook' not in url:
                            lead['website'] = url
                            break
            except:
                pass
            
            # Address
            try:
                addr_patterns = [
                    r'(?:Address|Location)[:\s]*([^\n]{10,100})',
                    r'(?:Located at|Visit us)[:\s]*([^\n]{10,100})'
                ]
                for pattern in addr_patterns:
                    match = re.search(pattern, visible_text, re.I)
                    if match:
                        lead['address'] = self.clean_text(match.group(1))
                        lead['pincode'] = self.extract_pincode(lead['address'])
                        break
            except:
                pass
            
            # Opening hours
            try:
                hours_match = re.search(r'(?:Hours|Open|Timing)[:\s]*([^\n]+(?:\n[^\n]+)?)', visible_text, re.I)
                if hours_match:
                    lead['opening_hours'] = self.clean_text(hours_match.group(1))[:100]
            except:
                pass
            
            # About/description
            try:
                about_elem = page.locator('[data-ad-preview="message"], .x1iorvi4').first
                if about_elem.count() > 0:
                    lead['notes'] = self.clean_text(about_elem.text_content())[:300]
            except:
                pass
            
            # Extract other social links
            social_patterns = {
                'instagram': r'instagram\.com/([a-zA-Z0-9._]+)',
                'twitter': r'(?:twitter|x)\.com/([a-zA-Z0-9._]+)',
                'youtube': r'youtube\.com/(?:channel|c|user)/([a-zA-Z0-9._-]+)',
                'linkedin': r'linkedin\.com/(?:company|in)/([a-zA-Z0-9._-]+)'
            }
            
            for platform, pattern in social_patterns.items():
                match = re.search(pattern, content, re.I)
                if match:
                    lead['social_links'][platform] = f"https://{platform}.com/{match.group(1)}"
            
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
