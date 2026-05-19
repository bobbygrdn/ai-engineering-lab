import logging
from types import SimpleNamespace
import pytest

import modules.logic.agentic_logic as agentic_logic
from modules.logic.agentic_logic import classify_support_ticket_stream, classify_support_ticket_with_retries
from modules.schemas.type_safety import SupportTicket, Metadata


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


def fake_stream_single_delta():
   yield make_response_event(
       "response.output_text.delta",
       content='{"priority":"Low","department":"Billing","summary":"Single-delta summary."}',
   )
   yield make_response_event("response.output_text.done")


def fake_stream_malformed_but_extractable():
   yield make_response_event(
       "response.output_text.delta",
       content='prefix garbage {"priority":"Low","department":"Billing","summary":"Extractable."} suffix',
   )
   yield make_response_event("response.output_text.done")


def test_ttft_triggers_warning(monkeypatch, caplog):
   monkeypatch.setattr(
       "modules.logic.agentic_logic.openai_client.responses.create",
       lambda *args, **kwargs: fake_stream_single_delta(),
   )

   times = iter([100.0, 104.5]) 

   def fake_time():
       try:
           return next(times)
       except StopIteration:
           return 104.5

   monkeypatch.setattr(agentic_logic, "time", agentic_logic.time)
   monkeypatch.setattr(agentic_logic.time, "time", fake_time)

   caplog.set_level(logging.WARNING)
   ticket, metadata = classify_support_ticket_stream("Please help me with billing")

   assert ticket is not None
   assert any("Time to first token" in rec.getMessage() and rec.levelno == logging.WARNING for rec in caplog.records)

def test_stream_without_completed_returns_defaults(monkeypatch):
   monkeypatch.setattr(
       "modules.logic.agentic_logic.openai_client.responses.create",
       lambda *args, **kwargs: fake_stream_single_delta(),
   )

   ticket, metadata = classify_support_ticket_stream("I have a minor billing question.")

   assert ticket is not None
   assert isinstance(metadata, Metadata)
   assert metadata.usage.prompt_tokens == 0
   assert metadata.usage.completion_tokens == 0
   assert metadata.usage.total_tokens == 0

def test_malformed_json_falls_back_to_extract(monkeypatch):
   monkeypatch.setattr(
       "modules.logic.agentic_logic.openai_client.responses.create",
       lambda *args, **kwargs: fake_stream_malformed_but_extractable(),
   )

   ticket, metadata = classify_support_ticket_stream("Please check my double-charge")

   assert ticket is not None
   assert ticket.priority.value == "Low"
   assert ticket.department.value == "Billing"
   assert "Extractable" in ticket.summary

def test_missing_api_key_causes_safe_failure(monkeypatch):
   def raise_missing_key(*args, **kwargs):
       raise Exception("Missing API Key")

   monkeypatch.setattr("modules.logic.agentic_logic.openai_client.responses.create", raise_missing_key)
   monkeypatch.setattr(agentic_logic.openai_client, "api_key", None)

   ticket, metadata = classify_support_ticket_with_retries("I was charged twice")

   assert ticket is None
   assert isinstance(metadata, Metadata)
   assert metadata.usage.prompt_tokens == 0
   assert metadata.usage.completion_tokens == 0
   assert metadata.usage.total_tokens == 0

def test_handle_endpoint_returns_500_on_internal_error(monkeypatch):
   from fastapi.testclient import TestClient
   import app as app_module
   import json

   client = TestClient(app_module.app)
   original_handle = getattr(app_module.ai_service, "handle_ticket", None)

   def raise_error_generator(text):
       raise Exception("Missing API Key")
       yield  # Make this a generator function

   app_module.ai_service.handle_ticket = raise_error_generator

   try:
       resp = client.post("/api/handle", json={"email_text": "Will this fail?"})
       # With streaming, we get 200 with an error event inside the stream
       assert resp.status_code == 200
       
       # Parse SSE events to find the error event
       events = []
       for line in resp.text.strip().split("\n\n"):
           if line.startswith("data: "):
               events.append(json.loads(line[6:]))
       
       # Should have an error event
       error_events = [e for e in events if e.get("type") == "error"]
       assert len(error_events) > 0
       assert "Missing API Key" in error_events[0]["data"]["message"]
   finally:
       if original_handle is not None:
           app_module.ai_service.handle_ticket = original_handle