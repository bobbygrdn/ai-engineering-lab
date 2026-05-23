import os

from modules.tools.engine import engine, HookAbort
from modules.tools.hooks_builtin import rate_limit_hook_factory


LEGACY_TEST_DB = "db/test_roles.db"


def test_rate_limit_hook_blocks(tmp_path, monkeypatch):
    # simple tool manifest
    manifest = {
        "schema_version": "1.0",
        "name": "tool.test_rate",
        "version": "0.1",
        "description": "test rate",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": True},
    }

    def noop(args):
        return {"ok": True}

    engine.register_tool(manifest, noop)
    # small limiter
    hook = rate_limit_hook_factory(max_calls=2, window_seconds=60)
    engine.register_pre_invoke_hook(hook)
    from modules.auth.security import AuthManager
    token = AuthManager().create_access_token(user_id=1, username="alice")
    try:
        r1 = engine.invoke("tool.test_rate", {}, caller=token)
        assert r1["success"]
        r2 = engine.invoke("tool.test_rate", {}, caller=token)
        assert r2["success"]
        r3 = engine.invoke("tool.test_rate", {}, caller=token)
        assert r3["success"] is False
        assert r3["error"] == "rate limit exceeded"
    finally:
        engine.unregister_pre_invoke_hook(hook)


def test_role_check_hook_allows_and_denies(tmp_path):
    # exercise the state-store-backed role check factory
    from modules.state.sqlite_store import SQLiteStateStore
    # Defensive cleanup for legacy fixed-path test DB from older test versions.
    if os.path.exists(LEGACY_TEST_DB):
        try:
            os.remove(LEGACY_TEST_DB)
        except OSError:
            pass

    tmp_db = str(tmp_path / "test_roles.db")

    ss = SQLiteStateStore(db_path=tmp_db)
    ss.init_db()
    alice = ss.create_user("alice", "alice@example.com", "x")
    bob = ss.create_user("bob", "bob@example.com", "x")
    ss.assign_role_to_user(alice.id, "admin")

    manifest = {
        "schema_version": "1.0",
        "name": "tool.test_role_state",
        "version": "0.1",
        "description": "test role via state",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": True},
        "allowed_roles": ["admin"],
    }

    def noop(args):
        return {"ok": True}

    engine.register_tool(manifest, noop)
    from modules.tools.hooks_builtin import role_check_token_per_tool_factory
    from modules.auth.security import AuthManager
    auth = AuthManager()
    # create tokens for alice and bob
    alice_token = auth.create_access_token(user_id=alice.id, username="alice")
    bob_token = auth.create_access_token(user_id=bob.id, username="bob")
    hook = role_check_token_per_tool_factory(auth, ss, allowed_roles=["admin"], tool_name="tool.test_role_state")
    # isolate test: save and clear existing hooks (app may have registered its own)
    prev_hooks = list(engine._pre_invoke_hooks)
    engine.clear_pre_invoke_hooks()
    engine.register_pre_invoke_hook(hook)
    try:
        ok = engine.invoke("tool.test_role_state", {}, caller=alice_token)
        assert ok["success"] is True
        denied = engine.invoke("tool.test_role_state", {}, caller=bob_token)
        assert denied["success"] is False and denied["error"] == "caller missing required role"
    finally:
        # restore previous hooks
        engine.clear_pre_invoke_hooks()
        for h in prev_hooks:
            engine.register_pre_invoke_hook(h)
        # Defensive cleanup in case any legacy path was created indirectly.
        if os.path.exists(LEGACY_TEST_DB):
            try:
                os.remove(LEGACY_TEST_DB)
            except OSError:
                pass

