"""
Lead Scraper Pro - CSV Exporter
Exports leads to CSV with formatting and permission checks.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

from storage.database import get_database, DatabaseManager
from license.plan_manager import get_plan_manager, PlanManager


class CSVExporter:
    """Exports leads to CSV format with license checks."""
    
    # Default export columns
    DEFAULT_COLUMNS = [
        'id',
        'business_name',
        'category',
        'industry',
        'phone_numbers',
        'emails',
        'website',
        'address',
        'city',
        'state',
        'country',
        'pincode',
        'platform_source',
        'lead_type',
        'rating',
        'reviews_count',
        'notes',
        'scraped_at'
    ]
    
    def __init__(self):
        """Initialize CSV exporter."""
        self.db: DatabaseManager = get_database()
        self.plan_manager: PlanManager = get_plan_manager()
    
    def export(self,
               output_path: str,
               platform: str = None,
               lead_type: str = None,
               columns: List[str] = None,
               max_rows: int = None) -> Dict:
        """
        Export leads to CSV file.
        
        Args:
            output_path: Path to output CSV file
            platform: Filter by platform (optional)
            lead_type: Filter by lead type (optional)
            columns: Columns to include (default: all)
            max_rows: Maximum rows to export
            
        Returns:
            Dict with export status and stats
        """
        # Check export permission
        can_export, reason = self.plan_manager.can_export('csv')
        if not can_export:
            return {
                'success': False,
                'error': reason,
                'exported': 0
            }
        
        # Use default columns if not specified
        if not columns:
            columns = self.DEFAULT_COLUMNS
        
        # Determine limit
        plan = self.plan_manager.get_current_plan()
        if plan.get('is_trial'):
            return {
                'success': False,
                'error': 'CSV export is not available in Trial plan. Please upgrade.',
                'exported': 0
            }
        
        # Fetch leads
        if max_rows:
            limit = max_rows
        else:
            # For non-bulk plans, limit export
            if not plan.get('bulk_export'):
                limit = 100
            else:
                limit = 10000
        
        leads = self.db.get_leads(platform=platform, lead_type=lead_type, limit=limit)
        
        if not leads:
            return {
                'success': False,
                'error': 'No leads found matching the criteria.',
                'exported': 0
            }
        
        try:
            # Prepare data for export
            export_data = []
            for lead in leads:
                row = {}
                for col in columns:
                    value = lead.get(col, '')
                    
                    # Format lists as comma-separated
                    if isinstance(value, list):
                        value = '; '.join(str(v) for v in value if v)
                    elif isinstance(value, dict):
                        value = str(value)
                    
                    row[col] = value
                
                export_data.append(row)
            
            # Create DataFrame and export
            df = pd.DataFrame(export_data)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Export to CSV
            df.to_csv(output_path, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
            
            return {
                'success': True,
                'exported': len(export_data),
                'path': output_path,
                'columns': columns
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'exported': 0
            }
    
    def export_excel(self,
                     output_path: str,
                     platform: str = None,
                     lead_type: str = None,
                     columns: List[str] = None,
                     max_rows: int = None) -> Dict:
        """
        Export leads to Excel file (.xlsx).
        
        Same parameters as export().
        """
        # Check export permission
        can_export, reason = self.plan_manager.can_export('excel')
        if not can_export:
            return {
                'success': False,
                'error': reason,
                'exported': 0
            }
        
        plan = self.plan_manager.get_current_plan()
        if plan.get('is_trial'):
            return {
                'success': False,
                'error': 'Excel export is not available in Trial plan. Please upgrade.',
                'exported': 0
            }
        
        if not columns:
            columns = self.DEFAULT_COLUMNS
        
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
                'exported': 0
            }
        
        try:
            export_data = []
            for lead in leads:
                row = {}
                for col in columns:
                    value = lead.get(col, '')
                    if isinstance(value, list):
                        value = '; '.join(str(v) for v in value if v)
                    elif isinstance(value, dict):
                        value = str(value)
                    row[col] = value
                export_data.append(row)
            
            df = pd.DataFrame(export_data)
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            df.to_excel(output_path, index=False, engine='openpyxl')
            
            return {
                'success': True,
                'exported': len(export_data),
                'path': output_path,
                'columns': columns
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'exported': 0
            }


def get_csv_exporter() -> CSVExporter:
    """Get CSV exporter instance."""
    return CSVExporter()
