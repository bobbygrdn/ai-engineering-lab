import modules.logic.reflection as reflection
from modules.logic.reflection import run_reflection_pipeline
from modules.state.sqlite_store import SQLiteStateStore


def test_reflection_pipeline_flags_unverified_contact(monkeypatch, tmp_path):
    db_path = tmp_path / "reflection_contact.sqlite"
    store = SQLiteStateStore(db_path=str(db_path))
    store.init_db()
    user = store.create_user("tester", "tester@example.com", "hash")

    # Fake draft contains explicit contact details that should be blocked
    def fake_generate(prompt_text, policy_text, feedback=None, model=None):
        return {
            "text": "You can reach support at support@example.com or call 1-800-123-4567.",
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            "latency": 0.02,
        }

    # The critic (LLM) might erroneously mark it compliant; our rule should override that.
    def fake_critique(prompt_text, draft_text, policy_text, model=None):
        crit = reflection.CritiqueResult(
            compliant=True,
            score=0.9,
            issues=[],
            correction_instructions="",
            rationale="",
        )
        return crit, 0.01

    monkeypatch.setattr(reflection, "_generate_draft", fake_generate)
    monkeypatch.setattr(reflection, "_critique_draft", fake_critique)
    monkeypatch.setattr(reflection, "record_event", lambda *args, **kwargs: None)

    result = run_reflection_pipeline(
        prompt_text="User asks how to contact support.",
        max_attempts=1,
        state_store=store,
        user_id=user.id,
    )

    assert result.policy_compliant is False
    assert result.attempts == 1
    # Our automated rule should add the issue to the recorded review
    assert any("contains_unverified_contact_details" in (r.get("issues") or []) for r in result.reviews)
    assert "can’t help" in result.final_text or "I’m sorry" in result.final_text
