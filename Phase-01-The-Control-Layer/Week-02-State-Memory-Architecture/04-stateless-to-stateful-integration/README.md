# Part 4: Stateless to Stateful Integration

## Terms

- Stateless: A system that does not retain user/session data between requests.
- Stateful: A system that remembers user/session data across requests.
- Durable State Store: A persistent storage mechanism (e.g., database, file, Redis) that survives process restarts and time gaps.
- LLM (Large Language Model): The AI model handling user queries.
- API Request: A call made to your backend service, simulating user interaction.
- Logs: Records of system actions, used to verify correct behavior.

## Key Concepts

- Session Continuity: The ability to link separate requests to the same user over time.
- Identity Recognition: Mechanism for associating requests with a user (e.g., via token, session ID).
- State Hydration: Loading user state from the durable store at the start of each request.
- State Persistence: Saving updated user state back to the durable store after each request.
- Test Simulation: Mimicking real-world usage by spacing out requests and verifying state recall.

## Implementation Overview

This project demonstrates the transition from a stateless to a stateful architecture for LLM-driven user interactions. It uses SQLite as a durable state store to persist user data, memories, and messages. The system supports user registration, authentication, and session continuity, ensuring that user context is loaded and updated with each interaction. Logging is implemented for traceability.

**Primary capabilities:**

- User registration and authentication
- Persistent storage of user memories and messages
- Prompt assembly for LLM using user-specific context
- Logging of all interactions
- Automated test simulation of multi-step user flows

## How It Works

1. **Startup:** The application initializes database tables for users, memories, and messages.
2. **User Action:** The user selects to register or log in. Credentials are handled securely.
3. **Identity Recognition:** Upon login, the user is authenticated and assigned a unique user ID.
4. **State Hydration:** User-specific memories are loaded from the database.
5. **Interaction:** The user sends a message. The system assembles a prompt using both the current message and relevant past memories.
6. **LLM Processing:** The prompt is sent to the LLM (e.g., OpenAI GPT-4o-mini), and a response is generated.
7. **State Persistence:** The response and any new facts are parsed and written back to the database as new memories.
8. **Logging:** All actions are logged for traceability.
9. **Test Simulation:** The integration test script simulates real user flows, including registration, login, and state recall across sessions.

## Example Usage

```
run_cli([
    "register",
    "robert1",
    "testpass",
    "robert1@example.com",
    "login",
    "robert1",
    "testpass",
    "Hi, I'm Robert. I'm having trouble with my password.",
    "exit"
])

run_cli([
    "login",
    "robert1",
    "testpass",
    "Check the status of my ticket.",
    "exit"
])
```

## Next Steps

- Add token/session-based authentication for API endpoints.
- Implement more granular memory categories and retrieval strategies.
- Add support for concurrent user sessions and distributed state stores (e.g., Redis).
- Enhance logging with structured, queryable formats (e.g., JSON logs).
- Integrate automated tests for edge cases and error handling.
- Add metrics for latency, token usage, and cost tracking if using paid LLM APIs.
