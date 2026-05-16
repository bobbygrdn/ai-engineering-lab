import instructor
import os
from typing import Optional
from pydantic import ValidationError
from modules.schemas.type_safety import SupportTicket
from dotenv import load_dotenv
from modules.utils.logging import logger
from modules.utils.helpers import log_invalid_output

load_dotenv()

client = instructor.from_provider(
    "openai/gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0,
)

def classify_support_ticket(email_text: str) -> Optional[SupportTicket]:
    if not email_text.strip():
        raise ValueError("Email text cannot be empty.")

    try:
        response = client.chat.completions.create(
            response_model=SupportTicket,
            messages=[
                {"role": "system", "content": "You are a helpful customer support assistant that classifies incoming customer emails into support tickets with a priority, department, and summary. The priority can be Low, Medium, or High. The department can be Billing, Technical Support, or General Inquiry. The summary should be a brief description of the issue in 3 sentences or less. If the email text is unclear or does not provide enough information to classify, respond with a summary that indicates the need for further investigation."},
                {"role": "user", "content": email_text}
            ],
        )

        if not isinstance(response, SupportTicket):
            raise ValueError("Response does not match the SupportTicket schema.")
        return response
    except Exception as e:
        logger.error(f"Error during classification: {e}")
        return None


def classify_support_ticket_with_retries(email_text: str, max_retries: int = 3) -> Optional[SupportTicket]:
    for attempt in range(max_retries):
        try:
            response = classify_support_ticket(email_text)
            logger.info(f"Attempt {attempt + 1}: Prompted with: {email_text}")
            if response is None:
                log_invalid_output(email_text, None, "Invalid response from LLM")
                continue
            if "details are unclear" in response.summary or "need further investigation" in response.summary or "unclear" in response.summary:
                log_invalid_output(email_text, response.model_dump(), "Summary indicates uncertainty")
                return None
            return response
        except ValidationError as e:
            logger.error(f"Validation error for email: {email_text}. Error: {e}")
            log_invalid_output(email_text, None, str(e))
        except Exception as e:
            logger.error(f"Unexpected error during classification: {e}")
            log_invalid_output(email_text, None, f"Unexpected error: {str(e)}")
    log_invalid_output(email_text, None, "Failed classification after retries")
    return None