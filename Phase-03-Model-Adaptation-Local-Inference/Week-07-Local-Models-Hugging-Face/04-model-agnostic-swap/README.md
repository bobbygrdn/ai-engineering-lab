# Part 3: The Model Agnostic Swap

## Terms

- Intelligent Router
- Service Layer architecture
- Local inference server
- Pydantic schema
- Environment variables
- LLM client initialization
- Deterministic Wrapper

## Key Concepts

- Model-agnostic design through abstraction
- Dependency injection for LLM clients
- Configuration via environment variables
- Schema validation and enforcement
- Offline operation capability
- Interface segregation (separating service logic from LLM implementation)

## Implementation Overview

This project implements a model-agnostic support ticket classification system that can switch between different LLM backends (OpenAI API, local Llama.cpp server, or Instructor for structured outputs) while maintaining a consistent interface. The system uses Pydantic for schema validation of ticket classifications (priority, department, summary) and is configured via environment variables.

**Key capabilities:**

- Structured JSON output validation using Pydantic models
- Latency, token usage, and cost tracking
- Retry mechanisms with validation checks
- Streaming response simulation for local models
- Deterministic wrapper for consistent LLM interactions
- Support for both online (OpenAI) and offline (local Llama) operation

## How It Works

1. **Input Processing**: A support ticket text is passed to `classify_support_ticket()` in main.py
2. **Prompt Engineering**: The function constructs a prompt instructing the model to return JSON matching the `SupportTicket` schema
3. **LLM Abstraction**: The `LLMInterface` class in engine.py abstracts different backends:
   - For OpenAI: Uses OpenAI API with environment-configured base URL and key
   - For Llama.cpp: Uses local server with GGUF model
   - For Instructor: Uses OpenAI with response validation via Instructor library
4. **Structured Output**: The LLM interface returns a Pydantic `SupportTicket` object with validated fields
5. **Monitoring**: The `api_wrapper` decorator tracks latency, token usage, and cost (based on OpenAI pricing)
6. **Validation & Retry**: Optional retry logic checks for uncertain responses and logs invalid outputs
7. **Output**: Returns structured ticket classification with priority, department, and summary

## Example Usage

```python
email_text = "Hello, I was charged twice for my subscription and need a refund. Please help resolve this urgently."
response, metadata = classify_support_ticket(email_text)
print_ticket(response)
```

Output:

```
Priority  : High
Department: Billing
Summary   : Customer reports being charged twice for subscription and requests urgent refund resolution.
```

## Next Steps

1. **Expand LLM Backends**: Add support for additional providers (Anthropic, Hugging Face, local GGUF variants)
2. **Enhanced Routing**: Implement intelligent model selection based on ticket content or complexity
3. **Observability**: Add comprehensive logging, metrics collection, and dashboard integration
4. **Performance Optimization**: Implement response caching and batch processing for high-volume scenarios
5. **Testing Suite**: Add unit and integration tests for all LLM backends and edge cases
6. **Configuration Management**: Implement dynamic configuration reloading and environment-specific profiles
7. **Frontend Integration**: Develop a simple web interface or API endpoint for ticket submission
8. **Security Enhancements**: Add input sanitization, rate limiting, and secure credential management
