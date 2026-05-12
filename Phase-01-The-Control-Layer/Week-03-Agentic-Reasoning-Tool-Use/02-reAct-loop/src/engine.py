from schema import load_memories, prioritize_memories, assemble_prompt, validate_tool_input, validate_tool_output, invoke_tool, extract_tool_call
from db import update_email, update_password, update_username, is_ambiguous_message, parse_and_writeback
from llm_utils import send_to_llm
from dotenv import load_dotenv
from logger import logger
import openai
import os
import json

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

manifests = {
            'update_email': json.load(open("tool_manifests/update_email.json")),
            'update_password': json.load(open("tool_manifests/update_password.json")),
            'update_username': json.load(open("tool_manifests/update_username.json")),
        }

tool_functions = {
    'update_email': update_email,
    'update_password': update_password,
    'update_username': update_username,
}

def run_react_loop(user_message, user_id, model, messages_buffer):
    '''
    Run the ReAct loop: send the user message to the LLM, parse the response for tool calls, execute the tool if needed, and return the final response.
    '''
    final_answer = None
    verification_error_count = 0
    max_steps = 10
    steps = 0

    while steps < max_steps and verification_error_count < 3:
        steps += 1
        response = send_to_llm(user_message, model)

        if not is_ambiguous_message(user_message):
            messages_buffer.add_message("user", user_message)

            parse_and_writeback("user", user_message, user_id)

            memories = load_memories(user_id)
            if memories is not None:
                logger.info(f"Loaded memories for user_id={user_id} from SQLite durable store.")
            memories = prioritize_memories(memories)

            buffered_messages = messages_buffer.get_messages()
            prompt = assemble_prompt(memories, buffered_messages)

            response = send_to_llm(prompt, model)
            logger.info("[THOUGHT]: %s", response)

            if "final answer:" in response.lower():
                final_answer = response.split("final answer:")[-1].strip()
                logger.info("[FINAL ANSWER]: %s", final_answer)
                print(final_answer)
                break

            tool_name, tool_args = extract_tool_call(response)
            if tool_name and tool_args:
                try:
                    if 'user_id' not in tool_args:
                        tool_args['user_id'] = user_id
                    validate_tool_input(tool_name, tool_args, manifests)
                    result = tool_functions[tool_name](**tool_args)
                    logger.info(f"Tool '{tool_name}' executed successfully with result: {result}")
                    logger.info("[ACTION]: %s %s", tool_name, tool_args)
                    logger.info("[OBSERVATION]: %s", result)
                    verified = validate_tool_output(user_message, tool_name, tool_args, result, manifests)
                    logger.info("[VERIFICATION]: %s", "Passed" if verified else "Failed")
                    if verified:
                        print(f"{tool_name} executed successfully.")
                        break
                    else:
                        verification_error_count += 1
                    print("Verification failed. Please clarify your request or try again.")
                    if verification_error_count >= 3:
                        print("Too many failed verification attempts. Exiting the ReAct loop.")
                        logger.warning("Exceeded maximum verification failures. Exiting loop.")
                        break
                except Exception as e:
                    logger.error(f"Error occurred while executing tool: {e}")
                    print(f"Tool invocation failed: {e}")
            else:
                logger.info("[THOUGHT]: No tool call detected. Awaiting further input or clarification.")

            messages_buffer.add_message("assistant", response)

            parse_and_writeback("assistant", response, user_id)

            logger.info("LLM response: %s", response)
            print("LLM response:", response)

            if not tool_name and "final answer:" not in response.lower():
                logger.info("[THOUGHT]: No actionable tool call or final answer detected. Returning to user.")
                break
        else:
            logger.warning("Ambiguous message detected. Skipping ReAct loop for this message.")
            print("Your message was ambiguous. Please clarify your request.")
    if steps >= max_steps:
        print("Please clarify your request or try again.")
        logger.warning("Max steps reached in ReAct loop.")

    return final_answer if final_answer else response