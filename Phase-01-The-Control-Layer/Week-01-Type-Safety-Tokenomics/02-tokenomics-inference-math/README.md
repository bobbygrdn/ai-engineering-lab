# Part 2: Tokenomics & Inference Math

## Overview

This project extends the schema-enforced support ticket classifier with advanced LLM usage analytics, cost estimation, and real-time streaming metrics. It demonstrates how to measure, log, and optimize the economics and latency of LLM-powered workflows.

## Key Features

- **Streaming LLM Inference:**
  Real-time support ticket classification using OpenAI’s streaming API, with precise measurement of Time To First Token (TTFT) and total response duration.
- **Tokenomics & Cost Calculation:**
  Estimates prompt and completion token counts for every request and computes the cost using OpenAI’s published rates.
- **TTFT Thresholds & Observability:**
  Configurable TTFT threshold; logs warnings if exceeded to help monitor and optimize user experience.
- **Comprehensive Metadata Logging:**
  Every classification logs detailed metadata—including timing, cost, and token usage—for traceability and performance analysis.
- **Schema Enforcement & Validation:**
  All outputs are validated against a strict Pydantic schema. Invalid or ambiguous results are logged for further analysis.

## How It Works

1. **Input:**
   User email text is provided to the classifier.
2. **Classification:**
   The LLM is prompted (with explicit JSON schema instructions) to extract `priority`, `department`, and a concise `summary`.
3. **Streaming & Timing:**
   For streaming, the system measures TTFT (how quickly the first token arrives) and total duration, collecting the output incrementally.
4. **Tokenomics:**
   After completion, the system estimates token usage and calculates the cost of the request.
5. **Validation & Logging:**
   The output is validated against the schema. All metadata—including timing, cost, and token counts—is logged for every request.

## Example Usage

```
# Streaming classification with full metadata
ticket, metadata = classify_support_ticket_stream(email_text)
print_ticket(ticket)
print("Metadata:", metadata)
```

## Sample Metadata

```
{
  "total_duration": 2.3,
  "time_to_first_token": 1.7,
  "cost": 0.00002,
  "time_difference": 0.6
}
```

## Implementation Highlights

- **Pydantic Models:**
  Strictly define valid outputs for `priority`, `department`, and `summary`.
- **OpenAI Streaming API:**
  Enables real-time feedback and TTFT measurement.
- **Token Counting:**
  Uses `tiktoken` to estimate prompt and completion tokens.
- **Cost Calculation:**
  Applies OpenAI’s GPT-4o-mini pricing to estimate per-request cost.
- **Logging:**
  All attempts, results, and metadata are logged for analysis and debugging.

## Next Steps

- Analyze logs to optimize prompt design and reduce cost/latency.
- Add automated tests for streaming and tokenomics logic.
- Visualize TTFT and cost trends over time.
- Expand schema or add new business logic as needed.

**This project demonstrates not just how to classify support tickets with LLMs, but how to do so with full visibility into the economics and latency of every inference.**
