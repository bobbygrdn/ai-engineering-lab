from fastapi.testclient import TestClient
from app import app
import app as app_module
import pytest
import json
from modules.schemas.type_safety import SupportTicket, Metadata, Usage, SupportTicketResponse
from modules.utils.helpers import calculate_price

client = TestClient(app)

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
    assert response.json() == {"detail": "An error occurred: 500: Failed to classify the support ticket."}

def test_classify_endpoint_with_invalid_payload():
    response = client.post("/api/classify", json={"invalid_field": "test"})
    assert response.status_code == 422

def test_handle_endpoint():
    prompt_tokens = 86
    completion_tokens = 40
    expected_price = calculate_price(prompt_tokens, completion_tokens)

    def fake_handle_generator(text):
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
        response = client.post("/api/handle", json={"email_text": email_text})
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