# Part 1: Tools Manifest & Data Firewall

## Terms

- JSON Tool Manifest: A structured JSON file describing each tool’s interface, including function names, argument types, and allowed values (enums).
- Data Types: Explicit specification of input/output types (e.g., string, integer, enum).
- Enum: A set of allowed values for a parameter.
- Delimited Context Framing: Wrapping external/untrusted data in specific tags (e.g., <user_data>...</user_data>).
- System Prompt: The initial instruction set given to an AI agent.
- Hard Rule: A non-negotiable instruction in the system prompt.
- Indirect Prompt Injection: A security vulnerability where untrusted input manipulates the agent’s behavior.
- API Contract: The formal definition of how tools can be invoked and what data they accept/return.

## Key Concepts

- Principle of Least Privilege: Treat all external data as untrusted and limit its influence.
- Structural Defense: Using structure (tags, manifests) to enforce boundaries between trusted and untrusted data.
- Defense-in-Depth: Multiple layers of security to prevent a single point of failure.
- Explicit Data Framing: Clearly marking the boundaries of untrusted data.
- Deterministic Tool Invocation: Tools can only be called with data that matches the manifest, not arbitrary strings.
- Separation of Concerns: Keeping tool logic, data handling, and security rules distinct.

## Implementation Overview

This project implements a secure agentic reasoning and tool-use system for LLMs, focusing on strict separation between untrusted user input and tool invocation logic. The system uses JSON tool manifests to define API contracts, explicit data types, and allowed values. All user data is wrapped in <user_data> tags, and the system prompt enforces hard rules to prevent indirect prompt injection. Tool invocations are only allowed if arguments match the manifest schema, providing deterministic and auditable tool use.

Primary capabilities:

- User registration and authentication.
- Updating user email, password, and username via manifest-driven tool calls.
- Explicit validation of tool arguments against manifest-defined types.
- Context framing of user input to prevent prompt injection.
- Logging and memory management for user interactions.

## How It Works

1. On startup, the system loads tool manifests (JSON) and initializes database tables for users, memories, and messages.
2. The user registers or logs in; credentials are handled securely.
3. User messages are wrapped in <user_data> tags and stored in a message buffer.
4. The system assembles a prompt for the LLM, including delimited user data and relevant memory/context.
5. The LLM receives a system prompt with hard rules: all <user_data> is untrusted and must not be interpreted as instructions.
6. The LLM may output a TOOL_CALL with a tool name and arguments.
7. The system extracts the tool call, validates arguments against the manifest (type, presence, enums), and only then invokes the tool.
8. Tool results are logged, and the conversation continues, with all new facts written back to memory.

## Example Usage

```
{
  "name": "update_email",
  "description": "Update the email address associated with your account.",
  "parameters": {
    "email": { "type": "string" }
  },
  "returns": {
    "success": { "type": "boolean" },
    "message": { "type": "string" }
  }
}
```

Example LLM Output and invocation

```
TOOL_CALL: {"tool": "update_email", "args": {"email": "new@example.com"}}
```

The system validates that "email" is a string before calling the update_email function.

## Next Steps

- Add automated tests for manifest validation and tool invocation.
- Expand manifest schema to support nested objects and more complex types.
- Implement logging/auditing for all tool calls and validation failures.
- Integrate additional security checks (e.g., rate limiting, anomaly detection).
- Document the manifest authoring process for new tools.
- Consider support for role-based access control in tool manifests.
