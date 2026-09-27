"""
Lead Scraper Pro - Command Line Interface
Main CLI for the lead scraping application.
"""

import argparse
import sys
import os
import json
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper_engine import get_engine, ScraperEngine
from core import config as app_config
from license.plan_manager import get_plan_manager, PlanManager
from storage.database import get_database, DatabaseManager
from export.csv_exporter import get_csv_exporter
from export.json_exporter import get_json_exporter


class ValidationError(Exception):
    """Raised when user input fails validation. Never carries a stack trace to users."""


def validate_text(value: Optional[str], name: str, min_len: int = 1, max_len: int = 200) -> str:
    """Validate a free-text CLI input (query, location, key, ...)."""
    if value is None:
        raise ValidationError(f"{name} is required.")
    cleaned = str(value).strip()
    if len(cleaned) < min_len:
        raise ValidationError(f"{name} must not be empty.")
    if len(cleaned) > max_len:
        raise ValidationError(f"{name} must be at most {max_len} characters.")
    return cleaned


def validate_int(value: Optional[int], name: str, min_value: int, max_value: int) -> int:
    """Validate an integer CLI input within an inclusive range."""
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer.")
    if not (min_value <= number <= max_value):
        raise ValidationError(f"{name} must be between {min_value} and {max_value}.")
    return number


class LeadScraperCLI:
    """Main CLI application for Lead Scraper Pro."""
    
    APP_NAME = "Lead Scraper Pro"
    VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize CLI."""
        self.engine: ScraperEngine = None
        self.plan_manager: PlanManager = None
        self.db: DatabaseManager = None
        self._initialized = False
        self.json_mode = False

    def emit(self, payload: dict):
        """Print a machine-readable result when --json is used, else nothing."""
        if self.json_mode:
            print(json.dumps(payload))
        return payload

    def fail(self, message: str, code: int = 1):
        """Structured error output. Never leaks stack traces to clients."""
        if self.json_mode:
            print(json.dumps({"ok": False, "error": message}))
        else:
            print(f"[ERROR] {message}")
        raise SystemExit(code)

    def _init_components(self):
        """Lazy initialization of components."""
        if self._initialized:
            return

        try:
            self.db = get_database()
            self.plan_manager = get_plan_manager()
            self.engine = get_engine()
            self._initialized = True
        except ValidationError:
            raise
        except Exception as e:
            # Sanitized: never expose internals/tracebacks to the user.
            self.fail("Failed to initialize. Check LSP_DB_PATH and LSP_ENCRYPTION_KEY.", code=3)
    
    def print_banner(self):
        """Print application banner."""
        print("""
╔═══════════════════════════════════════════════════════════════╗
║                    LEAD SCRAPER PRO v1.0.0                    ║
║              B2B/B2C Lead Extraction System                   ║
╚═══════════════════════════════════════════════════════════════╝
        """)
    
    def print_disclaimer(self):
        """Print legal disclaimer."""
        print(self.plan_manager.show_disclaimer())
        print("\nPress Enter to continue or Ctrl+C to exit...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)
    
    def cmd_health(self, args):
        """Health check: verifies app boots, DB opens, and config resolves."""
        try:
            self._init_components()
            usage = self.plan_manager.get_usage_summary()
            payload = {
                "ok": True,
                "status": "ok",
                "app": self.APP_NAME,
                "version": self.VERSION,
                "plan": usage.get("plan_name"),
                "database": "reachable",
                "platforms_available": len(usage.get("platforms", [])),
                "encryption": "env" if app_config.get("LSP_ENCRYPTION_KEY") else "auto-generated",
            }
        except SystemExit:
            raise
        except Exception:
            payload = {"ok": False, "status": "error", "error": "Health check failed"}

        if self.json_mode or not payload["ok"]:
            print(json.dumps(payload))
            if not payload["ok"]:
                raise SystemExit(3)
            return payload

        print(f"[OK] {self.APP_NAME} v{self.VERSION} — status ok")
        print(f"  Plan:     {payload['plan']}")
        print(f"  Database: {payload['database']}")
        print(f"  Platforms available: {payload['platforms_available']}")
        return payload

    def cmd_status(self, args):
        """Show license and usage status."""
        self._init_components()
        
        usage = self.plan_manager.get_usage_summary()
        
        print("\n" + "=" * 50)
        print("LICENSE STATUS")
        print("=" * 50)
        print(f"  Plan:              {usage['plan_name']}")
        print(f"  Trial Mode:        {'Yes' if usage['is_trial'] else 'No'}")
        print(f"  Daily Usage:       {usage['daily_usage']} ({usage['daily_remaining']} remaining)")
        print(f"  Monthly Usage:     {usage['monthly_usage']} ({usage['monthly_remaining']} remaining)")
        print(f"  Export Allowed:    {'Yes' if usage['export_allowed'] else 'No'}")
        print(f"  Expiry Date:       {usage['expiry_date']}")
        print(f"  Total Leads in DB: {usage['total_leads_in_db']}")
        print("-" * 50)
        print("  Allowed Platforms:")
        for platform in usage['platforms']:
            print(f"    - {platform}")
        print("=" * 50 + "\n")
    
    def cmd_activate(self, args):
        """Activate a license key."""
        self._init_components()

        license_key = args.key
        if not license_key:
            license_key = input("Enter your license key: ").strip()

        license_key = validate_text(license_key, "license key", max_len=4096)

        if not self.json_mode:
            print("Validating license...")
        success, message = self.plan_manager.activate_license(license_key)

        if success:
            if self.json_mode:
                print(json.dumps({"ok": True, "activated": True, "message": message}))
                return
            print(f"[SUCCESS] {message}")
            self.cmd_status(args)
        else:
            self.fail(message or "License activation failed.", code=2)
    
    def cmd_scrape(self, args):
        """Execute a scraping operation."""
        self._init_components()

        platform = validate_text(args.platform, "platform", max_len=64).lower()
        query = validate_text(args.query, "query", max_len=200)
        location = validate_text(args.location, "location", max_len=200) if args.location else None
        max_results = validate_int(args.max, "max results", 1, 5000) or 50
        
        # Check if platform is allowed
        allowed = self.engine.get_available_platforms()
        if platform not in allowed:
            self.fail(
                f"Platform '{platform}' is not available in your current plan. "
                f"Available: {', '.join(allowed)}",
                code=2,
            )
        
        # Check limits
        can_scrape, reason = self.plan_manager.can_scrape(platform)
        if not can_scrape:
            self.fail(reason or "Scrape limit reached for your plan.", code=2)
        
        print(f"\n[INFO] Starting scrape on {platform}...")
        print(f"  Query: {query}")
        print(f"  Location: {location or 'Not specified'}")
        print(f"  Max Results: {max_results}")
        print("-" * 40)
        
        # Set up progress callback
        def on_lead_found(lead):
            name = lead.get('business_name', 'Unknown')[:40]
            phones = len(lead.get('phone_numbers', []))
            emails = len(lead.get('emails', []))
            print(f"  [+] {name} | Phones: {phones} | Emails: {emails}")
        
        def on_progress(msg):
            print(f"  [*] {msg}")
        
        def on_error(msg):
            print(f"  [!] Error: {msg}")
        
        self.engine.set_callbacks(
            on_lead_found=on_lead_found,
            on_progress=on_progress,
            on_error=on_error
        )
        
        # Execute scrape
        try:
            result = self.engine.scrape(
                platform=platform,
                query=query,
                location=location,
                max_results=max_results,
                headless=not args.visible
            )
            
            print("-" * 40)
            if result['success']:
                stats = result['stats']
                print(f"[SUCCESS] Scraping complete!")
                print(f"  Total found:  {stats['total']}")
                print(f"  New leads:    {stats['new']}")
                print(f"  Duplicates:   {stats['duplicates']}")
                print(f"  Errors:       {stats.get('errors', 0)}")
            else:
                print(f"[ERROR] {result.get('error', 'Unknown error')}")
                
        except KeyboardInterrupt:
            print("\n[INFO] Scraping stopped by user.")
            self.engine.stop()
        finally:
            self.engine.close()
    
    def cmd_export(self, args):
        """Export leads to file."""
        self._init_components()

        output = validate_text(args.output, "output path", max_len=512)
        format_type = args.format or 'csv'
        platform = validate_text(args.platform, "platform filter", max_len=64) if args.platform else None
        max_rows = validate_int(args.max, "max rows", 1, 100000)
        
        print(f"[INFO] Exporting leads to {format_type.upper()}...")
        
        if format_type == 'csv':
            exporter = get_csv_exporter()
            result = exporter.export(
                output_path=output,
                platform=platform,
                max_rows=max_rows
            )
        elif format_type == 'excel':
            exporter = get_csv_exporter()
            result = exporter.export_excel(
                output_path=output,
                platform=platform,
                max_rows=max_rows
            )
        elif format_type == 'json':
            exporter = get_json_exporter()
            result = exporter.export(
                output_path=output,
                platform=platform,
                max_rows=max_rows
            )
        else:
            print(f"[ERROR] Unknown format: {format_type}")
            return
        
        if result['success']:
            print(f"[SUCCESS] Exported {result['exported']} leads to {result.get('path', output)}")
        else:
            print(f"[ERROR] {result.get('error', 'Export failed')}")
    
    def cmd_list(self, args):
        """List leads in database."""
        self._init_components()

        platform = validate_text(args.platform, "platform filter", max_len=64) if args.platform else None
        limit = validate_int(args.limit, "limit", 1, 500) or 20
        
        leads = self.db.get_leads(platform=platform, limit=limit)
        
        if not leads:
            print("[INFO] No leads found.")
            return
        
        print(f"\n{'ID':<5} {'Business Name':<40} {'Platform':<15} {'Phone':<15} {'Email'}")
        print("-" * 100)
        
        for lead in leads:
            lead_id = lead.get('id', '')
            name = (lead.get('business_name', 'Unknown')[:38] + '..') if len(lead.get('business_name', '')) > 40 else lead.get('business_name', 'Unknown')
            platform = lead.get('platform_source', '')[:13]
            
            phones = lead.get('phone_numbers', [])
            phone = phones[0][:13] if phones else '-'
            
            emails = lead.get('emails', [])
            email = emails[0][:30] if emails else '-'
            
            print(f"{lead_id:<5} {name:<40} {platform:<15} {phone:<15} {email}")
        
        print("-" * 100)
        print(f"Showing {len(leads)} leads. Total in database: {self.db.get_lead_count()}")
    
    def cmd_platforms(self, args):
        """List available platforms."""
        self._init_components()
        
        all_platforms = self.engine.get_all_platforms()
        available = self.engine.get_available_platforms()
        
        print("\n" + "=" * 50)
        print("SUPPORTED PLATFORMS")
        print("=" * 50)
        
        for platform in all_platforms:
            status = "✓ Available" if platform in available else "✗ Upgrade Required"
            print(f"  {platform:<20} {status}")
        
        print("=" * 50 + "\n")
    
    def cmd_clear(self, args):
        """Clear all leads from database."""
        self._init_components()
        
        if not args.confirm:
            confirm = input("Are you sure you want to delete ALL leads? Type 'YES' to confirm: ")
            if confirm != 'YES':
                print("[INFO] Operation cancelled.")
                return
        
        self.db.clear_all_leads()
        print("[SUCCESS] All leads have been deleted.")
    
    def cmd_backup(self, args):
        """Create encrypted backup of leads."""
        self._init_components()
        
        output_path = args.output
        
        # CONSENT PROMPT
        print("\n" + "=" * 60)
        print("BACKUP CONSENT")
        print("=" * 60)
        print("""
This will create an ENCRYPTED backup of your lead database.

The backup file will contain:
  - All scraped leads (business names, phones, emails, etc.)
  - Backup metadata (date, lead count)
  
The backup is:
  ✓ Encrypted with AES-256 (Fernet)
  ✓ Compressed with gzip
  ✓ Only readable with this application
  
""")
        
        lead_count = self.db.get_lead_count()
        print(f"  Leads to backup: {lead_count}")
        print(f"  Output file: {output_path}")
        print("-" * 60)
        
        consent = input("\nDo you consent to create this backup? (yes/no): ").strip().lower()
        if consent not in ['yes', 'y']:
            print("[INFO] Backup cancelled.")
            return
        
        print("\n[INFO] Creating backup...")
        success, message, stats = self.db.create_backup(output_path, include_license=args.include_license)
        
        if success:
            print(f"[SUCCESS] {message}")
            print(f"  Leads backed up: {stats.get('leads_backed_up', 0)}")
            print(f"  File size: {stats.get('file_size', 0) / 1024:.1f} KB")
        else:
            print(f"[ERROR] {message}")
    
    def cmd_restore(self, args):
        """Restore leads from encrypted backup."""
        self._init_components()
        
        backup_path = args.input
        
        # Get backup info first
        info = self.db.get_backup_info(backup_path)
        if not info:
            print(f"[ERROR] Cannot read backup file: {backup_path}")
            print("The file may be corrupted or created with a different encryption key.")
            return
        
        # CONSENT PROMPT
        print("\n" + "=" * 60)
        print("RESTORE CONSENT")
        print("=" * 60)
        print(f"""
You are about to restore leads from a backup file.

Backup Information:
  - Created: {info.get('created_at', 'Unknown')}
  - Leads in backup: {info.get('lead_count', 0)}
  - File size: {info.get('file_size', 0) / 1024:.1f} KB
  
Current Database:
  - Existing leads: {self.db.get_lead_count()}
  
Restore Mode: {'MERGE (keep existing + add new)' if args.merge else 'REPLACE (delete existing, restore from backup)'}
""")
        print("-" * 60)
        
        if not args.merge:
            print("\n⚠️  WARNING: REPLACE mode will DELETE all existing leads!")
            confirm = input("Type 'REPLACE' to confirm destructive restore: ").strip()
            if confirm != 'REPLACE':
                print("[INFO] Restore cancelled.")
                return
        else:
            consent = input("\nDo you consent to restore this backup? (yes/no): ").strip().lower()
            if consent not in ['yes', 'y']:
                print("[INFO] Restore cancelled.")
                return
        
        print("\n[INFO] Restoring backup...")
        success, message, stats = self.db.restore_backup(backup_path, merge_mode=args.merge)
        
        if success:
            print(f"[SUCCESS] {message}")
            print(f"  Leads restored: {stats.get('restored', 0)}")
            print(f"  Duplicates skipped: {stats.get('duplicates', 0)}")
            print(f"  Errors: {stats.get('errors', 0)}")
        else:
            print(f"[ERROR] {message}")
    
    def run(self):
        """Run the CLI application."""
        parser = argparse.ArgumentParser(
            prog='lead_scraper',
            description='Lead Scraper Pro - B2B/B2C Lead Extraction System'
        )
        parser.add_argument('--version', action='version', version=f'%(prog)s {self.VERSION}')
        parser.add_argument('--json', action='store_true',
                            help='Emit machine-readable JSON output and JSON errors')

        # --json works before or after the subcommand
        json_parent = argparse.ArgumentParser(add_help=False)
        json_parent.add_argument('--json', action='store_true',
                                 help='Emit machine-readable JSON output and JSON errors')

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Health command
        health_parser = subparsers.add_parser('health', parents=[json_parent],
                                              help='Health check (boot, DB, config)')
        
        # Status command
        status_parser = subparsers.add_parser('status', parents=[json_parent], help='Show license and usage status')
        
        # Activate command
        activate_parser = subparsers.add_parser('activate', parents=[json_parent], help='Activate a license key')
        activate_parser.add_argument('-k', '--key', help='License key to activate')
        
        # Scrape command
        scrape_parser = subparsers.add_parser('scrape', parents=[json_parent], help='Scrape leads from a platform')
        scrape_parser.add_argument('platform', help='Platform to scrape (e.g., google_maps, justdial)')
        scrape_parser.add_argument('query', help='Search query (e.g., "restaurants", "plumbers")')
        scrape_parser.add_argument('-l', '--location', help='Location filter (e.g., "Mumbai")')
        scrape_parser.add_argument('-m', '--max', type=int, default=50, help='Maximum results (default: 50)')
        scrape_parser.add_argument('-v', '--visible', action='store_true', help='Show browser window')
        
        # Export command
        export_parser = subparsers.add_parser('export', parents=[json_parent], help='Export leads to file')
        export_parser.add_argument('output', help='Output file path')
        export_parser.add_argument('-f', '--format', choices=['csv', 'excel', 'json'], default='csv', help='Export format')
        export_parser.add_argument('-p', '--platform', help='Filter by platform')
        export_parser.add_argument('-m', '--max', type=int, help='Maximum rows to export')
        
        # List command
        list_parser = subparsers.add_parser('list', parents=[json_parent], help='List leads in database')
        list_parser.add_argument('-p', '--platform', help='Filter by platform')
        list_parser.add_argument('-l', '--limit', type=int, default=20, help='Number of leads to show')
        
        # Platforms command
        platforms_parser = subparsers.add_parser('platforms', parents=[json_parent], help='List available platforms')
        
        # Clear command
        clear_parser = subparsers.add_parser('clear', parents=[json_parent], help='Clear all leads from database')
        clear_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
        
        # Backup command
        backup_parser = subparsers.add_parser('backup', parents=[json_parent], help='Create encrypted backup of leads')
        backup_parser.add_argument('output', help='Output backup file path (.lsp extension recommended)')
        backup_parser.add_argument('--include-license', action='store_true', help='Include license state in backup')
        
        # Restore command
        restore_parser = subparsers.add_parser('restore', parents=[json_parent], help='Restore leads from encrypted backup')
        restore_parser.add_argument('input', help='Backup file path to restore from')
        restore_parser.add_argument('--merge', action='store_true', default=True, help='Merge with existing leads (default)')
        restore_parser.add_argument('--replace', action='store_true', help='Replace all existing leads')
        
        args = parser.parse_args()
        
        # Handle --replace flag
        if hasattr(args, 'replace') and args.replace:
            args.merge = False
        
        if not args.command:
            self.print_banner()
            parser.print_help()
            return
        
        # Map commands to methods
        commands = {
            'health': self.cmd_health,
            'status': self.cmd_status,
            'activate': self.cmd_activate,
            'scrape': self.cmd_scrape,
            'export': self.cmd_export,
            'list': self.cmd_list,
            'platforms': self.cmd_platforms,
            'clear': self.cmd_clear,
            'backup': self.cmd_backup,
            'restore': self.cmd_restore
        }

        handler = commands.get(args.command)
        if handler:
            self.json_mode = bool(args.json)
            try:
                handler(args)
            except SystemExit:
                raise
            except ValidationError as e:
                # Input validation failure -> structured error, exit 2, no traceback.
                self.fail(str(e), code=2)
            except Exception:
                # Never leak stack traces or internals to clients.
                self.fail("Command failed unexpectedly.", code=1)
        else:
            parser.print_help()


def main():
    """Entry point for CLI."""
    cli = LeadScraperCLI()
    cli.run()


if __name__ == '__main__':
    main()
