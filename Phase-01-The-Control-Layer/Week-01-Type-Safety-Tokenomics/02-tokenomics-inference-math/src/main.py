from pydantic import ValidationError
from schema import SupportTicket
from engine import instructor_client, openai_client
import os
from tabulate import tabulate
from logger import logging, log_invalid_output
import json
import re
import time
import tiktoken

def api_wrapper(api_func):
    def wrapped(*args, **kwargs):
        start = time.time()
        response, completion = api_func(*args, **kwargs)
        end = time.time()
        duration = end - start

        usage = getattr(completion, "usage", None)

        metadata = {
            "total_duration": duration,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0
            }
        }

        return response, metadata
    return wrapped

def extract_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else None

def calulate_price(prompt_tokens, completion_tokens):
    # Pricing based on OpenAI's GPT-4o-mini rates: $0.15 per 1M prompt tokens and $0.60 per 1M completion tokens
    prompt_cost = (prompt_tokens / 1_000_000) * 0.15
    completion_cost = (completion_tokens / 1_000_000) * 0.60
    total_cost = prompt_cost + completion_cost
    return total_cost

@api_wrapper
def classify_support_ticket(email_text: str) -> SupportTicket:
    response, completion = instructor_client.chat.completions.create_with_completion(
        response_model=SupportTicket,
        messages=[
            {
                "role": "user",
                "content": email_text
            }
        ]
    )
    return response, completion

def classify_support_ticket_stream(email_text: str):
    start = time.time()
    ttft = None
    content = ""

    stream = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    "Classify this support ticket and respond ONLY with a valid JSON object matching this schema:\n"
                    '{"priority": "High|Medium|Low", "department": "Billing|Tech|General", "summary": "string"}\n'
                    f"Ticket: {email_text}"
                )
            }
        ],
        stream=True
    )

    for i, partial in enumerate(stream):
        if i == 0:
            ttft = time.time() - start
        delta = getattr(partial.choices[0], "delta", None)
        token = getattr(delta, "content", "") if delta else ""
        content += token or ""

    TTFT_THRESHOLD = 2.0

    if ttft and ttft > TTFT_THRESHOLD:
        logging.warning(f"Time to first token ({ttft:.2f}s) exceeded threshold for input: {email_text}")
    else:
        logging.info(f"Time to first token: {ttft:.2f}s for input: {email_text}")
        
    total_duration = time.time() - start
    json_content = extract_json(content)
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    prompt_tokens = len(enc.encode(email_text))
    completion_tokens = len(enc.encode(content))
    if not json_content:
        raise ValueError("no JSON found in model output!")
    response = SupportTicket.model_validate_json(json_content) if json_content else None
    metadata = {
        "total_duration": total_duration,
        "time_to_first_token": ttft,
        "cost": calulate_price(prompt_tokens, completion_tokens),
        "time_difference": total_duration - ttft if ttft else None
    }
    logging.info(f"Metadata: {metadata} for input: {email_text}")
    return response, metadata

def classify_support_ticket_with_retries(email_text: str, max_retries: int = 3) -> SupportTicket:
    for attempt in range(max_retries):
        try:
            response, metadata = classify_support_ticket(email_text)
            logging.info(f"Attempt {attempt+1}: Prompted with: {email_text}")
            if "details are unclear" in response.summary or "need further investigation" in response.summary:
                log_invalid_output(email_text, response.model_dump(), "Summary indicates uncertainty")
                continue
            return response, metadata
        except ValidationError as e:
            logging.error(f"Validation error on attempt {attempt + 1}: {e}")
            log_invalid_output(email_text, None, e)
            validation_error = e
    logging.error("Failed to classify after retries.")
    return None, None

def print_ticket(ticket):
    if ticket:
        logging.info(f"Success: {ticket}")
        print(f"Priority  : {ticket.priority.value}")
        print(f"Department: {ticket.department.value}")
        print(f"Summary   : {ticket.summary}")
    else:
        logging.error("Failed to classify the support ticket.")


if __name__ == "__main__":
    email_text = "Hello, I was charged twice for my subscription and I need a refund. Please help me resolve this issue as soon as possible."
    response, metadata = classify_support_ticket_stream(email_text)
    print_ticket(response)