from types import SimpleNamespace
import json
import pytest
import modules.logic.agentic_logic as agentic_logic
from modules.logic.agentic_logic import classify_support_ticket_stream, classify_support_ticket_with_retries
from modules.schemas.type_safety import Metadata, SupportTicket
from modules.utils.helpers import log_invalid_output

def make_response_event(event_type: str, content: str | None = None, usage: dict | None = None):
    delta = None
    response = None

    if content is not None:
        delta = SimpleNamespace(content=content)
    if usage is not None:
        response = SimpleNamespace(usage=SimpleNamespace(**usage))

    event = SimpleNamespace(type=event_type)
    if delta is not None:
        event.delta = delta
    if response is not None:
        event.response = response
    return event

def fake_stream_success():
    yield make_response_event(
        "response.output_text.delta",
        content='{"priority":"Low","department":"Billing","summary":"Test summary."}',
    )
    yield make_response_event("response.output_text.done")
    yield make_response_event(
        "response.completed",
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )

def fake_stream_empty():
    yield make_response_event("response.output_text.done")
    yield make_response_event("response.completed", usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

def test_classify_support_ticket_stream(monkeypatch):
    monkeypatch.setattr(
        "modules.logic.agentic_logic.openai_client.responses.create",
        lambda *args, **kwargs: fake_stream_success(),
    )

    ticket, metadata = classify_support_ticket_stream("I have a billing issue.")

    assert isinstance(ticket, SupportTicket)
    assert ticket.priority.value == "Low"
    assert ticket.department.value == "Billing"
    assert ticket.summary == "Test summary."

    assert isinstance(metadata, Metadata)
    assert metadata.total_duration >= 0
    assert metadata.usage.prompt_tokens == 1
    assert metadata.usage.completion_tokens == 2
    assert metadata.usage.total_tokens == 3

def test_classify_support_ticket_with_empty_input():
    with pytest.raises(ValueError, match="Email text cannot be empty\\."):
        classify_support_ticket_stream("")

def test_classify_support_ticket_with_retries(monkeypatch):
    monkeypatch.setattr(
        "modules.logic.agentic_logic.openai_client.responses.create",
        lambda *args, **kwargs: fake_stream_success(),
    )

    email_text = "I need help with my billing issue. I was charged twice for my subscription."
    ticket, metadata = classify_support_ticket_with_retries(email_text)

    assert isinstance(ticket, SupportTicket)
    assert ticket.priority.value == "Low"
    assert ticket.department.value == "Billing"
    assert ticket.summary == "Test summary."

    assert isinstance(metadata, Metadata)
    assert metadata.total_duration >= 0
    assert metadata.usage.prompt_tokens == 1
    assert metadata.usage.completion_tokens == 2
    assert metadata.usage.total_tokens == 3

def test_classify_support_ticket_with_retries_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.logic.agentic_logic.openai_client.responses.create",
        lambda *args, **kwargs: fake_stream_empty(),
    )
    monkeypatch.setattr(agentic_logic, "log_invalid_output", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)

    email_text = "^^&()_&$#%^#_(_)*&^&*(^*(*&))"
    ticket, metadata = classify_support_ticket_with_retries(email_text, max_retries=2)

    assert ticket is None
    assert isinstance(metadata, Metadata)
    assert metadata.total_duration >= 0
    assert metadata.usage.prompt_tokens == 0
    assert metadata.usage.completion_tokens == 0
    assert metadata.usage.total_tokens == 0

def test_log_invalid_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    email_text = "Invalid email text"
    output = None
    error = "ValidationError: Invalid input"

    log_invalid_output(email_text, output, error)

    contents = (tmp_path / "invalid_outputs.jsonl").read_text().strip().splitlines()
    assert len(contents) == 1
    payload = json.loads(contents[0])
    assert payload["email_text"] == email_text
    assert payload["error"] == error