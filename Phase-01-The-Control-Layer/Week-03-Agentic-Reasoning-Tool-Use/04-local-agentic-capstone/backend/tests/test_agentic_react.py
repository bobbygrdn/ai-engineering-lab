from types import SimpleNamespace

from modules.logic.agentic_react import run_react_session


def _event(event_type: str, content: str | None = None):
    event = SimpleNamespace(type=event_type)
    if content is not None:
        event.delta = SimpleNamespace(content=content)
    return event


class FakeStateStore:
    def __init__(self):
        self.token_budget = 10_000
        self.added = []
        self.applied = []

    def get_user_by_id(self, user_id):
        return {"id": user_id, "username": "tester"}

    def add_memory(self, *, user_id, mtype, content, importance=0.5, tags=None, token_count=0):
        self.added.append(
            {
                "user_id": user_id,
                "mtype": mtype,
                "content": content,
                "importance": importance,
                "tags": tags or [],
                "token_count": token_count,
            }
        )

    def list_memories(self, user_id):
        return []

    def delete_memory(self, user_id, memory_id):
        return False

    def apply_patches(self, *, user_id, patches):
        self.applied.append({"user_id": user_id, "patches": patches})
        return [{"op": patch.get("op"), "ok": True, "id": patch.get("id", "generated-id")} for patch in patches]


def test_run_react_session_applies_sqlite_writeback_and_persists_memory(monkeypatch):
    raw_response = (
        'PATCHES: {"patches":[{"op":"upsert","type":"preferences","content":{"theme":"dark"},"importance":0.8}],'
        '"final_answer":{"status":"done"}}'
    )

    captured_writeback = {}

    monkeypatch.setattr(
        "modules.logic.agentic_react.openai.responses.create",
        lambda *args, **kwargs: iter([
            _event("response.output_text.delta", raw_response),
        ]),
    )
    monkeypatch.setattr("modules.logic.agentic_react.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "modules.logic.agentic_react.DurableMemoryManager.apply_llm_writeback",
        lambda self, text: captured_writeback.setdefault("raw", text) or {"applied": [{"op": "upsert", "ok": True}]},
    )

    state_store = FakeStateStore()
    tool_engine = SimpleNamespace(invoke=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tool invoke should not be called")))
    auth_manager = SimpleNamespace(create_access_token=lambda **kwargs: "token")

    events = list(
        run_react_session(
            prompt_text="Please store my preference and finish.",
            user_id=7,
            request_meta={},
            tool_engine=tool_engine,
            state_store=state_store,
            auth_manager=auth_manager,
            max_steps=2,
        )
    )

    assert captured_writeback["raw"] == raw_response
    assert any(entry["mtype"] == "agent_trace" for entry in state_store.added)
    assert any(entry["mtype"] == "agent_final_answer" for entry in state_store.added)
    assert any(event["type"] == "final" and event["data"] == {"status": "done"} for event in events)