#!/usr/bin/env python3
"""Extract full text of every text-bearing node, no truncation."""
import json
from pathlib import Path

data = json.loads((Path(__file__).parent / "board_raw.json").read_text())

def walk(node):
    if node.get("characters"):
        yield (node["id"], node.get("name", ""), node["characters"])
    for c in node.get("children", []) or []:
        yield from walk(c)

for nid, name, text in walk(data["document"]):
    print(f"\n{'='*80}\nNODE {nid}  name={name!r}\n{'='*80}")
    print(text)
