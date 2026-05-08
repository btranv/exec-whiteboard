#!/usr/bin/env python3
"""Orchestrator: Airtable snapshot + FigJam + new replies → digest → email.

Usage: daily_digest.py morning   (or evening)
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import airtable_state
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
        # 1. Pull live state
        fetch_board.main()
        sections = load_sections()
        figjam_text = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
        state = airtable_state.snapshot()
        state_text = airtable_state.render_for_llm(state)

        # 2. Read replies since last digest (mark processed so we don't re-bill on next run)
        unprocessed = replies_mod.fetch_unprocessed(mark_processed=True)
        log(f"replies: {len(unprocessed)}")

        # 3. Compose LLM context
        ctx = [
            "## AIRTABLE SNAPSHOT (operational state)",
            state_text,
            "",
            "## STRATEGIC WHITEBOARD (FigJam — input for new ideas)",
            figjam_text,
        ]
        if unprocessed:
            ctx.append("\n## NEW REPLIES FROM USER SINCE LAST DIGEST")
            for r in unprocessed:
                ctx.append(f"--- reply ({r['date']}) re: {r['subject']} ---")
                ctx.append(r["body"])
            ctx.append("\nUse these to identify what closed/dropped/surfaced. Don't re-suggest closed items.")
        ctx.append(f"\nGenerate the {slot} digest JSON now.")
        full_context = "\n".join(ctx)

        # 4. Build digest
        digest = digest_builder.build(slot, full_context, today)

        # 5. Render and send
        subject, html, text = render_email.render(slot, digest, today_short)
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

if __name__ == "__main__":
    main(sys.argv[1])
