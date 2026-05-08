#!/usr/bin/env python3
"""Convert a digest dict into styled blocks for the Google Doc.

Five voices:
  HEADLINE       — the bold one-sentence opener
  SECTION_LABEL  — small section heads ("Today", "Questions for you")
  TAG            — tiny red caps above an action ("BURN-CRITICAL")
  ACTION_TITLE   — bold numbered action
  BODY           — soft-gray normal text
  BULLET         — soft-gray with bullet prefix
  DATELINE       — tiny smallcaps gray timestamp
"""
from datetime import datetime
from zoneinfo import ZoneInfo
TZ = ZoneInfo("America/New_York")

def _b(text: str, style: str = "BODY"):
    return {"text": text, "style": style}

def _action(item: dict, n: int) -> list[dict]:
    out = []
    if item.get("tag"):
        out.append(_b(item["tag"].upper(), "TAG"))
    out.append(_b(f"{n}.  {item['title']}", "ACTION_TITLE"))
    out.append(_b(item["body"], "BODY"))
    return out

def _push_action(item: dict, n: int) -> list[dict]:
    return [
        _b(f"{n}.  {item['title']}", "ACTION_TITLE"),
        _b(item["body"], "BODY"),
    ]

def priorities_blocks(digest: dict, slot: str) -> list[dict]:
    when = datetime.now(TZ).strftime("%a %b %-d · %-I:%M %p")
    out = [
        _b(f"{when}  ·  {slot}".upper(), "DATELINE"),
        _b(digest["headline"], "HEADLINE"),
    ]
    if slot == "morning":
        out.append(_b("Today", "SECTION_LABEL"))
        for i, item in enumerate(digest.get("today", []), 1):
            out.extend(_action(item, i))
        if digest.get("questions"):
            out.append(_b("Questions for you", "SECTION_LABEL"))
            for q in digest["questions"]:
                out.append(_b(q, "BULLET"))
        if digest.get("radar"):
            out.append(_b("Also on the radar", "SECTION_LABEL"))
            for r in digest["radar"]:
                out.append(_b(r, "BULLET"))
    else:  # evening EOD wrap
        if digest.get("closed_today"):
            out.append(_b("Closed today", "SECTION_LABEL"))
            for c in digest["closed_today"]:
                out.append(_b(c, "BULLET"))
        if digest.get("carried_over"):
            out.append(_b("Carried over", "SECTION_LABEL"))
            for i, item in enumerate(digest["carried_over"], 1):
                out.extend(_push_action(item, i))
        if digest.get("surfaced_today"):
            out.append(_b("Surfaced today", "SECTION_LABEL"))
            for s in digest["surfaced_today"]:
                out.append(_b(s, "BULLET"))
        if digest.get("sleep_on_it"):
            out.append(_b("Sleep on it", "SECTION_LABEL"))
            for q in digest["sleep_on_it"]:
                out.append(_b(q, "BULLET"))
    return out

def history_blocks(digest: dict, slot: str, replies_summary: str | None = None) -> list[dict]:
    blocks = priorities_blocks(digest, slot)
    if replies_summary:
        blocks.append(_b("Replies since last digest", "SECTION_LABEL"))
        for line in replies_summary.split("\n"):
            line = line.strip()
            if line:
                blocks.append(_b(line, "BULLET"))
    return blocks
