from fastapi.testclient import TestClient
from app import app
import app as app_module
from modules.schemas.type_safety import SupportTicket, Metadata, Usage

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