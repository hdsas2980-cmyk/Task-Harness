#!/usr/bin/env python3
"""One-shot bulk converter: old JSON/JSONL/TXT -> .harness/harness.db.

This is not a compatibility layer. After conversion:
- agents read/write harness.db only
- leftover JSON files are read-only backups
- never insert old records one by one
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_db import main


if __name__ == "__main__":
    raise SystemExit(main())
