#!/usr/bin/env python3
"""Fetch the latest FigJam board JSON via the Figma REST API."""
import sys
import urllib.request
from pathlib import Path

import config

HERE = Path(__file__).parent
TOKEN_PATH = HERE / ".figma_token"
OUT_PATH = HERE / "board_raw.json"

def main():
    token = TOKEN_PATH.read_text().strip()
    req = urllib.request.Request(
        f"https://api.figma.com/v1/files/{config.figma_file_key}",
        headers={"X-Figma-Token": token},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    OUT_PATH.write_bytes(body)
    print(f"Wrote {len(body)} bytes to {OUT_PATH}", file=sys.stderr)

if __name__ == "__main__":
    main()
