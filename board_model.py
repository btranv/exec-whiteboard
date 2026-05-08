#!/usr/bin/env python3
"""Parse board_raw.json into a structured model: section name -> text body."""
import json
from pathlib import Path

HERE = Path(__file__).parent

def load_sections():
    """Return {logical_section_name: full_text} pulled from the FigJam board."""
    data = json.loads((HERE / "board_raw.json").read_text())
    sections = {}
    def walk(node):
        chars = node.get("characters")
        if chars:
            name = node.get("name", "") or ""
            first_line = chars.split("\n", 1)[0].strip()
            key = first_line or name.split("\n", 1)[0][:80]
            sections[key] = chars
        for c in node.get("children", []) or []:
            walk(c)
    walk(data["document"])
    return sections

def get(sections, *keywords):
    """Find a section whose key starts with one of the keywords (case-insensitive)."""
    for kw in keywords:
        kw_low = kw.lower()
        for key, body in sections.items():
            if key.lower().startswith(kw_low):
                return body
    return None
