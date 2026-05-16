from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_heartbeat():
    response = client.get("/api/heartbeat")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_classify_endpoint():
    email_text = "I was charged twice for my subscription. Please help me resolve this issue."
    response = client.post("/api/classify", json={"email_text": email_text})
    assert response.status_code == 200
    data = response.json()
    assert "priority" in data
    assert "department" in data
    assert "summary" in data

def test_classify_endpoint_empty_email():
    response = client.post("/api/classify", json={"email_text": ""})
    assert response.status_code == 500
    assert response.json() == {"detail": "An error occurred: 500: Failed to classify the support ticket."}

def test_classify_endpoint_with_invalid_payload():
    response = client.post("/api/classify", json={"invalid_field": "test"})
    assert response.status_code == 422