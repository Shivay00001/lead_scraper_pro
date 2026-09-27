"""
Smoke test: boot the CLI fresh and hit the main commands, asserting success.
Uses an isolated temp dir for DB + key files so nothing touches the real home.

Run:  python tests/test_cli_smoke.py
"""
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(REPO_ROOT, "main.py")


def run_cli(args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, MAIN] + args,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  OK: {message}")


def main():
    with tempfile.TemporaryDirectory(prefix="lsp_smoke_") as tmp:
        home = os.path.join(tmp, "home")
        os.makedirs(home, exist_ok=True)
        base_env = {
            "HOME": home,
            "LSP_DB_PATH": os.path.join(tmp, "leads.db"),
            "LSP_ENCRYPTION_KEY": "smoke-test-only-dummy-key-32-chars-min",
            "LSP_REVOCATION_URL": "",  # disabled
        }

        print("== health --json (fresh boot) ==")
        p = run_cli(["health", "--json"], base_env)
        check(p.returncode == 0, "health exits 0")
        body = json.loads(p.stdout.strip())
        check(body.get("ok") is True and body.get("status") == "ok", "health returns ok JSON")

        print("== health without --json ==")
        p = run_cli(["health"], base_env)
        check(p.returncode == 0, "health exits 0 in text mode")
        check("[OK]" in p.stdout, "health prints human-readable OK")

        print("== status ==")
        p = run_cli(["status"], base_env)
        check(p.returncode == 0, "status exits 0")
        check("LICENSE STATUS" in p.stdout, "status prints license summary")

        print("== platforms ==")
        p = run_cli(["platforms"], base_env)
        check(p.returncode == 0, "platforms exits 0")
        check("google_maps" in p.stdout, "platforms lists google_maps")

        print("== list (empty db) ==")
        p = run_cli(["list"], base_env)
        check(p.returncode == 0, "list exits 0 on empty DB")

        print("== export empty db ==")
        out = os.path.join(tmp, "leads.csv")
        p = run_cli(["export", out, "-f", "csv"], base_env)
        check(p.returncode == 0, "export exits 0 on empty DB")

        print("== validation: unknown platform rejected ==")
        p = run_cli(["scrape", "not_a_platform", "test", "--json"], base_env)
        check(p.returncode == 2, "unknown platform exits 2")
        body = json.loads(p.stdout.strip())
        check(body.get("ok") is False and "error" in body, "unknown platform -> structured JSON error")

        print("== validation: max out of range rejected ==")
        p = run_cli(["scrape", "google_search", "test", "-m", "99999", "--json"], base_env)
        check(p.returncode == 2, "max=99999 exits 2")
        body = json.loads(p.stdout.strip())
        check(body.get("ok") is False, "out-of-range max -> structured JSON error")

        print("== validation: empty query rejected ==")
        p = run_cli(["scrape", "google_search", "   ", "--json"], base_env)
        check(p.returncode == 2, "blank query exits 2")

        print("== no stack traces leak ==")
        p = run_cli(["scrape", "google_search", "   "], base_env)
        check("Traceback" not in p.stdout and "Traceback" not in p.stderr, "no traceback in output")

        # Fresh boot WITHOUT an explicit encryption key -> auto-generated per-user key
        print("== fresh boot without LSP_ENCRYPTION_KEY ==")
        env2 = dict(base_env)
        del env2["LSP_ENCRYPTION_KEY"]
        p = run_cli(["health", "--json"], env2)
        check(p.returncode == 0, "boots without LSP_ENCRYPTION_KEY (auto key)")
        key_file = os.path.join(home, ".lead_scraper_pro", "encryption.key")
        check(os.path.exists(key_file), "per-user encryption key file auto-created")

    print("\nsmoke OK: boot + health + status + platforms + list + export + validation")


if __name__ == "__main__":
    main()
