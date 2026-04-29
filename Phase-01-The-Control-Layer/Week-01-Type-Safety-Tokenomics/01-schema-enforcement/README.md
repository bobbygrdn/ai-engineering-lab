# Part 1: Type-Safety & Tokenomics

## Terms

- **Schema**
- **Pydantic**
- **Model (in Pydantic context)**
- **Validation**
- **Serialization / Deserialization**
- **Instructor Library**
- **PydanticAI**
- **LLM (Large Language Model)**
- **Prompt Engineering**
- **Support Ticket**
- **Priority (High/Med/Low)**
- **Department (Billing/Tech/General)**
- **Summary**
- **Retry Logic**

## Key Concepts

- The role of schema enforcement in AI reliability
- How Pydantic models define and enforce data structure
- Why and how AI outputs can be malformed
- Validating AI outputs against a schema
- How Instructor/PydanticAI libraries enforce schema compliance with LLMs
- Implementing validation retries and automated error handling
- Designing prompts for structured, schema-compliant outputs
- Classification challenges in support ticket systems

## Implementation Overview

This project implements a robust, schema-enforced AI pipeline for classifying support tickets from unstructured email text. Key features include:

- **Pydantic Model**: Strictly defines the output schema (`priority`, `department`, `summary`) using Python Enums for valid values.
- **Instructor Library**: Integrates with OpenAI GPT-4o-mini to enforce schema compliance on LLM outputs.
- **Validation Retries**: Automatically retries classification if the output does not fit the schema, up to a configurable limit.
- **Logging**: All attempts, successes, and validation errors are logged to `support_ticket.log` for traceability and debugging.
- **Edge Case Handling**: The system is tested with ambiguous, incomplete, and nonsensical inputs to ensure reliability.
- **Invalid Output Collection**: Any output that is unclear or fails validation is saved to `invalid_outputs.jsonl` for later analysis and prompt engineering improvements.

---

## How It Works

1. **Input** : Unstructured email text is provided.
2. **Prompting** : The email is sent to the LLM via the Instructor library, with a schema (Pydantic model) specifying required fields.
3. **Validation** : The LLM's output is validated against the schema.
4. **Retry Logic** : If validation fails, the process retries up to a set limit.
5. **Logging** : All attempts, errors, and invalid outputs are logged.
6. **Output** : On success, a structured support ticket (priority, department, summary) is returned and printed.

---

## Example Usage

```python
if __name__ == "__main__":
    email_text_list = [
        "Hello, I was charged twice for my subscription and I need a refund. Please help me resolve this issue as soon as possible.",
        "My internet connection is very slow and keeps dropping. Can you please assist me in fixing this problem?",
        "I have a question about your product features. Can you provide more information on how to use the advanced settings?",
        "Help!",
        "My account is locked, but I also want to change my billing address.",
        "jfodhafdsafhdslkafj"
    ]
    for email_text in email_text_list:
        ticket = classify_support_ticket_with_retries(email_text)
        print_ticket(ticket)
```

---

## Next Steps & Improvements

- Add unit tests for edge cases and malformed inputs
- Parameterize retry logic and logging for production use
- Integrate with real support ticketing systems or APIs
- Enhance prompt engineering for better LLM compliance
- Track and visualize validation error rates and retry statistics

---

<figure>
    <img src="End-to-End-Lifecycle-Diagram.png"
         alt="End to End Lifecycle Diagram">
    <figcaption style="text-align: center;">End to End Lifecycle of a Structured Support Ticket AI.</figcaption>
</figure>
