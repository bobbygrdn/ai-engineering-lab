# Part 2 Agentic ReAct Loop for LLM Tool Use

## Terms

- LLM (Large Language Model)
- Tool Call
- Observation
- Final Answer
- Python while loop
- Function execution
- Parsing
- Debugging

## Key Concepts

- Agentic Reasoning: The agent iteratively reasons, acts, and observes.
- ReAct Loop: The cycle of Thought → Action → Observation.
- Tool Use: The agent can call external functions/tools.
- Loop Termination: Detecting when to stop (i.e., when a "Final Answer" is given).
- Transparency: Making the agent’s reasoning visible for debugging.
- Parsing Structured Output: Extracting commands or actions from LLM responses.

## Implementation Overview

This project implements an agentic reasoning loop (ReAct) in Python, enabling an LLM to interactively process user requests, call external tools (functions), and update user data in a SQLite database. The agent's reasoning, tool calls, and observations are logged for transparency and debugging. The system parses LLM responses for structured tool calls, executes validated functions, and terminates the loop upon receiving a "Final Answer".

Primary capabilities:

- User authentication and registration
- Iterative LLM-driven reasoning and tool invocation
- Parsing and validating tool calls from LLM output
- Updating user data (email, password, username) via tool manifests
- Logging and debugging of agent reasoning and actions
- Memory management for user interactions

## How It Works

1. **Startup** : The app initializes database tables and prompts the user to register or log in.
2. **User Input** : The user enters a message for the LLM.
3. **ReAct Loop** :
   1. The agent sends the user message (and context) to the LLM.
   2. The LLM responds with either a tool call (e.g., `TOOL_CALL: {...}`) or a "Final Answer".
   3. The system parses the response:
      - If a tool call is detected, it validates and executes the corresponding function (e.g., update email).
      - The result is logged and, if required, verified against the manifest.
      - If verification passes, the loop may terminate; otherwise, it continues or requests clarification.
      - If a "Final Answer" is detected, the loop terminates and outputs the answer.
   4. All reasoning steps, actions, and observations are logged for transparency.
4. **Memory Management** : Recent messages and categorized memories are stored and prioritized for context.
5. **Loop Exit** : The loop ends on "Final Answer", user exit, or too many verification failures.

## Example Usage:

```

# Example: User wants to change their email
Enter your message for the LLM: set my email to test@abc.com

# LLM response (parsed):
TOOL_CALL: {"tool": "update_email", "args": {"email": "test@abc.com"}}

# Tool executes, updates the database, and confirms success.
```

## Next Steps

- Add more tool manifests for additional user actions.
- Enhance LLM prompt engineering for more robust tool call extraction.
- Implement richer memory/context management (e.g., long-term memory, summarization).
- Add unit and integration tests for tool validation and loop logic.
- Expand logging to include performance metrics (latency, cost, token usage).
- Support for additional LLM providers and models.
- Improve error handling and user feedback for ambiguous or failed actions.
