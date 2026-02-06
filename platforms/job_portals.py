"""
Lead Scraper Pro - Job Portals Scraper
Extracts company names and info from job postings on Naukri, Indeed, etc.
"""

import re
import time
from typing import Dict, List, Optional, Callable
from playwright.sync_api import sync_playwright, Page

from platforms.base_scraper import BaseScraper


class Scraper(BaseScraper):
    """Job portals scraper - extracts hiring company info."""
    
    PLATFORM_NAME = "job_portals"
    
    PORTALS = {
        'naukri': 'https://www.naukri.com',
        'indeed': 'https://www.indeed.co.in',
        'linkedin': 'https://www.linkedin.com/jobs'  # Limited without login
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
            locale='en-IN'
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(30000)
        return self._page
    
    def scrape(self, query: str, location: str = None, max_results: int = 50,
               rate_limiter=None, stop_check: Callable = None, headless: bool = True,
               portal: str = 'naukri', **kwargs) -> List[Dict]:
        """
        Scrape job portals for company info.
        
        Args:
            query: Job title/role to search
            location: City/location filter
            portal: Which portal to use (naukri, indeed)
        """
        if portal == 'naukri':
            return self._scrape_naukri(query, location, max_results, rate_limiter, stop_check, headless)
        elif portal == 'indeed':
            return self._scrape_indeed(query, location, max_results, rate_limiter, stop_check, headless)
        else:
            return self._scrape_naukri(query, location, max_results, rate_limiter, stop_check, headless)
    
    def _scrape_naukri(self, query: str, location: str, max_results: int,
                       rate_limiter, stop_check, headless: bool) -> List[Dict]:
        leads = []
        seen_companies = set()
        
        try:
            page = self._init_browser(headless)
            
            # Build Naukri search URL
            search_url = f"https://www.naukri.com/{query.replace(' ', '-')}-jobs"
            if location:
                search_url += f"-in-{location.replace(' ', '-').lower()}"
            
            page.goto(search_url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            # Close popups
            try:
                page.click('.crossIcon, .nI-gNb-x-icon, [class*="close"]', timeout=2000)
            except:
                pass
            
            collected = 0
            
            # Scroll and collect
            for _ in range(5):
                if stop_check and stop_check():
                    break
                
                # Job cards
                jobs = page.locator('.cust-job-tuple, .jobTuple, article.jobTuple').all()
                
                for job in jobs:
                    if stop_check and stop_check():
                        break
                    
                    if collected >= max_results:
                        break
                    
                    try:
                        # Company name
                        company_elem = job.locator('.comp-name, .companyInfo a, .company-name').first
                        if company_elem.count() == 0:
                            continue
                        
                        company_name = self.clean_text(company_elem.text_content())
                        
                        if not company_name or company_name.lower() in seen_companies:
                            continue
                        
                        seen_companies.add(company_name.lower())
                        
                        lead = {
                            'business_name': company_name,
                            'category': '',
                            'phone_numbers': [],
                            'emails': [],
                            'website': '',
                            'address': '',
                            'industry': '',
                            'lead_type': 'B2B',
                            'tags': ['job_portal', 'naukri', 'hiring']
                        }
                        
                        # Location
                        loc_elem = job.locator('.locWdth, .location, .job-location').first
                        if loc_elem.count() > 0:
                            lead['address'] = self.clean_text(loc_elem.text_content())
                            lead['city'] = lead['address'].split(',')[0].strip()
                        
                        # Rating
                        rating_elem = job.locator('.rating, .ambitionBox-rating').first
                        if rating_elem.count() > 0:
                            text = rating_elem.text_content()
                            match = re.search(r'(\d+\.?\d*)', text)
                            if match:
                                lead['rating'] = float(match.group(1))
                        
                        # Job title (for context)
                        title_elem = job.locator('.title, .jobTitle, a.title').first
                        if title_elem.count() > 0:
                            lead['notes'] = f"Hiring: {self.clean_text(title_elem.text_content())}"
                        
                        leads.append(lead)
                        collected += 1
                        
                    except:
                        continue
                
                if collected >= max_results:
                    break
                
                # Scroll
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)
                
        except Exception as e:
            print(f"[Naukri] Error: {e}")
        
        return leads
    
    def _scrape_indeed(self, query: str, location: str, max_results: int,
                       rate_limiter, stop_check, headless: bool) -> List[Dict]:
        leads = []
        seen_companies = set()
        
        try:
            page = self._init_browser(headless)
            
            # Build Indeed search URL
            search_url = f"https://www.indeed.co.in/jobs?q={query.replace(' ', '+')}"
            if location:
                search_url += f"&l={location.replace(' ', '+')}"
            
            page.goto(search_url, wait_until='domcontentloaded')
            
            if rate_limiter:
                rate_limiter.wait(self.PLATFORM_NAME)
            
            time.sleep(3)
            
            collected = 0
            
            # Job cards
            jobs = page.locator('.job_seen_beacon, .jobsearch-ResultsList > li').all()
            
            for job in jobs:
                if stop_check and stop_check():
                    break
                
                if collected >= max_results:
                    break
                
                try:
                    # Company name
                    company_elem = job.locator('.companyName, span[data-testid="company-name"]').first
                    if company_elem.count() == 0:
                        continue
                    
                    company_name = self.clean_text(company_elem.text_content())
                    
                    if not company_name or company_name.lower() in seen_companies:
                        continue
                    
                    seen_companies.add(company_name.lower())
                    
                    lead = {
                        'business_name': company_name,
                        'category': '',
                        'phone_numbers': [],
                        'emails': [],
                        'website': '',
                        'address': '',
                        'lead_type': 'B2B',
                        'tags': ['job_portal', 'indeed', 'hiring']
                    }
                    
                    # Location
                    loc_elem = job.locator('.companyLocation, [data-testid="text-location"]').first
                    if loc_elem.count() > 0:
                        lead['address'] = self.clean_text(loc_elem.text_content())
                    
                    # Job title
                    title_elem = job.locator('.jobTitle, h2 a').first
                    if title_elem.count() > 0:
                        lead['notes'] = f"Hiring: {self.clean_text(title_elem.text_content())}"
                    
                    leads.append(lead)
                    collected += 1
                    
                except:
                    continue
                    
        except Exception as e:
            print(f"[Indeed] Error: {e}")
        
        return leads
    
    def close(self):
        super().close()
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None
