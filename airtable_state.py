"""Airtable as operational state. Functions to read a snapshot for LLM consumption
and to apply structured updates."""
from datetime import date, datetime, timedelta
from typing import Any
import config
import airtable_client as at

# ---------- Linked-record name resolution ----------

def _id_to_name(records: list[dict]) -> dict[str, str]:
    out = {}
    for r in records:
        for key in ("Name", "Title"):
            if key in r["fields"]:
                out[r["id"]] = r["fields"][key]
                break
    return out

# ---------- Snapshot ----------

def snapshot() -> dict:
    """Pull the full operational state. Returns a dict with all four tables,
    each as a list of normalized records (linked-IDs resolved to names)."""
    team_recs        = at.list_records(config.airtable_tables["Team"])
    people_recs      = at.list_records(config.airtable_tables["People"])
    initiatives_recs = at.list_records(config.airtable_tables["Initiatives"])
    actions_recs     = at.list_records(config.airtable_tables["Actions"])

    name_idx = {**_id_to_name(team_recs),
                **_id_to_name(people_recs),
                **_id_to_name(initiatives_recs),
                **_id_to_name(actions_recs)}

    def resolve(value):
        if isinstance(value, list):
            return [name_idx.get(v, v) for v in value]
        return name_idx.get(value, value)

    def normalize(records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            f = {}
            for k, v in r["fields"].items():
                if isinstance(v, list) and v and isinstance(v[0], str) and v[0].startswith("rec"):
                    f[k] = resolve(v)
                else:
                    f[k] = v
            out.append({"id": r["id"], "fields": f})
        return out

    return {
        "Team":        normalize(team_recs),
        "People":      normalize(people_recs),
        "Initiatives": normalize(initiatives_recs),
        "Actions":     normalize(actions_recs),
    }

# ---------- Compact text rendering for LLM context ----------

def render_for_llm(state: dict, max_actions: int = 60) -> str:
    """Compress the state into a digestible text block for the LLM."""
    lines = []

    lines.append("## TEAM")
    for r in state["Team"]:
        f = r["fields"]
        lines.append(f"- [{r['id']}] {f.get('Name')} — {f.get('Role','')}  ({f.get('Status','')})")

    lines.append("\n## INITIATIVES")
    for r in state["Initiatives"]:
        f = r["fields"]
        owner = ", ".join(f.get("Owner", []) or [])
        target = f.get("Target date", "")
        tags = ", ".join(f.get("Tags", []) or [])
        lines.append(
            f"- [{r['id']}] {f.get('Name')}  "
            f"type={f.get('Type')}  stage={f.get('Stage')}  owner={owner}"
            f"{'  target=' + target if target else ''}"
            f"{'  tags=' + tags if tags else ''}"
        )
        if f.get("Why this matters"):
            lines.append(f"    why: {f['Why this matters']}")
        if f.get("Status notes"):
            lines.append(f"    notes: {f['Status notes']}")

    # Actions: prioritize open/in-progress, sort by tag-criticality, due-date
    open_actions = [r for r in state["Actions"] if r["fields"].get("Status") in (None, "Open", "In Progress", "Waiting On")]
    closed_actions = [r for r in state["Actions"] if r["fields"].get("Status") in ("Done", "Dropped")]

    def action_sort_key(r):
        f = r["fields"]
        prio_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(f.get("Priority", "Medium"), 2)
        burn = 0 if "Burn-Critical" in (f.get("Tags") or []) else 1
        due = f.get("Due date") or "9999-12-31"
        return (burn, prio_rank, due)

    open_actions.sort(key=action_sort_key)

    lines.append("\n## OPEN ACTIONS (sorted by criticality)")
    for r in open_actions[:max_actions]:
        f = r["fields"]
        owner = ", ".join(f.get("Owner", []) or [])
        init = ", ".join(f.get("Initiative", []) or [])
        due = f.get("Due date", "")
        tags = ", ".join(f.get("Tags", []) or [])
        lines.append(
            f"- [{r['id']}] {f.get('Title')}  "
            f"status={f.get('Status','Open')}  prio={f.get('Priority','Medium')}  owner={owner}"
            f"{'  init=' + init if init else ''}"
            f"{'  due=' + due if due else ''}"
            f"{'  tags=' + tags if tags else ''}"
        )
        if f.get("Notes"):
            lines.append(f"    notes: {f['Notes']}")

    if closed_actions:
        recently_closed = []
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        for r in closed_actions:
            f = r["fields"]
            last = f.get("Last touched") or f.get("Last Modified") or ""
            if last >= cutoff:
                recently_closed.append(r)
        if recently_closed:
            lines.append("\n## RECENTLY CLOSED (last 7 days)")
            for r in recently_closed[:20]:
                f = r["fields"]
                lines.append(f"- [{r['id']}] {f.get('Title')} ({f.get('Status')})")

    if state["People"]:
        lines.append("\n## PEOPLE")
        for r in state["People"][:80]:
            f = r["fields"]
            lines.append(
                f"- [{r['id']}] {f.get('Name')}  "
                f"types={','.join(f.get('Type', []) or [])}  status={f.get('Status','')}"
                f"{'  city=' + f.get('City', '') if f.get('City') else ''}"
                f"{'  last_touch=' + f.get('Last touch date', '') if f.get('Last touch date') else ''}"
            )

    return "\n".join(lines)

# ---------- Updates ----------

def apply_updates(updates: list[dict], team_index: dict[str, str] | None = None,
                  initiatives_index: dict[str, str] | None = None) -> list[str]:
    """Apply a list of updates produced by an LLM. Each update:
        {"table": "Actions"|"Initiatives"|"People",
         "op": "set"|"append_note"|"create",
         "id": "rec..." (omit for create),
         "fields": {...}}
    For "append_note", fields={"Notes": "text"} and we prepend a timestamp.
    Returns a list of human-readable change descriptions for the digest log.
    """
    log = []
    by_table = {}
    creates_by_table = {}
    for u in updates:
        tbl = u["table"]
        op = u["op"]
        fields = u.get("fields", {})
        if op == "create":
            creates_by_table.setdefault(tbl, []).append({"fields": fields})
            log.append(f"  + create {tbl}: {fields.get('Title') or fields.get('Name')}")
        elif op == "set":
            by_table.setdefault(tbl, []).append({"id": u["id"], "fields": fields})
            log.append(f"  ~ set {tbl} {u['id']}: {fields}")
        elif op == "append_note":
            existing_text = ""
            try:
                rec = at._request("GET", f"{at.API_ROOT}/{config.airtable_base_id}/{config.airtable_tables[tbl]}/{u['id']}")
                existing_text = rec["fields"].get("Notes", "")
            except Exception:
                pass
            ts = datetime.utcnow().strftime("%Y-%m-%d")
            new_note = f"[{ts}] {fields['Notes']}"
            combined = f"{new_note}\n{existing_text}" if existing_text else new_note
            by_table.setdefault(tbl, []).append({"id": u["id"], "fields": {"Notes": combined}})
            log.append(f"  + note {tbl} {u['id']}: {fields['Notes'][:60]}")
    for tbl, payload in by_table.items():
        at.update_records(config.airtable_tables[tbl], payload)
    for tbl, payload in creates_by_table.items():
        at.create_records(config.airtable_tables[tbl], payload)
    return log
