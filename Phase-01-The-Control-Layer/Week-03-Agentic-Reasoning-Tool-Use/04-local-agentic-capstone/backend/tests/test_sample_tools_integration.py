import importlib
import sqlite3

from modules.tools.engine import engine
from modules.tools.sample_tools import (
    GET_TICKET_MANIFEST,
    get_ticket_by_id,
    LIST_BY_STATUS_MANIFEST,
    list_tickets_by_status,
    SEARCH_KEYWORD_MANIFEST,
    search_tickets_keyword,
    COUNT_OPEN_BY_DEPT_MANIFEST,
    count_open_by_department,
)


def setup_db(tmp_path):
    db = tmp_path / "tickets.db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE tickets (id INTEGER PRIMARY KEY, title TEXT, body TEXT, status TEXT, department TEXT)"
    )
    cur.executemany(
        "INSERT INTO tickets (title, body, status, department) VALUES (?,?,?,?)",
        [
            ("First", "Body one", "open", "Billing"),
            ("Second", "Body two", "closed", "Technical Support"),
            ("Third invoice", "Invoice body", "open", "Billing"),
        ],
    )
    conn.commit()
    conn.close()
    return str(db)


def test_sample_tools(tmp_path, monkeypatch):
    db_path = setup_db(tmp_path)
    # patch DB_PATH used by sample_tools
    sql_mod = importlib.import_module("modules.tools.sql_read_only")
    monkeypatch.setattr(sql_mod, "DB_PATH", db_path)

    # register tools
    engine.register_tool(GET_TICKET_MANIFEST, get_ticket_by_id)
    engine.register_tool(LIST_BY_STATUS_MANIFEST, list_tickets_by_status)
    engine.register_tool(SEARCH_KEYWORD_MANIFEST, search_tickets_keyword)
    engine.register_tool(COUNT_OPEN_BY_DEPT_MANIFEST, count_open_by_department)

    from modules.auth.security import AuthManager
    ai_token = AuthManager().create_access_token(user_id=0, username="ai")

    # get by id
    r = engine.invoke("tickets.get_by_id", {"ticket_id": 1}, caller=ai_token)
    assert r["success"] and r["result"]["ticket"]["id"] == 1

    # list by status
    r2 = engine.invoke("tickets.list_by_status", {"status": "open", "limit": 10}, caller=ai_token)
    assert r2["success"] and r2["result"]["count"] == 2

    # search keyword (must be framed)
    from modules.tools.framing import frame_user_data
    framed_kw = frame_user_data("invoice")
    r3 = engine.invoke("tickets.search_keyword", {"keyword": framed_kw, "limit": 10}, caller=ai_token)
    assert r3["success"] and r3["result"]["count"] == 1

    # count open by department
    r4 = engine.invoke("tickets.count_open_by_department", {"department": "Billing"}, caller=ai_token)
    assert r4["success"] and r4["result"]["count"] == 2
