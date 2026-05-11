import json
import time
import shutil
import os
import sqlite3
import re
from typing import List, Dict, Any
from logger import logger
from engine import summarize_buffer, classify_message
from pydantic import BaseModel, ValidationError
from db import add_memory, load_memories, update_email, update_password, update_username
from enum import Enum

DB_PATH = "users.db"

class MemoryEntry(BaseModel):
    role: str
    content: str
    timestamp: int

class MemoryCategory(Enum):
    PREFERENCES = 'preferences'
    PAST_ISSUES = 'past_issues'
    SYSTEM_CONTEXT = 'system_context'

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

    prompt.append("<user_data>")
    prompt.extend([m['content'] for m in conversation])
    prompt.append("</user_data>")

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

def validate_tool_input(tool_name, input_args, manifests) -> bool:
    '''
    Validate the tool input against the manifest schema. This is a critical step to ensure that we do not execute any harmful or malformed inputs.
    '''
    manifest = manifests[tool_name]
    params = manifest["parameters"]

    for key, spec in params.items():
        if key not in input_args:
            raise ValueError(f"Missing required parameter: {key}")
        value = input_args[key]
        if spec["type"] == "string" and not isinstance(value, str):
            raise TypeError(f"Parameter {key} must be a string")
        if spec["type"] == "number" and not isinstance(value, (int, float)):
            raise TypeError(f"Parameter {key} must be a number")
        if spec["type"] == "enum" and value not in spec["values"]:
            raise ValueError(f"Parameter {key} must be one of {spec['values']}")
    return True

def invoke_tool(tool_name, input_args, manifests):
    '''
    Invoke the tool with the validated input. This function should only be called after validate_tool_input has been successfully executed.
    '''
    validate_tool_input(tool_name, input_args, manifests)

    if tool_name == 'update_email':
        return update_email(**input_args)
    elif tool_name == 'update_password':
        return update_password(**input_args)
    elif tool_name == 'update_username':
        return update_username(**input_args)

def extract_tool_call(response):
    '''Extract the tool call from the LLM response. We will look for a specific pattern TOOL_CALL: {'tool': 'tool_name', 'args': {...}}. This is a simple approach and can be enhanced with more robust parsing if needed.
    '''
    match = re.search(r'TOOL_CALL:\s*(\{.*\})', response)
    if match:
        try:
            tool_call = json.loads(match.group(1))
            return tool_call['tool'], tool_call['args']
        except Exception as e:
            logger.error(f"Failed to parse tool call: {e}")
    return None, None

class MessageBuffer:
    '''
    A simple message buffer to hold recent interactions. This can be used to manage the context window and ensure that we only keep the most relevant messages for the LLM.
    '''
    def __init__(self, user_id: int, max_size: int = 6):
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
