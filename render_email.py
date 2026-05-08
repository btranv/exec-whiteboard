#!/usr/bin/env python3
"""Render the digest JSON into clean HTML + plain-text fallback.

Includes deep-links to each Action's Airtable record."""
import config

INK = "#1a1a1a"
SUB = "#5b5b5b"
MUTE = "#8a8a8a"
ACCENT = "#c41d3e"
SOFT = "#f6f4f2"
LINE = "#e6e3df"

FONT = ("-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', "
        "Roboto, 'Helvetica Neue', Arial, sans-serif")

def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def _section_label(text: str) -> str:
    return (
        f'<div style="font-family:{FONT};font-size:11px;letter-spacing:1.6px;'
        f'text-transform:uppercase;color:{MUTE};font-weight:600;'
        f'margin:32px 0 14px 0;">{_esc(text)}</div>'
    )

def _tag_pill(text: str) -> str:
    if not text:
        return ""
    return (
        f'<span style="display:inline-block;background:{ACCENT};color:#ffffff;'
        f'font-size:10px;letter-spacing:0.8px;font-weight:700;padding:3px 8px;'
        f'border-radius:3px;vertical-align:2px;margin-left:8px;">{_esc(text)}</span>'
    )

def _action_url(table_name: str, action_id: str) -> str:
    base = config.airtable_base_id
    table_id = config.airtable_tables.get(table_name, "")
    return f"https://airtable.com/{base}/{table_id}/{action_id}"

def _open_link(table_name: str, action_id: str) -> str:
    if not action_id or not action_id.startswith("rec"):
        return ""
    url = _action_url(table_name, action_id)
    return (
        f'<a href="{url}" style="color:{MUTE};font-size:11px;text-decoration:none;'
        f'border-bottom:1px solid {LINE};margin-left:6px;vertical-align:1px;">'
        f'open ↗</a>'
    )

def _numbered_card(n: int, title: str, body: str, tag: str = "",
                   action_id: str = "", table_name: str = "Actions") -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="margin:0 0 18px 0;">'
        f'<tr>'
        f'<td valign="top" width="44" style="font-family:{FONT};font-size:34px;'
        f'font-weight:300;color:{MUTE};line-height:1;padding-top:2px;">{n}</td>'
        f'<td valign="top" style="font-family:{FONT};">'
        f'<div style="font-size:17px;font-weight:600;color:{INK};line-height:1.35;">'
        f'{_esc(title)}{_tag_pill(tag)}{_open_link(table_name, action_id)}</div>'
        f'<div style="font-size:15px;color:{SUB};line-height:1.55;margin-top:6px;">'
        f'{_esc(body)}</div>'
        f'</td>'
        f'</tr></table>'
    )

def _bullet_line(text: str, action_id: str = "", table_name: str = "Actions") -> str:
    return (
        f'<div style="font-family:{FONT};font-size:15px;color:{SUB};'
        f'line-height:1.55;margin:0 0 10px 0;padding-left:18px;position:relative;">'
        f'<span style="position:absolute;left:0;top:0;color:{MUTE};">•</span>'
        f'{_esc(text)}{_open_link(table_name, action_id)}</div>'
    )

def _airtable_top_link() -> str:
    base = config.airtable_base_id
    actions_id = config.airtable_tables.get("Actions", "")
    url = f"https://airtable.com/{base}/{actions_id}"
    return (
        f'<div style="font-family:{FONT};font-size:12px;margin:0 0 16px 0;">'
        f'<a href="{url}" style="color:{ACCENT};text-decoration:none;font-weight:600;'
        f'border-bottom:1px solid {ACCENT};padding-bottom:1px;">Open Sector Ops ↗</a>'
        f'</div>'
    )

def render_morning(d: dict, today_short: str) -> tuple[str, str, str]:
    subject = f"Morning marching orders — {today_short}"
    parts = []
    parts.append(_airtable_top_link())
    parts.append(
        f'<div style="font-family:{FONT};font-size:13px;color:{MUTE};'
        f'letter-spacing:0.5px;">{_esc(today_short.upper())}</div>'
    )
    parts.append(
        f'<div style="font-family:{FONT};font-size:24px;font-weight:700;color:{INK};'
        f'line-height:1.3;margin:8px 0 0 0;">{_esc(d["headline"])}</div>'
    )
    parts.append(_section_label("Today — 3 things"))
    for i, item in enumerate(d.get("today", []), 1):
        parts.append(_numbered_card(i, item["title"], item["body"], item.get("tag", ""),
                                    item.get("action_id", "")))
    if d.get("questions"):
        parts.append(_section_label("Questions for you"))
        for q in d["questions"]:
            parts.append(_bullet_line(q))
    if d.get("radar"):
        parts.append(_section_label("Also on the radar"))
        for r in d["radar"]:
            parts.append(_bullet_line(r["label"], r.get("action_id", "")))
    parts.append(
        f'<div style="font-family:{FONT};font-size:11px;color:{MUTE};'
        f'margin-top:36px;padding-top:18px;border-top:1px solid {LINE};">'
        f'Reply with anything — I\'ll update Airtable, surface new items, and respond.</div>'
    )
    html = (
        f'<!doctype html><html><body style="margin:0;padding:0;background:#ffffff;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="background:#ffffff;"><tr><td align="center" style="padding:32px 16px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:560px;width:100%;text-align:left;"><tr><td>'
        + "".join(parts) +
        f'</td></tr></table></td></tr></table></body></html>'
    )
    text_lines = [today_short.upper(), "", d["headline"], "", "TODAY — 3 things"]
    for i, item in enumerate(d.get("today", []), 1):
        tag = f" [{item['tag']}]" if item.get("tag") else ""
        text_lines.append(f"\n{i}. {item['title']}{tag}")
        text_lines.append(f"   {item['body']}")
        if item.get("action_id"):
            text_lines.append(f"   {_action_url('Actions', item['action_id'])}")
    if d.get("questions"):
        text_lines.append("\nQUESTIONS FOR YOU")
        for q in d["questions"]:
            text_lines.append(f"  • {q}")
    if d.get("radar"):
        text_lines.append("\nALSO ON THE RADAR")
        for r in d["radar"]:
            text_lines.append(f"  • {r['label']}")
    return subject, html, "\n".join(text_lines)

def render_evening(d: dict, today_short: str) -> tuple[str, str, str]:
    subject = f"EOD wrap — {today_short}"
    parts = [_airtable_top_link()]
    parts.append(
        f'<div style="font-family:{FONT};font-size:13px;color:{MUTE};'
        f'letter-spacing:0.5px;">{_esc(today_short.upper())} · EOD WRAP</div>'
    )
    parts.append(
        f'<div style="font-family:{FONT};font-size:24px;font-weight:700;color:{INK};'
        f'line-height:1.3;margin:8px 0 0 0;">{_esc(d["headline"])}</div>'
    )
    if d.get("closed_today"):
        parts.append(_section_label("Closed today"))
        for c in d["closed_today"]:
            parts.append(_bullet_line(c["label"], c.get("action_id", "")))
    if d.get("carried_over"):
        parts.append(_section_label("Carried over"))
        for i, item in enumerate(d["carried_over"], 1):
            parts.append(_numbered_card(i, item["title"], item["body"], "",
                                        item.get("action_id", "")))
    if d.get("surfaced_today"):
        parts.append(_section_label("Surfaced today"))
        for s in d["surfaced_today"]:
            parts.append(_bullet_line(s))
    if d.get("sleep_on_it"):
        parts.append(_section_label("Sleep on it"))
        for q in d["sleep_on_it"]:
            parts.append(_bullet_line(q))
    parts.append(
        f'<div style="font-family:{FONT};font-size:11px;color:{MUTE};'
        f'margin-top:36px;padding-top:18px;border-top:1px solid {LINE};">'
        f'Reply with anything — I\'ll update Airtable and respond.</div>'
    )
    html = (
        f'<!doctype html><html><body style="margin:0;padding:0;background:#ffffff;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="background:#ffffff;"><tr><td align="center" style="padding:32px 16px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:560px;width:100%;text-align:left;"><tr><td>'
        + "".join(parts) +
        f'</td></tr></table></td></tr></table></body></html>'
    )
    text_lines = [f"{today_short.upper()} · EOD WRAP", "", d["headline"], ""]
    if d.get("closed_today"):
        text_lines.append("CLOSED TODAY")
        for c in d["closed_today"]:
            text_lines.append(f"  • {c['label']}")
    if d.get("carried_over"):
        text_lines.append("\nCARRIED OVER")
        for i, item in enumerate(d["carried_over"], 1):
            text_lines.append(f"\n  {i}. {item['title']}")
            text_lines.append(f"     {item['body']}")
    if d.get("surfaced_today"):
        text_lines.append("\nSURFACED TODAY")
        for s in d["surfaced_today"]:
            text_lines.append(f"  • {s}")
    if d.get("sleep_on_it"):
        text_lines.append("\nSLEEP ON IT")
        for q in d["sleep_on_it"]:
            text_lines.append(f"  • {q}")
    return subject, html, "\n".join(text_lines)

def render(slot: str, d: dict, today_short: str):
    return (render_morning if slot == "morning" else render_evening)(d, today_short)
