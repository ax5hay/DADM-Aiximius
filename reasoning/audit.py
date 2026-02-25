"""Append-only audit log for LLM reasoning requests (schema: audit_log_entry.json)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


def write_audit_entry(entry: Dict[str, Any]) -> None:
    """Append one audit log entry (JSON line) to file or stdout."""
    entry.setdefault("id", str(uuid4()))
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    out = os.environ.get("DADM_REASONING_AUDIT_LOG", "")
    line = json.dumps(entry) + "\n"
    if out and out != "-":
        try:
            with open(out, "a") as f:
                f.write(line)
        except OSError:
            print(line, end="")
    else:
        print(line, end="")
