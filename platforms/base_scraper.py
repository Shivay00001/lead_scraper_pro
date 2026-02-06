"""
Lead Scraper Pro - Base Scraper Class
Abstract base class for all platform scrapers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable
import re


class BaseScraper(ABC):
    """Abstract base class for all platform scrapers."""
    
    PLATFORM_NAME = "base"
    
    def __init__(self):
        """Initialize base scraper."""
        self._browser = None
        self._page = None
    
    @abstractmethod
    def scrape(self,
               query: str,
               location: str = None,
               max_results: int = 50,
               rate_limiter = None,
               stop_check: Callable = None,
               **kwargs) -> List[Dict]:
        """
        Execute scraping operation.
        
        Args:
            query: Search query
            location: Location filter
            max_results: Maximum results to return
            rate_limiter: RateLimiter instance
            stop_check: Callable that returns True to stop
            **kwargs: Platform-specific options
            
        Returns:
            List of lead dictionaries
        """
        pass
    
    def close(self):
        """Clean up browser resources."""
        if self._page:
            try:
                self._page.close()
            except:
                pass
        if self._browser:
            try:
                self._browser.close()
            except:
                pass
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text."""
        if not text:
            return []
        
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        
        # Filter out common false positives
        filtered = []
        for email in emails:
            email_lower = email.lower()
            if not any(x in email_lower for x in ['example.com', 'test.com', 'domain.com', '.png', '.jpg', '.gif']):
                filtered.append(email)
        
        return list(set(filtered))
    
    @staticmethod
    def extract_phones(text: str) -> List[str]:
        """Extract phone numbers from text."""
        if not text:
            return []
        
        # Indian phone patterns
        patterns = [
            r'\+91[-\s]?\d{10}',
            r'\+91[-\s]?\d{5}[-\s]?\d{5}',
            r'0\d{2,4}[-\s]?\d{6,8}',
            r'\d{10}',
            r'\d{5}[-\s]\d{5}',
        ]
        
        phones = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phones.extend(matches)
        
        # Clean and deduplicate
        cleaned = []
        seen = set()
        for phone in phones:
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 10 and digits[-10:] not in seen:
                seen.add(digits[-10:])
                cleaned.append(phone.strip())
        
        return cleaned
    
    @staticmethod
    def guess_emails(domain: str, business_name: str = None) -> List[Dict]:
        """
        Guess common business email addresses.
        
        Returns list of dicts with 'email' and 'type' (guessed/verified)
        """
        if not domain:
            return []
        
        # Clean domain
        domain = domain.lower().replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]
        
        guessed = []
        common_prefixes = ['info', 'contact', 'sales', 'hello', 'support', 'enquiry', 'inquiry']
        
        for prefix in common_prefixes:
            guessed.append({
                'email': f"{prefix}@{domain}",
                'type': 'guessed'
            })
        
        return guessed
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common unicode issues
        text = text.replace('\u00a0', ' ')
        text = text.replace('\u200b', '')
        
        return text.strip()
    
    @staticmethod
    def extract_pincode(address: str) -> str:
        """Extract Indian pincode from address."""
        if not address:
            return ""
        
        # Indian pincode pattern (6 digits)
        match = re.search(r'\b[1-9]\d{5}\b', address)
        if match:
            return match.group()
        
        return ""
