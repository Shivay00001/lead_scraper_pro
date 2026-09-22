"""Smoke test for lead_scraper_pro: deduplicator and rate limiter basics."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.deduplicator import Deduplicator
from core.rate_limiter import RateLimiter


def main():
    d = Deduplicator()
    assert d.normalize_phone("+91 98765 43210") == "9876543210"
    assert d.normalize_email(" Test@Example.com ") == "test@example.com"

    lead = {"phone_numbers": "9876543210", "emails": "a@b.com", "name": "Acme"}
    assert d.add_lead(lead) is True
    dup, _reason = d.is_duplicate({"phone_numbers": "9876543210", "emails": "other@x.com"})
    assert dup is True
    assert d.is_duplicate({"phone_numbers": "1111111111", "emails": "new@x.com"})[0] is False

    rl = RateLimiter()
    assert "google_maps" in RateLimiter.PLATFORM_DELAYS
    assert len(RateLimiter.USER_AGENTS) > 0

    print("smoke OK: Deduplicator normalize/dedupe, RateLimiter config")


if __name__ == "__main__":
    main()
