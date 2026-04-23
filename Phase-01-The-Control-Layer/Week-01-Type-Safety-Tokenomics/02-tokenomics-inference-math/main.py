import instructor
from pydantic import BaseModel, Field, ValidationError
from enum import Enum
from dotenv import load_dotenv
import os
from tabulate import tabulate
import logging
import json

load_dotenv()

logging.basicConfig(
    filename='support_ticket.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_invalid_output(email_text, output, error):
    with open('invalid_outputs.jsonl', 'a') as f:
        f.write(json.dumps({
            'email_text': email_text,
            'output': output,
            'error': str(error)
        }) + '\n')

class Priority(str, Enum):
    Low = 'Low'
    Medium = 'Medium'
    High = 'High'

class Department(str, Enum):
    Billing = 'Billing'
    Tech = 'Tech'
    General = 'General'

class SupportTicket(BaseModel):
    priority: Priority = Field(..., description='The priority level of the support ticket.')
    department: Department = Field(..., description='The department responsible for handling the issue.')
    summary: str = Field(..., description='A brief summary of the issue in 3 sentences or less.')

client = instructor.from_provider(
    "openai/gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0)

def classify_support_ticket(email_text: str) -> SupportTicket:
    response = client.chat.completions.create(
        response_model=SupportTicket,
        messages=[
            {
                "role": "user",
                "content": email_text
            }
        ]
    )

    return response

def classify_support_ticket_with_retries(email_text: str, max_retries: int = 3) -> SupportTicket:
    for attempt in range(max_retries):
        try:
            response = classify_support_ticket(email_text)
            logging.info(f"Attempt {attempt+1}: Prompted with: {email_text}")
            if "details are unclear" in response.summary or "need further investigation" in response.summary:
                log_invalid_output(email_text, response.dict(), "Summary indicates uncertainty")
            return response
        except ValidationError as e:
            logging.error(f"Validation error on attempt {attempt + 1}: {e}")
            log_invalid_output(email_text, response, e)
    logging.error("Failed to classify after retries.")
    return None

def print_ticket(ticket):
    if ticket:
        logging.info(f"Success: {ticket}")
        print(f"Priority  : {ticket.priority.value}")
        print(f"Department: {ticket.department.value}")
        print(f"Summary   : {ticket.summary}")
    else:
        logging.error("Failed to classify the support ticket.")

if __name__ == "__main__":
    email_text_list = [
        """Hello, I was charged twice for my subscription and I need a refund. Please help me resolve this issue as soon as possible.""",
        """My internet connection is very slow and keeps dropping. Can you please assist me in fixing this problem?""",
        """I have a question about your product features. Can you provide more information on how to use the advanced settings?""",
        """Help!""",
        """My account is locked, but I also want to change my billing address.""",
        """jfodhafdsafhdslkafj"""
    ]
    for email_text in email_text_list:
        ticket = classify_support_ticket_with_retries(email_text)
        print_ticket(ticket)
