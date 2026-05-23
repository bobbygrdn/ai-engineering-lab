import os
import sqlite3
import tempfile

from modules.tools.engine import engine
from modules.tools.sql_read_only import SQL_READ_ONLY_MANIFEST, read_only_query_tool


def test_invoke_read_only_query(tmp_path):
    # create a temporary sqlite db
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, title TEXT, status TEXT)")
    cur.execute("INSERT INTO tickets (title,status) VALUES (?,?)", ("Test","open"))
    conn.commit()
    conn.close()

    # patch module DB path to point to tmp db
    import importlib
    mod = importlib.import_module("modules.tools.sql_read_only")
    mod.DB_PATH = str(db_path)

    from modules.auth.security import AuthManager
    ai_token = AuthManager().create_access_token(user_id=0, username="ai")
    # register tool and invoke
    engine.register_tool(SQL_READ_ONLY_MANIFEST, read_only_query_tool)
    resp = engine.invoke("sqlite.read_only_query", {"query": "SELECT id, title, status FROM tickets"}, caller=ai_token)
    assert resp["success"] is True
    assert resp["result"]["count"] == 1

