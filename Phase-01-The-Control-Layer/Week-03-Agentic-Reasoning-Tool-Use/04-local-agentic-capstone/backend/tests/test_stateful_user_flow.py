import uuid

from fastapi.testclient import TestClient

from app import app
import app as app_module
from modules.schemas.type_safety import SupportAIService
from modules.state import SQLiteStateStore


client = TestClient(app)


def _register_user():
    username = f"flow_{uuid.uuid4().hex[:8]}"
    password = "StrongPass123!"
    email = f"{username}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    return username, password, body["access_token"]


def _login(username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_multi_step_stateful_flow_with_recall(tmp_path, monkeypatch):
    db_path = tmp_path / "app_state.db"
    store = SQLiteStateStore(db_path=str(db_path))
    store.init_db()
    monkeypatch.setattr(app_module, "state_store", store)
    monkeypatch.setattr(app_module, "ai_service", SupportAIService(state_store=store))

    username, password, access_token = _register_user()

    captured_prompts: list[str] = []

    def fake_stream(prompt_text: str):
        captured_prompts.append(prompt_text)
        if len(captured_prompts) == 1:
            response_text = (
                "Acknowledged. PATCHES:["
                '{"op":"upsert","type":"preferences","content":{"communication_preference":"email updates"},"importance":0.9,"token_count":6}'
                "]"
            )
        else:
            response_text = "You prefer email updates for communication."

        yield {"type": "delta", "data": {"text": response_text}}
        yield {"type": "done", "data": {}}
        yield {
            "type": "completed",
            "data": {
                "intent": "simple",
                "response_text": response_text,
                "metadata": {
                    "total_duration": 0.01,
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                        "interaction_price": 0.0,
                    },
                },
            },
        }

    import modules.logic.reflection as reflection_mod

    class FakeReflectionResult:
        def __init__(self, text: str):
            self.final_text = text
            self.policy_compliant = True
            self.attempts = 1
            self.generation_latency = 0.01
            self.critique_latency = 0.0
            self.total_latency = 0.01
            self.reviews = []
            self.usage = {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "interaction_price": 0.0,
            }

    def fake_run_reflection(prompt_text: str, **kwargs):
        captured_prompts.append(prompt_text)
        if len(captured_prompts) == 1:
            response_text = (
                "Acknowledged. PATCHES:["
                '{"op":"upsert","type":"preferences","content":{"communication_preference":"email updates"},"importance":0.9,"token_count":6}'
                "]"
            )
        else:
            response_text = "You prefer email updates for communication."

        return FakeReflectionResult(response_text)

    monkeypatch.setattr(reflection_mod, "run_reflection_pipeline", fake_run_reflection)

    first = client.post(
        "/api/handle",
        json={"email_text": "I prefer email updates for account alerts."},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert first.status_code == 200

    new_session_access_token = _login(username, password)
    second = client.post(
        "/api/handle",
        json={"email_text": "What communication preference do I have?"},
        headers={"Authorization": f"Bearer {new_session_access_token}"},
    )
    assert second.status_code == 200

    assert len(captured_prompts) == 2
    assert "communication_preference" in captured_prompts[1]
    assert "email updates" in captured_prompts[1]
