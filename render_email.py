#!/usr/bin/env python3
"""Render the digest JSON into clean HTML + plain-text fallback.

Design principles (Airbnb-style email):
- One font stack, two text colors, one accent
- Generous whitespace
- Numbered cards for the main actions
- Small-caps section labels
- Urgency tags as small pills
- 600px max width, mobile-first
"""

# Colors
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

def _numbered_card(n: int, title: str, body: str, tag: str = "") -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="margin:0 0 18px 0;">'
        f'<tr>'
        f'<td valign="top" width="44" style="font-family:{FONT};font-size:34px;'
        f'font-weight:300;color:{MUTE};line-height:1;padding-top:2px;">{n}</td>'
        f'<td valign="top" style="font-family:{FONT};">'
        f'<div style="font-size:17px;font-weight:600;color:{INK};line-height:1.35;">'
        f'{_esc(title)}{_tag_pill(tag)}</div>'
        f'<div style="font-size:15px;color:{SUB};line-height:1.55;margin-top:6px;">'
        f'{_esc(body)}</div>'
        f'</td>'
        f'</tr></table>'
    )

def _bullet_line(text: str) -> str:
    return (
        f'<div style="font-family:{FONT};font-size:15px;color:{SUB};'
        f'line-height:1.55;margin:0 0 10px 0;padding-left:18px;position:relative;">'
        f'<span style="position:absolute;left:0;top:0;color:{MUTE};">•</span>'
        f'{_esc(text)}</div>'
    )

def _person_card(person: str, message: str) -> str:
    return (
        f'<div style="font-family:{FONT};margin:0 0 16px 0;padding:14px 16px;'
        f'background:{SOFT};border-radius:8px;">'
        f'<div style="font-size:14px;font-weight:600;color:{INK};">{_esc(person)}</div>'
        f'<div style="font-size:14px;color:{SUB};line-height:1.55;margin-top:6px;'
        f'font-style:italic;">"{_esc(message)}"</div>'
        f'</div>'
    )

def render_morning(d: dict, today_short: str) -> tuple[str, str, str]:
    """Returns (subject, html, text)."""
    subject = f"Morning marching orders — {today_short}"

    # HTML
    parts = []
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
        parts.append(_numbered_card(i, item["title"], item["body"], item.get("tag", "")))
    if d.get("questions"):
        parts.append(_section_label("Questions for you"))
        for q in d["questions"]:
            parts.append(_bullet_line(q))
    if d.get("radar"):
        parts.append(_section_label("Also on the radar"))
        for r in d["radar"]:
            parts.append(_bullet_line(r))
    parts.append(
        f'<div style="font-family:{FONT};font-size:11px;color:{MUTE};'
        f'margin-top:36px;padding-top:18px;border-top:1px solid {LINE};">'
        f'Generated from the Executive Whiteboard FigJam. Reply with what got done — '
        f'feedback shapes tomorrow\'s digest.</div>'
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

    # Plain-text fallback
    text_lines = [today_short.upper(), "", d["headline"], "", "TODAY — 3 things"]
    for i, item in enumerate(d.get("today", []), 1):
        tag = f" [{item['tag']}]" if item.get("tag") else ""
        text_lines.append(f"\n{i}. {item['title']}{tag}")
        text_lines.append(f"   {item['body']}")
    if d.get("questions"):
        text_lines.append("\nQUESTIONS FOR YOU")
        for q in d["questions"]:
            text_lines.append(f"  • {q}")
    if d.get("radar"):
        text_lines.append("\nALSO ON THE RADAR")
        for r in d["radar"]:
            text_lines.append(f"  • {r}")
    return subject, html, "\n".join(text_lines)

def render_evening(d: dict, today_short: str) -> tuple[str, str, str]:
    subject = f"EOD wrap — {today_short}"
    parts = []
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
            parts.append(_bullet_line(c))
    if d.get("carried_over"):
        parts.append(_section_label("Carried over"))
        for i, item in enumerate(d["carried_over"], 1):
            parts.append(_numbered_card(i, item["title"], item["body"]))
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
        f'Reply with anything — I\'ll respond and keep the action log current.</div>'
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
            text_lines.append(f"  • {c}")
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
