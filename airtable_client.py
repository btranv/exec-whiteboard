"""Thin Airtable Web API + Meta API client. No SDK — just urllib + json.

Auth: PAT in .airtable_token (gitignored).
Base ID: from config.airtable_base_id.
"""
import json
import urllib.request
import urllib.parse
from pathlib import Path

import config

HERE = Path(__file__).parent
TOKEN_PATH = HERE / ".airtable_token"
API_ROOT = "https://api.airtable.com/v0"

def _token() -> str:
    return TOKEN_PATH.read_text().strip()

def _request(method: str, url: str, body: dict | None = None, params: dict | None = None) -> dict:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Airtable {method} {url} failed {e.code}: {body}") from e

# ---- Meta API (schema) ----

def list_tables() -> list[dict]:
    res = _request("GET", f"{API_ROOT}/meta/bases/{config.airtable_base_id}/tables")
    return res["tables"]

def create_table(name: str, fields: list[dict], description: str = "") -> dict:
    body = {"name": name, "fields": fields}
    if description:
        body["description"] = description
    return _request("POST", f"{API_ROOT}/meta/bases/{config.airtable_base_id}/tables", body)

def add_field(table_id: str, field: dict) -> dict:
    return _request("POST", f"{API_ROOT}/meta/bases/{config.airtable_base_id}/tables/{table_id}/fields", field)

def find_table(name: str) -> dict | None:
    for t in list_tables():
        if t["name"] == name:
            return t
    return None

# ---- Records API ----

def list_records(table_id: str, **params) -> list[dict]:
    out = []
    offset = None
    while True:
        p = dict(params)
        if offset:
            p["offset"] = offset
        res = _request("GET", f"{API_ROOT}/{config.airtable_base_id}/{table_id}", params=p)
        out.extend(res.get("records", []))
        offset = res.get("offset")
        if not offset:
            break
    return out

def create_records(table_id: str, records: list[dict]) -> list[dict]:
    """records = [{'fields': {...}}, ...]. Max 10 per call — auto-batches."""
    out = []
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        res = _request("POST", f"{API_ROOT}/{config.airtable_base_id}/{table_id}",
                       {"records": batch, "typecast": True})
        out.extend(res.get("records", []))
    return out

def update_records(table_id: str, records: list[dict]) -> list[dict]:
    """records = [{'id': 'rec...', 'fields': {...}}, ...]. PATCH semantics."""
    out = []
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        res = _request("PATCH", f"{API_ROOT}/{config.airtable_base_id}/{table_id}",
                       {"records": batch, "typecast": True})
        out.extend(res.get("records", []))
    return out
