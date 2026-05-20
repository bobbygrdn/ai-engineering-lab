from datetime import datetime
from modules.utils.logging import logger
import json
import re
from typing import Optional, Any

def log_invalid_output(email_text, output, error):
    record = {
        "timestamp": datetime.now().isoformat(),
        "email_text": email_text,
        "output": output,
        "error": error,
    }
    with open('invalid_outputs.jsonl', 'a', encoding='utf-8') as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")

def extract_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else None

def calculate_price(prompt_tokens, completion_tokens):
    # Pricing based on OpenAI's GPT-4o-mini rates: $0.15 per 1M tokens and $0.60 per 1M completion tokens
    prompt_cost = (prompt_tokens / 1_000_000) * 0.15
    completion_cost = (completion_tokens / 1_000_000) * 0.60
    return prompt_cost + completion_cost

def print_ticket(ticket):
    if ticket:
        logger.info(f"Success: {ticket}")
        print(f"Priority: {ticket.priority}")
        print(f"Department: {ticket.department}")
        print(f"Summary: {ticket.summary}")
    else:
        logger.error("Failed to classify the support ticket.")

def _event_type(event: Any) -> Optional[str]:
    delta = getattr(event, "delta", None) if not isinstance(event, dict) else event.get("delta")

    if not delta:
        return ""
    if isinstance(delta, dict):
        return delta.get("content", "") or delta.get("text", "") or ""
    return getattr(delta, "content", "") or getattr(delta, "text", "") or ""

def _extract_usage_from_event(event: Any) -> dict:
    response = getattr(event, "response", None) if not isinstance(event, dict) else event.get("response")
    if not response:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if isinstance(response, dict):
        usage = response.get("usage", {}) or {}
    else:
        usage = getattr(response, "usage", {}) or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0)
    }