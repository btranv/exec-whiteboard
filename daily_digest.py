#!/usr/bin/env python3
"""Orchestrator: read replies + board + doc -> build digest -> update doc -> send email.

Usage: daily_digest.py morning   (or evening)
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import action_log_doc
import config
import digest_builder
import fetch_board
import render_email
import replies as replies_mod
import send_email
from board_model import load_sections

TZ = ZoneInfo("America/New_York")
LOG = HERE / "digest.log"

def log(msg: str):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{ts}] {msg}\n"
    LOG.open("a").write(line)
    print(line, end="", file=sys.stderr)

def main(slot: str):
    assert slot in ("morning", "evening"), f"unknown slot: {slot}"
    today_dt = datetime.now(TZ)
    today = today_dt.strftime("%A %B %-d, %Y")
    today_short = today_dt.strftime("%a %b %-d")
    log(f"START {slot} digest for {today}")
    try:
        # 1. Refresh inputs
        fetch_board.main()
        sections = load_sections()
        board_text = "\n\n---\n\n".join(
            f"## {key}\n{body}" for key, body in sections.items()
        )

        # 2. Read replies since last digest
        unprocessed = replies_mod.fetch_unprocessed()
        replies_summary = replies_mod.summarize_for_log(unprocessed)
        log(f"replies: {len(unprocessed)}")

        # 3. Read current doc state (so the LLM knows what was prioritized + what got done)
        doc_state = action_log_doc.read_full()

        # 4. Build LLM context with all three: board + replies + doc
        llm_input_parts = [
            "## CURRENT FIGJAM BOARD",
            board_text,
            "",
            "## SECTOR ACTION LOG (current state in shared doc)",
            doc_state,
        ]
        if unprocessed:
            llm_input_parts.append("")
            llm_input_parts.append("## NEW REPLIES FROM USER SINCE LAST DIGEST")
            for r in unprocessed:
                llm_input_parts.append(f"--- reply ({r['date']}) re: {r['subject']} ---")
                llm_input_parts.append(r["body"])
            llm_input_parts.append("")
            llm_input_parts.append(
                "Use these replies to update what's done, deprioritized, or newly urgent. "
                "Do NOT re-suggest items the user said they completed."
            )
        full_context = "\n".join(llm_input_parts)

        # 5. Build digest
        digest = digest_builder.build(slot, full_context, today)

        # 6. Update doc: replace priorities + prepend styled history entry
        action_log_doc.update_priorities_and_prepend_history(digest, slot, replies_summary)
        doc_link = action_log_doc.doc_url()
        log(f"doc updated: {doc_link}")

        # 7. Send email (always include the doc link prominently at top)
        subject, html, text = render_email.render(slot, digest, today_short)
        html = _inject_doc_link_html(html, doc_link)
        text = f"Action log: {doc_link}\n\n{text}"
        send_email.send(config.recipient_email, subject, text, body_html=html)
        log(f"SENT subject={subject!r}")

    except Exception:
        err = traceback.format_exc()
        log(f"ERROR: {err}")
        try:
            send_email.send(
                config.recipient_email,
                f"[FAILED] {slot} digest — {today_short}",
                f"Digest job failed.\n\n{err}",
            )
        except Exception:
            pass
        raise

def _inject_doc_link_html(html: str, link: str) -> str:
    """Insert a small 'Action log →' link near the top of the rendered email."""
    pill = (
        f'<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
        f'font-size:12px;margin:0 0 16px 0;">'
        f'<a href="{link}" style="color:#c41d3e;text-decoration:none;font-weight:600;'
        f'border-bottom:1px solid #c41d3e;padding-bottom:1px;">Open action log ↗</a>'
        f'</div>'
    )
    # Insert right after the inner <td> opens (before our content table).
    marker = '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;text-align:left;"><tr><td>'
    return html.replace(marker, marker + pill, 1)

if __name__ == "__main__":
    main(sys.argv[1])
