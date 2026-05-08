#!/usr/bin/env python3
"""Polling driver: every 15 min, check for new the user replies and respond to each."""
import socket
import ssl
import sys
import traceback
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import config
import replies as replies_mod
import respond_to_reply
import send_email

TZ = ZoneInfo("America/New_York")
LOG = HERE / "polling.log"
FAIL_STATE = HERE / ".polling_consecutive_failures"

# Number of consecutive failures before we email the user about it.
ALERT_THRESHOLD = 6  # ~90 min of failed polls

# Errors we never email about — they self-heal on next poll.
TRANSIENT = (socket.gaierror, socket.timeout, ConnectionError, ssl.SSLError,
             TimeoutError, urllib.error.URLError)

def log(msg: str):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    LOG.open("a").write(f"[{ts}] {msg}\n")

def _read_fail_count() -> int:
    if not FAIL_STATE.exists():
        return 0
    try:
        return int(FAIL_STATE.read_text().strip())
    except Exception:
        return 0

def _set_fail_count(n: int):
    FAIL_STATE.write_text(str(n))

def main():
    try:
        new = replies_mod.fetch_unprocessed(mark_processed=False)
        _set_fail_count(0)  # reset on any successful poll
        if not new:
            return
        log(f"found {len(new)} new replies")
        handled_ids = []
        for reply in new:
            try:
                preview = reply["body"][:80].replace("\n", " ")
                log(f"  -> handling reply {reply['id']}: {preview!r}")
                respond_to_reply.handle_one(reply)
                handled_ids.append(reply["id"])
            except Exception:
                log(f"  !! failed reply {reply['id']}: {traceback.format_exc()}")
        if handled_ids:
            replies_mod.mark_processed(handled_ids)
            log(f"marked {len(handled_ids)} processed")
    except TRANSIENT as e:
        # Network blip — log only, no email.
        log(f"transient network error (no alert): {type(e).__name__}: {e}")
    except Exception:
        err = traceback.format_exc()
        log(f"ERROR: {err}")
        n = _read_fail_count() + 1
        _set_fail_count(n)
        if n == ALERT_THRESHOLD:
            log(f"alert threshold hit ({n} consecutive failures) — emailing the user")
            try:
                send_email.send(
                    config.recipient_email,
                    "[FAILED] reply polling — persistent",
                    f"Polling has failed {n} times in a row (~{n*15} min).\n\n{err}",
                )
            except Exception:
                pass

if __name__ == "__main__":
    main()
