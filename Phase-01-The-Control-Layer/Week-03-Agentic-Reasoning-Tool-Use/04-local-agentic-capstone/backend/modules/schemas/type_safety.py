from pydantic import BaseModel, Field
from modules.utils.logging import logger
from enum import Enum
import time

class Priority(str, Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'

class Department(str, Enum):
    BILLING = 'Billing'
    TECHNICAL = 'Technical Support'
    GENERAL = 'General Inquiry'

class Usage(BaseModel):
    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens used")
    interaction_price: float = Field(..., description="Calculated price for the interaction based on token usage")

class SupportTicket(BaseModel):
    priority: Priority = Field(..., description="The priority level of the support ticket")
    department: Department = Field(..., description="The department responsible for handling the ticket")
    summary: str = Field(..., description="A brief summary of the issue in 3 sentences or less")

class ClassifyRequest(BaseModel):
    email_text: str = Field(..., description="The text of the customer email to classify")

class Metadata(BaseModel):
    total_duration: float = Field(..., description="Total processing time in seconds.")
    usage: Usage = Field(..., description="Token usage information from the API response.")

class SupportTicketResponse(BaseModel):
    intent: str = Field(..., description="The predicted intent of the customer email")
    response_text: str = Field(..., description="The generated response text for the customer email")
    metadata: Metadata = Field(..., description="Metadata about the processing of the request, including token usage, cost and duration")

class ModelInterface:
    def infer_response(self, email_text: str) -> SupportTicketResponse:
        raise NotImplementedError

class SLModel(ModelInterface):

    def infer_response(self, email_text: str):
        start = time.time()

        try:
            from modules.logic import agentic_logic
            openai_client = agentic_logic.openai_client
            _event_type = agentic_logic._event_type
            _delta_text_from_event = agentic_logic._delta_text_from_event
            _usage_from_event = agentic_logic._usage_from_event
            from modules.utils.helpers import calculate_price

            content_parts: list[str] = []
            usage_dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "interaction_price": 0.0}

            stream = openai_client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": "You are a helpful support assistant. Reply in one short polite paragraph."},
                    {"role": "user", "content": email_text},
                ],
                stream=True,
            )

            for i, event in enumerate(stream):
                et = _event_type(event)
                if et == "response.output_text.delta":
                    delta_text = _delta_text_from_event(event)
                    content_parts.append(delta_text)
                    yield {"type": "delta", "data": {"text": delta_text}}
                elif et == "response.output_text.done":
                    yield {"type": "done", "data": {}}
                elif et == "response.completed":
                    usage_dict = _usage_from_event(event)
                    break

            response_text = "".join(content_parts).strip()
            if not response_text:
                response_text = "Thanks for reaching out. We received your request and will follow up shortly."

            input_tokens = usage_dict.get("prompt_tokens", 0)
            output_tokens = usage_dict.get("completion_tokens", 0)
            interaction_price = usage_dict.get("interaction_price", calculate_price(input_tokens, output_tokens))

        except Exception as e:
            logger.exception(f"Error during SLModel inference: {e}", exc_info=True)
            response_text = "Thanks for reaching out. We received your request and will follow up shortly."
            input_tokens = 0
            output_tokens = 0
            interaction_price = 0.0

        metadata = Metadata(
            total_duration=time.time() - start,
            usage=Usage(
                prompt_tokens=int(input_tokens),
                completion_tokens=int(output_tokens),
                total_tokens=int(input_tokens or 0) + int(output_tokens or 0),
                interaction_price=float(interaction_price),
            )
        )

        response = SupportTicketResponse(
            intent="simple",
            response_text=response_text,
            metadata=metadata
        )

        yield {"type": "completed", "data": response.model_dump()}

class FrontierModel(ModelInterface):

    def infer_response(self, email_text: str):
        start = time.time()

        from modules.utils.helpers import calculate_price
        from modules.logic import agentic_logic

        openai_client = agentic_logic.openai_client
        _event_type = agentic_logic._event_type
        _delta_text_from_event = agentic_logic._delta_text_from_event
        _usage_from_event = agentic_logic._usage_from_event
        classify_support_ticket_with_retries = agentic_logic.classify_support_ticket_with_retries

        ticket, ticket_metadata = classify_support_ticket_with_retries(email_text)

        if ticket is None:
            gen_user_text = "We reviewed the request and need a human to investigate further. Please acknowledge and promise follow-up."
        else:
            gen_user_text = (
                f"Customer issue: {ticket.summary}\n"
                f"Department: {ticket.department.value}\n"
                f"Priority: {ticket.priority.value}\n\n"
                "Write a short, empathetic customer-facing reply (one paragraph) that explains next steps."
            )

        try:
            content_parts: list[str] = []
            gen_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            stream = openai_client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": "You are a helpful and concise support agent."},
                    {"role": "user", "content": gen_user_text},
                ],
                stream=True,
            )

            for i, event in enumerate(stream):
                et = _event_type(event)
                if et == "response.output_text.delta":
                    delta_text = _delta_text_from_event(event)
                    content_parts.append(delta_text)
                    yield {"type": "delta", "data": {"text": delta_text}}
                elif et == "response.output_text.done":
                    yield {"type": "done", "data": {}}
                elif et == "response.completed":
                    gen_usage = _usage_from_event(event)
                    break

            gen_text = "".join(content_parts).strip()
            if not gen_text:
                gen_text = "We reviewed your request and will have a human follow up shortly."

            gen_input_tokens = gen_usage.get("prompt_tokens", 0)
            gen_output_tokens = gen_usage.get("completion_tokens", 0)

        except Exception as e:
            logger.exception(f"Error during FrontierModel inference: {e}", exc_info=True)
            gen_text = "We reviewed your request and will have a human follow up shortly."
            gen_input_tokens = 0
            gen_output_tokens = 0

        cls_usage = ticket_metadata.usage if ticket_metadata is not None else Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0, interaction_price=0.0)
        total_prompt = int(cls_usage.prompt_tokens or 0) + int(gen_input_tokens or 0)
        total_completion = int(cls_usage.completion_tokens or 0) + int(gen_output_tokens or 0)
        total_tokens = total_prompt + total_completion
        interaction_price = calculate_price(total_prompt, total_completion)

        metadata = Metadata(
            total_duration=time.time() - start,
            usage=Usage(
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_tokens=total_tokens,
                interaction_price=interaction_price,
            ),
        )

        response = SupportTicketResponse(
            intent="complex",
            response_text=gen_text,
            metadata=metadata
        )

        yield {"type": "completed", "data": response.model_dump()}

def classify_intent(email_text: str) -> str:
    simple_keywords = ['status', 'thank you', 'resolved', 'close ticket']
    complex_keywords = ['billing', 'charge', 'refund', 'error', 'troubleshoot']
    text_lower = email_text.lower()

    if any(keyword in text_lower for keyword in simple_keywords):
        return "simple"
    if any(keyword in text_lower for keyword in complex_keywords):
        return "complex"
    return "simple"

class SupportAIService:
    def __init__(self):
        self.sl_model = SLModel()
        self.frontier_model = FrontierModel()

    def handle_ticket(self, email_text: str):
        intent = classify_intent(email_text)
        if intent == "simple":
            yield from self.sl_model.infer_response(email_text)
        else:
            yield from self.frontier_model.infer_response(email_text)