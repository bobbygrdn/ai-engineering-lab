from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field


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
        self._messages.append(StoredMessage(message=message, token_count=max(0, int(token_count))))
        self._total_tokens += max(0, int(token_count))
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

    def has_role(self, role: str) -> bool:
        return any(stored.message.role == role for stored in self._messages)

    def reset(self) -> None:
        self._messages = []
        self._total_tokens = 0
        self._persist_state()

    def _trim_to_budget(self) -> None:
        while self._total_tokens > self.token_budget:
            removable_index = next((index for index, stored in enumerate(self._messages) if stored.message.role != "system"), None)
            if removable_index is None:
                break
            removed = self._messages.pop(removable_index)
            self._total_tokens -= removed.token_count

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