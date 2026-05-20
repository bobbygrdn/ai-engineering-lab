from modules.utils.helpers import log_invalid_output, extract_json, calculate_price, print_ticket
from modules.schemas.type_safety import SupportTicket, Metadata, Usage
from modules.utils.logging import logger
from modules.utils.exceptions import EmptyPromptError, RateLimitExceededError, RefusalError
from typing import Optional, Tuple, Any
from pydantic import ValidationError
from json import JSONDecodeError
from dotenv import load_dotenv
import openai
import time
import json
import os

load_dotenv()

openai_client = openai
openai_client.api_key = os.getenv("OPENAI_API_KEY")

def _event_type(event: Any) -> str:
    if isinstance(event, dict):
        return event.get("type", "")
    return getattr(event, "type", "") or ""

def _delta_text_from_event(event: Any) -> str:
    if isinstance(event, dict):
        delta = event.get("delta")
    else:
        delta = getattr(event, "delta", None)

    if delta is None:
        return ""
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        return delta.get("content", "") or delta.get("text", "") or ""
    return getattr(delta, "content", "") or getattr(delta, "text", "") or ""

def _usage_from_event(event: Any) -> dict:
    if isinstance(event, dict):
        response = event.get("response")
        usage = event.get("usage")
    else:
        response = getattr(event, "response", None)
        usage = getattr(event, "usage", None)

    if usage is None and response is not None:
        if isinstance(response, dict):
            usage = response.get("usage")
        else:
            usage = getattr(response, "usage", None)

    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "interaction_price": 0.0}

    if isinstance(usage, dict):
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "interaction_price": calculate_price(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
        }

    return {
        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        "interaction_price": calculate_price(getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0),
    }

def classify_support_ticket_stream(email_text: str) -> Tuple[Optional[SupportTicket], Metadata]:
    """
    Uses the Responses API streaming events to accumulate text, parse JSON,
    and always return Metadata (with defaults when usage isn't available).
    """
    if not email_text.strip():
        raise EmptyPromptError("Email text cannot be empty.")

    usage_dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "interaction_price": 0.0}
    start = time.time()
    content_parts: list[str] = []
    ttft: Optional[float] = None

    system_prompt = (
        "You are a JSON-only classifier. Return EXACTLY one valid JSON object and nothing else. "
        "The JSON must contain keys: \"priority\" (Low|Medium|High), "
        "\"department\" (Billing|Technical Support|General Inquiry), "
        "and \"summary\" (a brief 1-3 sentence summary)."
    )

    refusal_detected = False

    try:

        stream = openai_client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": email_text},
            ],
            stream=True,
        )

        for i, event in enumerate(stream):
            logger.info(f"Received event: {event}" + "\n")
            event_type = _event_type(event)
            if i == 0:
                ttft = time.time() - start

            if event_type in {"response.refusal.delta", "response.refusal.done"}:
                refusal_detected = True
                logger.warning(f"Refusal event received for email: {email_text} - event: {event}")
                break

            if event_type == "response.output_text.delta":
                content_parts.append(_delta_text_from_event(event))
            elif event_type == "response.output_text.done":
                continue
            elif event_type == "response.completed":
                usage_dict = _usage_from_event(event)
                break

        TTFT_THRESHOLD = 3.0

        if ttft and ttft > TTFT_THRESHOLD:
            logger.warning(f"Time to first token ({ttft:.2f}s) exceeded threshold for email: {email_text}")
        else:
            logger.info(f"Time to first token: {ttft:.2f}s for email: {email_text}")

        total_duration = time.time() - start
        metadata = Metadata(total_duration=total_duration, usage=Usage(**usage_dict))

        raw_text = "".join(content_parts).strip()
        if refusal_detected or any(phrase in raw_text.lower() for phrase in ("i can't assist", "i cannot assist", "i'm sorry", "i cannot comply")):
            log_invalid_output(email_text, raw_text or None, "Model refusal")
            raise RefusalError("Model refused to answer.")

        if not raw_text:
            logger.error("No content received from stream.")
            log_invalid_output(email_text, raw_text or None, "Empty stream content")
            return None, metadata

        try:
            payload = json.loads(raw_text)
        except JSONDecodeError:
            maybe = extract_json(raw_text)
            if maybe:
                try:
                    payload = json.loads(maybe)
                except JSONDecodeError:
                    logger.error("Fallback JSON extraction also failed.")
                    log_invalid_output(email_text, raw_text, "No valid JSON found in the response.")
                    return None, metadata
            else:
                logger.error("No valid JSON found in the response.")
                log_invalid_output(email_text, raw_text, "No valid JSON found in the response.")
                return None, metadata

        ticket = SupportTicket.model_validate(payload)
        return ticket, metadata
    except openai.RateLimitError as e:
        logger.error(f"Rate limit during classification stream: {e}")
        log_invalid_output(email_text, None, f"Rate limit: {str(e)}")
        raise RateLimitExceededError(str(e)) from e
    except Exception as e:
        logger.error(f"Error during classification stream: {e}")
        total_duration = time.time() - start
        metadata = Metadata(total_duration=total_duration, usage=Usage(**usage_dict))
        log_invalid_output(email_text, None, f"Exception during streaming: {str(e)}")
        return None, metadata

def classify_support_ticket_with_retries(email_text: str, max_retries: int = 3, raise_on_failure: bool = False) -> tuple[Optional[SupportTicket], Metadata]:
    last_metadata = Metadata(
        total_duration=0.0,
        usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0, interaction_price=0.0),
    )
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response, metadata = classify_support_ticket_stream(email_text)
            last_metadata = metadata
            logger.info(f"Attempt {attempt + 1}: Prompted with: {email_text}")
            if response is None:
                log_invalid_output(email_text, None, "Invalid response from LLM")
                continue
            if any(kw in (response.summary or "").lower() for kw in ("details are unclear", "need further investigation", "unclear")):
                log_invalid_output(email_text, response.model_dump(), "Summary indicates uncertainty")
                return None, metadata
            return response, metadata
        except EmptyPromptError:
            raise
        except RefusalError as e:
            last_error = e
            logger.warning(f"Refusal for email: {email_text}. Error: {e}")
            log_invalid_output(email_text, None, str(e))
        except RateLimitExceededError as e:
            last_error = e
            logger.warning(f"Rate limit for email: {email_text}. Error: {e}")
            log_invalid_output(email_text, None, str(e))
        except ValidationError as e:
            last_error = e
            logger.error(f"Validation error for email: {email_text}. Error: {e}")
            log_invalid_output(email_text, None, str(e))
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error during classification: {e}")
            log_invalid_output(email_text, None, f"Unexpected error: {str(e)}")
    if raise_on_failure and last_error is not None:
        raise last_error
    log_invalid_output(email_text, None, "Failed classification after retries")
    return None, last_metadata
