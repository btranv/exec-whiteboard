#!/usr/bin/env python3
"""One-time backfill: seed Team manually, then LLM-extract Initiatives+Actions
from the FigJam board and insert into Airtable.

Idempotent on re-run for Team. For Initiatives/Actions, re-running creates
duplicates — only run once after provisioning.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import airtable_client as at
import config
import fetch_board
from board_model import load_sections

KEY_PATH = Path(__file__).parent / ".anthropic_key"
MODEL = "claude-sonnet-4-6"

# ---------- Team (hand-seeded) ----------

TEAM_SEED = [
    {"Name": "Brian Tran",     "Role": "CEO / Founder",       "Status": "Active"},
    {"Name": "Justin",         "Role": "Ops / Finance / Legal", "Status": "Active"},
    {"Name": "Tae",            "Role": "Engineering",          "Status": "Active"},
    {"Name": "Neil",           "Role": "AI Chief of Staff",    "Status": "Active",
     "Notes": "Persona that runs digests + reply loop. Distinct from Neil-the-product."},
    {"Name": "Brett Fraser",   "Role": "Advisor",              "Status": "Advisor"},
    {"Name": "Jordan",         "Role": "Advisor",              "Status": "Advisor"},
    {"Name": "Brandon Larcom", "Role": "Advisor",              "Status": "Advisor"},
    {"Name": "Joe Quenqua",    "Role": "Advisor (Press)",      "Status": "Advisor"},
    {"Name": "David Hatkoff",  "Role": "Advisor (Brand)",      "Status": "Advisor"},
    {"Name": "Kiethan Bundy",  "Role": "Advisor (Events / Photos)", "Status": "Advisor"},
]

# ---------- LLM extraction ----------

EXTRACT_SYSTEM = """You are setting up a project-management base for the user. Read the strategic whiteboard content below and extract:

1. INITIATIVES — multi-step projects (events, partnership pushes, investor rounds, expansion efforts, product builds, legal matters). NOT individual to-dos.
2. ACTIONS — discrete to-dos. Each one doable. Pull from "To-Do List", "Growth Action Items", and any other action-shaped items.

Output ONE JSON object, no preamble, no markdown fences:

{
  "initiatives": [
    {
      "name": "Specific name (e.g. 'Pride Event @ Chelsea Hotel — June 13/14')",
      "type": "Event | Partnership | Investor Round | Product | Press | Legal | City Expansion | Membership Drive | Other",
      "stage": "Idea | Planning | Active | Wrapping | Done | Killed",
      "target_date": "YYYY-MM-DD or null",
      "revenue_impact": 0,
      "why": "1-2 sentence reason this matters (preserves the strategic context)",
      "status_notes": "Current state in 1-3 sentences",
      "tags": ["Burn-Critical" | "Time-Boxed" | "Decay Risk" | "Quick Win" | "Strategic"]
    }
  ],
  "actions": [
    {
      "title": "Verb-led action (~6-12 words)",
      "status": "Open | In Progress | Waiting On | Done | Dropped",
      "priority": "Critical | High | Medium | Low",
      "tags": ["Burn-Critical" | "Decay Risk" | "Quick Win" | "By Noon" | "Time-Boxed"],
      "due_date": "YYYY-MM-DD or null",
      "notes": "1-2 sentence detail. Include named people, dollar amounts, deadlines.",
      "initiative_name": "Exact name from initiatives[] above, or null if standalone",
      "source": "FigJam-derived"
    }
  ]
}

RULES:
- Be FAITHFUL to the board. Don't invent items. Don't expand a sticky into 5 sub-actions unless the sticky genuinely contains 5 things.
- Initiative names must be unique and specific.
- For actions linked to an initiative, the initiative_name must EXACTLY match an entry in initiatives[].
- Skip stale items (already-passed events with no follow-up implied).
- Cap at ~25 initiatives and ~50 actions. Pick the most operationally useful, not the kitchen sink."""

def llm_extract(board_text: str) -> dict:
    api_key = KEY_PATH.read_text().strip()
    payload = {
        "model": MODEL,
        "max_tokens": 16000,
        "system": EXTRACT_SYSTEM,
        "messages": [{"role": "user", "content": f"## STRATEGIC WHITEBOARD\n\n{board_text}\n\nExtract now."}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    text = resp["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)

# ---------- Seeders ----------

def seed_team() -> dict[str, str]:
    """Returns {name: record_id}."""
    table_id = config.airtable_tables["Team"]
    existing = {r["fields"].get("Name"): r["id"] for r in at.list_records(table_id)}
    to_create = [{"fields": p} for p in TEAM_SEED if p["Name"] not in existing]
    print(f"Team: {len(existing)} existing, creating {len(to_create)}…")
    if to_create:
        created = at.create_records(table_id, to_create)
        for r in created:
            existing[r["fields"]["Name"]] = r["id"]
    return existing

def seed_initiatives(extracted: list[dict], team: dict[str, str]) -> dict[str, str]:
    table_id = config.airtable_tables["Initiatives"]
    payloads = []
    for item in extracted:
        f = {
            "Name": item["name"],
            "Type": item.get("type"),
            "Stage": item.get("stage"),
            "Why this matters": item.get("why", ""),
            "Status notes": item.get("status_notes", ""),
        }
        if item.get("target_date"):
            f["Target date"] = item["target_date"]
        if item.get("revenue_impact"):
            f["Revenue impact"] = item["revenue_impact"]
        if item.get("tags"):
            f["Tags"] = item["tags"]
        # Default Owner to Brian for now (he can re-assign)
        f["Owner"] = [team["Brian Tran"]]
        payloads.append({"fields": f})
    print(f"Initiatives: creating {len(payloads)}…")
    created = at.create_records(table_id, payloads)
    return {r["fields"]["Name"]: r["id"] for r in created}

def seed_actions(extracted: list[dict], team: dict[str, str], initiatives: dict[str, str]):
    table_id = config.airtable_tables["Actions"]
    payloads = []
    skipped = 0
    for item in extracted:
        f = {
            "Title": item["title"],
            "Status": item.get("status", "Open"),
            "Priority": item.get("priority", "Medium"),
            "Source": item.get("source", "FigJam-derived"),
            "Notes": item.get("notes", ""),
        }
        if item.get("tags"):
            f["Tags"] = item["tags"]
        if item.get("due_date"):
            f["Due date"] = item["due_date"]
        # Owner default = Brian
        f["Owner"] = [team["Brian Tran"]]
        # Link to initiative if name matches
        init_name = item.get("initiative_name")
        if init_name and init_name in initiatives:
            f["Initiative"] = [initiatives[init_name]]
        elif init_name:
            skipped += 1
        payloads.append({"fields": f})
    print(f"Actions: creating {len(payloads)}… ({skipped} initiative-link mismatches)")
    at.create_records(table_id, payloads)

# ---------- Main ----------

def main():
    print("Fetching board…")
    fetch_board.main()
    sections = load_sections()
    board_text = "\n\n---\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
    print(f"Board loaded: {len(board_text)} chars")

    print("\n--- Pass 1: Team ---")
    team = seed_team()

    print("\n--- LLM extract: Initiatives + Actions ---")
    extracted = llm_extract(board_text)
    print(f"  initiatives: {len(extracted.get('initiatives', []))}")
    print(f"  actions: {len(extracted.get('actions', []))}")

    print("\n--- Pass 2: Initiatives ---")
    initiatives = seed_initiatives(extracted["initiatives"], team)

    print("\n--- Pass 3: Actions ---")
    seed_actions(extracted["actions"], team, initiatives)

    print("\nBackfill complete.")

if __name__ == "__main__":
    main()
