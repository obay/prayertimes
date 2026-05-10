#!/usr/bin/env python3
"""One-time OAuth setup for the prayertimes workflow.

Usage:
    python bootstrap_oauth.py /path/to/credentials.json

`credentials.json` is downloaded from Google Cloud Console after creating
an OAuth 2.0 Client ID of type "Desktop app". This script opens a browser
to grant calendar access, then prints the three secrets you add to GitHub
Actions: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN.
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: bootstrap_oauth.py /path/to/credentials.json", file=sys.stderr)
        return 2
    creds_path = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        print("ERROR: no refresh_token returned. Re-run after revoking previous grants at",
              "https://myaccount.google.com/permissions", file=sys.stderr)
        return 1

    with open(creds_path) as f:
        cfg = json.load(f)
    section = cfg.get("installed") or cfg.get("web") or {}

    bar = "=" * 64
    print()
    print(bar)
    print("SUCCESS — add these as GitHub Actions repository secrets:")
    print(bar)
    print(f"GOOGLE_CLIENT_ID={section.get('client_id', '')}")
    print(f"GOOGLE_CLIENT_SECRET={section.get('client_secret', '')}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
