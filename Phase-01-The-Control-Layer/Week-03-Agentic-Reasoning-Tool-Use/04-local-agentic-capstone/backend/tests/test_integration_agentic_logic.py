import os
from modules.logic.agentic_logic import classify_support_ticket_with_retries

def test_live_openai_classification():
    ticket, metadata = classify_support_ticket_with_retries(
        "I was charged twice for my subscription and need help resolving the issue."
    )

    assert ticket is not None
    assert ticket.priority.value in {"Low", "Medium", "High"}
    assert ticket.department.value in {
        "Billing",
        "Technical Support",
        "General Inquiry",
    }
    assert len(ticket.summary) > 0

    assert metadata is not None
    assert metadata.total_duration >= 0
    assert metadata.usage.total_tokens >= 0
    assert metadata.usage.prompt_tokens >= 0
    assert metadata.usage.completion_tokens >= 0