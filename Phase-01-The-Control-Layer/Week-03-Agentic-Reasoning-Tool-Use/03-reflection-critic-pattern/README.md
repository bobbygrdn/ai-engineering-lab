# Part 3 Reflection & Critic Pattern

## Terms

- Agent A (Responder)
- Agent B (Critic)
- Self-correction
- Company Policy (text file)
- Agentic Workflow
- Support Ticket Agent
- Error detection
- Instruction feedback loop

## Key Concepts

- Reflection Pattern: An agent reviews its own or another agent's output for quality.
- Critic Pattern: A secondary agent evaluates and provides corrective feedback.
- Self-correction Loop: Iterative process where output is improved based on feedback.
- Separation of Concerns: Distinct roles for response generation and critique.
- Policy Compliance: Ensuring outputs adhere to external rules or guidelines.
- Agentic Workflow Design: Structuring multi-agent systems for reliability and quality.

## Implementation Overview

This project implements a multi-agent support ticket system using the Reflection and Critic patterns. The system separates the response generation (ResponderAgent) from critique (CriticAgent), enforcing company policy compliance through an instruction feedback loop and self-correction. The workflow is designed for reliability, error detection, and adherence to external rules.

**Primary Capabilities:**

- User authentication and registration
- Support ticket management
- LLM-driven response generation for account actions (email, password, username updates)
- Automated critique and self-correction of responses for policy compliance
- Tool manifest validation for safe tool invocation
- Message buffer and memory prioritization for context management

## How It Works

1. **User Authentication:** User registers or logs in.
2. **Message Input:** User submits a support request (e.g., update email).
3. **Ambiguity Check:** System checks if the message is ambiguous.
4. **Ticket Validation:** If an account action is requested, the system verifies a valid Ticket ID.
5. **Prompt Assembly:** Recent messages and prioritized memories are combined into a prompt.
6. **ResponderAgent:** Generates a response or tool call using the LLM.
7. **Tool Execution:** If a tool call is detected, input is validated and the tool is executed (e.g., update_email).
8. **Confirmation Message:** A user-facing confirmation is generated.
9. **CriticAgent:** Critiques the confirmation for policy compliance.
10. **Self-correction Loop:** If not approved, the response is revised up to three times.
11. **Logging and Storage:** All interactions are logged and stored in the message buffer.

## Example Usage

```
# User: "change my email to new@example.com. Ticket ID: TICKET-12345"
run_react_loop("change my email to new@example.com. Ticket ID: TICKET-12345", user_id, model, messages_buffer)
# Output: "I understand you wanted to update your email. Your email has been updated successfully. If you need further assistance, please let me know."
```

## Next Steps

- Add automated tests for edge cases in the self-correction loop.
- Expand tool manifests for additional support actions.
- Integrate more granular policy modules (e.g., regional compliance).
- Implement user-facing feedback for critique failures.
- Add metrics for latency, error rates, and policy compliance rates.
