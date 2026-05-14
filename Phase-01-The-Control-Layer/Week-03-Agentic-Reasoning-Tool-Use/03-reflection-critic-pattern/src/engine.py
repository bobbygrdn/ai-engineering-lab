from schema import load_memories, prioritize_memories, assemble_prompt, validate_tool_input, validate_tool_output, invoke_tool, extract_tool_call
from db import update_email, update_password, update_username, is_ambiguous_message, parse_and_writeback, get_ticket_by_id
from models import ResponderAgent, CriticAgent
from llm_utils import send_to_llm
from dotenv import load_dotenv
from logger import logger
import openai
import os
import json
import re

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

def account_action_requested(user_message):
    keywords = ["update", "change", "reset", "email", "username", "password"]
    return any(word in user_message.lower() for word in keywords)

def ticket_id_provided(user_message):
    return bool(re.search(r"\b[Tt]icket\s*ID[:\s]*\w+", user_message))

def extract_ticket_id(user_message):
    match = re.search(r"\b[Tt]icket\s*ID[:\s]*([A-Za-z0-9\-]+)", user_message)
    return match.group(1) if match else None

def is_valid_ticket(ticket_id, user_id):
    ticket = get_ticket_by_id(ticket_id)
    return ticket is not None and ticket['user_id'] == user_id

def generate_update_confirmation(field):
    return (
        f"I understand you wanted to update your {field}. "
        f"Your {field} has been updated successfully. "
        "If you need further assistance, please let me know."
    )

def run_react_loop(user_message, user_id, model, messages_buffer):
    if is_ambiguous_message(user_message):
        logger.warning("Ambiguous message detected: '%s'", user_message)
        print("Your message was ambiguous. Please clarify your request.")
        return

    ticket_id = extract_ticket_id(user_message)
    if account_action_requested(user_message):
        if not ticket_id or not is_valid_ticket(ticket_id, user_id):
            print("Please provide a valid Ticket ID associated with your account before I can update your information.")
            return

    messages_buffer.add_message("user", user_message)
    parse_and_writeback("user", user_message, user_id)

    memories = load_memories(user_id)
    if memories is not None:
        logger.info(f"Loaded memories for user_id={user_id} from SQLite durable store.")
    memories = prioritize_memories(memories)
    buffered_messages = messages_buffer.get_messages()
    prompt = assemble_prompt(memories, buffered_messages)

    responder = ResponderAgent(model)
    critic = CriticAgent(model)
    max_corrections = 3

    response = responder.respond(prompt)
    tool_name, tool_args = extract_tool_call(response)
    tool_result = None

    if tool_name and tool_args:
        if 'user_id' not in tool_args:
            tool_args['user_id'] = user_id
        if 'ticket_id' not in tool_args and ticket_id:
            tool_args['ticket_id'] = ticket_id
        validate_tool_input(tool_name, tool_args, manifests)
        tool_result = tool_functions[tool_name](**tool_args)
        logger.info(f"Tool '{tool_name}' executed successfully with result: {tool_result}")

    if tool_result is not None:
        TOOL_FIELD_MAP = {
            "update_email": "email",
            "update_password": "password",
            "update_username": "username"
        }
        field = TOOL_FIELD_MAP.get(tool_name, "account information")
        user_facing_message = generate_update_confirmation(field)
        critique = critic.critique(user_facing_message)
        logger.info("Critique: %s", critique)
        if critique.strip().lower() != "approved":
            logger.warning("Critic did not approve, but sending deterministic confirmation anyway.")

        print("LLM response:", user_facing_message)
        messages_buffer.add_message("assistant", user_facing_message)
        parse_and_writeback("assistant", user_facing_message, user_id)
        logger.info("LLM response: %s", user_facing_message)
        return user_facing_message
    else:
        user_facing_message = response
        for _ in range(max_corrections):
            critique = critic.critique(user_facing_message)
            logger.info("Critique: %s", critique)
            if critique.strip().lower() == "approved":
                break
            revision_prompt = (
                f"Revise the following message to comply with company policy, using this critique:\n"
                f"Message: {user_facing_message}\nCritique: {critique}"
            )
            user_facing_message = responder.respond(revision_prompt)
        else:
            logger.error("Failed to generate a policy-compliant message after several attempts.")
        print("LLM response:", user_facing_message)
        messages_buffer.add_message("assistant", user_facing_message)
        parse_and_writeback("assistant", user_facing_message, user_id)
        logger.info("LLM response: %s", user_facing_message)
        return user_facing_message