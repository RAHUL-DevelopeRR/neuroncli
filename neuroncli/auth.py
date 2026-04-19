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
    Run the full OAuth PKCE flow:
    1. Generate PKCE challenge
    2. Open browser to OpenRouter auth
    3. Start localhost server to catch redirect
    4. Exchange code for API key
    5. Store key locally

    Returns the API key on success, None on failure.
    """
    # Reset
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

    # Start callback server in background
    try:
        server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _OAuthCallbackHandler)
    except OSError:
        # Port in use — another instance is running
        print(f"\n  \033[91m[X] Port {CALLBACK_PORT} is in use. Close other instances first.\033[0m")
        return None
    server.timeout = 120  # 2 minute timeout

    print("\n  \033[96m\033[1m[AUTH]\033[0m Opening browser for OpenRouter login...")
    print(f"  \033[90mIf browser doesn't open, visit:\033[0m")
    print(f"  \033[90m{auth_url[:80]}...\033[0m\n")

    # Open browser
    try:
        webbrowser.open(auth_url)
    except Exception:
        print("  \033[90m(Browser could not be opened. Use the URL above.)\033[0m")

    print("  \033[93mWaiting for authentication...\033[0m", end="", flush=True)

    # Wait for the callback (blocks until request or timeout)
    try:
        server.handle_request()  # Handles exactly one request
    except Exception:
        pass
    finally:
        server.server_close()

    code = _OAuthCallbackHandler.auth_code
    if not code:
        print(f"\n  \033[91m[X] OAuth timed out or failed.\033[0m")
        return _manual_key_fallback()

    print(f" \033[92mv\033[0m")
    print("  \033[96mExchanging code for API key...\033[0m", end="", flush=True)

    # Exchange code for key
    try:
        api_key = _exchange_code_for_key(code, code_verifier)
    except RuntimeError as e:
        print(f"\n  \033[91m[X] {e}\033[0m")
        return _manual_key_fallback()

    # Store
    store_api_key(api_key)
    print(f" \033[92mv\033[0m")
    print(f"  \033[92m\033[1m[OK] API key saved to {CONFIG_FILE}\033[0m\n")

    return api_key


def _manual_key_fallback() -> str | None:
    """Fallback: let user manually paste their OpenRouter API key."""
    print(f"\n  \033[96m\033[1m[MANUAL SETUP]\033[0m")
    print(f"  \033[90mOAuth didn't work. You can paste your key instead:\033[0m")
    print(f"  \033[90m1. Go to: https://openrouter.ai/settings/keys\033[0m")
    print(f"  \033[90m2. Click 'Create Key'\033[0m")
    print(f"  \033[90m3. Copy the key (starts with sk-or-...)\033[0m\n")

    try:
        key = input("  \033[93mPaste your API key (or Enter to skip): \033[0m").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not key:
        print(f"\n  \033[90mSkipped. Using Ollama fallback if available.\033[0m\n")
        return None

    if key.startswith("sk-or-") or key.startswith("sk-"):
        store_api_key(key)
        print(f"  \033[92m\033[1m[OK] API key saved to {CONFIG_FILE}\033[0m\n")
        return key
    else:
        print(f"  \033[91m[X] Invalid key format. Expected 'sk-or-...' \033[0m")
        print(f"  \033[90mGet one at: https://openrouter.ai/settings/keys\033[0m\n")
        return None


# ── Public API ────────────────────────────────────────────────────

def ensure_api_key() -> str | None:
    """
    Ensure an API key is available. Checks in order:
    1. OPENROUTER_API_KEY env var
    2. ~/.neuroncli/config.json
    3. Interactive OAuth PKCE flow (first-run)
    4. Manual key paste (fallback if OAuth fails)

    Returns the API key or None if all methods fail.
    """
    # Check env var first
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key

    # Check local config
    stored_key = get_stored_api_key()
    if stored_key:
        return stored_key

    # First run — interactive OAuth
    print("\n  \033[96m\033[1m╔════════════════════════════════════════════════╗")
    print("  ║  Welcome to NeuronCLI!                         ║")
    print("  ║  Let's connect your free OpenRouter account.   ║")
    print("  ║  This only happens once.                       ║")
    print("  ╚════════════════════════════════════════════════╝\033[0m")

    return run_oauth_flow()

