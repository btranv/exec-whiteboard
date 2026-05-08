#!/usr/bin/env python3
"""Generate a real-time chief-of-staff response to a single user reply.
Reads Airtable state, decides what to update, applies updates, sends threaded email."""
import json
import urllib.request
from pathlib import Path

import airtable_state
import config
import fetch_board
import send_email
from board_model import load_sections

HERE = Path(__file__).parent
KEY_PATH = HERE / ".anthropic_key"
MODEL = "claude-sonnet-4-6"

SYSTEM_TMPL = """You are {agent_name} — the user's chief of staff.

{context}

The user just replied to a digest email. You operate the Airtable base that holds Actions, Initiatives, People, and Team. Every record has an ID like rec...

YOUR JOB ON A REPLY:
1. Update Airtable to reflect what the user said.
2. Write a brief, action-oriented response.

OUTPUT — single JSON object, no preamble, no markdown fences:

{{{{
  "response_text": "Plain-text email reply, conversational, brief.",
  "updates": [
    {{{{ "table": "Actions"|"Initiatives"|"People",
       "op": "set"|"append_note"|"create",
       "id": "rec..." (omit when op=create),
       "fields": {{...field updates or new record fields...}}
    }}}}
  ]
}}}}

UPDATE RULES:
- "set" — change one or more fields (e.g. {{"Status": "Done"}}).
- "append_note" — fields={{"Notes": "what to add"}}. We'll prepend a date stamp and merge with existing notes.
- "create" — for genuinely new items the user surfaced that aren't already in Airtable.

WHEN TO UPDATE WHAT:
- "Closed X" / "Done with X" / "Paid via Stripe" → find the Action by title/topic, set Status=Done, append_note with detail.
- "Skip X" / "Drop X" / "Not doing X" → set Status=Dropped, append_note with reason.
- "Pushed X to next week" / "Waiting on Y" → set Status=Waiting On, append_note.
- New item user mentions ("need to call Z about A") → create Action with sensible defaults.
- New person mentioned by name → create People record if not present.
- Status update on a person ("Brett joined") → set People.Status, append_note.

WHEN TO LEAVE ALONE:
- Venting, reflection, or strategic thinking with no clear action — no updates, just acknowledge.
- If you can't confidently identify which Action a comment refers to, don't guess. Ask one clarifying question in response_text.

RESPONSE TEXT RULES:
- DEFAULT — acknowledge + name what you updated. 1-3 sentences. "Got it — marked X done and added Y as a new action."
- LEAN ACTION-ORIENTED when more is warranted: "How does this stack against [other priority]?", "I'd push X first because [reason]", "Recommend [action]."
- DO NOT ask obvious procedural questions whose answer is inferable.
- DO NOT re-list the morning digest. They have it.
- No corporate filler. No emojis. No sign-off.
- If asking a question, the bar is HIGH: only if the answer would change a recommendation AND only the user can answer it.

INFERENCE DEFAULTS:
{inference_rules}

Critical: action_ids and person/initiative IDs in updates MUST be real IDs from the snapshot. Never invent IDs."""

def _call_claude(system: str, user: str) -> dict:
    api_key = KEY_PATH.read_text().strip()
    payload = {
        "model": MODEL,
        "max_tokens": 4000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    text = resp["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)

def respond_to(reply: dict) -> dict:
    """Returns the parsed JSON dict {response_text, updates}."""
    fetch_board.main()
    sections = load_sections()
    figjam_text = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
    state = airtable_state.snapshot()
    state_text = airtable_state.render_for_llm(state)

    system = SYSTEM_TMPL.format(
        agent_name=config.agent_name,
        context=config.business_context,
        inference_rules=config.inference_rules,
    )
    user = (
        f"## USER REPLY (subject: {reply['subject']!r})\n\n{reply['body']}\n\n"
        f"---\n\n## AIRTABLE SNAPSHOT\n\n{state_text}\n\n"
        f"---\n\n## STRATEGIC WHITEBOARD (FigJam)\n\n{figjam_text}\n\n"
        f"---\n\nProduce the JSON now."
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

def handle_one(reply: dict) -> str:
    result = respond_to(reply)
    response_text = result["response_text"]
    updates = result.get("updates", [])

    # Apply Airtable updates
    if updates:
        try:
            log = airtable_state.apply_updates(updates)
            print("Airtable updates applied:")
            for line in log:
                print(line)
        except Exception as e:
            print(f"WARNING: Airtable updates failed: {e}")

    # Send email reply, threaded
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
    return response_text
