# Week 1: The Architecture & API Layer

## Objective

To master the programmatic interface of LLMs and enforce strict data types on non-deterministic models.

## Key Technical Accomplishments

- **Structured Outputs:** Utilized OpenAI's `parse` method to guarantee JSON responses.
- **Schema Validation:** Defined Pydantic models to act as a "Contract" between the AI and the Python backend.
- **Constraint Engineering:** Used Python `Enums` to force the AI into specific classification categories (High/Medium/Low urgency).
- **Defensive Programming:** Implemented logic to handle `NoneType` responses when the model encounters ambiguous data.

## Proof of Work

The script successfully parses messy, unstructured technical logs into a clean, actionable table:

| Technology | Owner | Urgency |
| :--------- | :---- | :------ |
| PostgreSQL | Sarah | High    |
| AWS Lambda | Joe   | High    |

<img width="858" height="347" alt="Screenshot 2026-04-04 200449" src="https://github.com/user-attachments/assets/399e9cb9-6a88-4f35-8ba8-052a89cbf284" />
