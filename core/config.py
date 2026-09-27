"""
Lead Scraper Pro - Centralized Configuration
All runtime configuration comes from environment variables.
Copy .env.example to .env and adjust, or export vars in the shell.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from repo root (next to main.py) if present.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except Exception:
    pass  # python-dotenv optional; plain environment variables still work


def get(name: str, default: str = None) -> str:
    """Return an environment variable, or the given default."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value


def app_data_dir() -> str:
    """Per-user data directory (DB + persisted encryption key)."""
    data_dir = os.path.join(os.path.expanduser("~"), ".lead_scraper_pro")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def db_path() -> str:
    """SQLite database path. LSP_DB_PATH overrides the default location."""
    return get("LSP_DB_PATH") or os.path.join(app_data_dir(), "leads.db")


def encryption_key() -> str:
    """
    Encryption key material for field-level encryption (Fernet via PBKDF2).
    Priority: LSP_ENCRYPTION_KEY env var -> per-user persisted key file.
    Never falls back to a hardcoded default.
    """
    env_key = get("LSP_ENCRYPTION_KEY")
    if env_key:
        return env_key

    key_file = os.path.join(app_data_dir(), "encryption.key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            stored = f.read().strip()
        if stored:
            return stored

    # First run: generate a random per-user key and persist it (0600).
    import secrets
    generated = secrets.token_urlsafe(48)
    with open(key_file, "w") as f:
        f.write(generated)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return generated


def license_server_url() -> str:
    """Online license validation endpoint base."""
    return get("LSP_LICENSE_SERVER_URL", "https://api.leadscraperpro.com/v1/license")


def revocation_url() -> str:
    """
    URL of a plain-text file listing revoked license keys (one per line).
    Empty/unset disables the remote revocation check entirely.
    """
    return get("LSP_REVOCATION_URL", "")


def public_key_path() -> str:
    """
    Optional path to a PEM public key file that replaces the embedded
    demo key for license signature verification.
    """
    return get("LSP_PUBLIC_KEY_PATH", "")
