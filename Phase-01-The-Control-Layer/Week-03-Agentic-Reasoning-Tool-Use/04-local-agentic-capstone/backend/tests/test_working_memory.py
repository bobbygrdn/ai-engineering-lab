from modules.memory import ConversationBuilder
from modules.schemas.type_safety import SupportAIService


def test_conversation_builder_trims_oldest_non_system_messages(tmp_path):
    state_path = tmp_path / "conversation_state.json"
    builder = ConversationBuilder(state_path=state_path, token_budget=10)

    builder.append_message("system", "system instructions", 2)
    builder.append_message("user", "first user message", 4)
    builder.append_message("assistant", "assistant reply", 5)

    assert builder.total_tokens == 7
    assert builder.to_api_messages() == [
        {"role": "system", "content": "system instructions"},
        {"role": "assistant", "content": "assistant reply"},
    ]

    persisted = state_path.read_text(encoding="utf-8")
    assert "conversation_state" not in persisted
    assert '"total_tokens": 7' in persisted


def test_conversation_builder_persists_and_loads_state(tmp_path):
    state_path = tmp_path / "conversation_state.json"
    first = ConversationBuilder(state_path=state_path, token_budget=20)
    first.append_message("system", "system instructions", 2)
    first.append_message("user", "hello", 3)

    second = ConversationBuilder(state_path=state_path, token_budget=20)

    assert second.total_tokens == 5
    assert second.to_api_messages() == [
        {"role": "system", "content": "system instructions"},
        {"role": "user", "content": "hello"},
    ]


def test_support_ai_service_uses_conversation_memory(tmp_path, monkeypatch):
    state_path = tmp_path / "conversation_state.json"
    service = SupportAIService(state_path=state_path, token_budget=100)

    captured_prompts: list[str] = []

    def fake_stream(first_prompt: str):
        captured_prompts.append(first_prompt)
        yield {"type": "delta", "data": {"text": "Thanks for the update."}}
        yield {"type": "done", "data": {}}
        yield {
            "type": "completed",
            "data": {
                "intent": "simple",
                "response_text": "Thanks for the update.",
                "metadata": {
                    "total_duration": 1.0,
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                        "interaction_price": 0.0,
                    },
                },
            },
        }

    monkeypatch.setattr(service.sl_model, "infer_response", fake_stream)

    first_events = list(service.handle_ticket("Please check my account status."))
    assert any(event["type"] == "completed" for event in first_events)
    assert "System:" in captured_prompts[0]
    assert "User: Please check my account status." in captured_prompts[0]

    second_events = list(service.handle_ticket("I also need a receipt."))
    assert any(event["type"] == "completed" for event in second_events)
    assert len(captured_prompts) == 2
    assert "Thanks for the update." in captured_prompts[1]