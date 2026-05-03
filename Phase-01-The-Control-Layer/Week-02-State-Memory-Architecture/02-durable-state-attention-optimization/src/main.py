from engine import send_to_llm
from schema import load_memories, prioritize_memories, assemble_prompt, parse_and_writeback
from logger import logger
import os
import json

def main():
    '''
    Main function to orchestrate the workflow of loading memories, assembling the prompt, sending it to the LLM, and writing back any updates.
    '''
    filepath = os.getenv("memories_file_path", "memories.json")
    model = os.getenv("model_name", "gpt-4o-mini")

    try:
        if not os.path.exists(filepath):
            logger.warning("Memories file not found at %s. Creating a new one.", filepath)
            with open(filepath, 'w') as file:
                json.dump({"preferences": [], "past_issues": [], "system_context": []}, file, indent=2)

        user_message = input("Enter your message for the LLM: ")

        memories = load_memories(filepath)
        memories = prioritize_memories(memories)

        prompt = assemble_prompt(memories, user_message)

        response = send_to_llm(prompt, model)

        parse_and_writeback(response, filepath)

        logger.info("LLM response: %s", response)
        print("LLM Response:", response)
    except Exception as e:
        logger.exception("Fatal error in main workflow: %s", e)

if __name__ == "__main__":
    main()
