"""
Automated helper to generate Google Drive refresh tokens for all 4 storage nodes.
Usage: python get_gdrive_tokens.py
"""
import sys
import json
import requests
import webbrowser
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

REDIRECT_PORT = 8080
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        
        # Ignore favicon or random browser noise requests
        if parsed.path.endswith("favicon.ico"):
            self.send_response(404)
            self.end_headers()
            return

        if "code" in query:
            auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style='font-family: sans-serif; text-align: center; padding-top: 50px; background: #1e1e2e; color: #a6e3a1;'>
                    <h1>&#10004; Account Authorized Successfully!</h1>
                    <p style='color: #cdd6f4;'>You can close this tab and return to your terminal.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def get_token_for_node(node_num: int, client_id: str, client_secret: str) -> str:
    global auth_code
    auth_code = None
    
    scope = "https://www.googleapis.com/auth/drive.file"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    print(f"\n────────────────────────────────────────────────────────────")
    print(f"  🔑 AUTHORIZING GOOGLE DRIVE ACCOUNT #{node_num} (Node-{node_num})")
    print(f"────────────────────────────────────────────────────────────")
    input(f"  --> Press Enter when ready to log in with Google Account #{node_num}... ")

    print(f"  Opening browser window for Account #{node_num}...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", REDIRECT_PORT), OAuthHandler)
    
    # Wait specifically until auth_code is received (ignoring favicon noise)
    timeout_start = time.time()
    while auth_code is None:
        server.handle_request()
        if time.time() - timeout_start > 180:  # 3 minute timeout
            print("  ✗ Request timed out waiting for browser sign-in.")
            server.server_close()
            sys.exit(1)

    server.server_close()

    print("  Exchanging authorization code for refresh token...")
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })

    if resp.status_code != 200:
        print(f"  ✗ Token exchange failed: {resp.text}")
        sys.exit(1)

    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print("  ✗ No refresh token returned. Make sure to click 'Allow' on consent screen.")
        sys.exit(1)

    print(f"  ✓ Account #{node_num} Authorized Successfully!")
    return refresh_token


def main():
    print("=" * 60)
    print("  UTIM Marketplace — Google Drive 4-Node Token Generator")
    print("=" * 60)

    client_id = input("\n  Enter GDRIVE_CLIENT_ID: ").strip()
    client_secret = input("  Enter GDRIVE_CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        print("  ✗ Client ID and Client Secret are required.")
        sys.exit(1)

    tokens = {}
    for node in range(1, 5):
        tokens[f"GDRIVE_NODE{node}_REFRESH_TOKEN"] = get_token_for_node(node, client_id, client_secret)

    print("\n" + "=" * 60)
    print("  🎉 ALL 4 NODES AUTHORIZED SUCCESSFULLY!")
    print("=" * 60)
    print("\nAdd these lines to your server .env file:\n")
    print(f"GDRIVE_CLIENT_ID={client_id}")
    print(f"GDRIVE_CLIENT_SECRET={client_secret}")
    for k, v in tokens.items():
        print(f"{k}={v}")

    # Optionally write to .env
    with open(".env", "a", encoding="utf-8") as f:
        f.write(f"\nGDRIVE_CLIENT_ID={client_id}\n")
        f.write(f"GDRIVE_CLIENT_SECRET={client_secret}\n")
        for k, v in tokens.items():
            f.write(f"{k}={v}\n")
    print("\n  ✓ All 4 tokens saved to .env file successfully!")

if __name__ == "__main__":
    main()
