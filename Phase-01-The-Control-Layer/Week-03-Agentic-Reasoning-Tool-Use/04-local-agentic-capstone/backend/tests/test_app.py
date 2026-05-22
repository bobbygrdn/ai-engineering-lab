from fastapi.testclient import TestClient
from app import app
import app as app_module
import pytest
import json
import uuid
from modules.schemas.type_safety import SupportTicket, Metadata, Usage, SupportAIService
from modules.auth import RateLimitRule
from modules.utils.helpers import calculate_price
from modules.state import SQLiteStateStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_state_store(tmp_path, monkeypatch):
    db_path = tmp_path / "app_state.db"
    store = SQLiteStateStore(db_path=str(db_path))
    store.init_db()
    monkeypatch.setattr(app_module, "state_store", store)
    monkeypatch.setattr(app_module, "ai_service", SupportAIService(state_store=store))
    app_module.auth_rate_limiter.reset()
    yield


def _register_user_and_token(username: str | None = None):
    unique_username = username or f"user_{uuid.uuid4().hex[:8]}"
    payload = {
        "username": unique_username,
        "email": f"{unique_username}@example.com",
        "password": "StrongPass123!",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200
    body = response.json()
    return body["access_token"], body["refresh_token"], payload

def test_heartbeat():
    response = client.get("/api/heartbeat")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_classify_endpoint():
    fake_ticket = SupportTicket(priority="Low", department="Billing", summary="Test summary.")
    fake_metadata = Metadata(total_duration=1.23, usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30, interaction_price=0.002))
    original = getattr(app_module, "classify_support_ticket_with_retries", None)
    app_module.classify_support_ticket_with_retries = lambda text: (fake_ticket, fake_metadata)

    try:
        email_text = "I was charged twice for my subscription. Please help me resolve this issue."
        response = client.post("/api/classify", json={"email_text": email_text})
        assert response.status_code == 200
        body = response.json()
        assert "ticket" in body and "metadata" in body
        ticket = body["ticket"]
        metadata = body["metadata"]

        assert isinstance(ticket, dict)
        assert "priority" in ticket
        assert "department" in ticket
        assert "summary" in ticket

        assert isinstance(metadata, dict)
        assert "total_duration" in metadata
        assert isinstance(metadata.get("usage"), dict)
        assert "prompt_tokens" in metadata["usage"]
        assert "completion_tokens" in metadata["usage"]
        assert "total_tokens" in metadata["usage"]
        assert "interaction_price" in metadata["usage"]
    finally:
        if original is not None:
            app_module.classify_support_ticket_with_retries = original

def test_classify_endpoint_empty_email():
    response = client.post("/api/classify", json={"email_text": ""})
    assert response.status_code == 500
    assert response.json() == {"detail": "Email text cannot be empty."}

def test_classify_endpoint_with_invalid_payload():
    response = client.post("/api/classify", json={"invalid_field": "test"})
    assert response.status_code == 422


def test_register_login_and_refresh_flow():
    access_token, refresh_token, payload = _register_user_and_token()
    assert access_token
    assert refresh_token

    login = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()
    assert "refresh_token" in login.json()

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["access_token"] != access_token
    assert refreshed_body["refresh_token"] != refresh_token


def test_logout_revokes_refresh_token():
    _, refresh_token, _ = _register_user_and_token()

    logout = client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 401
    assert refreshed.json()["detail"] == "Refresh token expired or revoked"


def test_auth_rate_limit_on_login(monkeypatch):
    _, _, payload = _register_user_and_token()
    app_module.AUTH_ENDPOINT_RULES["/api/auth/login"] = RateLimitRule(limit=2, window_seconds=60)
    app_module.AUTH_USERNAME_RULE = RateLimitRule(limit=2, window_seconds=60)
    app_module.auth_rate_limiter.reset()

    first = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    second = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    third = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_logout_all_revokes_every_refresh_token():
    access_token, refresh_token, payload = _register_user_and_token()

    # Generate another refresh by logging in again (simulates second device/session)
    login = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200
    second_refresh = login.json()["refresh_token"]

    # Call logout-all using access token
    resp = client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Both refresh tokens should be invalid now
    r1 = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    r2 = client.post("/api/auth/refresh", json={"refresh_token": second_refresh})
    assert r1.status_code == 401
    assert r2.status_code == 401


def test_handle_requires_auth():
    response = client.post("/api/handle", json={"email_text": "hello"})
    assert response.status_code == 401

def test_handle_endpoint():
    prompt_tokens = 86
    completion_tokens = 40
    expected_price = calculate_price(prompt_tokens, completion_tokens)
    access_token, _, _ = _register_user_and_token()

    def fake_handle_generator(*args, **kwargs):
        """Mock generator that yields streaming events"""
        yield {"type": "delta", "data": {"text": "Thanks for reaching "}}
        yield {"type": "delta", "data": {"text": "out."}}
        yield {"type": "done", "data": {}}
        yield {
            "type": "completed",
            "data": {
                "intent": "simple",
                "response_text": "Thanks for reaching out. We received your request and will follow up shortly.",
                "metadata": {
                    "total_duration": 1.23,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "interaction_price": expected_price
                    }
                }
            }
        }

    original_handle = getattr(app_module.ai_service, "handle_ticket", None)
    app_module.ai_service.handle_ticket = fake_handle_generator

    try:
        email_text = "Just checking my account status."
        response = client.post(
            "/api/handle",
            json={"email_text": email_text},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                import json
                events.append(json.loads(line[6:]))

        # Verify delta events
        delta_events = [e for e in events if e["type"] == "delta"]
        assert len(delta_events) == 2
        assert delta_events[0]["data"]["text"] == "Thanks for reaching "
        assert delta_events[1]["data"]["text"] == "out."

        # Verify done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

        # Verify completed event
        completed_events = [e for e in events if e["type"] == "completed"]
        assert len(completed_events) == 1
        body = completed_events[0]["data"]
        assert body["intent"] == "simple"
        assert "Thanks" in body["response_text"]
        assert isinstance(body["metadata"].get("usage"), dict)
        assert "prompt_tokens" in body["metadata"]["usage"]
        assert "completion_tokens" in body["metadata"]["usage"]
        assert "total_tokens" in body["metadata"]["usage"]
        assert body["metadata"]["usage"]["interaction_price"] == pytest.approx(expected_price)

    finally:
        if original_handle is not None:
            app_module.ai_service.handle_ticket = original_handle


def test_interactions_are_user_scoped_and_searchable(monkeypatch):
    access_token, _, payload = _register_user_and_token()

    def fake_handle_generator(*args, **kwargs):
        yield {"type": "delta", "data": {"text": "Hello "}}
        yield {"type": "done", "data": {}}
        yield {
            "type": "completed",
            "data": {
                "intent": "simple",
                "response_text": "Hello back.",
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

    monkeypatch.setattr(app_module.ai_service, "handle_ticket", fake_handle_generator)
    sent = client.post(
        "/api/handle",
        json={"email_text": "Status update please"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert sent.status_code == 200

    all_events = client.get("/api/interactions", headers={"Authorization": f"Bearer {access_token}"})
    assert all_events.status_code == 200
    items = all_events.json()["items"]
    assert len(items) > 0

    completed_events = client.get(
        "/api/interactions",
        params={"event_type": "completed"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert completed_events.status_code == 200
    filtered = completed_events.json()["items"]
    assert all(evt["event_type"] == "completed" for evt in filtered)