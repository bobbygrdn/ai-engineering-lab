# Part 3: Context Compression (Summarization)

## Terms

- Summarization Loop
- LLM (Large Language Model)
- Context window
- Recursive Memory
- Token limit
- Message history
- 2-sentence summary
- Distillation

## Key Concepts

- Context Compression: Reducing the amount of information while retaining essential meaning.
- Long-term Memory for AI: Persisting distilled knowledge beyond the immediate context window.
- Recursion in Memory: Using summaries of summaries to manage growing histories.
- Trade-off: Balancing detail retention with context window/token constraints.
- Information Loss: Risk of omitting important details during summarization.

## Implementation Overview

This project implements a context compression and recursive memory system for LLM-based agents. It manages message history and long-term memory by distilling interactions into summaries, storing categorized memories, and recursively compressing message buffers to fit within LLM context windows and token limits. The primary capabilities include:

- Summarizing message buffers into 2-sentence summaries when the buffer exceeds a set size.
- Categorizing and persisting user/assistant interactions as preferences, past issues, or system context.
- Recursively compressing and prioritizing memories to balance detail retention and context constraints.
- Assembling prompts for the LLM using prioritized, distilled memories and recent message history.

## How It Works

1. On startup, the system loads or initializes memories.json and messages_buffer.json.
2. The user inputs a message, which is added to the message buffer.
3. If the buffer exceeds 10 messages, it is summarized into a 2-sentence distillation using the LLM, and the buffer is replaced with this summary.
4. Each message is classified (preference, past issue, or system context) and written to the appropriate section in memories.json.
5. When preparing a prompt for the LLM, the system:
   - Loads and prioritizes memories by recency.
   - Assembles a prompt with recent messages, prioritized preferences, past issues, and system context.
6. The prompt is sent to the LLM, and the response is both displayed and written back into memory, continuing the summarization loop.

## Example Usage

```
# main.py (simplified)
user_message = input("Enter your message for the LLM: ")
messages_buffer.add_message("user", user_message)
parse_and_writeback("user", user_message, memories_file)
...
prompt = assemble_prompt(memories, buffered_messages)
response = send_to_llm(prompt, model)
messages_buffer.add_message("assistant", response)
parse_and_writeback("assistant", response, memories_file)
```

## Next Steps

- Add evaluation metrics for information loss during summarization (e.g., compare original vs. summary content).
- Implement configurable buffer size and summary length.
- Integrate visualization of memory evolution and context window usage.
- Support for multiple LLM models and dynamic model selection based on context size.
- Add automated tests for memory categorization and prompt assembly logic.
