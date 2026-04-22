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

---

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

1. **Input**: User email text is provided to the classifier.
2. **Classification**: The LLM is prompted to extract `priority`, `department`, and a concise `summary`.
3. **Schema Enforcement**: Output is validated against the Pydantic model. If invalid, the system retries with the same or improved prompt.
4. **Logging**: Each attempt and result is logged. Unclear or invalid outputs are collected for review.
5. **Output**: Only schema-compliant, validated support tickets are returned.

---

## Example Usage

```python
ticket = classify_support_ticket_with_retries(email_text)
print_ticket(ticket)
```

---

## Next Steps & Improvements

- Analyze `invalid_outputs.jsonl` to refine prompts and improve reliability.
- Add automated tests for regression and edge cases.
- Visualize or summarize logs for insights.
- Expand the schema or add new fields as needed.

---

<figure>
    <img src="End-to-End-Lifecycle-Diagram.png"
         alt="End to End Lifecycle Diagram">
    <figcaption style="text-align: center;">End to End Lifecycle of a Structured Support Ticket AI.</figcaption>
</figure>
