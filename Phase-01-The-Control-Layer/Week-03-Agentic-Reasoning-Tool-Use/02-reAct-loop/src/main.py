from db import create_memories_table, create_users_table, create_messages_table
from auth import authenticate_user, register_user
from engine import run_react_loop
from schema import MessageBuffer
from logger import logger
import os
import getpass
import sys

test_mode = '--test-mode' in sys.argv

def main():
    '''
    Main function to orchestrate the workflow of loading memories, assembling the prompt, sending it to the LLM, and writing back any updates.
    '''
    model = os.getenv("model_name", "gpt-4o-mini")

    try:
        create_memories_table()
        create_users_table()
        create_messages_table()

        print("Welcome to the LLM Interface!")

        # Login or registration loop
        while True:
            logger.debug("DEBUG: About to prompt for action")
            user_action = input("Please select an action (register/login): ").strip().lower()
            logger.debug(f"DEBUG: User selected action '{user_action}'")
            if user_action == "register":
                logger.debug("DEBUG: About to prompt for username")
                username = input("Username: ")
                if test_mode:
                    password = input("Password: ")
                else:
                    password = getpass.getpass("Password: ")
                email = input("Email (optional): ")
                if register_user(username, password, email):
                    print("Registration successful!")
                else:
                    print("Registration failed. Please try again.")
            else:
                logger.debug("DEBUG: About to prompt for username")
                username = input("Username: ")
                if test_mode:
                    password = input("Password: ")
                else:
                    password = getpass.getpass("Password: ")
                user_id = authenticate_user(username, password)
                if user_id:
                    print("Login successful!")
                    break
                else:
                    print("Login failed. Please try again.")

        messages_buffer = MessageBuffer(user_id)

        # Main interaction loop
        while True:
            user_message = input("Enter your message for the LLM: ")
            if user_message.lower() in ["exit", "quit"]:
                logger.info("Exiting the application.")
                break

            if user_message.strip() == "":
                logger.warning("Empty message entered. Please provide a valid message.")
                print("Please let me know what I can help with!")
                continue

            # Run the ReAct loop for the user's message
            run_react_loop(user_message, user_id, model, messages_buffer)
    except Exception as e:
        logger.exception("Fatal error in main workflow: %s", e)

if __name__ == "__main__":
    main()
