#!/usr/bin/env python3
"""Provision the Sector Ops base: Team, People, Initiatives, Actions.

Idempotent: re-run safely. Skips existing tables, adds missing fields.
Linked fields are added in a second pass after all tables exist.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import airtable_client as at

# ---------- Field-spec helpers ----------

def text(name): return {"name": name, "type": "singleLineText"}
def long(name): return {"name": name, "type": "multilineText"}
def num(name, precision=0): return {"name": name, "type": "number", "options": {"precision": precision}}
def date(name): return {"name": name, "type": "date", "options": {"dateFormat": {"name": "iso"}}}
def created_at(name): return {"name": name, "type": "createdTime", "options": {"result": {"type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "America/New_York"}}}}
def modified_at(name): return {"name": name, "type": "lastModifiedTime", "options": {"result": {"type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "America/New_York"}}}}

def select(name, choices: list[str]):
    return {"name": name, "type": "singleSelect", "options": {"choices": [{"name": c} for c in choices]}}
def multi(name, choices: list[str]):
    return {"name": name, "type": "multipleSelects", "options": {"choices": [{"name": c} for c in choices]}}

def link(name, linked_table_id: str, prefers_single=False):
    # Add-field accepts only linkedTableId for new link fields. The
    # prefersSingleRecordLink toggle has to be set later via the UI or via
    # field-update. We pass prefers_single only so the planning list reads
    # naturally; it's intentionally not sent.
    return {"name": name, "type": "multipleRecordLinks",
            "options": {"linkedTableId": linked_table_id}}

# ---------- Table specs ----------

# Tables WITHOUT linked fields first; we add links in a second pass.

TEAM_FIELDS = [
    text("Name"),
    text("Role"),
    text("Email"),
    select("Status", ["Active", "Advisor", "Inactive"]),
    long("Notes"),
]

PEOPLE_FIELDS = [
    text("Name"),
    multi("Type", ["Member", "Prospect", "Investor", "Advisor", "Brand Partner", "Press", "Vendor", "Friend"]),
    select("Status", ["Active", "Warm", "Cold", "Closed", "Lost"]),
    date("Last touch date"),
    long("Last touch note"),
    text("City"),
    multi("What they care about", ["Tech", "Culture", "Press", "Travel", "Hospitality", "Health", "Beauty", "Fashion", "Investing", "Membership"]),
    long("Notes"),
]

INITIATIVES_FIELDS = [
    text("Name"),
    select("Type", ["Event", "Partnership", "Investor Round", "Product", "Press", "Legal", "City Expansion", "Membership Drive", "Other"]),
    select("Stage", ["Idea", "Planning", "Active", "Wrapping", "Done", "Killed"]),
    date("Target date"),
    num("Revenue impact", precision=0),
    long("Why this matters"),
    long("Status notes"),
    multi("Tags", ["Burn-Critical", "Time-Boxed", "Decay Risk", "Quick Win", "Strategic"]),
]

ACTIONS_FIELDS = [
    text("Title"),
    select("Status", ["Open", "In Progress", "Waiting On", "Done", "Dropped"]),
    select("Priority", ["Critical", "High", "Medium", "Low"]),
    multi("Tags", ["Burn-Critical", "Decay Risk", "Quick Win", "By Noon", "Time-Boxed"]),
    date("Due date"),
    long("Notes"),
    select("Source", ["FigJam-derived", "Reply-surfaced", "Neil-suggested", "Manual"]),
]

# Linked field passes — added AFTER all tables exist. Format:
#   (table_name_to_add_to, link_field_name, linked_table_name, prefers_single)
LINKED_FIELDS = [
    ("People",      "Relationship owner", "Team",        True),
    ("Initiatives", "Owner",              "Team",        True),
    ("Initiatives", "Stakeholders",       "Team",        False),
    ("Initiatives", "People involved",    "People",      False),
    ("Actions",     "Owner",              "Team",        True),
    ("Actions",     "Initiative",         "Initiatives", True),
    ("Actions",     "People involved",    "People",      False),
]

TABLE_SPECS = [
    ("Team",        TEAM_FIELDS,        "Sector team + advisors. Owner/stakeholder lookup."),
    ("People",      PEOPLE_FIELDS,      "Members, prospects, investors, partners — the relationship system."),
    ("Initiatives", INITIATIVES_FIELDS, "Multi-step projects: events, partnerships, investor rounds, etc."),
    ("Actions",     ACTIONS_FIELDS,     "Discrete to-dos. The day-to-day workhorse."),
]

# ---------- Provisioning ----------

def main():
    existing = {t["name"]: t for t in at.list_tables()}
    print(f"Existing tables: {list(existing)}")

    table_ids = {}

    # Pass 1: create base tables (no linked fields yet)
    for name, fields, desc in TABLE_SPECS:
        if name in existing:
            print(f"  ✓ {name} exists ({existing[name]['id']})")
            table_ids[name] = existing[name]["id"]
            continue
        print(f"  + creating {name}…")
        result = at.create_table(name, fields, desc)
        table_ids[name] = result["id"]
        print(f"    id={result['id']}")

    # Refresh schema view to find any auto-created tables
    fresh = {t["name"]: t for t in at.list_tables()}
    for name in [s[0] for s in TABLE_SPECS]:
        table_ids[name] = fresh[name]["id"]

    # Pass 2: add linked fields
    table_field_names = {name: {f["name"] for f in fresh[name]["fields"]} for name in table_ids}
    for table_name, field_name, linked_table_name, prefers_single in LINKED_FIELDS:
        if field_name in table_field_names[table_name]:
            print(f"  ✓ {table_name}.{field_name} already linked")
            continue
        print(f"  + adding link {table_name}.{field_name} → {linked_table_name}")
        at.add_field(table_ids[table_name], link(field_name, table_ids[linked_table_name], prefers_single))

    print("\nAll tables provisioned.")
    for n, i in table_ids.items():
        print(f"  {n}: {i}")

if __name__ == "__main__":
    main()
