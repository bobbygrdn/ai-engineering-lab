from db import add_memory, load_memories, update_email, update_password, update_username
from pydantic import BaseModel, ValidationError
from models import MemoryEntry, MemoryCategory
from typing import List, Dict, Any
from logger import logger
from enum import Enum
from llm_utils import send_to_llm
import json
import time
import shutil
import os
import sqlite3
import re

DB_PATH = "users.db"

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

def validate_tool_output(user_message: str, tool_name: str, tool_args: dict, result: dict, manifests: dict, model: str = "gpt-4o-mini") -> bool:
    '''
    Verify that the tool output meets the requirements the user specified in their message and that it adheres to the manifest specifications for that tool. This is a safeguard to prevent incorrect or malicious tool calls from being executed.
    '''
    manifest = manifests[tool_name]
    prompt = (
        f"The user requested the following change: '{user_message}'.\n"
        f"The tool '{tool_name}' was called with arguments: {tool_args} and returned result: {result}.\n"
        f"Based on the tool's manifest specifications: {manifest}, did the tool call meet the user's request and adhere to the manifest requirements? Answer 'yes' or 'no' and explain why."
    )
    verification_response = send_to_llm(prompt, model)
    if verification_response.lower().startswith("yes"):
        return True
    else:
        logger.warning(f"Tool output verification failed: {verification_response}")
        return False

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
