#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from account_registrar import PromptBridge


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a response to a pending codex-auth bridge request.")
    parser.add_argument("--bridge-dir", type=Path, required=True, help="Bridge directory used by account_registrar.py")
    parser.add_argument("--value", required=True, help="Response value to send")
    args = parser.parse_args()

    logger = logging.getLogger("bridge_reply")
    logger.addHandler(logging.NullHandler())
    bridge = PromptBridge(args.bridge_dir, logger)
    bridge.send_value(value=args.value)
    print(f"Bridge response sent via {args.bridge_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
