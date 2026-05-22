from pydantic import BaseModel, Field
from modules.utils.logging import logger
from modules.memory import ConversationBuilder
from modules.memory.integration import DurableMemoryManager
from modules.memory import DurableMemoryStore
from modules.memory.durable_memory import WRITEBACK_INSTRUCTION, extract_patches_from_text
from modules.state import SQLiteStateStore
from enum import Enum
from pathlib import Path
from typing import Any, Optional
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


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=10, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=10, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class UserProfile(BaseModel):
    id: int
    username: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserProfile

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
from modules.utils.interactions import record_event


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
    def __init__(
        self,
        state_path: str | Path | None = None,
        token_budget: int = 4000,
        state_store: Optional[SQLiteStateStore] = None,
    ):
        self.sl_model = SLModel()
        self.frontier_model = FrontierModel()
        self.state_store = state_store
        self.token_budget = token_budget
        self.conversation = ConversationBuilder(state_path=state_path, token_budget=token_budget)

        # legacy file-based durable memory for non-user-scoped test and fallback flows
        self.durable_mgr = DurableMemoryManager(store=DurableMemoryStore(token_budget=token_budget))

        if not self.conversation.has_role("system"):
            sys_text = (
                "You are a helpful support agent. Use the prior conversation when responding.\n"
                + WRITEBACK_INSTRUCTION
            )
            self.conversation.append_message("system", sys_text, _estimate_token_count(sys_text))

    def _log_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        user_id: Optional[int] = None,
        request_meta: Optional[dict[str, str]] = None,
    ) -> None:
        try:
            record_event(event_type, payload)
        except Exception:
            pass
        if self.state_store is None:
            return
        try:
            self.state_store.record_interaction(
                event_type=event_type,
                payload=payload,
                user_id=user_id,
                ip_address=(request_meta or {}).get("ip_address"),
                user_agent=(request_meta or {}).get("user_agent"),
            )
        except Exception as exc:
            logger.debug(f"Failed to persist interaction event: {exc}")

    def _build_prompt_legacy(self, email_text: str, intent: Optional[str] = None) -> str:
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

        self.conversation.append_message("user", email_text, _estimate_token_count(email_text))
        if intent == "simple":
            transcript = self.conversation.render_transcript_compact(max_tokens=120, max_messages=6).strip()
            types_to_hydrate = ["preferences"]
        else:
            transcript = self.conversation.render_transcript().strip()
            types_to_hydrate = ["preferences", "past_issues", "system_context"]

        try:
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
            parts.append(transcript if transcript else email_text)
            if middle_section:
                parts.append(middle_section)
            if bottom_section:
                parts.append(bottom_section)

            assembled = "\n\n".join(parts)
            system_msgs = [m for m in self.conversation.messages if m.role == "system"]
            system_line = f"System: {system_msgs[0].content}" if system_msgs else ""

            last_assistant = persisted_last_assistant
            if last_assistant is None:
                for m in reversed(self.conversation.messages):
                    if m.role == "assistant":
                        last_assistant = m.content
                        break

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
            return transcript if transcript else email_text

    def _build_prompt_db(self, user_id: int, email_text: str, intent: Optional[str] = None) -> str:
        if self.state_store is None:
            return self._build_prompt_legacy(email_text, intent)

        if intent == "simple":
            message_limit = 8
            types_to_hydrate = ["preferences"]
        else:
            message_limit = 20
            types_to_hydrate = ["preferences", "past_issues", "system_context"]

        recent_messages = self.state_store.get_recent_messages(user_id=user_id, limit=message_limit)
        transcript_lines = [f"{msg['role'].title()}: {msg['content']}" for msg in recent_messages]
        transcript = "\n".join(transcript_lines).strip()

        zones = self.state_store.hydrate_memories(
            user_id=user_id,
            types=types_to_hydrate,
            max_tokens=self.token_budget,
        )

        def _render_memories(title: str, items: list[Any]) -> str:
            if not items:
                return ""
            lines = [f"### {title}"]
            for m in items:
                lines.append(f"- [{m.type}] {m.content}")
            return "\n".join(lines)

        top = _render_memories("Memory Peak (Top)", zones.get("top", []))
        middle = _render_memories("Low-Attention Zone (Middle)", zones.get("middle", []))
        bottom = _render_memories("Memory Peak (Bottom)", zones.get("bottom", []))

        system_line = (
            "System: You are a helpful support agent. Use the prior conversation when responding.\n"
            + WRITEBACK_INSTRUCTION
        )
        parts = [system_line]
        if top:
            parts.append(top)
        if transcript:
            parts.append(transcript)
        if middle:
            parts.append(middle)
        if bottom:
            parts.append(bottom)
        parts.append(f"User: {email_text}")
        return "\n\n".join(parts)

    def _build_prompt(self, email_text: str, intent: Optional[str] = None, user_id: Optional[int] = None) -> str:
        if user_id is not None and self.state_store is not None:
            return self._build_prompt_db(user_id=user_id, email_text=email_text, intent=intent)
        return self._build_prompt_legacy(email_text=email_text, intent=intent)

    def handle_ticket(
        self,
        email_text: str,
        user_id: Optional[int] = None,
        request_meta: Optional[dict[str, str]] = None,
        session_id: Optional[str] = None,
    ):
        intent = classify_intent(email_text)

        if user_id is not None and self.state_store is not None:
            self.state_store.add_message(
                user_id=user_id,
                role="user",
                content=email_text,
                token_count=_estimate_token_count(email_text),
                session_id=session_id,
            )

        prompt_text = self._build_prompt(email_text, intent, user_id=user_id)
        self._log_event(
            "prompt_sent",
            {
                "intent": intent or "unknown",
                "summary": prompt_text[:500],
                "prompt_tokens_est": _estimate_token_count(prompt_text),
            },
            user_id=user_id,
            request_meta=request_meta,
        )

        assistant_response_text = ""
        stream = self.sl_model.infer_response(prompt_text) if intent == "simple" else self.frontier_model.infer_response(prompt_text)

        try:
            for event in stream:
                try:
                    if isinstance(event, dict):
                        t = event.get("type")
                        if t == "delta":
                            d = event.get("data", {}) or {}
                            txt = d.get("text") if isinstance(d, dict) else None
                            self._log_event("delta", {"text": (txt or "")[:1000]}, user_id, request_meta)
                        elif t == "done":
                            self._log_event("done", {}, user_id, request_meta)
                        elif t == "completed":
                            d = event.get("data", {}) or {}
                            self._log_event(
                                "completed",
                                {"response_text": (d.get("response_text") or "")[:1000], "intent": d.get("intent")},
                                user_id,
                                request_meta,
                            )
                            assistant_response_text = str(d.get("response_text", ""))
                except Exception:
                    pass
                yield event
        finally:
            if not assistant_response_text:
                return

            if user_id is not None and self.state_store is not None:
                self.state_store.add_message(
                    user_id=user_id,
                    role="assistant",
                    content=assistant_response_text,
                    token_count=_estimate_token_count(assistant_response_text),
                    session_id=session_id,
                )
            else:
                self.conversation.append_message(
                    "assistant",
                    assistant_response_text,
                    _estimate_token_count(assistant_response_text),
                )

            self._log_event("assistant_appended", {"text": assistant_response_text[:1000]}, user_id, request_meta)

            try:
                if user_id is not None and self.state_store is not None:
                    patches = extract_patches_from_text(assistant_response_text)
                    res = self.state_store.apply_patches(user_id=user_id, patches=patches)
                else:
                    applied = self.durable_mgr.apply_llm_writeback(assistant_response_text)
                    res = applied.get("applied", []) if isinstance(applied, dict) else []
                logger.info(f"Applied durable memory patches: {res}")
                self._log_event("writeback_applied", {"result": res}, user_id, request_meta)
            except Exception as exc:
                logger.debug(f"No structured write-back applied or parse failed: {exc}")
                self._log_event("writeback_failed", {"error": str(exc)[:1000]}, user_id, request_meta)