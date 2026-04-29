# Part 4: Error States & Benchmarking

## Terms

- Error States
- Benchmarking
- Rate Limits
- Empty Prompts
- Refusals (Safety Filters)
- Baseline Report
- Accuracy vs. Schema
- Average Cost per Ticket
- Test Emails
- Logging

## Key Concepts

- Fault Tolerance: Designing systems to handle and recover from errors gracefully.
- Failure Simulation: Intentionally triggering errors to test system robustness.
- Metrics & Benchmarking: Quantitatively measuring system performance and reliability.
- Schema Validation: Ensuring outputs conform to expected data structures.
- Cost Analysis: Calculating resource usage or expenses per operation.
- Graceful Degradation: Providing fallback behaviors when errors occur.

## Implementation Overview

This project benchmarks an AI-powered support ticket classification system, focusing on error handling, schema validation, and cost analysis. It simulates various error states (rate limits, empty prompts, refusals), logs invalid outputs, and measures performance and cost per ticket. The system validates outputs against a strict schema and provides a summary report on accuracy and average cost.

**Primary capabilities:**

- Support ticket classification using LLMs (OpenAI GPT-4o-mini).
- Error simulation and handling (rate limits, empty prompts, refusals).
- Output schema validation (using Pydantic).
- Logging of invalid outputs and errors.
- Benchmarking with a suite of test emails.
- Calculation of accuracy vs. schema and average cost per ticket.
- Detailed logging and summary reporting.

## How It Works

1. **Input** : A list of test support emails is defined in the benchmark module.
2. **Processing** : Each email is processed by [process_email], which:
   - Checks for empty prompts, rate limit, or refusal triggers.
   - Calls the LLM to classify the ticket and generate a response.
   - Validates the output against the [SupportTicket]schema.
   - Handles and logs errors (validation, refusal, rate limit, empty prompt).
3. **Error Handling** : Custom exceptions are raised for rate limits, empty prompts, and refusals. Invalid outputs are logged to [invalid_outputs.jsonl].
4. **Benchmarking** : For each email, the result (validity and cost) is recorded.
5. **Metrics** : After all emails are processed:
   - Accuracy (valid outputs / total).
   - Average cost per valid ticket.
   - Tabulated summary of results.
6. **Logging** : All events, errors, and metadata are logged for traceability.

## Example Usage

```
from benchmark import run_benchmark

if __name__ == "__main__":
    run_benchmark()
```

Example output (printed summary):

```
Accuracy vs. Schema: 85.00%
Average Cost per Ticket: $0.0002
#  Email                                    Valid  Cost
1  Hello, I was charged twice...            True   $0.0002
2  My internet connection is very...        True   $0.0002
...
```

## Next Steps

- Add more granular error categories and recovery strategies.
- Integrate additional LLM providers for comparative benchmarking.
- Expand schema validation to cover more complex ticket types.
- Implement asynchronous processing for higher throughput.
- Visualize benchmarking results (charts, dashboards).
