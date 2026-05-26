import json
import os
from datetime import datetime, timezone

METRICS_PATH = os.path.join("logs", "metrics.jsonl")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def record_metric(record: dict, state_store=None, user_id=None):
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    record_copy = dict(record)
    record_copy["ts"] = _now_iso()
    with open(METRICS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record_copy, ensure_ascii=False) + "\n")

    if state_store is not None and hasattr(state_store, "record_metric"):
        try:
            state_store.record_metric(record_copy, user_id=user_id)
        except Exception:
            pass


def log_interaction(record: dict):
    record_metric(record)


__all__ = ["log_interaction", "record_metric"]
