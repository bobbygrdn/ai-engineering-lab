"""A minimal read-only SQLite query tool with manifest and strict validation."""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DB_PATH = os.path.normpath(os.path.join(BASE_DIR, "db", "app_state.db"))

# Manifest: explicit JSON Schema for inputs. Must match manifest_schema expectations.
SQL_READ_ONLY_MANIFEST: Dict[str, Any] = {
    "schema_version": "1.0",
    "name": "sqlite.read_only_query",
    "version": "0.1",
    "description": "Execute a read-only SELECT query against the application sqlite DB.",
    "allowed_callers": [],
    "inputs": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                # require a SELECT statement only
                "pattern": "(?i)^\\s*SELECT\\b",
            },
            "params": {
                "type": "array",
                "items": {},
                "default": [],
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def read_only_query_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a read-only SELECT query and return rows as list of dicts."""
    query: str = args["query"]
    params: List[Any] = args.get("params", [])
    limit: int = args.get("limit", 100)

    if not query.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("database not found")

    # connect read-only to be extra safe
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(query + f" LIMIT {int(limit)}", params)
        rows = [dict(r) for r in cur.fetchall()]
        return {"rows": rows, "count": len(rows)}
    finally:
        conn.close()
