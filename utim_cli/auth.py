"""
UTIM CLI — Authentication

Flow:
  1. Open browser → Firebase auth page (hosted by the UTIM web app or
     directly via firebaseui / identitytoolkit redirect)
  2. After sign-in, Firebase redirects to localhost:31415/auth/callback
     with ?token=<firebase_id_token>&email=<email>&uid=<uid>&name=<name>
  3. CLI POSTs the Firebase ID token to the Railway server
     POST https://api.utim.dev/auth/firebase-login
  4. Server verifies the token, provisions the user, returns api_key
  5. CLI stores api_key in local config — used as X-API-Key forever after
"""
from __future__ import annotations

import http.server
import socketserver
import threading
import urllib.parse
import webbrowser
from typing import Optional

import os
import requests
from rich.console import Console

from .config import config

_IS_TEST = False

# ── Constants ─────────────────────────────────────────────────────────────────

PURPLE = "#cba6f7"
BLUE   = "#42bcf5"
YELLOW = "#f9e2af"

# Production server — all auth calls go here
SERVER_URL = os.environ.get("UTIM_SERVER_URL", "https://api.utim.dev")
WEB_URL = os.environ.get("UTIM_WEB_URL", "https://utim.dev")

# Firebase project config (public — safe to embed in CLI)
FIREBASE_PROJECT_ID  = "u-t-i-m-39c26"
FIREBASE_API_KEY     = "AIzaSyAV-L3jY6dS3wXMMNGnYnPTX3IuqBFqK4E"
FIREBASE_AUTH_DOMAIN = "u-t-i-m-39c26.firebaseapp.com"

console = Console()

# ── Callback HTTP handler ─────────────────────────────────────────────────────

class _AuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny local server that catches the Firebase redirect and closes itself."""

    # Shared state written by do_GET, read by login()
    received: dict = {}

    def log_message(self, *args):  # silence stdlib HTTP logs
        pass

    def do_GET(self):
        query  = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        token = params.get("token",  [None])[0]
        email = params.get("email",  [None])[0]
        uid   = params.get("uid",    [None])[0]
        name  = params.get("name",   [None])[0]

        if token and email:
            _AuthCallbackHandler.received = {
                "token": token,
                "email": email,
                "uid":   uid or "",
                "name":  name or email.split("@")[0],
            }
            self._send_html(_SUCCESS_HTML)
        else:
            self._send_html(_FAILURE_HTML, status=400)

        # Shut down the local server from a background thread
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _send_html(self, body: str, status: int = 200):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


# ── Public login() function ───────────────────────────────────────────────────

def login(restart: bool = True) -> None:
    """
    Sign in via the Device Authorization Flow.
    
    1. CLI requests a one-time code from the server.
    2. CLI displays a short URL + code and copies the URL to the clipboard on Termux.
    3. User visits the URL, signs in via Firebase, clicks Authorize.
    4. Once authorized, user presses Enter in CLI to verify (or pastes their API Key).
    """
    import sys
    import time
    import requests
    import os as _os
    import subprocess as _sub


    def raw_print(*args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        msg = sep.join(str(arg) for arg in args) + end
        sys.__stdout__.write(msg)
        sys.__stdout__.flush()

    def restart_process():
        if "pytest" not in sys.argv[0] and "py.test" not in sys.argv[0] and "PYTEST_CURRENT_TEST" not in _os.environ:
            args = []
            for arg in sys.argv:
                if " " in arg and not (arg.startswith('"') and arg.endswith('"')):
                    args.append(f'"{arg}"')
                else:
                    args.append(arg)
            
            if args[0].strip('"').lower().endswith("utim.py"):
                cmd = [sys.executable, "-m", "utim_cli.utim"] + args[1:]
            else:
                cmd = [args[0].strip('"')] + args[1:]

            time.sleep(0.5)

            # Clear current terminal screen & scrollback buffer
            if _os.name == "nt":
                _os.system("cls")
            else:
                sys.__stdout__.write("\x1b[2J\x1b[3J\x1b[H")
                sys.__stdout__.flush()

            # Restart UTIM right in the current terminal window
            if _os.name == "nt":
                try:
                    code = _sub.call(cmd)
                    sys.exit(code)
                except Exception:
                    pass
            try:
                _os.execv(cmd[0], cmd)
            except Exception:
                sys.exit(0)

    # Sleep briefly to ensure prompt_toolkit's terminal-suspension sequences are flushed
    time.sleep(0.3)

    # ANSI formatting
    PURPLE = "\033[1;35m"
    BLUE   = "\033[1;34m"
    YELLOW = "\033[1;33m"
    GREEN  = "\033[1;32m"
    DIM    = "\033[2m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    _is_termux = (
        (_os.environ.get("PREFIX", "").find("com.termux") != -1) or
        _os.path.exists("/data/data/com.termux")
    )

    raw_print(f"\n  {PURPLE}UTIM CLI — Secure Device Sign-In{RESET}\n")
    raw_print(f"  {DIM}Requesting authorization code from UTIM server…{RESET}")

    # Step 1 — request a device code from the server
    try:
        resp = requests.post(
            f"{SERVER_URL}/auth/device/request",
            timeout=15,
        )
        if resp.status_code != 200:
            raw_print(f"\n  \033[1;31m✗ Server error (HTTP {resp.status_code}). Please try again.\033[0m\n")
            return
        data = resp.json()
    except Exception as exc:
        raw_print(f"\n  \033[1;31m✗ Could not reach UTIM server: {exc}\033[0m\n")
        return

    device_code  = data["device_code"]
    user_code    = data["user_code"]
    verify_url   = data["verify_url"]
    expires_in   = data.get("expires_in", 600)

    # Copy to clipboard on Termux/Android
    clipboard_notice = ""
    if _is_termux:
        try:
            _sub.run(
                ["termux-clipboard-set", verify_url],
                timeout=3, check=False,
                stdout=_sub.DEVNULL, stderr=_sub.DEVNULL,
            )
            clipboard_notice = f"  {GREEN}✓ Sign-in link copied to clipboard!{RESET}\n"
        except Exception:
            pass

    # Print compact Termux/Android friendly instructions
    raw_print(f"\n  {BOLD}🔑 Device Sign-In Required:{RESET}")
    raw_print(f"  1. Open link: {BLUE}{verify_url}{RESET}")
    if clipboard_notice:
        raw_print(f"     {clipboard_notice.strip()}")
    raw_print(f"  2. Enter code: {YELLOW}{BOLD}{user_code}{RESET} (if prompted)\n")

    # Step 2 — Interactive verification prompt loop
    while True:
        try:
            user_input = input("  Press Enter to check status (or paste API Key directly, 'q' to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            raw_print(f"\n\n  {YELLOW}Cancelled.{RESET}\n")
            return

        if user_input.lower() == 'q':
            raw_print(f"\n  {YELLOW}Cancelled.{RESET}\n")
            return

        # Case A: User pasted a standard API Key directly
        if user_input.startswith("sk-") or len(user_input) > 20:
            api_key = user_input
            raw_print(f"\n  {DIM}Validating API key...{RESET}")
            try:
                val_resp = requests.get(
                    f"{SERVER_URL}/api/user-plan",
                    headers={"X-API-Key": api_key},
                    timeout=15
                )
                if val_resp.status_code == 200:
                    body = val_resp.json()
                    config.set("token", "device_flow")
                    config.set("email", body.get("email", "local@utim.dev"))
                    config.set("uid", body.get("user_id", ""))
                    config.set("firebase_uid", body.get("firebase_uid", ""))
                    config.set("name", body.get("display_name") or body.get("email", "").split("@")[0])
                    config.set("api_key", api_key)
                    raw_print(f"\n  {GREEN}✓ Authorized! Welcome back.{RESET}")
                    raw_print(f"  Signed in as {BLUE}{body.get('email', '')}{RESET}\n")
                    
                    if restart:
                        restart_process()
                    return
                else:
                    raw_print(f"\n  \033[1;31m✗ Invalid API Key. Please try again.\033[0m\n")
            except Exception as e:
                raw_print(f"\n  \033[1;31m✗ Could not validate API key: {e}\033[0m\n")
            continue

        # Case B: User pressed Enter to check/verify browser sign-in status
        raw_print(f"  {DIM}Verifying authorization status...{RESET}")
        try:
            pr = requests.get(
                f"{SERVER_URL}/auth/device/poll",
                params={"device_code": device_code},
                timeout=10,
            )
            if pr.status_code == 200:
                body = pr.json()
                status = body.get("status")
                if status == "authorized":
                    config.set("token", "device_flow")
                    config.set("email", body.get("email", ""))
                    config.set("uid", body.get("user_id", ""))
                    config.set("firebase_uid", body.get("firebase_uid", ""))
                    config.set("name", body.get("display_name") or body.get("email", "").split("@")[0])
                    config.set("api_key", body["api_key"])
                    
                    raw_print(f"\n  {GREEN}✓ Authorized! Welcome back.{RESET}")
                    raw_print(f"  Signed in as {BLUE}{body.get('email', '')}{RESET}")
                    raw_print(f"  Credits: {body.get('credits', 0):,.0f} UTIM\n")
                    
                    if restart:
                        restart_process()
                    return
                else:
                    raw_print(f"  {YELLOW}⚠  Authorization pending. Please complete it at: {BLUE}{verify_url}{RESET}")
            else:
                raw_print(f"\n  \033[1;31m✗ Verification failed (HTTP {pr.status_code}). Please try again.\033[0m\n")
        except Exception as e:
            raw_print(f"\n  \033[1;31m✗ Error during verification: {e}\033[0m\n")


# ── HTML templates ────────────────────────────────────────────────────────────

_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>UTIM CLI — Signed In</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#0d1117;color:#c9d1d9;display:flex;align-items:center;
         justify-content:center;height:100vh}
    .card{background:#161b22;border:1px solid #30363d;border-radius:12px;
          padding:48px 40px;max-width:420px;text-align:center;
          box-shadow:0 16px 48px rgba(0,0,0,0.6)}
    .icon{color:#3fb950;margin-bottom:24px}
    .icon svg{width:72px;height:72px}
    h1{color:#58a6ff;font-size:1.5rem;margin-bottom:12px}
    p{color:#8b949e;line-height:1.6;font-size:0.95rem}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    </div>
    <h1>Signed in successfully!</h1>
    <p>You're authenticated with UTIM CLI.<br>You can close this tab and return to your terminal.</p>
  </div>
</body>
</html>"""

_FAILURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>UTIM CLI — Auth Failed</title>
  <style>
    body{font-family:system-ui,sans-serif;background:#0d1117;color:#c9d1d9;
         display:flex;align-items:center;justify-content:center;height:100vh}
    .card{background:#161b22;border:1px solid #f85149;border-radius:12px;
          padding:48px 40px;max-width:420px;text-align:center}
    h1{color:#f85149;margin-bottom:12px}
    p{color:#8b949e;line-height:1.6}
  </style>
</head>
<body>
  <div class="card">
    <h1>Authentication Failed</h1>
    <p>Missing token or email. Please try signing in again.</p>
  </div>
</body>
</html>"""
