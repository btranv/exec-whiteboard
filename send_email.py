#!/usr/bin/env python3
"""Send an email via Gmail API (OAuth)."""
import base64
import sys
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config

HERE = Path(__file__).parent
TOKEN = HERE / ".gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def _service():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json())
        else:
            raise RuntimeError("Gmail token invalid; rerun oauth_setup.py")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def send(to_addr: str, subject: str, body_text: str, body_html: str | None = None,
         thread_id: str | None = None, in_reply_to: str | None = None,
         references: str | None = None):
    msg = EmailMessage()
    msg["From"] = config.sender_email
    msg["To"] = to_addr
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    svc = _service()
    sent = svc.users().messages().send(userId="me", body=body).execute()
    print(f"Sent id={sent.get('id')} thread={sent.get('threadId')} subject={subject!r}",
          file=sys.stderr)
    return sent

if __name__ == "__main__":
    send(config.recipient_email, sys.argv[1], sys.argv[2])
