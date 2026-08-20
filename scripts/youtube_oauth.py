"""One-time YouTube OAuth helper — obtain a refresh token.

Run once after setting YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET. It performs the
OAuth flow and prints a refresh token to paste into your `.env` / GitHub Secrets.

We never store your Google password — only the OAuth refresh token, which you can
revoke at any time from your Google Account security settings.
"""

from __future__ import annotations

import sys

from app.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main() -> int:
    s = get_settings()
    if not (s.youtube_client_id and s.youtube_client_secret):
        print("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET first (see SETUP.md Part 6).")
        return 1
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except Exception:
        print("Install the YouTube extras first:  pip install -e '.[youtube]'")
        return 1

    client_config = {
        "installed": {
            "client_id": s.youtube_client_id,
            "client_secret": s.youtube_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    # Console flow: prints a URL, you paste back the code.
    creds = flow.run_local_server(port=0) if _can_open_browser() else flow.run_console()
    if not creds.refresh_token:
        print("No refresh token returned. Remove the app's access under your Google "
              "Account and try again (this forces a fresh consent).")
        return 1
    print("\n=== SUCCESS ===")
    print("Add this to your .env / GitHub Secrets (keep it secret):\n")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    return 0


def _can_open_browser() -> bool:
    import os

    return bool(os.environ.get("DISPLAY")) or sys.platform == "darwin"


if __name__ == "__main__":
    sys.exit(main())
