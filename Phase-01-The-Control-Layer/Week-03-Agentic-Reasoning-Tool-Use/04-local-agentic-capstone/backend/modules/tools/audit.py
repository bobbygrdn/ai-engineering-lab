"""Audit utilities: prune logs older than retention window and helpers."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

INTERACTIONS_PATH = os.path.join("logs", "interactions", "interactions.log")
RETENTION_DAYS = 30


def _parse_ts(entry: dict[str, Any]) -> datetime | None:
    ts = entry.get("ts")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def prune_old_events() -> int:
    """Prune events older than RETENTION_DAYS. Returns number of removed lines."""
    if not os.path.exists(INTERACTIONS_PATH):
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    kept: list[str] = []
    removed = 0
    try:
        with open(INTERACTIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    ts = _parse_ts(obj)
                    if ts is None or ts >= cutoff:
                        kept.append(line)
                    else:
                        removed += 1
                except Exception:
                    # keep malformed lines
                    kept.append(line)
    except FileNotFoundError:
        return 0

    try:
        with open(INTERACTIONS_PATH, "w", encoding="utf-8") as f:
            for l in kept:
                f.write(l)
    except Exception:
        return 0

    return removed
