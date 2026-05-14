from pydantic import BaseModel
from enum import Enum
from llm_utils import critique_response, send_to_llm

class MemoryEntry(BaseModel):
    role: str
    content: str
    timestamp: int

class MemoryCategory(Enum):
    PREFERENCES = 'preferences'
    PAST_ISSUES = 'past_issues'
    SYSTEM_CONTEXT = 'system_context'

class ResponderAgent():
    def __init__(self, model: str):
        self.model = model

    def respond(self, prompt: str) -> str:
        return send_to_llm(prompt, self.model)

class CriticAgent():
    def __init__(self, model: str):
        self.model = model

    def critique(self, prompt: str) -> str:
        return critique_response(prompt, self.model, policy="company_policy.txt")