"""
Lead Scraper Pro - Admin Key Generator
Run this script to generate new license keys for customers.
"""

import json
import base64
import os
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# --- CONFIGURATION ---
PRIVATE_KEY_FILE = "admin_private_key.pem"
PUBLIC_KEY_FILE = "app_public_key.pem"

def generate_key_pair():
    """Generate new RSA key pair if not exists."""
    if os.path.exists(PRIVATE_KEY_FILE):
        print("Using existing keys...")
        with open(PRIVATE_KEY_FILE, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        return private_key

    print("Generating new RSA keys...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Save Private Key (Keep Safe!)
    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
    # Save Public Key (Put this in the App)
    public_key = private_key.public_key()
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    
    print(f"Keys saved to {PRIVATE_KEY_FILE} and {PUBLIC_KEY_FILE}")
    print("IMPORTANT: Replace PUBLIC_KEY_PEM in license/license_validator.py with the content of app_public_key.pem")
    return private_key

def create_license(private_key, plan_id="starter", days=30, customer_email=""):
    """Create a signed license key."""
    expiry = datetime.now() + timedelta(days=days)
    
    payload = {
        "plan": plan_id,
        "expiry": expiry.isoformat(),
        "email": customer_email,
        "created": datetime.now().isoformat()
    }
    
    # JSON -> Bytes
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
    
    # Sign
    signature = private_key.sign(
        payload_b64.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    key = f"{payload_b64}.{signature_b64}"
    return key, payload

if __name__ == "__main__":
    pk = generate_key_pair()
    
    print("\n--- NEW LICENSE GENERATOR ---")
    plan = input("Plan (starter/pro/agency) [agency]: ").strip() or "agency"
    days = int(input("Duration (days) [365]: ").strip() or 365)
    email = input("Customer Email: ").strip()
    
    key, data = create_license(pk, plan, days, email)
    
    print("\n" + "="*60)
    print("LICENSE KEY GENERATED")
    print("="*60)
    print(key)
    print("="*60)
    print(f"Plan: {plan.upper()} | Expiry: {data['expiry']}")
    print("\nSend the key above to the customer.")
