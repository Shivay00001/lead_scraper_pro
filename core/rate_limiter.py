"""
Lead Scraper Pro - Rate Limiter
Implements randomized delays and request throttling.
"""

import random
import time
from typing import Dict, Optional
from datetime import datetime, timedelta


class RateLimiter:
    """Rate limiter with randomized delays and per-domain tracking."""
    
    # Default delay ranges per platform (in seconds)
    PLATFORM_DELAYS = {
        'google_maps': (2.0, 5.0),
        'google_search': (3.0, 7.0),
        'justdial': (2.0, 4.0),
        'sulekha': (2.0, 4.0),
        'indiamart': (3.0, 6.0),
        'bing_maps': (1.5, 3.0),
        'yelp': (2.0, 4.0),
        'yellow_pages': (1.5, 3.0),
        'youtube': (2.0, 5.0),
        'instagram': (3.0, 6.0),
        'twitter': (2.0, 5.0),
        'job_portals': (2.0, 4.0),
        'default': (2.0, 4.0)
    }
    
    # User agents for rotation
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self):
        """Initialize rate limiter."""
        self._last_request_time: Dict[str, datetime] = {}
        self._request_counts: Dict[str, int] = {}
        self._user_agent_index = 0
    
    def wait(self, platform: str = 'default', multiplier: float = 1.0):
        """
        Wait with randomized delay before next request.
        
        Args:
            platform: Platform identifier for delay lookup
            multiplier: Multiply delay by this factor (for backing off)
        """
        delay_range = self.PLATFORM_DELAYS.get(platform, self.PLATFORM_DELAYS['default'])
        min_delay, max_delay = delay_range
        
        # Apply multiplier
        min_delay *= multiplier
        max_delay *= multiplier
        
        # Add jitter
        delay = random.uniform(min_delay, max_delay)
        
        # Add extra delay if requests are happening too fast
        now = datetime.now()
        if platform in self._last_request_time:
            elapsed = (now - self._last_request_time[platform]).total_seconds()
            if elapsed < min_delay:
                delay += (min_delay - elapsed)
        
        time.sleep(delay)
        self._last_request_time[platform] = datetime.now()
        self._request_counts[platform] = self._request_counts.get(platform, 0) + 1
    
    def get_user_agent(self) -> str:
        """Get a rotating user agent."""
        ua = self.USER_AGENTS[self._user_agent_index % len(self.USER_AGENTS)]
        self._user_agent_index += 1
        return ua
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(self.USER_AGENTS)
    
    def should_pause(self, platform: str, max_requests: int = 50) -> bool:
        """
        Check if we should pause scraping to avoid detection.
        
        Args:
            platform: Platform identifier
            max_requests: Max requests before suggesting pause
            
        Returns:
            True if pause is recommended
        """
        count = self._request_counts.get(platform, 0)
        return count >= max_requests
    
    def pause(self, duration: int = None):
        """
        Pause for a longer duration (anti-detection).
        
        Args:
            duration: Pause duration in seconds (random if None)
        """
        if duration is None:
            duration = random.randint(30, 60)
        
        print(f"[RateLimiter] Pausing for {duration} seconds to avoid detection...")
        time.sleep(duration)
    
    def reset_count(self, platform: str = None):
        """Reset request count for a platform or all platforms."""
        if platform:
            self._request_counts[platform] = 0
        else:
            self._request_counts.clear()
    
    def get_request_count(self, platform: str) -> int:
        """Get request count for a platform."""
        return self._request_counts.get(platform, 0)
    
    def human_delay(self):
        """Add a human-like micro-delay (typing, reading, etc.)."""
        time.sleep(random.uniform(0.3, 1.0))
    
    def scroll_delay(self):
        """Delay appropriate for scrolling behavior."""
        time.sleep(random.uniform(0.5, 1.5))


# Singleton instance
_rate_limiter_instance = None

def get_rate_limiter() -> RateLimiter:
    """Get or create singleton rate limiter instance."""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance
