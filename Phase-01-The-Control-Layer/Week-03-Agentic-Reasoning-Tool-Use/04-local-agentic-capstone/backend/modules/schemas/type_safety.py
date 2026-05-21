from pydantic import BaseModel, Field
from modules.utils.logging import logger
from modules.memory import ConversationBuilder
from modules.memory.integration import DurableMemoryManager
from modules.memory import DurableMemoryStore
from modules.memory.durable_memory import WRITEBACK_INSTRUCTION
from enum import Enum
from pathlib import Path
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


from modules.utils.tokenizer import count_tokens


def _estimate_token_count(text: str) -> int:
    return max(1, count_tokens(text, model="gpt-4o-mini"))

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

            sys_prompt = "You are a helpful support assistant. Reply in one short polite paragraph.\n" + WRITEBACK_INSTRUCTION
            stream = openai_client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": sys_prompt},
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

        # record metrics (prompt/completion tokens and TTFT)
        try:
            from modules.utils.metrics import log_interaction
            log_interaction({
                "model": "gpt-4o-mini",
                "intent": "simple",
                "prompt_tokens": int(input_tokens),
                "completion_tokens": int(output_tokens),
                "total_tokens": int(input_tokens or 0) + int(output_tokens or 0),
                "duration": metadata.total_duration,
            })
        except Exception:
            pass

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

            sys_prompt = "You are a helpful and concise support agent.\n" + WRITEBACK_INSTRUCTION
            stream = openai_client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": sys_prompt},
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

        try:
            from modules.utils.metrics import log_interaction
            log_interaction({
                "model": "gpt-4o-mini",
                "intent": "complex",
                "prompt_tokens": int(total_prompt),
                "completion_tokens": int(total_completion),
                "total_tokens": int(total_tokens),
                "duration": metadata.total_duration,
            })
        except Exception:
            pass

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
    def __init__(self, state_path: str | Path | None = None, token_budget: int = 4000):
        self.sl_model = SLModel()
        self.frontier_model = FrontierModel()
        self.conversation = ConversationBuilder(state_path=state_path, token_budget=token_budget)

        # durable memory manager for typed memories
        self.durable_mgr = DurableMemoryManager(store=DurableMemoryStore(token_budget=token_budget))

        if not self.conversation.has_role("system"):
            sys_text = (
                "You are a helpful support agent. Use the prior conversation when responding.\n"
                + WRITEBACK_INSTRUCTION
            )
            self.conversation.append_message(
                "system",
                sys_text,
                _estimate_token_count(sys_text),
            )

    def _build_prompt(self, email_text: str, intent: str | None = None) -> str:
        # Read persisted conversation first to deterministically capture the latest assistant
        # message before a new user append may trigger trimming and eviction.
        persisted_last_assistant = None
        try:
            sp = getattr(self.conversation, "state_path", None)
            if sp and sp.exists():
                import json
                raw = json.loads(sp.read_text(encoding="utf-8"))
                for item in reversed(raw.get("messages", [])):
                    if item.get("role") == "assistant":
                        persisted_last_assistant = item.get("content")
                        break
        except Exception:
            persisted_last_assistant = None

        # append the current user message (this may trim older messages)
        self.conversation.append_message("user", email_text, _estimate_token_count(email_text))
        # choose compact transcript for simple intents to reduce tokens and latency
        if intent == "simple":
            transcript = self.conversation.render_transcript_compact(max_tokens=120, max_messages=6).strip()
            types_to_hydrate = ["preferences"]
        else:
            transcript = self.conversation.render_transcript().strip()
            types_to_hydrate = ["preferences", "past_issues", "system_context"]

        # Hydrate typed memories and assemble attention-optimized sections
        try:
            # use cache-enabled hydrate to avoid repeated disk loads
            zones = self.durable_mgr.hydrate_cached(types=types_to_hydrate, max_tokens=self.conversation.token_budget)

            def _short_content(m):
                s = str(m.content)
                words = s.split()
                if len(words) > 30:
                    return "..." + " ".join(words[-20:])
                return s

            def _render_list(title: str, items: list) -> str:
                if not items:
                    return ""
                lines = [f"### {title}"]
                for m in items:
                    lines.append(f"- [{m.type}] {_short_content(m)}")
                return "\n".join(lines)

            top_section = _render_list("Memory Peak (Top)", zones.get("top", []))
            middle_section = _render_list("Low-Attention Zone (Middle)", zones.get("middle", []))
            bottom_section = _render_list("Memory Peak (Bottom)", zones.get("bottom", []))

            parts = []
            if top_section:
                parts.append(top_section)
            if transcript:
                parts.append(transcript)
            else:
                parts.append(email_text)
            if middle_section:
                parts.append(middle_section)
            if bottom_section:
                parts.append(bottom_section)

            assembled = "\n\n".join(parts)
            # rebuild final assembled prompt explicitly to ensure system, last assistant, transcript and user lines
            system_msgs = [m for m in self.conversation.messages if m.role == "system"]
            system_line = f"System: {system_msgs[0].content}" if system_msgs else ""

            # Use the persisted last assistant we captured before appending the new user message
            last_assistant = persisted_last_assistant

            # If persisted snapshot didn't have an assistant, fall back to in-memory and state
            if last_assistant is None:
                # try the public messages list first
                for m in reversed(self.conversation.messages):
                    if m.role == "assistant":
                        last_assistant = m.content
                        break
                # fallback: try stored state messages for robustness
                if last_assistant is None:
                    try:
                        for stored in reversed(self.conversation.state.messages):
                            if getattr(stored.message, "role", "") == "assistant":
                                last_assistant = getattr(stored.message, "content", None)
                                break
                    except Exception:
                        pass

            user_line = f"User: {email_text}"

            final_parts = []
            if system_line:
                final_parts.append(system_line)
            if last_assistant:
                final_parts.append(f"Assistant: {last_assistant}")
            if assembled:
                final_parts.append(assembled)
            final_parts.append(user_line)

            return "\n\n".join(final_parts)
        except Exception:
            # fallback to transcript only
            if not transcript:
                return email_text
            return transcript

    def handle_ticket(self, email_text: str):
        intent = classify_intent(email_text)
        prompt_text = self._build_prompt(email_text, intent)
        assistant_response_text = ""
        if intent == "simple":
            stream = self.sl_model.infer_response(prompt_text)
        else:
            stream = self.frontier_model.infer_response(prompt_text)

        try:
            for event in stream:
                if isinstance(event, dict) and event.get("type") == "completed":
                    data = event.get("data", {}) or {}
                    assistant_response_text = str(data.get("response_text", ""))
                yield event
        finally:
            if assistant_response_text:
                self.conversation.append_message(
                    "assistant",
                    assistant_response_text,
                    _estimate_token_count(assistant_response_text),
                )
                # attempt to parse structured write-back patches from assistant and apply
                try:
                    res = self.durable_mgr.apply_llm_writeback(assistant_response_text)
                    logger.info(f"Applied durable memory patches: {res}")
                except Exception as e:
                    logger.debug(f"No structured write-back applied or parse failed: {e}")