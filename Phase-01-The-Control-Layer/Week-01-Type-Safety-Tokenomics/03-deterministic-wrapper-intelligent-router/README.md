## Part 3: Deterministic Wrapper & Intelligent Router

## Terms

- Deterministic Wrapper
- Intelligent Router
- Python Service Class (e.g., SupportAIService)
- Decision Gate / Routing Gate
- Inference
- Intent Complexity
- SLM (Small Language Model)
- Frontier Model
- Pydantic object
- Model-Agnosticism
- Inference Efficiency
- Unit Economics of AI
- Tokenomics
- Regex classifier
- Unified interface

## Key Concepts

- Isolation of "AI chaos": Encapsulating unpredictable or variable AI behavior behind a controlled interface.
- Decision Gate: A pre-inference filter that determines the minimal necessary compute for a given input.
- Model selection based on intent complexity: Using lightweight methods to triage requests and route them to the most cost-effective model.
- Model-agnostic business logic: Decoupling business logic from model specifics, relying on standardized outputs.
- Inference efficiency and cost optimization: Ensuring that computational resources (and thus costs) are matched to the complexity of the task.
- Validation and standardization: Using Pydantic to enforce output schemas regardless of model source

## Overview

This project implements a deterministic wrapper and intelligent router for AI-powered support ticket handling. It encapsulates unpredictable AI behavior behind a controlled, model-agnostic interface, using decision gates to optimize inference efficiency and cost. The system leverages Pydantic for schema validation and standardization, ensuring reliable outputs regardless of the underlying model.

- Deterministic API wrapper for AI inference with timing and token usage tracking
- Intelligent routing between SLM (Small Language Model) and Frontier Model based on intent complexity
- Regex-based intent classifier for lightweight triage
- Unified, model-agnostic interface for business logic
- Pydantic-based schema validation for all inputs/outputs
- Logging of invalid outputs for audit and debugging
- Cost calculation for inference based on token usage

## How It Works

1. **Input** : A support ticket text is received.
2. **Intent Classification** : The [classify_intent()](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) function uses regex/keyword matching to determine if the request is "simple" or "complex".
3. **Routing Gate** :

- "Simple" intents are routed to the [SLMModel](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- "Complex" intents are routed to the [FrontierModel](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).

1. **Inference** : The selected model generates a response, wrapped by [api_wrapper](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) to measure duration and token usage.
2. **Validation** : All outputs are validated against Pydantic schemas ([SupportTicket](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [SupportResponse](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
3. **Logging** : Invalid outputs are logged for review.
4. **Output** : The standardized response, including metadata (duration, token usage, model), is returned.

## Example Usage

```
service = SupportAIService()
test_cases = [
    "Can you check the status of my ticket?",
    "Thank you for your help, please close the ticket.",
    "I was charged twice for my subscription and need a refund.",
    "There is an error when I try to log in.",
    "Just wanted to say thanks!"
]

for i, text in enumerate(test_cases, 1):
    print(f"\nTest case {i}: {text}")
    response = service.handle_ticket(text)
    print(f"Intent: {response.intent}")
    print(f"Response: {response.response_text}")
    print(f"Metadata: {response.metadata.model_dump()}")
```

## Implementation Highlights

- **Deterministic Wrapper** : See [api_wrapper](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) in [main.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Intelligent Router** : See [SupportAIService](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) and [classify_intent](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) in [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Python Service Class** : [SupportAIService](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) in [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Decision Gate / Routing Gate** : [classify_intent](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) and routing logic in [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Inference** : [infer_response](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) methods in [SLMModel](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) and [FrontierModel](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
- **Intent Complexity** : Keyword-based in [classify_intent](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
- **SLM / Frontier Model** : Implemented as classes in [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Pydantic object** : [SupportTicket](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [SupportResponse](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [Metadata](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) in [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Model-Agnosticism** : Unified interface in [ModelInterface](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
- **Inference Efficiency** : Routing and timing in [main.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) and [schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html).
- **Unit Economics of AI / Tokenomics** : Cost calculation in [calulate_price](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([main.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
- **Regex classifier** : [classify_intent](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).
- **Unified interface** : [SupportAIService.handle_ticket](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html) ([schema.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/10c8e557c8/resources/app/out/vs/code/electron-browser/workbench/workbench.html)).

## **Tech Stack** :

- Python 3
- Pydantic
- OpenAI, Instructor (for model APIs)
- dotenv, logging, tabulate, tiktoken

## Next Steps

- Integrate real token counting and cost calculation for each model
- Expand intent classification with more advanced NLP or ML
- Add unit and integration tests for all routing and validation logic
- Support additional models and dynamic model selection
- Expose as a REST API (e.g., with FastAPI)
- Add monitoring for latency, error rates, and cost per request
