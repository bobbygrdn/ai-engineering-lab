import json
import time
import shutil
import os
from typing import List, Dict, Any
from logger import logger
from engine import summarize_buffer, classify_message
from pydantic import BaseModel, ValidationError
from db import add_memory, load_memories
from enum import Enum

class MemoryEntry(BaseModel):
    role: str
    content: str
    timestamp: int

class MemoryCategory(Enum):
    PREFERENCES = "preferences"
    PAST_ISSUES = "past_issues"
    SYSTEM_CONTEXT = "system_context"

def prioritize_memories(memories: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    '''
    Prioritize the memories based on their timestamps.
    '''
    for key in memories:
        def safe_timestamp(x):
            try:
                return int(x.get('timestamp', 0))
            except Exception:
                return 0
        memories[key] = sorted(memories[key], key=lambda x: safe_timestamp(x), reverse=True)
    return memories

def assemble_prompt(memories: Dict[str, List[Dict[str, Any]]], conversation: List[Dict[str, Any]]) -> str:
    '''
    Assemble the prompt for the LLM by combining the relevant memories and instructions. Prioritize the preferences and system_context in the Attention Peaks, and include past issues as needed in the Low-Attention Zone.
    '''
    prompt = []

    prompt.extend([m['content'] for m in conversation])

    prompt.append("Instructions: ...")
    prompt.extend(m['content'] for m in memories['preferences'][:1])

    prompt.extend(m['content'] for m in memories['past_issues'])

    prompt.extend([m['content'] for m in memories['system_context']])
    prompt.append("End of prompt.")
    return "\n".join(prompt)

def parse_and_writeback(role: str, response: str, user_id: int, model: str = "gpt-4o-mini"):
    '''
    Parse the LLM response and write back any new facts or updates to the memories table in the db.
    '''
    try:
        new_fact = MemoryEntry(role=role, content=response, timestamp=int(time.time()))
    except ValidationError as e:
        logger.error(f"Error creating MemoryEntry for response '{response}': {e}")
        return

    classification = classify_message(response, model)

    preference_keywords = ["prefer", "like", "dislike", "want", "please keep", "please avoid", "i do not like", "i would rather", "i wish"]
    is_preference = role == "user" and any(keyword in response.lower() for keyword in preference_keywords)
    if is_preference:
        category = MemoryCategory.PREFERENCES
    else:
        try:
            category = MemoryCategory[classification.upper()]
            logger.info(f"Classified new fact '{response}' into category: {category.value}")
        except KeyError:
            category = MemoryCategory.PAST_ISSUES
            logger.warning(f"Classification '{classification}' not recognized. Defaulting to 'past_issues' category.")

    add_memory(user_id, category.value, new_fact.role, new_fact.content, new_fact.timestamp)

class MessageBuffer:
    '''
    A simple message buffer to hold recent interactions. This can be used to manage the context window and ensure that we only keep the most relevant messages for the LLM.
    '''
    def __init__(self, user_id: int, max_size: int = 10):
        self.user_id = user_id
        self.max_size = max_size

    def add_message(self, role: str, message: str):
        timestamp = int(time.time())
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (self.user_id, role, message, timestamp)
            )

            cur = conn.execute(
                "SELECT id FROM messages WHERE user_id=? ORDER BY timestamp DESC", (self.user_id,)
            )
            ids = [row[0] for row in cur.fetchall()]
            if len(ids) > self.max_size:
                for old_id in ids[self.max_size:]:
                    conn.execute("DELETE FROM messages WHERE id=?", (old_id,))
            conn.commit()

    def get_messages(self):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "SELECT role, content, timestamp FROM messages WHERE user_id=? ORDER BY timestamp ASC",
                (self.user_id,)
            )
            return [
                {"role": role, "content": content, "timestamp": timestamp}
                for role, content, timestamp in cur.fetchall()
            ]