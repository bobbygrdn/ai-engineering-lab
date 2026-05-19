from types import SimpleNamespace
import pytest
from modules.utils import helpers

def test_calculate_price_basic():
    price = helpers.calculate_price(1000000, 1000000)
    assert pytest.approx(price, rel=1e-6) == 0.75

    assert helpers.calculate_price(0, 0) == 0.0

def test_extract_json_success():
    text = "Here is the object: {\"a\": 1, \"b\": \"x\"} and some trailing text."
    extracted = helpers.extract_json(text)

    assert extracted is not None
    assert extracted.strip().startswith("{")
    assert "\"a\": 1" in extracted
    assert "\"b\": \"x\"" in extracted

def test_extract_json_no_json():
    text = "No JSON here, just plain text."
    assert helpers.extract_json(text) is None

def make_event(delta_content=None, usage=None, as_dict=False):
    delta = None
    response = None

    if delta_content is not None:
        delta = SimpleNamespace(content=delta_content)
    if usage is not None:
        response = SimpleNamespace(usage=usage)
    if as_dict:
        ev = {}
        if delta is not None:
            ev["delta"] = {"content": delta_content}
        if response is not None:
            ev["response"] = {"usage": usage}
        return ev
    ev = SimpleNamespace(type="response.output_text.delta")
    if delta is not None:
        ev.delta = delta
    if response is not None:
        ev.response = response
    return ev

def test_event_type_with_namespace_and_dict():
    ns = make_event(delta_content="hello", as_dict=False)
    assert helpers._event_type(ns) == "hello"

    d = make_event(delta_content="dict-hello", as_dict=True)
    assert helpers._event_type(d) == "dict-hello"

def test_event_type_missing_delta():
    ev = SimpleNamespace()
    assert helpers._event_type(ev) == ""
    assert helpers._event_type({}) == ""

def test_extract_usage_from_event_namespace_and_dict():
    usage = {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
    ns = make_event(usage=usage, as_dict=False)
    result_ns = helpers._extract_usage_from_event(ns)
    assert result_ns["prompt_tokens"] == 5
    assert result_ns["completion_tokens"] == 10
    assert result_ns["total_tokens"] == 15

    d = make_event(usage=usage, as_dict=True)
    result_d = helpers._extract_usage_from_event(d)
    assert result_d["prompt_tokens"] == 5
    assert result_d["completion_tokens"] == 10
    assert result_d["total_tokens"] == 15

def test_extract_usage_from_event_missing_response():
    assert helpers._extract_usage_from_event(SimpleNamespace()) == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert helpers._extract_usage_from_event({}) == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}