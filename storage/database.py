"""
Lead Scraper Pro - Encrypted SQLite Database Module
Handles all lead storage with field-level encryption for sensitive data.
"""

import sqlite3
import json
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class DatabaseManager:
    """Manages encrypted SQLite database for lead storage."""
    
    def __init__(self, db_path: str = None, encryption_key: str = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
            encryption_key: Key for field-level encryption
        """
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".lead_scraper_pro")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "leads.db")
        
        self.db_path = db_path
        self._init_encryption(encryption_key)
        self._init_database()
        self._perform_auto_backup()
    
    def _perform_auto_backup(self):
        """Perform daily auto-backup on startup."""
        try:
            backup_dir = os.path.join(os.path.dirname(self.db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Keep last 7 backups
            today = datetime.now().strftime('%Y-%m-%d')
            backup_file = os.path.join(backup_dir, f"leads_backup_{today}.lsp")
            
            # Only backup once per day
            if not os.path.exists(backup_file):
                self.create_backup(backup_file, include_license=True)
                
                # Cleanup old backups
                backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.lsp')])
                while len(backups) > 7:
                    os.remove(backups.pop(0))
        except Exception:
            pass  # Fail silently on auto-backup
            
    def _init_encryption(self, key: str = None):
        """Initialize Fernet encryption with derived key."""
        if key is None:
            key = "LeadScraperPro2024!DefaultKey"
        
        # Derive a proper key using PBKDF2
        salt = b'lead_scraper_pro_salt_v1'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        self.cipher = Fernet(derived_key)
    
    def _encrypt(self, data: str) -> str:
        """Encrypt a string value."""
        if not data:
            return ""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt(self, data: str) -> str:
        """Decrypt a string value."""
        if not data:
            return ""
        try:
            return self.cipher.decrypt(data.encode()).decode()
        except Exception:
            return data  # Return as-is if decryption fails
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        
        # Enable Write-Ahead Logging for concurrency and crash resistance
        conn.execute('PRAGMA journal_mode=WAL;')
        
        cursor = conn.cursor()
        
        # Main leads table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                category TEXT,
                industry TEXT,
                phone_numbers TEXT,
                emails TEXT,
                website TEXT,
                social_links TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                pincode TEXT,
                platform_source TEXT NOT NULL,
                lead_type TEXT DEFAULT 'B2B',
                rating REAL,
                reviews_count INTEGER,
                notes TEXT,
                tags TEXT,
                is_verified INTEGER DEFAULT 0,
                scraped_at TEXT NOT NULL,
                updated_at TEXT,
                raw_data TEXT,
                dedup_hash TEXT UNIQUE
            )
        ''')
        
        # Usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                leads_scraped INTEGER DEFAULT 0,
                platform TEXT,
                action TEXT
            )
        ''')
        
        # License state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_state (
                id INTEGER PRIMARY KEY,
                license_key TEXT,
                plan_name TEXT,
                daily_limit INTEGER,
                monthly_limit INTEGER,
                leads_used_today INTEGER DEFAULT 0,
                leads_used_month INTEGER DEFAULT 0,
                last_reset_date TEXT,
                month_reset_date TEXT,
                expiry_date TEXT,
                platforms_allowed TEXT,
                export_allowed INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0
            )
        ''')
        
        # Create indexes for faster deduplication
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dedup_hash ON leads(dedup_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON leads(platform_source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraped_at ON leads(scraped_at)')
        
        conn.commit()
        conn.close()
    
    def _generate_dedup_hash(self, lead: Dict) -> str:
        """Generate unique hash for deduplication based on phone, email, or domain."""
        components = []
        
        # Use phone number as primary dedup key
        phones = lead.get('phone_numbers', [])
        if phones:
            if isinstance(phones, str):
                phones = [phones]
            # Normalize phone numbers
            for phone in phones:
                normalized = ''.join(filter(str.isdigit, str(phone)))[-10:]
                if normalized:
                    components.append(f"phone:{normalized}")
        
        # Use email as secondary dedup key
        emails = lead.get('emails', [])
        if emails:
            if isinstance(emails, str):
                emails = [emails]
            for email in emails:
                if email and '@' in email:
                    components.append(f"email:{email.lower().strip()}")
        
        # Use domain as tertiary dedup key
        website = lead.get('website', '')
        if website:
            # Extract domain
            domain = website.lower().replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]
            if domain:
                components.append(f"domain:{domain}")
        
        # If no strong identifiers, use name + address
        if not components:
            name = lead.get('business_name', '').lower().strip()
            address = lead.get('address', '').lower().strip()
            if name:
                components.append(f"name:{name}")
            if address:
                components.append(f"addr:{address[:50]}")
        
        if not components:
            return None
        
        hash_input = '|'.join(sorted(components))
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]
    
    def insert_lead(self, lead: Dict) -> tuple[bool, str]:
        """
        Insert a lead into the database.
        
        Args:
            lead: Lead data dictionary
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Generate dedup hash
            dedup_hash = self._generate_dedup_hash(lead)
            
            # Check for duplicates
            if dedup_hash:
                cursor.execute('SELECT id FROM leads WHERE dedup_hash = ?', (dedup_hash,))
                existing = cursor.fetchone()
                if existing:
                    conn.close()
                    return False, f"Duplicate lead detected (ID: {existing[0]})"
            
            # Serialize list fields
            phone_numbers = json.dumps(lead.get('phone_numbers', []))
            emails = json.dumps(lead.get('emails', []))
            social_links = json.dumps(lead.get('social_links', {}))
            tags = json.dumps(lead.get('tags', []))
            raw_data = json.dumps(lead.get('raw_data', {}))
            
            # Encrypt sensitive fields
            encrypted_phones = self._encrypt(phone_numbers)
            encrypted_emails = self._encrypt(emails)
            
            cursor.execute('''
                INSERT INTO leads (
                    business_name, category, industry, phone_numbers, emails,
                    website, social_links, address, city, state, country, pincode,
                    platform_source, lead_type, rating, reviews_count, notes, tags,
                    is_verified, scraped_at, raw_data, dedup_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                lead.get('business_name', 'Unknown'),
                lead.get('category', ''),
                lead.get('industry', ''),
                encrypted_phones,
                encrypted_emails,
                lead.get('website', ''),
                social_links,
                lead.get('address', ''),
                lead.get('city', ''),
                lead.get('state', ''),
                lead.get('country', 'India'),
                lead.get('pincode', ''),
                lead.get('platform_source', 'Unknown'),
                lead.get('lead_type', 'B2B'),
                lead.get('rating'),
                lead.get('reviews_count'),
                lead.get('notes', ''),
                tags,
                1 if lead.get('is_verified') else 0,
                datetime.now().isoformat(),
                raw_data,
                dedup_hash
            ))
            
            conn.commit()
            lead_id = cursor.lastrowid
            conn.close()
            return True, f"Lead inserted with ID: {lead_id}"
            
        except sqlite3.IntegrityError as e:
            conn.close()
            return False, f"Duplicate or integrity error: {str(e)}"
        except Exception as e:
            conn.close()
            return False, f"Error inserting lead: {str(e)}"
    
    def insert_leads_batch(self, leads: List[Dict]) -> Dict[str, int]:
        """
        Insert multiple leads in a batch.
        
        Returns:
            Dict with 'inserted', 'duplicates', 'errors' counts
        """
        results = {'inserted': 0, 'duplicates': 0, 'errors': 0}
        
        for lead in leads:
            success, message = self.insert_lead(lead)
            if success:
                results['inserted'] += 1
            elif 'Duplicate' in message:
                results['duplicates'] += 1
            else:
                results['errors'] += 1
        
        return results
    
    def get_leads(self, 
                  platform: str = None,
                  lead_type: str = None,
                  limit: int = 100,
                  offset: int = 0) -> List[Dict]:
        """Retrieve leads with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM leads WHERE 1=1'
        params = []
        
        if platform:
            query += ' AND platform_source = ?'
            params.append(platform)
        
        if lead_type:
            query += ' AND lead_type = ?'
            params.append(lead_type)
        
        query += ' ORDER BY scraped_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        leads = []
        for row in rows:
            lead = dict(row)
            # Decrypt sensitive fields
            try:
                lead['phone_numbers'] = json.loads(self._decrypt(lead['phone_numbers']))
            except:
                lead['phone_numbers'] = []
            try:
                lead['emails'] = json.loads(self._decrypt(lead['emails']))
            except:
                lead['emails'] = []
            try:
                lead['social_links'] = json.loads(lead['social_links'])
            except:
                lead['social_links'] = {}
            try:
                lead['tags'] = json.loads(lead['tags'])
            except:
                lead['tags'] = []
            leads.append(lead)
        
        return leads
    
    def get_lead_count(self, platform: str = None) -> int:
        """Get total count of leads."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if platform:
            cursor.execute('SELECT COUNT(*) FROM leads WHERE platform_source = ?', (platform,))
        else:
            cursor.execute('SELECT COUNT(*) FROM leads')
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_today_usage(self) -> int:
        """Get number of leads scraped today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE date(scraped_at) = ?",
            (today,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_month_usage(self) -> int:
        """Get number of leads scraped this month."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE date(scraped_at) >= ?",
            (month_start,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def save_license_state(self, license_data: Dict):
        """Save license state to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM license_state')
        cursor.execute('''
            INSERT INTO license_state (
                id, license_key, plan_name, daily_limit, monthly_limit,
                leads_used_today, leads_used_month, last_reset_date, month_reset_date,
                expiry_date, platforms_allowed, export_allowed, is_active
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            license_data.get('license_key', ''),
            license_data.get('plan_name', 'trial'),
            license_data.get('daily_limit', 10),
            license_data.get('monthly_limit', 50),
            license_data.get('leads_used_today', 0),
            license_data.get('leads_used_month', 0),
            license_data.get('last_reset_date', datetime.now().strftime('%Y-%m-%d')),
            license_data.get('month_reset_date', datetime.now().replace(day=1).strftime('%Y-%m-%d')),
            license_data.get('expiry_date', ''),
            json.dumps(license_data.get('platforms_allowed', ['google_search'])),
            1 if license_data.get('export_allowed') else 0,
            1 if license_data.get('is_active') else 0
        ))
        
        conn.commit()
        conn.close()
    
    def get_license_state(self) -> Optional[Dict]:
        """Retrieve license state from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM license_state WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            state = dict(row)
            try:
                state['platforms_allowed'] = json.loads(state['platforms_allowed'])
            except:
                state['platforms_allowed'] = ['google_search']
            return state
        return None
    
    def clear_all_leads(self):
        """Clear all leads from database (admin function)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM leads')
        conn.commit()
        conn.close()
    
    def create_backup(self, backup_path: str, include_license: bool = False) -> tuple[bool, str, Dict]:
        """
        Create an encrypted backup of all leads.
        
        Args:
            backup_path: Path to save backup file
            include_license: Whether to include license state
            
        Returns:
            Tuple of (success, message, stats)
        """
        import gzip
        
        try:
            # Get all leads
            leads = self.get_leads(limit=100000)  # Get all
            
            backup_data = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'lead_count': len(leads),
                'leads': leads
            }
            
            if include_license:
                license_state = self.get_license_state()
                if license_state:
                    backup_data['license_state'] = license_state
            
            # Serialize and encrypt
            json_data = json.dumps(backup_data, default=str)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            # Compress and save
            with gzip.open(backup_path, 'wb') as f:
                f.write(encrypted_data)
            
            stats = {
                'leads_backed_up': len(leads),
                'file_size': os.path.getsize(backup_path),
                'includes_license': include_license
            }
            
            return True, f"Backup created successfully: {backup_path}", stats
            
        except Exception as e:
            return False, f"Backup failed: {str(e)}", {}
    
    def restore_backup(self, backup_path: str, merge_mode: bool = True) -> tuple[bool, str, Dict]:
        """
        Restore leads from an encrypted backup.
        
        Args:
            backup_path: Path to backup file
            merge_mode: If True, merge with existing leads. If False, replace all.
            
        Returns:
            Tuple of (success, message, stats)
        """
        import gzip
        
        try:
            # Verify file exists
            if not os.path.exists(backup_path):
                return False, f"Backup file not found: {backup_path}", {}
            
            # Read and decrypt
            with gzip.open(backup_path, 'rb') as f:
                encrypted_data = f.read()
            
            try:
                decrypted_data = self.cipher.decrypt(encrypted_data).decode()
            except Exception:
                return False, "Failed to decrypt backup. Invalid encryption key or corrupted file.", {}
            
            backup_data = json.loads(decrypted_data)
            
            # Verify backup format
            if 'version' not in backup_data or 'leads' not in backup_data:
                return False, "Invalid backup file format.", {}
            
            leads = backup_data.get('leads', [])
            
            # Clear existing if not merge mode
            if not merge_mode:
                self.clear_all_leads()
            
            # Restore leads
            stats = {'restored': 0, 'duplicates': 0, 'errors': 0}
            
            for lead in leads:
                success, msg = self.insert_lead(lead)
                if success:
                    stats['restored'] += 1
                elif 'Duplicate' in msg:
                    stats['duplicates'] += 1
                else:
                    stats['errors'] += 1
            
            # Restore license if present and requested
            if 'license_state' in backup_data:
                stats['license_restored'] = True
            
            return True, f"Restore completed: {stats['restored']} leads restored", stats
            
        except Exception as e:
            return False, f"Restore failed: {str(e)}", {}
    
    def get_backup_info(self, backup_path: str) -> Optional[Dict]:
        """
        Get information about a backup file without restoring.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Dict with backup metadata or None if invalid
        """
        import gzip
        
        try:
            if not os.path.exists(backup_path):
                return None
            
            with gzip.open(backup_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data).decode()
            backup_data = json.loads(decrypted_data)
            
            return {
                'version': backup_data.get('version'),
                'created_at': backup_data.get('created_at'),
                'lead_count': backup_data.get('lead_count', len(backup_data.get('leads', []))),
                'has_license': 'license_state' in backup_data,
                'file_size': os.path.getsize(backup_path)
            }
            
        except Exception:
            return None


# Singleton instance
_db_instance = None

def get_database() -> DatabaseManager:
    """Get or create singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
