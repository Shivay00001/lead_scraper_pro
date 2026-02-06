"""
Lead Scraper Pro - Scraper Engine
Main orchestrator for all scraping operations.
"""

import importlib
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from storage.database import get_database, DatabaseManager
from license.plan_manager import get_plan_manager, PlanManager
from core.rate_limiter import get_rate_limiter, RateLimiter
from core.deduplicator import get_deduplicator, Deduplicator


class ScraperEngine:
    """Main scraper orchestrator that coordinates all scraping operations."""
    
    # Platform module mapping - 14 platforms
    PLATFORM_MODULES = {
        # PRIMARY - HIGH VALUE
        'google_maps': 'platforms.google_maps',
        'google_search': 'platforms.google_search',
        'justdial': 'platforms.justdial',
        'sulekha': 'platforms.sulekha',
        # SECONDARY
        'indiamart': 'platforms.indiamart',
        'bing_maps': 'platforms.bing_maps',
        'apple_maps': 'platforms.apple_maps',
        'yelp': 'platforms.yelp',
        'yellow_pages': 'platforms.yellow_pages',
        # SIGNAL-BASED
        'youtube': 'platforms.youtube',
        'instagram': 'platforms.instagram',
        'twitter': 'platforms.twitter',
        'facebook': 'platforms.facebook',
        # INDIRECT B2B
        'job_portals': 'platforms.job_portals',
    }
    
    def __init__(self):
        """Initialize scraper engine."""
        self.db: DatabaseManager = get_database()
        self.plan_manager: PlanManager = get_plan_manager()
        self.rate_limiter: RateLimiter = get_rate_limiter()
        self.deduplicator: Deduplicator = get_deduplicator()
        
        # Load existing leads into deduplicator
        self.deduplicator.load_from_database(self.db)
        
        # Loaded scraper instances
        self._scrapers: Dict[str, Any] = {}
        
        # Callbacks for progress reporting
        self._on_lead_found: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        # State
        self._is_running = False
        self._should_stop = False
    
    def set_callbacks(self,
                      on_lead_found: Callable = None,
                      on_progress: Callable = None,
                      on_error: Callable = None):
        """Set callback functions for scraping events."""
        self._on_lead_found = on_lead_found
        self._on_progress = on_progress
        self._on_error = on_error
    
    def _get_scraper(self, platform: str):
        """
        Get or load a platform scraper.
        
        Args:
            platform: Platform identifier
            
        Returns:
            Scraper instance
        """
        if platform in self._scrapers:
            return self._scrapers[platform]
        
        module_name = self.PLATFORM_MODULES.get(platform)
        if not module_name:
            raise ValueError(f"Unknown platform: {platform}")
        
        try:
            module = importlib.import_module(module_name)
            scraper_class = getattr(module, 'Scraper', None)
            if scraper_class:
                scraper = scraper_class()
                self._scrapers[platform] = scraper
                return scraper
        except ImportError as e:
            raise ImportError(f"Failed to load scraper for {platform}: {e}")
        
        return None
    
    def _check_limits(self, platform: str) -> tuple[bool, str]:
        """Check if scraping is allowed."""
        return self.plan_manager.can_scrape(platform)
    
    def scrape(self,
               platform: str,
               query: str,
               location: str = None,
               max_results: int = 50,
               **kwargs) -> Dict:
        """
        Execute a scraping operation.
        
        Args:
            platform: Platform to scrape
            query: Search query (category, keyword, etc.)
            location: Location filter
            max_results: Maximum number of results to return
            **kwargs: Additional platform-specific options
            
        Returns:
            Dict with results and statistics
        """
        # Check license and limits
        can_scrape, reason = self._check_limits(platform)
        if not can_scrape:
            return {
                'success': False,
                'error': reason,
                'leads': [],
                'stats': {'total': 0, 'new': 0, 'duplicates': 0}
            }
        
        # Check daily/monthly remaining
        usage = self.plan_manager.get_usage_summary()
        remaining = min(usage['daily_remaining'], usage['monthly_remaining'])
        
        if remaining <= 0:
            return {
                'success': False,
                'error': 'Lead limit reached. Please upgrade your plan.',
                'leads': [],
                'stats': {'total': 0, 'new': 0, 'duplicates': 0}
            }
        
        # Cap max_results to remaining quota
        max_results = min(max_results, remaining)
        
        self._is_running = True
        self._should_stop = False
        
        try:
            # Get scraper
            scraper = self._get_scraper(platform)
            if not scraper:
                return {
                    'success': False,
                    'error': f'Scraper not available for platform: {platform}',
                    'leads': [],
                    'stats': {'total': 0, 'new': 0, 'duplicates': 0}
                }
            
            # Report progress
            if self._on_progress:
                self._on_progress(f"Starting scrape on {platform}...")
            
            # Execute scrape
            raw_leads = scraper.scrape(
                query=query,
                location=location,
                max_results=max_results,
                rate_limiter=self.rate_limiter,
                stop_check=lambda: self._should_stop,
                **kwargs
            )
            
            # Process leads
            stats = {'total': len(raw_leads), 'new': 0, 'duplicates': 0, 'errors': 0}
            saved_leads = []
            
            for lead in raw_leads:
                if self._should_stop:
                    break
                
                # Check if duplicate
                is_dup, dup_reason = self.deduplicator.is_duplicate(lead)
                if is_dup:
                    stats['duplicates'] += 1
                    continue
                
                # Add platform source
                lead['platform_source'] = platform
                lead['scraped_at'] = datetime.now().isoformat()
                
                # Save to database
                success, message = self.db.insert_lead(lead)
                
                if success:
                    self.deduplicator.add_lead(lead)
                    stats['new'] += 1
                    saved_leads.append(lead)
                    
                    if self._on_lead_found:
                        self._on_lead_found(lead)
                else:
                    if 'Duplicate' in message:
                        stats['duplicates'] += 1
                    else:
                        stats['errors'] += 1
                        if self._on_error:
                            self._on_error(message)
            
            return {
                'success': True,
                'leads': saved_leads,
                'stats': stats
            }
            
        except Exception as e:
            if self._on_error:
                self._on_error(str(e))
            return {
                'success': False,
                'error': str(e),
                'leads': [],
                'stats': {'total': 0, 'new': 0, 'duplicates': 0, 'errors': 1}
            }
        finally:
            self._is_running = False
    
    def stop(self):
        """Stop the current scraping operation."""
        self._should_stop = True
    
    def is_running(self) -> bool:
        """Check if scraping is in progress."""
        return self._is_running
    
    def get_available_platforms(self) -> List[str]:
        """Get list of platforms available in current plan."""
        plan = self.plan_manager.get_current_plan()
        return plan.get('platforms_allowed', ['google_search'])
    
    def get_all_platforms(self) -> List[str]:
        """Get list of all supported platforms."""
        return list(self.PLATFORM_MODULES.keys())
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics."""
        return self.plan_manager.get_usage_summary()
    
    def close(self):
        """Clean up resources."""
        for scraper in self._scrapers.values():
            if hasattr(scraper, 'close'):
                scraper.close()
        self._scrapers.clear()


# Singleton instance
_engine_instance = None

def get_engine() -> ScraperEngine:
    """Get or create singleton scraper engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ScraperEngine()
    return _engine_instance
