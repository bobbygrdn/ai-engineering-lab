# Part 1: The Working Memory (Context Construction)

## Terms

- System/User/Assistant message structure
- ConversationBuilder class
- Message object
- Prompt formatting
- Hard Token Limit (4,000 tokens)
- Sliding Window
- Token counting

## Key Concepts

- Context construction: How to build a prompt from a sequence of messages.
- Token budgeting: Ensuring the prompt does not exceed a maximum token count.
- Sliding window algorithm: Retaining the most recent messages by dropping the oldest when over budget.
- Role-based message formatting: Distinguishing between system, user, and assistant messages.

## Implementation Overview

This module implements a ConversationBuilder class to manage a conversation history for prompt construction, enforcing a strict token budget (default 4,000 tokens). It uses a sliding window algorithm to retain the most recent messages, dropping the oldest non-system messages when the token limit is exceeded. Messages are structured as MessageObject instances with role and content fields, and are formatted for API compatibility. Token counting is performed using the tiktoken library. The system tracks and persists conversation state and token metrics in a JSON file.

**Primary capabilities:**

- Add messages with roles (system, user, assistant)
- Enforce a hard token limit using a sliding window
- Format prompts for API consumption
- Persist and reload conversation state and metrics

## How It Works

1. **Initialization** : ConversationBuilder loads conversation history and token limits from a metrics JSON file.
2. **Adding Messages** : New messages are appended and the conversation is trimmed using a sliding window to stay within the token limit, always preserving system messages.
3. **Token Counting** : Each message's token count is estimated using tiktoken.
4. **Sliding Window** : If the token limit is exceeded, the oldest non-system messages are removed until the budget is met.
5. **Prompt Formatting** : Messages are ordered (system, user, assistant) and formatted as required by the OpenAI API.
6. **Persistence** : Conversation state and token metrics are saved to a JSON file after each update.

## Example Usage

```
if __name__ == "__main__":
    # Add a token limit to the first instantiation, then remove the token limit and it will pull from the json file
    conversation_builder = ConversationBuilder(token_limit=500)

    # Change up these message statements each time to simulate a user talking with your AI system.
    conversation_builder.add_message("user", "Thank you. I think that is all I need.")
    conversation_builder.add_message("assistant", "You're welcome! If you have any more questions in the future, feel free to ask. Have a great day!")
    print(conversation_builder.format_prompt())
    print(f"Current tokens: {conversation_builder.current_tokens}")
    print(f"Token Limit: {conversation_builder.token_limit}")
```

Next Steps

- Add unit tests for edge cases (e.g., only system messages, rapid message addition).
- Parameterize the model for tiktoken to support different LLMs.
- Add support for message metadata (timestamps, IDs).
- Integrate with a live API for real-time prompt submission and response handling.
- Implement logging for token overflows and message drops.
