"""
Lead Scraper Pro - Lead Deduplicator
Handles deduplication of leads using multiple identifiers.
"""

import re
import hashlib
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import urlparse


class Deduplicator:
    """Deduplicates leads based on phone, email, and domain."""
    
    def __init__(self):
        """Initialize deduplicator with empty seen sets."""
        self._seen_phones: Set[str] = set()
        self._seen_emails: Set[str] = set()
        self._seen_domains: Set[str] = set()
        self._seen_hashes: Set[str] = set()
    
    def normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for comparison.
        
        Args:
            phone: Raw phone number string
            
        Returns:
            Normalized phone number (last 10 digits)
        """
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(phone))
        
        # Take last 10 digits (for Indian numbers)
        if len(digits) >= 10:
            return digits[-10:]
        
        return digits if len(digits) >= 7 else ""
    
    def normalize_email(self, email: str) -> str:
        """
        Normalize email for comparison.
        
        Args:
            email: Raw email string
            
        Returns:
            Normalized email (lowercase, trimmed)
        """
        if not email:
            return ""
        
        email = email.lower().strip()
        
        # Basic validation
        if '@' not in email or '.' not in email.split('@')[-1]:
            return ""
        
        return email
    
    def extract_domain(self, url: str) -> str:
        """
        Extract normalized domain from URL.
        
        Args:
            url: Website URL
            
        Returns:
            Normalized domain
        """
        if not url:
            return ""
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain
        except Exception:
            return ""
    
    def generate_hash(self, lead: Dict) -> str:
        """
        Generate unique hash for a lead.
        
        Args:
            lead: Lead dictionary
            
        Returns:
            Hash string
        """
        components = []
        
        # Add normalized phones
        phones = lead.get('phone_numbers', [])
        if isinstance(phones, str):
            phones = [phones]
        for phone in phones:
            normalized = self.normalize_phone(phone)
            if normalized:
                components.append(f"p:{normalized}")
        
        # Add normalized emails
        emails = lead.get('emails', [])
        if isinstance(emails, str):
            emails = [emails]
        for email in emails:
            normalized = self.normalize_email(email)
            if normalized:
                components.append(f"e:{normalized}")
        
        # Add domain
        website = lead.get('website', '')
        domain = self.extract_domain(website)
        if domain:
            components.append(f"d:{domain}")
        
        # If no strong identifiers, use name + location
        if not components:
            name = (lead.get('business_name') or '').lower().strip()
            city = (lead.get('city') or '').lower().strip()
            address = (lead.get('address') or '').lower().strip()[:30]
            
            if name:
                components.append(f"n:{name}")
            if city:
                components.append(f"c:{city}")
            if address:
                components.append(f"a:{address}")
        
        if not components:
            return ""
        
        # Sort and hash
        hash_input = '|'.join(sorted(components))
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]
    
    def is_duplicate(self, lead: Dict) -> Tuple[bool, str]:
        """
        Check if a lead is a duplicate.
        
        Args:
            lead: Lead dictionary
            
        Returns:
            Tuple of (is_duplicate, reason)
        """
        # Check phones
        phones = lead.get('phone_numbers', [])
        if isinstance(phones, str):
            phones = [phones]
        for phone in phones:
            normalized = self.normalize_phone(phone)
            if normalized and normalized in self._seen_phones:
                return True, f"Duplicate phone: {phone}"
        
        # Check emails
        emails = lead.get('emails', [])
        if isinstance(emails, str):
            emails = [emails]
        for email in emails:
            normalized = self.normalize_email(email)
            if normalized and normalized in self._seen_emails:
                return True, f"Duplicate email: {email}"
        
        # Check domain
        website = lead.get('website', '')
        domain = self.extract_domain(website)
        if domain and domain in self._seen_domains:
            return True, f"Duplicate domain: {domain}"
        
        # Check hash
        lead_hash = self.generate_hash(lead)
        if lead_hash and lead_hash in self._seen_hashes:
            return True, "Duplicate hash"
        
        return False, ""
    
    def add_lead(self, lead: Dict) -> bool:
        """
        Add a lead to the seen sets.
        
        Args:
            lead: Lead dictionary
            
        Returns:
            True if added, False if duplicate
        """
        is_dup, reason = self.is_duplicate(lead)
        if is_dup:
            return False
        
        # Add phones
        phones = lead.get('phone_numbers', [])
        if isinstance(phones, str):
            phones = [phones]
        for phone in phones:
            normalized = self.normalize_phone(phone)
            if normalized:
                self._seen_phones.add(normalized)
        
        # Add emails
        emails = lead.get('emails', [])
        if isinstance(emails, str):
            emails = [emails]
        for email in emails:
            normalized = self.normalize_email(email)
            if normalized:
                self._seen_emails.add(normalized)
        
        # Add domain
        website = lead.get('website', '')
        domain = self.extract_domain(website)
        if domain:
            self._seen_domains.add(domain)
        
        # Add hash
        lead_hash = self.generate_hash(lead)
        if lead_hash:
            self._seen_hashes.add(lead_hash)
        
        return True
    
    def deduplicate_list(self, leads: List[Dict]) -> List[Dict]:
        """
        Deduplicate a list of leads.
        
        Args:
            leads: List of lead dictionaries
            
        Returns:
            Deduplicated list
        """
        unique_leads = []
        
        for lead in leads:
            if self.add_lead(lead):
                unique_leads.append(lead)
        
        return unique_leads
    
    def get_stats(self) -> Dict:
        """Get deduplication statistics."""
        return {
            'unique_phones': len(self._seen_phones),
            'unique_emails': len(self._seen_emails),
            'unique_domains': len(self._seen_domains),
            'total_hashes': len(self._seen_hashes)
        }
    
    def clear(self):
        """Clear all seen sets."""
        self._seen_phones.clear()
        self._seen_emails.clear()
        self._seen_domains.clear()
        self._seen_hashes.clear()
    
    def load_from_database(self, db):
        """
        Load existing leads from database to prevent duplicates.
        
        Args:
            db: DatabaseManager instance
        """
        leads = db.get_leads(limit=10000)
        for lead in leads:
            self.add_lead(lead)


# Singleton instance
_deduplicator_instance = None

def get_deduplicator() -> Deduplicator:
    """Get or create singleton deduplicator instance."""
    global _deduplicator_instance
    if _deduplicator_instance is None:
        _deduplicator_instance = Deduplicator()
    return _deduplicator_instance
