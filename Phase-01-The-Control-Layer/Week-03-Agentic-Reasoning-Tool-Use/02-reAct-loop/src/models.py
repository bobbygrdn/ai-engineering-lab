from pydantic import BaseModel
from enum import Enum

class MemoryEntry(BaseModel):
    role: str
    content: str
    timestamp: int

class MemoryCategory(Enum):
    PREFERENCES = 'preferences'
    PAST_ISSUES = 'past_issues'
    SYSTEM_CONTEXT = 'system_context'