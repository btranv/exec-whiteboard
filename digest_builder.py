#!/usr/bin/env python3
"""Call Claude API for a structured digest (JSON), then render via render_email.py."""
import json
import sys
import urllib.request
from pathlib import Path

import config

HERE = Path(__file__).parent
KEY_PATH = HERE / ".anthropic_key"
MODEL = "claude-sonnet-4-6"

MORNING_SYSTEM_TMPL = """You are the user's chief of staff. {context}

Today is {today}. Generate a MORNING digest.

You MUST output a single valid JSON object, nothing else (no markdown fences, no preamble). Schema:

{{{{
  "headline": "ONE sentence — the single most important thing about today and why. Punchy, specific, no hedging.",
  "today": [
    {{{{
      "title": "Verb-led action title (~6-10 words).",
      "body": "2-3 sentences. The actual instruction. Include specific names, numbers, deadlines. The user should be able to act without re-reading the board.",
      "tag": "Optional short tag in CAPS (e.g. 'BY NOON', 'BURN-CRITICAL', 'DECAY RISK', 'EVENT'). Empty string if none."
    }}}}
  ],
  "questions": [
    "Short question the user needs to answer to unblock prioritization. 1-3 questions max. Empty array if none."
  ],
  "radar": [
    "One-line item the user should be aware of but NOT act on today. Up to 5. Each starts with the topic."
  ]
}}}}

PRIORITIZATION:
1. Burn-rate critical (hit the milestone in the business context above).
2. Time-boxed events with near deadlines (look for event sections in the board).
3. Relationship decay (warm contacts going cold).
4. The user's own Growth Action Items section if present.
5. Strategy items only if nothing urgent.

EXACTLY 3 items in "today". No more, no less."""

EVENING_SYSTEM_TMPL = """You are the user's chief of staff. {context}

Today is {today}. Generate an EOD WRAP — the user reads this in the evening to close out the day.

This is REFLECTIVE, not directive. The morning email was the marching orders. The day's conversation has happened (you've been chatting with the user via reply throughout the day). Now look backward + set up tomorrow.

You MUST output a single valid JSON object, nothing else (no markdown fences, no preamble). Schema:

{{{{
  "headline": "ONE sentence reflecting how the day landed. Honest, not cheerleading.",
  "closed_today": [
    "Specific item the user closed today (from replies/conversation). 1-5 items. Empty if nothing closed."
  ],
  "carried_over": [
    {{{{
      "title": "Verb-led action that didn't close",
      "body": "1-2 sentences. Why it didn't close + what the next move is."
    }}}}
  ],
  "surfaced_today": [
    "New items that came up in today's conversation that aren't already on the board. Bullet form. Empty if nothing new."
  ],
  "sleep_on_it": [
    "1-2 strategic questions to percolate overnight. Often becomes tomorrow's morning headline."
  ]
}}}}

PRIORITIZATION (for ordering within sections): burn-rate critical first, then time-boxed events, then decay-risk relationships, then Growth Action Items.

If the user sent NO replies today, base "closed_today" on inference from doc/board state. If you can't honestly say anything closed, return empty array — don't fabricate."""

def build(slot: str, board_text: str, today: str) -> dict:
    tmpl = MORNING_SYSTEM_TMPL if slot == "morning" else EVENING_SYSTEM_TMPL
    system = tmpl.format(context=config.business_context, today=today)
    user_msg = f"Current state of the strategic whiteboard:\n\n{board_text}\n\nGenerate the {slot} digest JSON now."
    api_key = KEY_PATH.read_text().strip()
    payload = {
        "model": MODEL,
        "max_tokens": 3000,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
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
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    text = resp["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("\n", 1)[0]
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)

if __name__ == "__main__":
    slot = sys.argv[1]
    board = (HERE / "board_full.txt").read_text()
    print(json.dumps(build(slot, board, "today"), indent=2))
