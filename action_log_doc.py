#!/usr/bin/env python3
"""Action Log Google Doc — editorial typography (restrained).

Anchors are sentence-case ("Priorities" / "History") so the doc reads like
a magazine column, not a UI dashboard.
"""
from pathlib import Path
import config
import google_clients
import doc_blocks

HERE = Path(__file__).parent
DOC_TITLE = config.doc_title
SUBTITLE = config.doc_subtitle
PRIORITIES_HEADING = "Priorities"
HISTORY_HEADING = "History"

INK = "#1a1a1a"
SOFT = "#3a3a3a"
MUTE = "#8a8a8a"
ACCENT = "#c41d3e"

def _hex_to_rgb(h: str):
    return {"red": int(h[1:3], 16)/255, "green": int(h[3:5], 16)/255, "blue": int(h[5:7], 16)/255}

# Each style: paragraph (named, space_above_pt, space_below_pt) + text (size, weight, color, smallcaps)
STYLE_SPEC = {
    # Anchors
    "TITLE":   {"named": "TITLE",     "space_above": 0,  "space_below": 4,  "size": 22, "bold": True,  "color": INK,  "uppercase": False},
    "SUBTITLE":{"named": "NORMAL_TEXT","space_above": 0,  "space_below": 24, "size": 11, "bold": False, "color": MUTE, "uppercase": False, "italic": True},
    "ANCHOR":  {"named": "HEADING_1", "space_above": 32, "space_below": 8,  "size": 16, "bold": True,  "color": INK,  "uppercase": False},

    # Per-digest header
    "DATELINE":{"named": "NORMAL_TEXT","space_above": 16, "space_below": 4,  "size":  9, "bold": True,  "color": MUTE, "uppercase": False, "letterspacing": True},
    "HEADLINE":{"named": "NORMAL_TEXT","space_above": 6,  "space_below": 18, "size": 14, "bold": True,  "color": INK,  "uppercase": False},

    # Sections within a digest
    "SECTION_LABEL": {"named": "NORMAL_TEXT", "space_above": 18, "space_below": 8, "size": 11, "bold": True, "color": INK, "uppercase": False},

    # Actions
    "TAG":          {"named": "NORMAL_TEXT", "space_above": 12, "space_below": 2,  "size":  9, "bold": True,  "color": ACCENT, "uppercase": False, "letterspacing": True},
    "ACTION_TITLE": {"named": "NORMAL_TEXT", "space_above": 0,  "space_below": 4,  "size": 12, "bold": True,  "color": INK,    "uppercase": False},
    "BODY":         {"named": "NORMAL_TEXT", "space_above": 0,  "space_below": 8,  "size": 11, "bold": False, "color": SOFT,   "uppercase": False},
    "BULLET":       {"named": "NORMAL_TEXT", "space_above": 0,  "space_below": 4,  "size": 11, "bold": False, "color": SOFT,   "uppercase": False, "indent": 18, "bullet": True},
}

def get_or_create_doc_id() -> str:
    if config.action_log_doc_id:
        return config.action_log_doc_id
    docs = google_clients.docs()
    doc = docs.documents().create(body={"title": DOC_TITLE}).execute()
    doc_id = doc["documentId"]
    print(f"WARNING: Created new action log doc {doc_id}. "
          f"Add to .sector_config.json as 'action_log_doc_id' to persist.")
    _seed_doc(doc_id)
    return doc_id

def doc_url(doc_id: str | None = None) -> str:
    return f"https://docs.google.com/document/d/{doc_id or get_or_create_doc_id()}/edit"

def _seed_doc(doc_id: str):
    docs = google_clients.docs()
    seed = (
        f"{DOC_TITLE}\n"
        f"{SUBTITLE}\n"
        f"{PRIORITIES_HEADING}\n"
        "(empty — first digest will populate)\n"
        f"{HISTORY_HEADING}\n"
    )
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": seed}}]},
    ).execute()
    _restyle_anchors(doc_id)

def _restyle_anchors(doc_id: str):
    docs = google_clients.docs()
    doc = docs.documents().get(documentId=doc_id).execute()
    requests = []
    for el in doc["body"]["content"]:
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(r.get("textRun", {}).get("content", "") for r in para.get("elements", [])).rstrip("\n")
        if text == DOC_TITLE:
            requests.extend(_style_para_requests(el, "TITLE"))
        elif text == SUBTITLE:
            requests.extend(_style_para_requests(el, "SUBTITLE"))
        elif text in (PRIORITIES_HEADING, HISTORY_HEADING):
            requests.extend(_style_para_requests(el, "ANCHOR"))
    if requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

def _style_para_requests(el: dict, style_name: str) -> list[dict]:
    spec = STYLE_SPEC[style_name]
    rng = {"startIndex": el["startIndex"], "endIndex": el["endIndex"]}
    text_end = el["endIndex"] - 1
    requests = []
    # Paragraph style
    para_style = {"namedStyleType": spec["named"]}
    fields = ["namedStyleType"]
    if spec.get("space_above") is not None:
        para_style["spaceAbove"] = {"magnitude": spec["space_above"], "unit": "PT"}
        fields.append("spaceAbove")
    if spec.get("space_below") is not None:
        para_style["spaceBelow"] = {"magnitude": spec["space_below"], "unit": "PT"}
        fields.append("spaceBelow")
    if spec.get("indent"):
        para_style["indentStart"] = {"magnitude": spec["indent"], "unit": "PT"}
        fields.append("indentStart")
    requests.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": para_style, "fields": ",".join(fields)}})

    # Text style
    if text_end > el["startIndex"]:
        text_style = {}
        text_fields = []
        if spec.get("size"):
            text_style["fontSize"] = {"magnitude": spec["size"], "unit": "PT"}
            text_fields.append("fontSize")
        if spec.get("bold"):
            text_style["bold"] = True
            text_fields.append("bold")
        if spec.get("italic"):
            text_style["italic"] = True
            text_fields.append("italic")
        if spec.get("color"):
            text_style["foregroundColor"] = {"color": {"rgbColor": _hex_to_rgb(spec["color"])}}
            text_fields.append("foregroundColor")
        if text_fields:
            requests.append({"updateTextStyle": {
                "range": {"startIndex": el["startIndex"], "endIndex": text_end},
                "textStyle": text_style,
                "fields": ",".join(text_fields),
            }})

    # Bullet preset (applied after text inserted; needs a separate pass since bullet API is param-based)
    if spec.get("bullet"):
        requests.append({"createParagraphBullets": {
            "range": rng,
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }})
    return requests

def read_full() -> str:
    doc_id = get_or_create_doc_id()
    docs = google_clients.docs()
    doc = docs.documents().get(documentId=doc_id).execute()
    out = []
    for el in doc["body"]["content"]:
        para = el.get("paragraph")
        if not para:
            continue
        for r in para.get("elements", []):
            t = r.get("textRun", {}).get("content")
            if t:
                out.append(t)
    return "".join(out)

def _find_section_indexes(doc_id: str):
    docs = google_clients.docs()
    doc = docs.documents().get(documentId=doc_id).execute()
    body = doc["body"]["content"]
    pri_start = pri_end = hist_start = None
    for el in body:
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(r.get("textRun", {}).get("content", "") for r in para.get("elements", [])).strip()
        if text == PRIORITIES_HEADING and pri_start is None:
            pri_start = el["endIndex"]
        elif text == HISTORY_HEADING and hist_start is None:
            pri_end = el["startIndex"]
            hist_start = el["endIndex"]
    if pri_start is None or pri_end is None or hist_start is None:
        raise RuntimeError("Doc missing Priorities or History anchors; reseed.")
    return pri_start, pri_end, hist_start

def _insert_blocks_and_style(doc_id: str, insert_at: int, blocks: list[dict]):
    docs = google_clients.docs()
    payload = "\n" + "".join(b["text"] + "\n" for b in blocks)
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": insert_at}, "text": payload}}]},
    ).execute()
    # Re-fetch and style each inserted paragraph in order.
    doc = docs.documents().get(documentId=doc_id).execute()
    body = doc["body"]["content"]
    style_requests = []
    block_iter = iter(blocks)
    target = next(block_iter, None)
    for el in body:
        if target is None:
            break
        if el.get("startIndex", 0) < insert_at:
            continue
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(r.get("textRun", {}).get("content", "") for r in para.get("elements", [])).rstrip("\n")
        if text != target["text"]:
            continue
        style_requests.extend(_style_para_requests(el, target["style"]))
        target = next(block_iter, None)
    if style_requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": style_requests}).execute()

def update_priorities_and_prepend_history(digest: dict, slot: str, replies_summary: str | None = None):
    doc_id = get_or_create_doc_id()
    docs = google_clients.docs()

    # Pass 1: prepend new history entry just under "History" anchor.
    _, _, hist_start = _find_section_indexes(doc_id)
    _insert_blocks_and_style(doc_id, hist_start, doc_blocks.history_blocks(digest, slot, replies_summary))

    # Pass 2: replace the live priorities block.
    pri_start, pri_end, _ = _find_section_indexes(doc_id)
    if pri_end > pri_start:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"deleteContentRange": {"range": {"startIndex": pri_start, "endIndex": pri_end}}}]},
        ).execute()
    pri_start, _, _ = _find_section_indexes(doc_id)
    _insert_blocks_and_style(doc_id, pri_start, doc_blocks.priorities_blocks(digest, slot))
