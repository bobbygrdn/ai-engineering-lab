from types import SimpleNamespace
import pytest

from modules.schemas.type_safety import SLModel, FrontierModel, SupportTicket, Metadata, Usage
from modules.utils.helpers import calculate_price


def make_stream_events(text: str, input_tokens: int = 0, output_tokens: int = 0):
    def _make_event(event_type: str, content: str | None = None, usage: dict | None = None):
        ev = SimpleNamespace(type=event_type)
        if content is not None:
            ev.delta = SimpleNamespace(content=content)
        if usage is not None:
            ev.response = SimpleNamespace(usage=SimpleNamespace(**usage))
        return ev

    mid = len(text) // 2
    yield _make_event("response.output_text.delta", content=text[:mid])
    yield _make_event("response.output_text.delta", content=text[mid:])
    yield _make_event("response.output_text.done")
    yield _make_event("response.completed", usage={"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens})


def test_slmodel_stream_generation(monkeypatch):
    gen_text = "Thanks — we'll look into this."
    monkeypatch.setattr("modules.logic.agentic_logic.openai_client.responses.create", lambda *a, **k: make_stream_events(gen_text, 3, 4))

    model = SLModel()
    events = list(model.infer_response("Status update please"))

    # Verify delta events
    delta_events = [e for e in events if e["type"] == "delta"]
    assert len(delta_events) > 0
    assert "".join(e["data"]["text"] for e in delta_events) == gen_text

    # Verify done event
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1

    # Verify completed event
    completed_events = [e for e in events if e["type"] == "completed"]
    assert len(completed_events) == 1
    resp = completed_events[0]["data"]

    assert resp["intent"] == "simple"
    assert "Thanks" in resp["response_text"]
    assert resp["metadata"]["usage"]["prompt_tokens"] == 3
    assert resp["metadata"]["usage"]["completion_tokens"] == 4
    assert resp["metadata"]["usage"]["interaction_price"] == calculate_price(3, 4)


def test_frontiermodel_stream_classify_and_generate(monkeypatch):
    fake_ticket = SupportTicket(priority="Low", department="Billing", summary="Charged twice.")
    cls_usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30, interaction_price=calculate_price(10, 20))
    cls_meta = Metadata(total_duration=0.1, usage=cls_usage)

    monkeypatch.setattr(
        "modules.logic.agentic_logic.classify_support_ticket_with_retries",
        lambda text: (fake_ticket, cls_meta),
    )

    gen_text = "We will refund the duplicate charge."
    monkeypatch.setattr("modules.logic.agentic_logic.openai_client.responses.create", lambda *a, **k: make_stream_events(gen_text, 2, 5))

    model = FrontierModel()
    events = list(model.infer_response("I was charged twice for my subscription."))

    # Verify delta events
    delta_events = [e for e in events if e["type"] == "delta"]
    assert len(delta_events) > 0
    assert "".join(e["data"]["text"] for e in delta_events) == gen_text

    # Verify done event
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1

    # Verify completed event with merged usage
    completed_events = [e for e in events if e["type"] == "completed"]
    assert len(completed_events) == 1
    resp = completed_events[0]["data"]

    assert resp["intent"] == "complex"
    assert "refund" in resp["response_text"].lower()
    assert resp["metadata"]["usage"]["prompt_tokens"] == 12  # 10 + 2
    assert resp["metadata"]["usage"]["completion_tokens"] == 25  # 20 + 5
    assert resp["metadata"]["usage"]["interaction_price"] == calculate_price(12, 25)

