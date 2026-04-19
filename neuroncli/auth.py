"""NeuronCLI — OAuth PKCE flow for automatic OpenRouter API key provisioning.

On first run, opens the user's browser to OpenRouter's login page.
After the user logs in, OpenRouter redirects back to a tiny localhost server
which captures the auth code and exchanges it for a permanent API key.

Zero manual copy-paste. One click.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path


# ── Config paths ──────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".neuroncli"
CONFIG_FILE = CONFIG_DIR / "config.json"
CALLBACK_PORT = 19284  # Local server port to catch the redirect from zero-x.live
LOCAL_CALLBACK = f"http://localhost:{CALLBACK_PORT}"
# OpenRouter callback → zero-x.live → redirects to localhost with ?code=
CALLBACK_URL = "https://zero-x.live/neuroncli/callback"


# ── PKCE helpers ──────────────────────────────────────────────────

def _generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier (43-128 chars)."""
    return secrets.token_urlsafe(64)


def _generate_code_challenge(verifier: str) -> str:
    """SHA-256 hash the verifier and base64url-encode it."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ── Local config storage ─────────────────────────────────────────

def load_config() -> dict:
    """Load saved config from ~/.neuroncli/config.json."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(data: dict) -> None:
    """Save config to ~/.neuroncli/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_stored_api_key() -> str | None:
    """Get the stored OpenRouter API key, if any."""
    config = load_config()
    return config.get("openrouter_api_key")


def store_api_key(key: str) -> None:
    """Store the OpenRouter API key locally."""
    config = load_config()
    config["openrouter_api_key"] = key
    save_config(config)


# ── OAuth PKCE flow ──────────────────────────────────────────────

class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the OAuth redirect code.
    Handles redirects from zero-x.live callback page."""

    auth_code: str | None = None

    def _send_cors_headers(self):
        """Allow cross-origin requests from zero-x.live."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        code = params.get("code", [None])[0]

        if code:
            _OAuthCallbackHandler.auth_code = code
            # Show success page
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <head>
                <style>
                    body {
                        font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
                        display: flex; justify-content: center; align-items: center;
                        min-height: 100vh; margin: 0;
                        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
                        color: #e0e0e0;
                    }
                    .card {
                        text-align: center; padding: 60px;
                        background: rgba(255,255,255,0.05);
                        border: 1px solid rgba(255,255,255,0.1);
                        border-radius: 24px;
                        backdrop-filter: blur(20px);
                    }
                    h1 { color: #f0a028; font-size: 2em; }
                    p { color: #aaa; font-size: 1.1em; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>&#10003; NeuronCLI Connected</h1>
                    <p>Your OpenRouter API key has been provisioned.<br>
                    You can close this tab and return to the terminal.</p>
                </div>
            </body>
            </html>
            """)
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error: No auth code received</h1>")

    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass


def _exchange_code_for_key(code: str, code_verifier: str) -> str:
    """POST to OpenRouter to exchange the auth code for an API key."""
    payload = json.dumps({
        "code": code,
        "code_verifier": code_verifier,
        "code_challenge_method": "S256",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/auth/keys",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data["key"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter key exchange failed (HTTP {e.code}): {body}")
    except Exception as e:
        raise RuntimeError(f"OpenRouter key exchange failed: {e}")


def run_oauth_flow() -> str | None:
    """
    Run OAuth PKCE + manual paste IN PARALLEL:
    - Background thread: localhost server waits for callback (10 min)
    - Foreground: user can paste key manually while waiting
    - Whichever succeeds first wins.
    """
    _OAuthCallbackHandler.auth_code = None

    # Generate PKCE pair
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)

    # Build auth URL
    auth_url = (
        f"https://openrouter.ai/auth?"
        f"callback_url={urllib.parse.quote(CALLBACK_URL)}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    # Start callback server in background thread
    server = None
    try:
        server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _OAuthCallbackHandler)
    except OSError:
        pass  # Port in use — skip background listener

    server_thread = None
    if server:
        server.timeout = 600  # 10 MINUTES — enough for signup + email verify + survey
        def _listen():
            try:
                server.handle_request()
            except Exception:
                pass
            finally:
                server.server_close()
        server_thread = threading.Thread(target=_listen, daemon=True)
        server_thread.start()

    # Open browser
    print("\n  \033[96m\033[1m[AUTH]\033[0m Opening browser for OpenRouter login...")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # Show user-friendly instructions
    print(f"  \033[90m──────────────────────────────────────────────\033[0m")
    print(f"  \033[97mSign up / log in to OpenRouter in your browser.\033[0m")
    print(f"  \033[97mAfter login, you'll be redirected back here.\033[0m")
    print(f"  \033[90m──────────────────────────────────────────────\033[0m")
    print(f"  \033[90mIf auto-redirect doesn't work:\033[0m")
    print(f"  \033[90m1. Go to: \033[4mhttps://openrouter.ai/settings/keys\033[0m")
    print(f"  \033[90m2. Click 'Create Key' -> copy the key\033[0m")
    print(f"  \033[90m3. Paste it below\033[0m")
    print(f"  \033[90m──────────────────────────────────────────────\033[0m\n")

    # PARALLEL: Wait for EITHER OAuth callback OR manual paste
    # Poll every 2 seconds to check if background OAuth succeeded
    import time
    import sys
    import select

    api_key = None

    # On Windows, we can't use select() on stdin. Use a simpler approach.
    if sys.platform == "win32":
        api_key = _windows_parallel_auth(server_thread, code_verifier)
    else:
        api_key = _unix_parallel_auth(server_thread, code_verifier)

    # Clean up server
    if server:
        try:
            server.server_close()
        except Exception:
            pass

    if api_key:
        store_api_key(api_key)
        print(f"\n  \033[92m\033[1m[OK] API key saved to {CONFIG_FILE}\033[0m")
        print(f"  \033[92m\033[1m     You won't be asked again.\033[0m\n")
        return api_key

    print(f"\n  \033[90mNo API key provided. Using Ollama fallback if available.\033[0m\n")
    return None


def _check_oauth_result(code_verifier: str) -> str | None:
    """Check if the background OAuth server received a code."""
    code = _OAuthCallbackHandler.auth_code
    if not code:
        return None
    try:
        return _exchange_code_for_key(code, code_verifier)
    except RuntimeError:
        return None


def _validate_key(key: str) -> bool:
    """Check if a pasted key looks valid."""
    key = key.strip()
    return len(key) > 10 and (key.startswith("sk-or-") or key.startswith("sk-"))


def _windows_parallel_auth(server_thread, code_verifier: str) -> str | None:
    """Windows: prompt for manual paste while checking OAuth in background."""
    import time

    print("  \033[93mPaste your API key below (or wait for auto-redirect):\033[0m")
    print("  \033[93m> \033[0m", end="", flush=True)

    try:
        key = input().strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if key and _validate_key(key):
        return key

    # Check if OAuth completed while user was typing
    result = _check_oauth_result(code_verifier)
    if result:
        print("  \033[92m[v] Auto-redirect succeeded!\033[0m")
        return result

    # Neither worked — wait up to 30 more seconds for OAuth
    print("  \033[90mWaiting for browser redirect...\033[0m", end="", flush=True)
    for _ in range(15):
        time.sleep(2)
        result = _check_oauth_result(code_verifier)
        if result:
            print(f" \033[92mv\033[0m")
            return result
        print(".", end="", flush=True)

    print(f" \033[91mx\033[0m")
    return None


def _unix_parallel_auth(server_thread, code_verifier: str) -> str | None:
    """Unix: prompt for manual paste while checking OAuth in background."""
    import time

    print("  \033[93mPaste your API key below (or wait for auto-redirect):\033[0m")
    print("  \033[93m> \033[0m", end="", flush=True)

    try:
        key = input().strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if key and _validate_key(key):
        return key

    # Check if OAuth completed while user was typing
    result = _check_oauth_result(code_verifier)
    if result:
        print("  \033[92m[v] Auto-redirect succeeded!\033[0m")
        return result

    # Neither worked — wait up to 30 more seconds for OAuth
    print("  \033[90mWaiting for browser redirect...\033[0m", end="", flush=True)
    for _ in range(15):
        time.sleep(2)
        result = _check_oauth_result(code_verifier)
        if result:
            print(f" \033[92mv\033[0m")
            return result
        print(".", end="", flush=True)

    print(f" \033[91mx\033[0m")
    return None


# ── Public API ────────────────────────────────────────────────────

def ensure_api_key() -> str | None:
    """
    Ensure an API key is available. Checks in order:
    1. OPENROUTER_API_KEY env var
    2. ~/.neuroncli/config.json
    3. OAuth PKCE (background) + manual paste (foreground) — in parallel

    Returns the API key or None if all methods fail.
    """
    # Check env var
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key

    # Check local config
    stored_key = get_stored_api_key()
    if stored_key:
        return stored_key

    # First run — welcome message
    print("\n  \033[96m\033[1m╔══════════════════════════════════════════════════╗")
    print("  ║  Welcome to NeuronCLI!                            ║")
    print("  ║  Free AI coding agent — one-time setup below.     ║")
    print("  ╚══════════════════════════════════════════════════╝\033[0m")

    return run_oauth_flow()

