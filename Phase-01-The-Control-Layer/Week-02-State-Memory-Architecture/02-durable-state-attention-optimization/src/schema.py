import json
import time
import shutil
from typing import List, Dict, Any
from logger import logger

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

def assemble_prompt(memories: Dict[str, List[Dict[str, Any]]], user_message: str) -> str:
    '''
    Assemble the prompt for the LLM by combining the relevant memories and instructions. Prioritize the preferences and system_context in the Attention Peaks, and include past issues as needed in the Low-Attention Zone.
    '''
    prompt = []

    prompt.append(f"User Message: {user_message}")

    prompt.append("Instructions: ...")
    prompt.extend(m['content'] for m in memories['preferences'][:1])

    prompt.extend(m['content'] for m in memories['past_issues'])

    prompt.extend([m['content'] for m in memories['system_context']])
    prompt.append("End of prompt.")
    return "\n".join(prompt)

def parse_and_writeback(response: str, filepath: str):
    '''
    Parse the LLM response and write back any new facts or updates to the memories JSON file. For simplicity, this example just appends the response as a new fact in the past_issues section.
    '''
    new_fact = {"content": response, "timestamp": int(time.time())}

    memories = load_memories(filepath)
    memories['past_issues'].append(new_fact)
    with open(filepath, 'w') as file:
        json.dump(memories, file, indent=2)
