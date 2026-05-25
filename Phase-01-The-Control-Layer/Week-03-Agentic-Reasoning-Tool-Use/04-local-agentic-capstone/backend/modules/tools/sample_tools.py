"""Specific single-action read-only tools for tickets (examples)."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict

from . import sql_read_only as sql_mod


GET_TICKET_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.get_by_id",
    "version": "0.1",
    "description": "Get a single ticket by id (read-only).",
    "inputs": {
        "type": "object",
        "properties": {"ticket_id": {"type": "integer", "minimum": 1}},
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
}


def get_ticket_by_id(args: Dict[str, Any]) -> Dict[str, Any]:
    tid = int(args["ticket_id"])
    conn = sqlite3.connect(sql_mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, status, department, body FROM tickets WHERE id = ?", (tid,))
        row = cur.fetchone()
        if not row:
            return {"ticket": None}
        return {"ticket": dict(row)}
    finally:
        conn.close()


LIST_BY_STATUS_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.list_by_status",
    "version": "0.1",
    "description": "List tickets by status (read-only).",
    "inputs": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "closed", "pending"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50},
        },
        "required": ["status"],
        "additionalProperties": False,
    },
}


def list_tickets_by_status(args: Dict[str, Any]) -> Dict[str, Any]:
    status = args["status"]
    limit = int(args.get("limit", 50))
    conn = sqlite3.connect(sql_mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, status, department FROM tickets WHERE status = ? LIMIT ?", (status, limit))
        rows = [dict(r) for r in cur.fetchall()]
        return {"rows": rows, "count": len(rows)}
    finally:
        conn.close()


SEARCH_KEYWORD_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.search_keyword",
    "version": "0.1",
    "description": "Search ticket titles and bodies for a keyword (read-only).",
    "requires_framed_user_data": True,
    "inputs": {
        "type": "object",
        "properties": {"keyword": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}},
        "required": ["keyword"],
        "additionalProperties": False,
    },
}


def search_tickets_keyword(args: Dict[str, Any]) -> Dict[str, Any]:
    kw = args["keyword"]
    # accept framed user data; extract raw text if necessary
    try:
        from .framing import extract_user_text

        kw = extract_user_text(kw)
    except Exception:
        pass
    limit = int(args.get("limit", 50))
    like = f"%{kw}%"
    conn = sqlite3.connect(sql_mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, status, department FROM tickets WHERE title LIKE ? OR body LIKE ? LIMIT ?",
            (like, like, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"rows": rows, "count": len(rows)}
    finally:
        conn.close()


COUNT_OPEN_BY_DEPT_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.count_open_by_department",
    "version": "0.1",
    "description": "Count open tickets for a specific department (read-only).",
    "inputs": {
        "type": "object",
        "properties": {"department": {"type": "string", "minLength": 1}},
        "required": ["department"],
        "additionalProperties": False,
    },
}


def count_open_by_department(args: Dict[str, Any]) -> Dict[str, Any]:
    dept = args["department"]
    conn = sqlite3.connect(sql_mod.DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open' AND department = ?", (dept,))
        (count,) = cur.fetchone()
        return {"count": int(count)}
    finally:
        conn.close()


# ------------------
# Mutating tools (DB updates)
# ------------------

CREATE_TICKET_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.create",
    "version": "0.1",
    "description": "Create a new ticket in the database.",
    "mutates": True,
    "inputs": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 3},
            "body": {"type": "string", "minLength": 1},
            "department": {"type": "string", "minLength": 1},
            "status": {"type": "string", "enum": ["open", "pending", "closed"], "default": "open"},
        },
        "required": ["title", "body", "department"],
        "additionalProperties": False,
    },
}


def create_ticket(args: Dict[str, Any]) -> Dict[str, Any]:
    title = args["title"].strip()
    body = args["body"].strip()
    department = args["department"].strip()
    status = args.get("status", "open")
    conn = sqlite3.connect(sql_mod.DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute(
            "INSERT INTO tickets (title, body, department, status) VALUES (?, ?, ?, ?)",
            (title, body, department, status),
        )
        ticket_id = cur.lastrowid
        conn.commit()
        return {"ticket_id": int(ticket_id)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


UPDATE_STATUS_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.update_status",
    "version": "0.1",
    "description": "Update the status of an existing ticket.",
    "mutates": True,
    "inputs": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "integer", "minimum": 1},
            "status": {"type": "string", "enum": ["open", "pending", "closed"]},
        },
        "required": ["ticket_id", "status"],
        "additionalProperties": False,
    },
}


def update_ticket_status(args: Dict[str, Any]) -> Dict[str, Any]:
    tid = int(args["ticket_id"])
    status = args["status"]
    conn = sqlite3.connect(sql_mod.DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, tid))
        if cur.rowcount == 0:
            conn.rollback()
            return {"updated": False, "reason": "not_found"}
        conn.commit()
        return {"updated": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


ADD_NOTE_MANIFEST = {
    "schema_version": "1.0",
    "name": "tickets.add_note",
    "version": "0.1",
    "description": "Append a note to a ticket (stored in a separate notes table).",
    "mutates": True,
    "inputs": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "integer", "minimum": 1},
            "note": {"type": "string", "minLength": 1},
            "author": {"type": "string", "minLength": 1},
        },
        "required": ["ticket_id", "note", "author"],
        "additionalProperties": False,
    },
}


def add_ticket_note(args: Dict[str, Any]) -> Dict[str, Any]:
    tid = int(args["ticket_id"])
    note = args["note"].strip()
    author = args["author"].strip()
    conn = sqlite3.connect(sql_mod.DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        # ensure ticket exists
        cur.execute("SELECT 1 FROM tickets WHERE id = ?", (tid,))
        if cur.fetchone() is None:
            conn.rollback()
            return {"added": False, "reason": "ticket_not_found"}
        cur.execute("INSERT INTO ticket_notes (ticket_id, author, note) VALUES (?, ?, ?)", (tid, author, note))
        note_id = cur.lastrowid
        conn.commit()
        return {"added": True, "note_id": int(note_id)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
