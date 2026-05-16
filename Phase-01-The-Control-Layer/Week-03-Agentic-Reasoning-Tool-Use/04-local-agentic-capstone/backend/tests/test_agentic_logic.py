from modules.logic.agentic_logic import classify_support_ticket, classify_support_ticket_with_retries
from modules.schemas.type_safety import SupportTicket
from modules.utils.helpers import log_invalid_output
import os

def test_classify_support_ticket():
    email_text = "I need help with my billing issue. I was charged twice for my subscription."
    ticket = classify_support_ticket(email_text)
    assert isinstance(ticket, SupportTicket)
    assert ticket.priority in ["Low", "Medium", "High"]
    assert ticket.department in ["Billing", "Technical Support", "General Inquiry"]
    assert len(ticket.summary) > 0

def test_classify_support_ticket_with_empty_input():
    email_text = ""
    try:
        classify_support_ticket(email_text)
        assert False, "Expected an exception for empty email text"
    except ValueError as e:
        assert str(e) == "Email text cannot be empty."

def test_classify_support_ticket_with_retries():
    email_text = "I need help with my billing issue. I was charged twice for my subscription."
    ticket = classify_support_ticket_with_retries(email_text)
    assert isinstance(ticket, SupportTicket)
    assert ticket.priority in ["Low", "Medium", "High"]
    assert ticket.department in ["Billing", "Technical Support", "General Inquiry"]
    assert len(ticket.summary) > 0

def test_classify_support_ticket_with_retries_failure():
    email_text = "^^&()_&$#%^#_(_)*&^&*(^*(*&))"
    ticket = classify_support_ticket_with_retries(email_text, max_retries=2)
    assert ticket is None, "Expected None for failed classification after retries"

def test_log_invalid_output():
    email_text = "Invalid email text"
    output = None
    error = "ValidationError: Invalid input"

    log_file = "invalid_outputs.log"
    existing_log_contents = ""
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            existing_log_contents = f.read()

    log_invalid_output(email_text, output, error)

    with open(log_file, 'r') as f:
        updated_log_contents = f.read()

    new_log_contents = updated_log_contents[len(existing_log_contents):]

    assert email_text in new_log_contents
    assert error in new_log_contents