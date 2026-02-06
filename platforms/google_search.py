"""
Lead Scraper Pro - Google Search Deep Scraper
Scrapes business info from SERP and visits contact pages for deep extraction.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Google Search deep scraper - visits websites and contact pages."""
    
    PLATFORM_NAME = "google_search"
    BASE_URL = "https://www.google.com"
    
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
        self._page.set_default_timeout(20000)
        
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
        Deep scrape Google Search - visits each website and its contact page.
        """
        leads = []
        
        try:
            page = self._init_browser(headless)
            
            # Build business-focused search query
            search_query = query
            if location:
                search_query = f"{query} in {location}"
            
            # Add business keywords
            if not any(kw in query.lower() for kw in ['company', 'business', 'service', 'agency']):
                search_query += " business contact"
            
            # Navigate to Google
            page.goto(self.BASE_URL, wait_until='networkidle')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Accept cookies if present
            try:
                page.click('button:has-text("Accept")', timeout=3000)
            except:
                pass
            
            # Search
            search_box = page.locator('textarea[name="q"], input[name="q"]').first
            search_box.fill(search_query)
            search_box.press('Enter')
            
            page.wait_for_selector('#search', timeout=10000)
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            # Collect website URLs from SERP
            website_urls = []
            collected = 0
            current_page = 1
            max_pages = min(10, (max_results // 10) + 1)
            
            while len(website_urls) < max_results * 2 and current_page <= max_pages:
                if stop_check and stop_check():
                    break
                
                # Get all result links
                results = page.locator('div.g a[href^="http"]').all()
                
                for result in results:
                    try:
                        href = result.get_attribute('href')
                        if not href:
                            continue
                        
                        # Skip non-business sites
                        skip_domains = ['google.', 'youtube.', 'facebook.', 'twitter.', 'linkedin.', 
                                       'instagram.', 'wikipedia.', 'reddit.', 'quora.', 'pinterest.',
                                       'amazon.', 'flipkart.', 'gov.', 'edu.']
                        
                        if any(domain in href.lower() for domain in skip_domains):
                            continue
                        
                        if href not in website_urls:
                            website_urls.append(href)
                    except:
                        continue
                
                # Next page
                try:
                    next_btn = page.locator('#pnnext').first
                    if next_btn.count() > 0 and len(website_urls) < max_results * 2:
                        next_btn.click()
                        page.wait_for_load_state('networkidle')
                        if rate_limiter:
                            rate_limiter.wait(self.PLATFORM_NAME)
                        current_page += 1
                    else:
                        break
                except:
                    break
            
            # Deep scrape each website
            print(f"[GoogleSearch] Found {len(website_urls)} websites. Deep scraping...")
            
            for i, url in enumerate(website_urls[:max_results]):
                if stop_check and stop_check():
                    break
                
                try:
                    lead = self._deep_scrape_website(page, url, rate_limiter)
                    if lead and lead.get('business_name') and (lead.get('emails') or lead.get('phone_numbers')):
                        leads.append(lead)
                        print(f"  [{i+1}/{min(len(website_urls), max_results)}] {lead['business_name'][:40]}")
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"[GoogleSearch] Error: {e}")
        
        return leads
    
    def _deep_scrape_website(self, page: Page, url: str, rate_limiter) -> Optional[Dict]:
        """Deep scrape a website and its contact page."""
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(2)
            
            lead = {
                'business_name': '',
                'category': '',
                'phone_numbers': [],
                'emails': [],
                'website': url,
                'address': '',
                'city': '',
                'state': '',
                'country': 'India',
                'pincode': '',
                'social_links': {},
                'lead_type': 'B2B',
                'tags': ['google_search', 'deep_scraped'],
                'notes': '',
                'raw_data': {'source_url': url}
            }
            
            # Get page content
            content = page.content()
            visible_text = page.evaluate('() => document.body.innerText') or ''
            
            # Extract business name from title
            try:
                title = page.title()
                if title:
                    # Clean title - remove common suffixes
                    name = title.split('|')[0].split('-')[0].split('–')[0].strip()
                    lead['business_name'] = self.clean_text(name)[:100]
            except:
                pass
            
            if not lead['business_name']:
                # Try H1
                try:
                    h1 = page.locator('h1').first
                    if h1.count() > 0:
                        lead['business_name'] = self.clean_text(h1.text_content())[:100]
                except:
                    pass
            
            if not lead['business_name']:
                return None
            
            # Extract emails from homepage
            emails = self.extract_emails(content)
            phones = self.extract_phones(visible_text)
            
            lead['emails'] = list(set(emails))[:10]
            lead['phone_numbers'] = list(set(phones))[:5]
            
            # Try to find and visit contact page
            contact_links = self._find_contact_links(page)
            
            for contact_url in contact_links[:2]:  # Try up to 2 contact pages
                try:
                    page.goto(contact_url, wait_until='domcontentloaded', timeout=10000)
                    
                    if rate_limiter:
                        rate_limiter.human_delay()
                    
                    contact_content = page.content()
                    contact_text = page.evaluate('() => document.body.innerText') or ''
                    
                    # Extract more data from contact page
                    contact_emails = self.extract_emails(contact_content)
                    contact_phones = self.extract_phones(contact_text)
                    
                    lead['emails'] = list(set(lead['emails'] + contact_emails))[:10]
                    lead['phone_numbers'] = list(set(lead['phone_numbers'] + contact_phones))[:5]
                    
                    # Try to extract address
                    address = self._extract_address(contact_text)
                    if address:
                        lead['address'] = address
                        lead['pincode'] = self.extract_pincode(address)
                    
                except:
                    continue
            
            # Extract social links
            lead['social_links'] = self._extract_social_links(content)
            
            # Guess emails if none found
            if not lead['emails']:
                guessed = self.guess_emails(url)
                lead['emails'] = [g['email'] for g in guessed[:3]]
                lead['tags'].append('emails_guessed')
            
            # Filter out generic/common emails
            lead['emails'] = [e for e in lead['emails'] if not any(x in e.lower() for x in ['noreply', 'no-reply', 'mailer-daemon'])]
            
            return lead
            
        except Exception as e:
            return None
    
    def _find_contact_links(self, page: Page) -> List[str]:
        """Find contact/about page links."""
        contact_urls = []
        
        contact_texts = ['contact', 'about', 'reach us', 'get in touch', 'connect']
        
        for text in contact_texts:
            try:
                links = page.locator(f'a:has-text("{text}")').all()
                for link in links:
                    href = link.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            # Relative URL - construct absolute
                            base = page.url.split('/')[0:3]
                            href = '/'.join(base) + href
                        if href.startswith('http') and href not in contact_urls:
                            contact_urls.append(href)
            except:
                continue
        
        return contact_urls[:5]
    
    def _extract_address(self, text: str) -> str:
        """Try to extract address from text."""
        # Look for address patterns
        patterns = [
            r'(?:address|location|office)[:\s]*([^,\n]{10,100}(?:india|road|street|nagar|colony)?)',
            r'\d+[/,\s]+[^,\n]{10,80}(?:road|street|nagar|colony|sector|floor)[^,\n]{0,50}',
            r'[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*\d{6}'  # City, State, Pincode
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return self.clean_text(match.group(0))[:200]
        
        return ''
    
    def _extract_social_links(self, content: str) -> Dict:
        """Extract social media links from page content."""
        socials = {}
        
        patterns = {
            'facebook': r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+',
            'instagram': r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+',
            'twitter': r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9._-]+',
            'linkedin': r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+',
            'youtube': r'https?://(?:www\.)?youtube\.com/(?:channel|c|user)/[a-zA-Z0-9._-]+'
        }
        
        for platform, pattern in patterns.items():
            match = re.search(pattern, content, re.I)
            if match:
                socials[platform] = match.group(0)
        
        return socials
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
