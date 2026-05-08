#!/usr/bin/env python3
"""Shared Google API service builders (Gmail/Drive/Docs)."""
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

HERE = Path(__file__).parent
TOKEN = HERE / ".gmail_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

def creds():
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not c.valid:
        if c.expired and c.refresh_token:
            c.refresh(Request())
            TOKEN.write_text(c.to_json())
        else:
            raise RuntimeError("Token invalid; rerun oauth_setup.py")
    return c

def gmail():
    return build("gmail", "v1", credentials=creds(), cache_discovery=False)

def drive():
    return build("drive", "v3", credentials=creds(), cache_discovery=False)

def docs():
    return build("docs", "v1", credentials=creds(), cache_discovery=False)
