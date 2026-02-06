"""
Lead Scraper Pro - Plan Manager Module
Manages license state, usage tracking, and limit enforcement.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from storage.database import get_database
from license.license_validator import LicenseValidator


class PlanManager:
    """Manages license plans and enforces usage limits."""
    
    def __init__(self):
        """Initialize plan manager."""
        self.db = get_database()
        self.validator = LicenseValidator()
        self._current_license = None
        self._load_license_state()
    
    def _load_license_state(self):
        """Load license state from database."""
        state = self.db.get_license_state()
        if state:
            self._current_license = state
            self._check_reset_limits()
        else:
            # Default to trial
            self._current_license = self.validator.get_trial_license()
            self._current_license['leads_used_today'] = 0
            self._current_license['leads_used_month'] = 0
            self._current_license['last_reset_date'] = datetime.now().strftime('%Y-%m-%d')
            self._current_license['month_reset_date'] = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            self.db.save_license_state(self._current_license)
    
    def _check_reset_limits(self):
        """Check and reset daily/monthly limits if needed."""
        today = datetime.now().strftime('%Y-%m-%d')
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        needs_save = False
        
        # Reset daily limit
        if self._current_license.get('last_reset_date') != today:
            self._current_license['leads_used_today'] = 0
            self._current_license['last_reset_date'] = today
            needs_save = True
        
        # Reset monthly limit
        if self._current_license.get('month_reset_date') != month_start:
            self._current_license['leads_used_month'] = 0
            self._current_license['month_reset_date'] = month_start
            needs_save = True
        
        if needs_save:
            self.db.save_license_state(self._current_license)
    
    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """
        Activate a new license key.
        
        Args:
            license_key: The license key to activate
            
        Returns:
            Tuple of (success, message)
        """
        # Validate the license
        is_valid, result = self.validator.validate(license_key)
        
        if not is_valid:
            return False, result.get('error', 'Invalid license key')
        
        # Update license state
        self._current_license = result
        self._current_license['leads_used_today'] = 0
        self._current_license['leads_used_month'] = 0
        self._current_license['last_reset_date'] = datetime.now().strftime('%Y-%m-%d')
        self._current_license['month_reset_date'] = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        self._current_license['is_active'] = True
        
        # Save to database
        self.db.save_license_state(self._current_license)
        
        plan_name = self._current_license.get('plan_name', 'Unknown')
        return True, f"License activated successfully! Plan: {plan_name}"
    
    def get_current_plan(self) -> Dict:
        """Get current license/plan information."""
        self._check_reset_limits()
        
        # Recalculate usage from database
        self._current_license['leads_used_today'] = self.db.get_today_usage()
        self._current_license['leads_used_month'] = self.db.get_month_usage()
        
        return self._current_license.copy()
    
    def can_scrape(self, platform: str = None) -> Tuple[bool, str]:
        """
        Check if scraping is allowed under current license.
        
        Args:
            platform: Platform to check (optional)
            
        Returns:
            Tuple of (allowed, reason)
        """
        self._check_reset_limits()
        
        # Recalculate actual usage
        current_today = self.db.get_today_usage()
        current_month = self.db.get_month_usage()
        
        # Check if license is active
        if not self._current_license.get('is_active', False):
            return False, "License is not active. Please activate a valid license."
        
        # Check expiry
        expiry_date = self._current_license.get('expiry_date')
        if expiry_date:
            try:
                expiry = datetime.fromisoformat(expiry_date)
                if datetime.now() > expiry:
                    return False, "License has expired. Please renew your license."
            except ValueError:
                pass
        
        # Check daily limit
        daily_limit = self._current_license.get('daily_limit', 10)
        if current_today >= daily_limit:
            return False, f"Daily limit reached ({current_today}/{daily_limit} leads). Limit resets tomorrow."
        
        # Check monthly limit
        monthly_limit = self._current_license.get('monthly_limit', 50)
        if current_month >= monthly_limit:
            return False, f"Monthly limit reached ({current_month}/{monthly_limit} leads). Limit resets next month."
        
        # Check platform access
        if platform:
            allowed_platforms = self._current_license.get('platforms_allowed', ['google_search'])
            if platform not in allowed_platforms:
                return False, f"Platform '{platform}' is not available in your current plan. Upgrade to access more platforms."
        
        return True, "OK"
    
    def record_lead_scraped(self, count: int = 1):
        """Record that leads were scraped (for limit tracking)."""
        self._current_license['leads_used_today'] = self._current_license.get('leads_used_today', 0) + count
        self._current_license['leads_used_month'] = self._current_license.get('leads_used_month', 0) + count
        self.db.save_license_state(self._current_license)
    
    def can_export(self, format_type: str = 'csv') -> Tuple[bool, str]:
        """
        Check if export is allowed under current license.
        
        Args:
            format_type: Export format (csv, excel, json)
            
        Returns:
            Tuple of (allowed, reason)
        """
        if not self._current_license.get('is_active', False):
            return False, "License is not active."
        
        export_allowed = self._current_license.get('export_allowed', False)
        if not export_allowed:
            return False, "Export is not available in your current plan. Upgrade to enable exports."
        
        # Check for bulk export permission
        bulk_export = self._current_license.get('bulk_export', False)
        
        return True, "OK"
    
    def get_usage_summary(self) -> Dict:
        """Get usage summary for display."""
        plan = self.get_current_plan()
        
        daily_limit = plan.get('daily_limit', 10)
        monthly_limit = plan.get('monthly_limit', 50)
        leads_today = self.db.get_today_usage()
        leads_month = self.db.get_month_usage()
        
        return {
            'plan_name': plan.get('plan_name', 'Trial'),
            'is_trial': plan.get('is_trial', True),
            'daily_usage': f"{leads_today}/{daily_limit}",
            'daily_remaining': max(0, daily_limit - leads_today),
            'monthly_usage': f"{leads_month}/{monthly_limit}",
            'monthly_remaining': max(0, monthly_limit - leads_month),
            'export_allowed': plan.get('export_allowed', False),
            'platforms': plan.get('platforms_allowed', []),
            'expiry_date': plan.get('expiry_date', 'N/A'),
            'total_leads_in_db': self.db.get_lead_count()
        }
    
    def show_disclaimer(self) -> str:
        """Get the legal disclaimer text."""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                         LEAD SCRAPER PRO - DISCLAIMER                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software collects ONLY publicly available business information.       ║
║                                                                              ║
║  By using this software, you agree that:                                     ║
║                                                                              ║
║  1. You will use the collected data in compliance with all applicable       ║
║     laws and regulations, including but not limited to GDPR, CCPA,          ║
║     and local data protection laws.                                         ║
║                                                                              ║
║  2. You will NOT use this software to:                                      ║
║     - Bypass any login or authentication systems                            ║
║     - Circumvent CAPTCHAs or anti-bot measures                              ║
║     - Access non-public or restricted data                                  ║
║     - Engage in any illegal or unethical activities                         ║
║                                                                              ║
║  3. You are solely responsible for how you use the collected data.          ║
║                                                                              ║
║  4. The developers are not responsible for any misuse of this software.     ║
║                                                                              ║
║  5. Scraping may violate the Terms of Service of some websites.             ║
║     Use at your own risk.                                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# Singleton instance
_plan_manager_instance = None

def get_plan_manager() -> PlanManager:
    """Get or create singleton plan manager instance."""
    global _plan_manager_instance
    if _plan_manager_instance is None:
        _plan_manager_instance = PlanManager()
    return _plan_manager_instance
