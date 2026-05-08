#!/usr/bin/env python3
"""Read incoming user replies + mark them as processed."""
import base64
import re
from pathlib import Path

import config
import google_clients

HERE = Path(__file__).parent
PROCESSED_LABEL_NAME = "neil/digest-reply-processed"

def _ensure_label() -> str:
    if config.processed_label_id:
        return config.processed_label_id
    svc = google_clients.gmail()
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for l in labels:
        if l["name"] == PROCESSED_LABEL_NAME:
            print(f"WARNING: Found existing label id {l['id']}. "
                  f"Add to .sector_config.json as 'processed_label_id' to persist.")
            return l["id"]
    new = svc.users().labels().create(
        userId="me",
        body={"name": PROCESSED_LABEL_NAME, "labelListVisibility": "labelShow",
              "messageListVisibility": "show"},
    ).execute()
    print(f"WARNING: Created new label id {new['id']}. "
          f"Add to .sector_config.json as 'processed_label_id' to persist.")
    return new["id"]

def _strip_quoted(text: str) -> str:
    text = re.split(r"\nOn .+ wrote:\s*\n", text, maxsplit=1)[0]
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()

def _payload_text(payload) -> str:
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if mime == "text/plain" and data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        t = _payload_text(part)
        if t:
            return t
    if mime == "text/html" and data:
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", "", html)
    return ""

def fetch_unprocessed(mark_processed: bool = True) -> list[dict]:
    label_id = _ensure_label()
    svc = google_clients.gmail()
    query = (
        f"from:{config.recipient_email} to:{config.sender_email} "
        f"-label:{PROCESSED_LABEL_NAME}"
    )
    res = svc.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = res.get("messages", [])
    out = []
    to_label = []
    for m in messages:
        msg = svc.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        text = _payload_text(msg["payload"])
        text = _strip_quoted(text)
        if text:
            out.append({
                "id": m["id"],
                "thread_id": msg.get("threadId"),
                "message_id": headers.get("message-id", ""),
                "references": headers.get("references", "") or headers.get("message-id", ""),
                "subject": headers.get("subject", "(no subject)"),
                "date": headers.get("date", ""),
                "body": text,
            })
        to_label.append(m["id"])
    if to_label and mark_processed:
        svc.users().messages().batchModify(
            userId="me",
            body={"ids": to_label, "addLabelIds": [label_id]},
        ).execute()
    return out

def mark_processed(message_ids: list[str]):
    if not message_ids:
        return
    label_id = _ensure_label()
    svc = google_clients.gmail()
    svc.users().messages().batchModify(
        userId="me",
        body={"ids": message_ids, "addLabelIds": [label_id]},
    ).execute()

def summarize_for_log(replies: list[dict]) -> str:
    if not replies:
        return ""
    parts = []
    for r in replies:
        parts.append(f"  • {r['date']} — re: {r['subject']}")
        for line in r["body"].splitlines():
            line = line.strip()
            if line:
                parts.append(f"      {line}")
    return "\n".join(parts)
