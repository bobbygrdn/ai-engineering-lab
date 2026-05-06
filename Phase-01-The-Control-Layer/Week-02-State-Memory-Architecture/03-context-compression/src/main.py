from engine import send_to_llm
from schema import load_memories, prioritize_memories, assemble_prompt, parse_and_writeback, MessageBuffer
from logger import logger
import os
import json

def main():
    '''
    Main function to orchestrate the workflow of loading memories, assembling the prompt, sending it to the LLM, and writing back any updates.
    '''
    memories_file = os.getenv("memories_file_path", "memories.json")
    messages_buffer_file = os.getenv("messages_buffer_file_path", "messages_buffer.json")
    model = os.getenv("model_name", "gpt-4o-mini")
    messages_buffer = MessageBuffer(messages_buffer_file)

    try:
        if not os.path.exists(memories_file):
            logger.warning("Memories file not found at %s. Creating a new one.", memories_file)
            with open(memories_file, 'w') as file:
                json.dump({"preferences": [], "past_issues": [], "system_context": []}, file, indent=2)
        if not os.path.exists(messages_buffer_file):
            logger.warning("Messages buffer file not found at %s. Creating a new one.", messages_buffer_file)
            with open(messages_buffer_file, 'w') as file:
                json.dump({"messages": []}, file, indent=2)

        while True:
            user_message = input("Enter your message for the LLM: ")
            if user_message.lower() in ["exit", "quit"]:
                logger.info("Exiting the application.")
                break

            if user_message.strip() == "":
                logger.warning("Empty message entered. Please provide a valid message.")
                print("Please let me know what I can help with!")
                continue

            
            messages_buffer.add_message("user", user_message)
            parse_and_writeback("user", user_message, memories_file)

            memories = load_memories(memories_file)
            memories = prioritize_memories(memories)

            buffered_messages = messages_buffer.get_messages()
            prompt = assemble_prompt(memories, buffered_messages)

            response = send_to_llm(prompt, model)
            messages_buffer.add_message("assistant", response)

            parse_and_writeback("assistant", response, memories_file)

            logger.info("LLM response: %s", response)
            print("LLM Response:", response)
    except Exception as e:
        logger.exception("Fatal error in main workflow: %s", e)

if __name__ == "__main__":
    main()
