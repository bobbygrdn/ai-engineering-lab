from types import SimpleNamespace

import modules.logic.agentic_react as agentic_react
from modules.logic.agentic_react import run_react_session
from modules.state.sqlite_store import SQLiteStateStore


def _event(event_type: str, content: str | None = None):
    event = SimpleNamespace(type=event_type)
    if content is not None:
        event.delta = SimpleNamespace(content=content)
    return event


def test_run_react_session_persists_sqlite_memory_and_writeback(monkeypatch, tmp_path):
    db_path = tmp_path / "agentic.sqlite"
    store = SQLiteStateStore(db_path=str(db_path), token_budget=10_000)
    store.init_db()
    user = store.create_user("tester", "tester@example.com", "hash")

    raw_response = (
        'PATCHES: {"patches":[{"op":"upsert","type":"preferences","content":{"theme":"dark"},"importance":0.8}],'
        '"final_answer":{"status":"done"}}'
    )

    monkeypatch.setattr(
        agentic_react.openai.responses,
        "create",
        lambda *args, **kwargs: iter([_event("response.output_text.delta", raw_response)]),
    )
    monkeypatch.setattr(agentic_react, "record_event", lambda *args, **kwargs: None)

    engine = SimpleNamespace(
        invoke=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tool invoke should not be called"))
    )
    auth = SimpleNamespace(create_access_token=lambda **kwargs: "token")

    events = list(
        run_react_session(
            "Please store my preference and finish.",
            user.id,
            {},
            engine,
            store,
            auth,
            max_steps=2,
        )
    )

    assert any(event["type"] == "observation" and "writeback" in event["data"] for event in events)
    assert any(event["type"] == "final" and event["data"] == {"status": "done"} for event in events)

    memories = store.list_memories(user.id)
    memory_types = [memory.type for memory in memories]
    assert "preferences" in memory_types
    assert "agent_trace" in memory_types
    assert "agent_final_answer" in memory_types

    preference_memory = next(memory for memory in memories if memory.type == "preferences")
    assert preference_memory.content == {"theme": "dark"}