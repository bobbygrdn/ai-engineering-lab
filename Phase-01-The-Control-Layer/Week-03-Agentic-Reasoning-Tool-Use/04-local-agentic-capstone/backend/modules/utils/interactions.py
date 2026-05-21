import json
import os
from datetime import datetime, timezone
from typing import Any, Dict
import logging

INTERACTIONS_PATH = os.path.join("logs", "interactions", "interactions.log")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Record a structured interaction event to logs/interactions/interactions.log as JSONL

    Also emits a one-line info log for quick tailing.
    """
    os.makedirs(os.path.dirname(INTERACTIONS_PATH), exist_ok=True)
    entry = dict(payload)
    entry["ts"] = _now_iso()
    entry["event"] = event_type
    try:
        with open(INTERACTIONS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort; do not raise during runtime
        pass

    # also log a concise human-friendly line
    try:
        logger = logging.getLogger("interactions")
        summary = entry.get("summary") or entry.get("text") or entry.get("intent") or str(event_type)
        logger.info(f"{event_type}: {summary}")
    except Exception:
        pass


__all__ = ["record_event"]
