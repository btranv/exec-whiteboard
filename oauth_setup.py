#!/usr/bin/env python3
"""One-time: open a browser, sign in to the sender Gmail account, save refresh token.

Run from the venv:
    /Users/bvt/exec-whiteboard/.venv/bin/python oauth_setup.py
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).parent
CREDS = HERE / ".gcp_credentials.json"
TOKEN = HERE / ".gmail_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",  # read replies, label them
    "https://www.googleapis.com/auth/drive.file",    # create/access only files this app made
    "https://www.googleapis.com/auth/documents",     # read/write doc body
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",  # force refresh_token to be issued
        authorization_prompt_message="Opening browser. Sign in as the configured sender and approve.",
        success_message="Done. You can close this tab and return to terminal.",
        open_browser=True,
    )
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    print(f"Saved token to {TOKEN}")
    print(f"Refresh token present: {bool(creds.refresh_token)}")

if __name__ == "__main__":
    main()
