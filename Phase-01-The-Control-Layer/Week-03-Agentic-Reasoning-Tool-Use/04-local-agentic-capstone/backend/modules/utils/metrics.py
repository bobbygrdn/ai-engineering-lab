import json
import os
from datetime import datetime, timezone

METRICS_PATH = os.path.join("backend", "logs", "metrics.jsonl")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def log_interaction(record: dict):
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    record_copy = dict(record)
    record_copy["ts"] = _now_iso()
    with open(METRICS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record_copy, ensure_ascii=False) + "\n")


__all__ = ["log_interaction"]
