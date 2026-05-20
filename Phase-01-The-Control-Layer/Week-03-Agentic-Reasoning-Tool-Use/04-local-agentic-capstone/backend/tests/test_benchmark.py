import json
import time

import pytest

from modules.schemas.type_safety import Metadata, SupportTicket, Usage
from modules.utils.helpers import calculate_price
from modules.utils.exceptions import EmptyPromptError


def test_load_emails_from_json_and_text(tmp_path):
    from modules.utils.benchmark import load_emails

    json_path = tmp_path / "emails.json"
    json_path.write_text(json.dumps(["first email", "", {"email_text": "second email"}]), encoding="utf-8")
    assert load_emails(json_path) == ["first email", "", "second email"]

    text_path = tmp_path / "emails.txt"
    text_path.write_text("line one\n\nline two\n", encoding="utf-8")
    assert load_emails(text_path) == ["line one", "", "line two"]


def test_run_benchmark_writes_summary_and_trace(tmp_path, monkeypatch):
    from modules.utils import benchmark

    fake_ticket = SupportTicket(priority="Low", department="Billing", summary="Test summary.")
    fake_metadata = Metadata(
        total_duration=1.23,
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30, interaction_price=calculate_price(10, 20)),
    )

    def fake_classify(email_text, max_retries=3, raise_on_failure=False):
        if email_text == "":
            raise EmptyPromptError("Email text cannot be empty.")
        if "bad" in email_text:
            return None, fake_metadata
        return fake_ticket, fake_metadata

    monkeypatch.setattr(benchmark, "classify_support_ticket_with_retries", fake_classify)

    summary_path = tmp_path / "benchmark.md"
    trace_path = tmp_path / "benchmark_trace.jsonl"

    summary = benchmark.run_benchmark(["good email", "", "bad email"], summary_path, trace_path)

    assert summary["total"] == 3
    assert summary["valid_count"] == 1
    assert summary["invalid_count"] == 2
    assert summary["accuracy"] == pytest.approx(1 / 3)
    assert summary["average_cost_per_valid_ticket"] == calculate_price(10, 20)

    markdown = summary_path.read_text(encoding="utf-8")
    assert "# Benchmark Summary" in markdown
    assert "Accuracy: 33.33%" in markdown
    assert "| 1 | good email | Yes |" in markdown
    assert "| 2 | <empty> | No |" in markdown
    assert "| 3 | bad email | No |" in markdown

    trace_lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(trace_lines) == 7
    assert json.loads(trace_lines[-1])["event"] == "benchmark_summary"


def test_run_benchmark_times_out_slow_email(tmp_path, monkeypatch):
    from modules.utils import benchmark

    fake_metadata = Metadata(
        total_duration=0.1,
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2, interaction_price=calculate_price(1, 1)),
    )

    def slow_classify(email_text, max_retries=3, raise_on_failure=False):
        time.sleep(0.2)
        return None, fake_metadata

    monkeypatch.setattr(benchmark, "classify_support_ticket_with_retries", slow_classify)

    summary_path = tmp_path / "benchmark.md"
    trace_path = tmp_path / "benchmark_trace.jsonl"

    start = time.time()
    summary = benchmark.run_benchmark(["slow email"], summary_path, trace_path, email_timeout_seconds=0.05)
    elapsed = time.time() - start

    assert elapsed < 1.0
    assert summary["total"] == 1
    assert summary["valid_count"] == 0
    assert summary["invalid_count"] == 1
    assert "Timed out" in summary_path.read_text(encoding="utf-8")