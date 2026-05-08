#!/usr/bin/env python3
"""Generate a real-time chief-of-staff response to a single user reply, send threaded."""
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import action_log_doc
import config
import doc_blocks
import fetch_board
import google_clients
import send_email
from board_model import load_sections

HERE = Path(__file__).parent
KEY_PATH = HERE / ".anthropic_key"
TZ = ZoneInfo("America/New_York")
MODEL = "claude-sonnet-4-6"

SYSTEM_TMPL = """You are {agent_name} — the user's chief of staff.

{context}

The user just replied to a digest email. Your job:

DEFAULT BEHAVIOR — acknowledge + track. Most replies need 1-2 sentences. Confirm what you heard, log it, done.

WHEN YOU DO SAY MORE, lean ACTION-ORIENTED:
- "How does this stack against X?" (prioritization help)
- "I'd push X first because [one-sentence reason] — want me to deprioritize Y?"
- "Recommend [specific action]. Reason: [one sentence]."
- Surface trade-offs when there's a real one. Don't manufacture them.

DO NOT:
- Ask obvious procedural questions whose answer is inferable from context.
- Ask questions whose answers don't change a next action.
- Ask the user to re-state things they already told you.
- Re-list the morning digest. They have it.
- Add corporate filler ("Great work!", "Awesome update!"). No emojis. No sign-off.
- Action-ize venting. If they're venting, just acknowledge.

IF YOU MUST ASK A QUESTION, the bar is HIGH:
- Will the answer change what I recommend?
- Is it something only the user can tell me (not inferable from board/doc/common sense)?
If both yes, ask — one question, specific. If not, make the smartest default assumption and say so.

INFERENCE DEFAULTS:
{inference_rules}

You have access to the strategic whiteboard, the action log, and the digest you just sent. Use them when context is needed."""

def _call_claude(system: str, user: str) -> str:
    api_key = KEY_PATH.read_text().strip()
    payload = {
        "model": MODEL,
        "max_tokens": 800,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    return resp["content"][0]["text"].strip()

def respond_to(reply: dict) -> str:
    fetch_board.main()
    sections = load_sections()
    board_text = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
    doc_state = action_log_doc.read_full()

    system = SYSTEM_TMPL.format(
        agent_name=config.agent_name,
        context=config.business_context,
        inference_rules=config.inference_rules,
    )
    user = (
        f"User reply (subject: {reply['subject']!r}):\n\n"
        f"{reply['body']}\n\n"
        f"---\n\n"
        f"## Action Log (current state)\n{doc_state}\n\n"
        f"---\n\n"
        f"## Strategic whiteboard\n{board_text}\n\n"
        f"---\n\n"
        f"Write your reply now. Plain text. Email-style threading."
    )
    return _call_claude(system, user)

def _wrap_html(text: str) -> str:
    safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br>"))
    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
        'font-size:15px;color:#1a1a1a;line-height:1.55;max-width:560px;">'
        f"{safe}</div>"
    )

def _log_to_doc(reply: dict, response_text: str):
    when = datetime.now(TZ).strftime("%Y-%m-%d %a · %-I:%M %p %Z")
    blocks = [
        doc_blocks._b(f"{when}  ·  CONVERSATION", "DATELINE"),
        doc_blocks._b(f"{config.user_first_name}: {reply['body'].strip()}", "BODY"),
        doc_blocks._b(f"{config.agent_name}: {response_text.strip()}", "BODY"),
    ]
    doc_id = action_log_doc.get_or_create_doc_id()
    _, _, hist_start = action_log_doc._find_section_indexes(doc_id)
    action_log_doc._insert_blocks_and_style(doc_id, hist_start, blocks)

def handle_one(reply: dict):
    response_text = respond_to(reply)
    subject = reply["subject"]
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject
    send_email.send(
        config.recipient_email,
        subject,
        response_text,
        body_html=_wrap_html(response_text),
        thread_id=reply["thread_id"],
        in_reply_to=reply["message_id"],
        references=reply["references"],
    )
    _log_to_doc(reply, response_text)
    return response_text
