import json
import time
import shutil
import os
from typing import List, Dict, Any
from logger import logger
from engine import summarize_buffer, classify_message
from pydantic import BaseModel, ValidationError
from enum import Enum

class MemoryEntry(BaseModel):
    role: str
    content: str
    timestamp: int

class MemoryCategory(Enum):
    PREFERENCES = "preferences"
    PAST_ISSUES = "past_issues"
    SYSTEM_CONTEXT = "system_context"

def load_memories(filepath: str) -> Dict[str, List[Dict[str, Any]]]:
    '''
    Load the memories from the JSON file. If the file is missing or malformed, initialize it with empty lists for each category.
    '''
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)

        for key in ["preferences", "past_issues", "system_context"]:
            if key not in data or not isinstance(data[key], list):
                logger.error(f"Key '{key}' missing or not a list in memories.json. Reinitializing file.")
                raise ValueError(f"Key '{key}' missing or not a list.")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.exception(f"Error loading memories.json: {e}. Backing up and reinitializing file.")
        shutil.move(filepath, filepath + ".corrupt")

        with open(filepath, 'w') as file:
            json.dump({"preferences": [], "past_issues": [], "system_context": []}, file, indent=2)
            
        return {"preferences": [], "past_issues": [], "system_context": []}

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

def parse_and_writeback(role: str, response: str, filepath: str, model: str = "gpt-4o-mini"):
    '''
    Parse the LLM response and write back any new facts or updates to the memories JSON file.
    '''
    try:
        new_fact = MemoryEntry(role=role, content=response, timestamp=int(time.time()))
    except ValidationError as e:
        logger.error(f"Error creating MemoryEntry for response '{response}': {e}")
        return

    memories = load_memories(filepath)
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

    memories[category.value].append(new_fact.dict())
    with open(filepath, 'w') as file:
        json.dump(memories, file, indent=2)

class MessageBuffer:
    '''
    A simple message buffer to hold recent interactions. This can be used to manage the context window and ensure that we only keep the most relevant messages for the LLM.
    '''
    def __init__(self, filepath: str, max_size: int = 10):
        self.max_size = max_size
        self.filepath = filepath
        self.buffer = []
        self.load_from_file(self.filepath)

    def add_message(self, role: str, message: str):
        self.buffer.append({"role": role, "content": message, "timestamp": int(time.time())})
        if len(self.buffer) > self.max_size:
            summary = summarize_buffer(self.buffer, "gpt-4o-mini")
            self.buffer = [{"role": "summary", "content": summary, "timestamp": int(time.time())}]
        self.save_to_file(self.filepath)

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.buffer

    def save_to_file(self, filepath: str):
        with open(filepath, 'w') as file:
            json.dump({"messages": self.buffer}, file, indent=2)

    def load_from_file(self, filepath: str):
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.buffer = data.get("messages", [])