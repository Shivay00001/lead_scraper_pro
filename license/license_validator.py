"""
Lead Scraper Pro - License Validator Module
Handles cryptographic license validation with online and offline modes.
"""

import json
import hashlib
import base64
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


# RSA Public Key for license validation (embedded in app)
# In production, this would be your actual public key
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu7fN9G7EkD9G8FS6ZLIV
0vDq1LFgKbIVZTKq7xH4N5TMCgLv5bN3Ja3fW9K4h4bGhTFzYHRQtH3z1gDZAGiT
M7bG8QX9cL2m4dRJiTPW0kKKC1qMi3z6A6s3aHv1OvV5Y3VfsCRq3XKx0tMcqzHH
6m9gBfSjM2G0vL7XkZCkD0n4gVjWTsK9jvP3x5XR3v5N8jL4WTYkKqPm6oQ5dAE1
h3sI6V4GXWRB5YcJQYVdZqN3c5qP5Z4VK9X8dQ3Y0cX5xP3L7y4kPkMnF2x1E6X7
9gD2vPjL4kFmZ3xTL0t5rKvQY6o7HmK9pXhZT5L8cN2dR9qMv3s1B0hPZ6Q5xK3L
AQIDAQAB
-----END PUBLIC KEY-----"""


class LicenseValidator:
    """Validates license keys using cryptographic signatures."""
    
    # License API endpoint (for online validation)
    API_ENDPOINT = "https://api.leadscraperpro.com/v1/license"
    
    # Plan configurations
    PLANS = {
        'trial': {
            'name': 'Free Trial',
            'daily_limit': 10,
            'monthly_limit': 50,
            'platforms': ['google_search'],
            'export_allowed': False,
            'bulk_export': False,
            'duration_days': 14
        },
        'starter': {
            'name': 'Starter',
            'daily_limit': 50,
            'monthly_limit': 500,
            'platforms': ['google_search', 'google_maps', 'bing_maps'],
            'export_allowed': True,
            'bulk_export': False,
            'duration_days': 30
        },
        'pro': {
            'name': 'Pro',
            'daily_limit': 200,
            'monthly_limit': 2000,
            'platforms': ['google_search', 'google_maps', 'justdial', 'sulekha', 
                         'indiamart', 'bing_maps', 'yelp', 'yellow_pages'],
            'export_allowed': True,
            'bulk_export': True,
            'duration_days': 30
        },
        'agency': {
            'name': 'Agency',
            'daily_limit': 1000,
            'monthly_limit': 10000,
            'platforms': ['google_search', 'google_maps', 'justdial', 'sulekha',
                         'indiamart', 'bing_maps', 'apple_maps', 'yelp', 'yellow_pages',
                         'youtube', 'instagram', 'twitter', 'facebook', 'job_portals'],
            'export_allowed': True,
            'bulk_export': True,
            'duration_days': 30
        }
    }
    
    def __init__(self):
        """Initialize license validator."""
        self.public_key = serialization.load_pem_public_key(
            PUBLIC_KEY_PEM.encode(),
            backend=default_backend()
        )
        self._cached_license = None
        self._last_validation = None
    
    def _decode_license_key(self, license_key: str) -> Optional[Dict]:
        """
        Decode a license key into its components.
        
        License key format: BASE64(JSON_PAYLOAD).BASE64(SIGNATURE)
        """
        try:
            parts = license_key.strip().split('.')
            if len(parts) != 2:
                return None
            
            payload_b64, signature_b64 = parts
            
            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64 + '==').decode()
            payload = json.loads(payload_json)
            
            # Decode signature
            signature = base64.urlsafe_b64decode(signature_b64 + '==')
            
            return {
                'payload': payload,
                'signature': signature,
                'raw_payload': payload_b64
            }
        except Exception as e:
            return None
    
    def _verify_signature(self, payload_b64: str, signature: bytes) -> bool:
        """Verify the cryptographic signature of the license payload."""
        try:
            self.public_key.verify(
                signature,
                payload_b64.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False
    
    def check_revocation_status(self, license_key: str) -> bool:
        """
        Check if license is revoked remotely (Kill Switch).
        Returns True if revoked (banned), False if safe.
        """
        try:
            # Placeholder for user's revocation URL (e.g., GitHub Gist raw URL)
            # You can update this URL to a text file containing banned keys
            REVOCATION_URL = "https://gist.githubusercontent.com/placeholder/banned_keys.txt"
            
            # fast timeout, fail safe (if internet down, don't block app unless certain)
            response = requests.get(REVOCATION_URL, timeout=3)
            
            if response.status_code == 200:
                banned_keys = response.text.splitlines()
                # Check for exact match
                if any(license_key.strip() == key.strip() for key in banned_keys):
                    return True
            
            return False
        except:
            # If network error, assume safe (fail open) or strict (fail closed)
            # For user experience, we usually fail open unless strict security needed
            return False

    def validate_online(self, license_key: str) -> Tuple[bool, Dict]:
        """
        Validate license key via online API.
        
        Returns:
            Tuple of (is_valid, license_data or error_message)
        """
        # 1. Check Kill Switch first
        if self.check_revocation_status(license_key):
            return False, {'error': 'This license has been revoked by the administrator.'}

        # 2. Proceed with validation (Simulated online check since we don't have a backend yet)
        # In a real scenario, you'd hit your API here.
        # For now, we fall back to offline crypto validation which is secure enough
        return self.validate_offline(license_key)
    
    def validate_offline(self, license_key: str) -> Tuple[bool, Dict]:
        """
        Validate license key offline using embedded public key.
        
        Returns:
            Tuple of (is_valid, license_data or error_message)
        """
        decoded = self._decode_license_key(license_key)
        if not decoded:
            return False, {'error': 'Invalid license key format'}
        
        # Verify signature
        if not self._verify_signature(decoded['raw_payload'], decoded['signature']):
            return False, {'error': 'Invalid license signature'}
        
        payload = decoded['payload']
        
        # Check expiry
        expiry_date = payload.get('expiry')
        if expiry_date:
            try:
                expiry = datetime.fromisoformat(expiry_date)
                if datetime.now() > expiry:
                    return False, {'error': 'License has expired'}
            except ValueError:
                pass
        
        # Get plan configuration
        plan_id = payload.get('plan', 'trial')
        plan_config = self.PLANS.get(plan_id, self.PLANS['trial'])
        
        license_data = {
            'license_key': license_key,
            'plan_id': plan_id,
            'plan_name': plan_config['name'],
            'daily_limit': plan_config['daily_limit'],
            'monthly_limit': plan_config['monthly_limit'],
            'platforms_allowed': plan_config['platforms'],
            'export_allowed': plan_config['export_allowed'],
            'bulk_export': plan_config['bulk_export'],
            'expiry_date': expiry_date,
            'is_active': True,
            'customer_email': payload.get('email', ''),
            'customer_name': payload.get('name', '')
        }
        
        return True, license_data
    
    def validate(self, license_key: str, prefer_online: bool = True) -> Tuple[bool, Dict]:
        """
        Validate a license key.
        
        Args:
            license_key: The license key to validate
            prefer_online: If True, try online validation first
            
        Returns:
            Tuple of (is_valid, license_data or error)
        """
        if not license_key or len(license_key) < 20:
            return False, {'error': 'Invalid license key'}
        
        if prefer_online:
            return self.validate_online(license_key)
        else:
            return self.validate_offline(license_key)
    
    def _generate_device_id(self) -> str:
        """Generate a unique device identifier for license binding."""
        import platform
        import uuid
        
        components = [
            platform.node(),
            platform.machine(),
            platform.processor(),
            str(uuid.getnode())  # MAC address
        ]
        
        fingerprint = '|'.join(components)
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    
    def get_trial_license(self) -> Dict:
        """Get trial license configuration."""
        plan_config = self.PLANS['trial']
        
        return {
            'license_key': 'TRIAL',
            'plan_id': 'trial',
            'plan_name': plan_config['name'],
            'daily_limit': plan_config['daily_limit'],
            'monthly_limit': plan_config['monthly_limit'],
            'platforms_allowed': plan_config['platforms'],
            'export_allowed': plan_config['export_allowed'],
            'bulk_export': plan_config['bulk_export'],
            'expiry_date': (datetime.now() + timedelta(days=plan_config['duration_days'])).isoformat(),
            'is_active': True,
            'is_trial': True
        }
    
    def get_plan_info(self, plan_id: str) -> Optional[Dict]:
        """Get information about a specific plan."""
        return self.PLANS.get(plan_id)
    
    def list_plans(self) -> Dict:
        """List all available plans."""
        return self.PLANS.copy()


# For generating license keys (admin tool - would be separate)
class LicenseGenerator:
    """
    License key generator for admin use.
    This would be a separate admin tool, not distributed with the client.
    """
    
    @staticmethod
    def generate_keypair():
        """Generate RSA keypair for license signing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem, public_pem
    
    @staticmethod
    def generate_license(private_key_pem: bytes, payload: Dict) -> str:
        """
        Generate a signed license key.
        
        Args:
            private_key_pem: PEM-encoded private key
            payload: License payload dict
            
        Returns:
            Signed license key string
        """
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
            backend=default_backend()
        )
        
        # Serialize payload
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
        
        # Sign payload
        signature = private_key.sign(
            payload_b64.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        return f"{payload_b64}.{signature_b64}"
