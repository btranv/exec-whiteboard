#!/usr/bin/env python3
"""Call Claude API for a structured digest. Reads Airtable state + FigJam input.

Output schemas reference Airtable record IDs so the email can deep-link to the
original action and the LLM can later be asked to update it."""
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

You're choosing from existing Actions in the user's Airtable. Each has an ID like rec...

You MUST output a single valid JSON object, nothing else (no markdown fences, no preamble):

{{{{
  "headline": "ONE sentence — the single most important thing about today and why. Punchy, specific, no hedging.",
  "today": [
    {{{{
      "action_id": "rec...",                 // existing Action being surfaced
      "title": "Verb-led title (~6-10 words). May reword the source title for clarity.",
      "body": "2-3 sentences of action instruction. Names, numbers, deadlines.",
      "tag": "Optional CAPS tag (BY NOON, BURN-CRITICAL, DECAY RISK, EVENT). Empty string if none."
    }}}}
  ],
  "questions": [
    "Short question that unblocks prioritization. 0-3 max."
  ],
  "radar": [
    {{{{ "action_id": "rec...", "label": "One-line topic + status." }}}}
  ]
}}}}

PRIORITIZATION:
1. Burn-rate critical (the milestone in the business context).
2. Time-boxed events with near deadlines (target_date close).
3. Relationship decay (warm contacts going cold).
4. Growth Action Items.
5. Strategy items only if nothing urgent.

EXACTLY 3 items in "today". Always reference real action_ids from the snapshot — never invent."""

EVENING_SYSTEM_TMPL = """You are the user's chief of staff. {context}

Today is {today}. Generate an EOD WRAP. Look backward at what closed today, what carried over, what surfaced, what to sleep on.

You MUST output a single valid JSON object:

{{{{
  "headline": "ONE honest sentence on how the day landed.",
  "closed_today": [
    {{{{ "action_id": "rec...", "label": "Specific item the user closed today." }}}}
  ],
  "carried_over": [
    {{{{ "action_id": "rec...", "title": "Verb-led action that didn't close", "body": "Why it didn't close + next move." }}}}
  ],
  "surfaced_today": [
    "New items from today's conversation that aren't already on the board. 0-5."
  ],
  "sleep_on_it": [
    "1-2 strategic questions to percolate overnight."
  ]
}}}}

Use the snapshot + new replies to identify what closed/carried. If nothing genuinely closed, return empty array — don't fabricate."""

def build(slot: str, llm_context: str, today: str) -> dict:
    tmpl = MORNING_SYSTEM_TMPL if slot == "morning" else EVENING_SYSTEM_TMPL
    system = tmpl.format(context=config.business_context, today=today)
    api_key = KEY_PATH.read_text().strip()
    payload = {
        "model": MODEL,
        "max_tokens": 4000,
        "system": system,
        "messages": [{"role": "user", "content": llm_context}],
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
