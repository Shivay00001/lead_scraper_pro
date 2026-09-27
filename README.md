# Lead Scraper Pro

A commercial B2B/B2C lead scraping system with built-in license validation and usage limits. CLI-first (headless); optional desktop GUI.

## Quick start (fresh clone)

```bash
# 1. Clone and enter
git clone <repo-url> lead_scraper_pro && cd lead_scraper_pro

# 2. Create a virtualenv and install
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Install the Playwright browser (needed for scraping)
playwright install chromium

# 4. Configure environment (optional for first boot; REQUIRED for server/Docker)
cp .env.example .env              # then edit .env

# 5. Health check — should print OK and exit 0
python main.py health
```

That's it. No tribal knowledge: README + `.env.example` are sufficient to boot.

## Usage

```bash
python main.py health                            # health check (JSON: --json)
python main.py status                            # license + usage status
python main.py platforms                          # list platforms by plan
python main.py scrape google_maps "restaurants" -l "Mumbai" -m 50
python main.py list -l 20                         # list leads in DB
python main.py export leads.csv -f csv            # csv | excel | json
python main.py activate -k YOUR_LICENSE_KEY       # activate a license
python main.py backup backup.lsp                  # encrypted backup
python main.py restore backup.lsp --merge         # restore (merge or --replace)
python main.py clear --confirm                    # delete all leads

# Machine-readable output / errors for scripts and monitoring:
python main.py health --json
python main.py scrape bad_platform "x" --json     # -> {"ok": false, "error": "..."}, exit 2
```

Global flags: `--json` (machine-readable output), `--version`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LSP_DB_PATH` | `~/.lead_scraper_pro/leads.db` | SQLite database file path |
| `LSP_ENCRYPTION_KEY` | auto-generated per user | Key material for field-level lead encryption (Fernet via PBKDF2). Set explicitly in Docker/server deployments so the same DB stays readable. If unset, a random key is generated once and stored at `~/.lead_scraper_pro/encryption.key` (0600) |
| `LSP_LICENSE_SERVER_URL` | `https://api.leadscraperpro.com/v1/license` | Online license-validation endpoint (falls back to offline signature validation) |
| `LSP_REVOCATION_URL` | _(empty = disabled)_ | URL of a plain-text file with revoked license keys (one per line). Remote kill-switch |
| `LSP_PUBLIC_KEY_PATH` | _(embedded demo key)_ | Path to a PEM public key file replacing the embedded demo key for license verification. Generate with `python admin_keygen.py` |

No secrets are hardcoded. The embedded license public key is a **demo key** — generate your own pair with `python admin_keygen.py` before selling licenses, then set `LSP_PUBLIC_KEY_PATH`.

**Migration note:** versions before this change encrypted the DB with a fixed built-in key. To keep reading a database created by an older build, set `LSP_ENCRYPTION_KEY` to that build's key material. New installs should use a fresh random value or leave it unset (auto-generated).

## Deploy on Render

Option A — Docker (recommended):

1. Push this repo to GitHub.
2. In Render: **New → Web Service** → select the repo. Render detects the `Dockerfile`.
3. Add environment variables: at minimum `LSP_ENCRYPTION_KEY` (long random string). Optionally `LSP_REVOCATION_URL`, `LSP_PUBLIC_KEY_PATH`.
4. Attach a **Persistent Disk** mounted at `/app/data` so `LSP_DB_PATH=/app/data/leads.db` survives restarts (Render disks are ephemeral otherwise).
5. The container's default command runs `python main.py health --json` (used by the Docker `HEALTHCHECK`). Override the start command per job, e.g. `python main.py scrape justdial "dentists" -l Mumbai -m 200`, or use one-off jobs via `docker compose run`-style commands.

Option B — Native Python:

1. **New → Background Worker** (or Web Service; there is no HTTP server — see below).
2. Build command: `pip install -r requirements.txt && playwright install chromium`
3. Start command: `python main.py health` (verify), then schedule scrapes as **Cron Jobs**: e.g. `python main.py scrape google_maps "hotels" -l Delhi -m 100`.
4. Set the same environment variables as above; add a persistent disk for the DB path.

## Notes on the "no web server" design

- Lead Scraper Pro is a **CLI/desktop tool**, not an HTTP service. There are no HTTP endpoints, so **CORS does not apply** and no API-key auth header scheme is needed: the `health` CLI command is the equivalent of a `/health` endpoint (exit 0 + `{"status": "ok"}` with `--json`).
- Access control is license-based: `activate` unlocks plan tiers; `can_scrape` enforces daily/monthly limits before every scrape; export is gated by plan.
- Input validation: all external CLI inputs are validated (text length, integer ranges). Errors are structured (`{"ok": false, "error": "..."}` with `--json`); stack traces are never printed.
- GUI (optional): `pip install -r requirements-gui.txt`, then `python main.py gui`. The Docker image and `requirements.txt` intentionally exclude PySide6 — the container runs headless.

## Smoke test

```bash
python tests/test_smoke.py        # core: deduplication + rate limiting
python tests/test_cli_smoke.py    # boot + health + status + platforms + list + export + input validation
```

Both scripts are kept in the repo and run against an isolated temp dir.

## Supported platforms

Google Maps, Google Search, Justdial, Sulekha, IndiaMART, Bing Maps, Apple Maps, Yelp, Yellow Pages, YouTube, Instagram, Twitter/X, Facebook, Job Portals. Availability depends on the active license plan (`python main.py platforms`).

## Disclaimer

This software collects ONLY publicly available business information. Users are responsible for compliance with applicable laws and platform Terms of Service. Automated scraping may violate a platform's ToS — scrape responsibly and at a respectful rate (built-in rate limiting helps).
