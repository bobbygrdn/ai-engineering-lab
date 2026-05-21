from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field
from modules.utils.tokenizer import count_tokens
from modules.memory.summarizer import summarize_messages


DEFAULT_TOKEN_BUDGET = 4000


class MessageObject(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class StoredMessage(BaseModel):
    message: MessageObject
    token_count: int = Field(ge=0)


class ConversationState(BaseModel):
    token_budget: int = DEFAULT_TOKEN_BUDGET
    total_tokens: int = 0
    messages: list[StoredMessage] = Field(default_factory=list)


class ConversationBuilder:
    """Maintain a bounded in-memory conversation with JSON persistence."""

    def __init__(self, state_path: str | Path | None = None, token_budget: int = DEFAULT_TOKEN_BUDGET):
        self.state_path = Path(state_path) if state_path is not None else self._default_state_path()
        self.token_budget = token_budget
        self._messages: list[StoredMessage] = []
        self._total_tokens = 0
        self._load_state()

    @staticmethod
    def _default_state_path() -> Path:
        return Path(__file__).resolve().parents[2] / "logs" / "messages" / "conversation_state.json"

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def messages(self) -> list[MessageObject]:
        return [stored.message for stored in self._messages]

    @property
    def state(self) -> ConversationState:
        return ConversationState(
            token_budget=self.token_budget,
            total_tokens=self.total_tokens,
            messages=list(self._messages),
        )

    def append_message(self, role: str, content: str, token_count: int) -> MessageObject:
        message = MessageObject(role=role, content=content)
        # if token_count not provided or zero, estimate using tokenizer
        if not token_count:
            tc = max(0, int(count_tokens(content, model="gpt-4o-mini")))
        else:
            tc = max(0, int(token_count))
        stored = StoredMessage(message=message, token_count=tc)
        self._messages.append(stored)
        # remember last appended message to avoid immediate eviction
        self._last_appended = stored
        self._total_tokens += tc
        self._trim_to_budget()
        self._persist_state()
        return message

    def extend_messages(self, messages: Iterable[tuple[str, str, int]]) -> list[MessageObject]:
        appended: list[MessageObject] = []
        for role, content, token_count in messages:
            appended.append(self.append_message(role, content, token_count))
        return appended

    def to_api_messages(self) -> list[dict[str, str]]:
        return [message.model_dump() for message in self.messages]

    def render_transcript(self) -> str:
        lines: list[str] = []
        for message in self.messages:
            lines.append(f"{message.role.title()}: {message.content}")
        return "\n".join(lines)

    def render_transcript_compact(self, max_tokens: int = 200, max_messages: int = 8) -> str:
        """Render a compact version of the transcript prioritizing recent messages.

        Stops when `max_tokens` is reached or `max_messages` have been included.
        """
        rev = list(reversed(self.messages))
        lines: list[str] = []
        used = 0
        for m in rev[:max_messages]:
            words = m.content.split()
            if used >= max_tokens:
                break
            remaining = max_tokens - used
            take = min(len(words), remaining)
            snippet = " ".join(words[-take:]) if take < len(words) else m.content
            lines.append(f"{m.role.title()}: {snippet}")
            used += take
        return "\n".join(reversed(lines))

    def has_role(self, role: str) -> bool:
        return any(stored.message.role == role for stored in self._messages)

    def reset(self) -> None:
        self._messages = []
        self._total_tokens = 0
        self._persist_state()

    def _trim_to_budget(self) -> None:
        # If over budget, attempt summarization once to compact older messages,
        # otherwise remove the oldest non-system messages.
        if self._total_tokens > self.token_budget and len(self._messages) > 4:
            # summarize earliest half of messages to preserve content
            non_system = [m for m in self._messages if m.message.role != "system"]
            if len(non_system) > 2:
                # take earliest half
                cutoff = max(1, len(non_system) // 2)
                to_summarize = non_system[:cutoff]
                summary_text, summary_tokens = summarize_messages(to_summarize)
                # remove those messages
                remaining = [m for m in self._messages if m not in to_summarize]
                self._messages = remaining
                # append summary as assistant message
                summary_msg = MessageObject(role="assistant", content=summary_text)
                self._messages.insert(0, StoredMessage(message=summary_msg, token_count=summary_tokens))
                # recompute total tokens
                self._total_tokens = sum(s.token_count for s in self._messages)
                # if still over budget, fall through to deletion loop

        while self._total_tokens > self.token_budget:
            removable_index = next((index for index, stored in enumerate(self._messages) if stored.message.role != "system" and getattr(self, '_last_appended', None) is not stored), None)
            if removable_index is None:
                # nothing removable without evicting the most recent appended message
                break
            removed = self._messages.pop(removable_index)
            self._total_tokens -= removed.token_count
        # clear last_appended marker once trimming is complete
        if hasattr(self, "_last_appended"):
            try:
                del self._last_appended
            except Exception:
                pass

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return

        try:
            raw_state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            self._messages = []
            self._total_tokens = 0
            return

        if not isinstance(raw_state, dict):
            self._messages = []
            self._total_tokens = 0
            return

        self.token_budget = int(raw_state.get("token_budget", self.token_budget))

        loaded_messages: list[StoredMessage] = []
        for item in raw_state.get("messages", []):
            if not isinstance(item, dict):
                continue
            try:
                message = MessageObject.model_validate({"role": item.get("role"), "content": item.get("content", "")})
                loaded_messages.append(
                    StoredMessage(message=message, token_count=max(0, int(item.get("token_count", 0))))
                )
            except Exception:
                continue

        self._messages = loaded_messages
        self._total_tokens = int(raw_state.get("total_tokens", sum(stored.token_count for stored in loaded_messages)))
        self._trim_to_budget()

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "token_budget": self.token_budget,
            "total_tokens": self._total_tokens,
            "messages": [
                {
                    "role": stored.message.role,
                    "content": stored.message.content,
                    "token_count": stored.token_count,
                }
                for stored in self._messages
            ],
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "ConversationBuilder",
    "ConversationState",
    "MessageObject",
    "StoredMessage",
]