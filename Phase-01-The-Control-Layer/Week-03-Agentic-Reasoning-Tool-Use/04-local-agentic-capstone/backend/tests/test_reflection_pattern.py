import modules.logic.reflection as reflection
from modules.logic.reflection import run_reflection_pipeline
from modules.state.sqlite_store import SQLiteStateStore


def _event(event_type: str, content: str | None = None, usage: dict | None = None):
    event = {"type": event_type}
    if content is not None:
        event["delta"] = {"content": content}
    if usage is not None:
        event["response"] = {"usage": usage}
    return event


def test_reflection_pipeline_retries_until_policy_compliant(monkeypatch, tmp_path):
    db_path = tmp_path / "reflection.sqlite"
    store = SQLiteStateStore(db_path=str(db_path))
    store.init_db()
    user = store.create_user("tester", "tester@example.com", "hash")

    calls = []

    generation_calls = [
        iter([
            _event("response.output_text.delta", "Draft response one."),
            _event("response.completed", usage={"input_tokens": 10, "output_tokens": 12, "total_tokens": 22}),
        ]),
        iter([
            _event("response.output_text.delta", "Revised policy-safe response."),
            _event("response.completed", usage={"input_tokens": 11, "output_tokens": 14, "total_tokens": 25}),
        ]),
    ]

    critique_calls = [
        iter([
            _event(
                "response.output_text.delta",
                '{"compliant": false, "score": 0.2, "issues": ["missing safe alternative"], "correction_instructions": "Add a safe alternative and avoid policy conflicts.", "rationale": "unsafe"}',
            ),
            _event("response.completed", usage={"input_tokens": 8, "output_tokens": 9, "total_tokens": 17}),
        ]),
        iter([
            _event(
                "response.output_text.delta",
                '{"compliant": true, "score": 0.98, "issues": [], "correction_instructions": "", "rationale": "policy compliant"}',
            ),
            _event("response.completed", usage={"input_tokens": 8, "output_tokens": 9, "total_tokens": 17}),
        ]),
    ]

    def fake_create(*args, **kwargs):
        calls.append(kwargs.get("input", []))
        if len(calls) in (1, 3):
            return generation_calls.pop(0)
        return critique_calls.pop(0)

    monkeypatch.setattr(reflection.openai_client.responses, "create", fake_create)
    monkeypatch.setattr(reflection, "record_event", lambda *args, **kwargs: None)

    result = run_reflection_pipeline(
        prompt_text="User asks for a response that must follow policy.",
        max_attempts=2,
        state_store=store,
        user_id=user.id,
    )

    assert result.policy_compliant is True
    assert result.attempts == 2
    assert "Revised policy-safe response." in result.final_text
    assert len(result.reviews) == 2

    review_metrics = store.search_metrics(user_id=user.id, event_type="reflection_review")
    final_metrics = store.search_metrics(user_id=user.id, event_type="reflection_final")
    assert len(review_metrics) == 2
    assert len(final_metrics) == 1
    assert final_metrics[0]["payload"]["policy_compliant"] is True