import importlib
import sqlite3

from modules.tools.engine import engine, HookAbort
from modules.tools.sample_tools import (
    GET_TICKET_MANIFEST,
    get_ticket_by_id,
    LIST_BY_STATUS_MANIFEST,
    list_tickets_by_status,
)


def setup_db(tmp_path):
    db = tmp_path / "tickets.db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, title TEXT, body TEXT, status TEXT, department TEXT)")
    cur.executemany(
        "INSERT INTO tickets (title, body, status, department) VALUES (?,?,?,?)",
        [("A", "b", "open", "Billing"), ("C", "d", "open", "Billing")],
    )
    conn.commit()
    conn.close()
    return str(db)


def test_pre_invoke_hook_modifies_args(tmp_path, monkeypatch):
    db_path = setup_db(tmp_path)
    sql_mod = importlib.import_module("modules.tools.sql_read_only")
    monkeypatch.setattr(sql_mod, "DB_PATH", db_path)

    engine.register_tool(LIST_BY_STATUS_MANIFEST, list_tickets_by_status)

    # hook that forces limit to 1
    def force_limit(manifest, args, caller):
        if manifest["name"] == "tickets.list_by_status":
            new = dict(args)
            new["limit"] = 1
            return new

    engine.register_pre_invoke_hook(force_limit)

    from modules.auth.security import AuthManager
    ai_token = AuthManager().create_access_token(user_id=0, username="ai")
    try:
        r = engine.invoke("tickets.list_by_status", {"status": "open", "limit": 10}, caller=ai_token)
        assert r["success"] and r["result"]["count"] == 1
    finally:
        engine.unregister_pre_invoke_hook(force_limit)


def test_pre_invoke_hook_abort(tmp_path, monkeypatch):
    db_path = setup_db(tmp_path)
    sql_mod = importlib.import_module("modules.tools.sql_read_only")
    monkeypatch.setattr(sql_mod, "DB_PATH", db_path)

    engine.register_tool(GET_TICKET_MANIFEST, get_ticket_by_id)

    def deny_all(manifest, args, caller):
        raise HookAbort("denied by hook", retryable=False)

    engine.register_pre_invoke_hook(deny_all, prepend=True)
    from modules.auth.security import AuthManager
    ai_token = AuthManager().create_access_token(user_id=0, username="ai")
    try:
        resp = engine.invoke("tickets.get_by_id", {"ticket_id": 1}, caller=ai_token)
        assert resp["success"] is False and resp["error"] == "denied by hook"
    finally:
        engine.unregister_pre_invoke_hook(deny_all)
