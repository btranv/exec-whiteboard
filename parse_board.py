#!/usr/bin/env python3
"""Parse the FigJam board JSON into a clean section -> sticky structure."""
import json
from pathlib import Path

RAW = Path(__file__).parent / "board_raw.json"
data = json.loads(RAW.read_text())

def walk(node, depth=0, parent_section=None):
    """Yield (depth, type, name, text, id) for every node."""
    nid = node.get("id", "")
    ntype = node.get("type", "")
    name = node.get("name", "") or ""
    text = ""
    char = node.get("characters")
    if char:
        text = char
    yield (depth, ntype, name, text, nid, parent_section)
    for child in node.get("children", []) or []:
        yield from walk(child, depth + 1, parent_section)

nodes = list(walk(data["document"]))

# Print every node with text content
print(f"Total nodes: {len(nodes)}\n")
print("=" * 80)
print("ALL TEXT-BEARING NODES")
print("=" * 80)
for depth, ntype, name, text, nid, _ in nodes:
    if text or (ntype in ("SECTION", "SHAPE_WITH_TEXT", "STICKY", "TEXT") and name):
        prefix = "  " * depth
        label = f"[{ntype}]"
        snippet = (text or name).replace("\n", " | ")[:200]
        print(f"{prefix}{label} {nid} {snippet}")
