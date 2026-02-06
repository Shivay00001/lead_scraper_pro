"""
Lead Scraper Pro - JSON Exporter
Exports leads to JSON format with formatting options.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

from storage.database import get_database, DatabaseManager
from license.plan_manager import get_plan_manager, PlanManager


class JSONExporter:
    """Exports leads to JSON format with license checks."""
    
    def __init__(self):
        """Initialize JSON exporter."""
        self.db: DatabaseManager = get_database()
        self.plan_manager: PlanManager = get_plan_manager()
    
    def export(self,
               output_path: str = None,
               platform: str = None,
               lead_type: str = None,
               max_rows: int = None,
               pretty: bool = True) -> Dict:
        """
        Export leads to JSON file or return JSON string.
        
        Args:
            output_path: Path to output JSON file (None for dict return)
            platform: Filter by platform (optional)
            lead_type: Filter by lead type (optional)
            max_rows: Maximum rows to export
            pretty: Pretty print JSON (default: True)
            
        Returns:
            Dict with export status and data
        """
        # Check export permission
        can_export, reason = self.plan_manager.can_export('json')
        if not can_export:
            return {
                'success': False,
                'error': reason,
                'exported': 0
            }
        
        plan = self.plan_manager.get_current_plan()
        
        # Trial has limited JSON export (in-app only, no file)
        if plan.get('is_trial') and output_path:
            return {
                'success': False,
                'error': 'File export is not available in Trial plan. Data shown in app only.',
                'exported': 0
            }
        
        # Determine limit
        if max_rows:
            limit = max_rows
        else:
            if not plan.get('bulk_export'):
                limit = 100
            else:
                limit = 10000
        
        leads = self.db.get_leads(platform=platform, lead_type=lead_type, limit=limit)
        
        if not leads:
            return {
                'success': False,
                'error': 'No leads found matching the criteria.',
                'exported': 0,
                'data': []
            }
        
        try:
            # Clean leads for export
            export_data = []
            for lead in leads:
                clean_lead = {
                    'id': lead.get('id'),
                    'business_name': lead.get('business_name'),
                    'category': lead.get('category'),
                    'industry': lead.get('industry'),
                    'phone_numbers': lead.get('phone_numbers', []),
                    'emails': lead.get('emails', []),
                    'website': lead.get('website'),
                    'social_links': lead.get('social_links', {}),
                    'address': lead.get('address'),
                    'city': lead.get('city'),
                    'state': lead.get('state'),
                    'country': lead.get('country'),
                    'pincode': lead.get('pincode'),
                    'platform_source': lead.get('platform_source'),
                    'lead_type': lead.get('lead_type'),
                    'rating': lead.get('rating'),
                    'reviews_count': lead.get('reviews_count'),
                    'is_verified': lead.get('is_verified', False),
                    'notes': lead.get('notes'),
                    'tags': lead.get('tags', []),
                    'scraped_at': lead.get('scraped_at')
                }
                export_data.append(clean_lead)
            
            result = {
                'success': True,
                'exported': len(export_data),
                'data': export_data,
                'metadata': {
                    'exported_at': datetime.now().isoformat(),
                    'platform_filter': platform,
                    'lead_type_filter': lead_type,
                    'total_count': len(export_data)
                }
            }
            
            # Write to file if path specified
            if output_path:
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    if pretty:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    else:
                        json.dump(result, f, ensure_ascii=False)
                
                result['path'] = output_path
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'exported': 0
            }
    
    def export_as_string(self,
                         platform: str = None,
                         lead_type: str = None,
                         max_rows: int = 50,
                         pretty: bool = True) -> str:
        """
        Export leads as JSON string (for in-app display).
        
        Returns:
            JSON string
        """
        result = self.export(
            output_path=None,
            platform=platform,
            lead_type=lead_type,
            max_rows=max_rows,
            pretty=pretty
        )
        
        if result.get('success'):
            if pretty:
                return json.dumps(result['data'], indent=2, ensure_ascii=False)
            else:
                return json.dumps(result['data'], ensure_ascii=False)
        else:
            return json.dumps({'error': result.get('error')})


def get_json_exporter() -> JSONExporter:
    """Get JSON exporter instance."""
    return JSONExporter()
