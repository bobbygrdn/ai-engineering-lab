# Part 2: Chains & Automated Memory (Day 3 & 4)

## Objective

To move beyond manual history handling and implement a **self-managing state layer** . This phase focused on utilizing **LangChain Expression Language (LCEL)** to build a cohesive pipeline that automatically handles persistence via DynamoDB and enforces a sliding "Window Memory" to optimize token costs and performance.

## Key Technical Accomplishments

- **Automated Memory Orchestration:** Migrated from manual database read/write logic to LangChain’s native `DynamoDBChatMessageHistory`. This allows the orchestrator to automatically "remember" and "append" session data without custom glue code.
- **Sliding Window Implementation (80/20 Rule):** Applied a **$K=10$** window limit via an LCEL trimmer. By only passing the last 20 messages to the LLM, the system maintains the high-impact "20%" of current context while pruning irrelevant history to save on costs and latency.
- **Production-Grade Execution (.mjs):** Transitioned to an ECMAScript Module ( **ESM** ) environment to utilize **Top-Level Await** . This allows the Lambda to fetch secrets and initialize the model once during the "Cold Start," significantly accelerating subsequent "Warm Start" invocations.
- **Unified LCEL Pipeline:** Replaced fragmented function calls with a single `RunnableWithMessageHistory` chain. This pipeline links the prompt, the window-trimmer, the model, and the `StringOutputParser` into one declarative handshake.
- **Zero-Trust Security:** Maintained strict security protocols by utilizing **AWS Signature V4** with **MFA enforcement** , ensuring that only authenticated sessions with temporary credentials can trigger the API.

## Technical Architecture

- **Orchestration:** [LangChain](https://js.langchain.com/) (LCEL) for declarative chain composition.
- **State Store:** [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) for persistent, serverless message history.
- **Security:** [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) for encrypted API key retrieval.
- **Model:** OpenAI `gpt-4o-mini` for high-speed, cost-effective reasoning.
- **Deployment:** AWS Lambda (Node.js 20.x) with custom `esbuild` ESM-shim for legacy dependency compatibility.

| **Sequence**   | **User Input**                | **AI Response (State Awareness)**                                         |
| -------------- | ----------------------------- | ------------------------------------------------------------------------- |
| **Request 1**  | "My name is Robert."          | "Nice to meet you, Robert! How can I assist you today?"                   |
| **Request 2**  | "What is my name?"            | "Your name is Robert."                                                    |
| **Request 12** | [After 10 intermediate turns] | **Window Shift:**History for Request 1 is pruned to maintain performance. |

## Execution Success (CloudWatch Sanitized):

```
INFO  Secret Keys Found: [ 'OPENAI_API_KEY' ]
INFO  EVENT RECEIVED: {"sessionId": "dev-session-001", "input": "What is my name?"}
INFO  DynamoDB: Successfully retrieved 12 messages for session: dev-session-001
INFO  Memory: Trimming history to last 20 messages (K=10).
REPORT RequestId: [REDACTED]  Duration: 512.42 ms  Billed Duration: 513 ms  Max Memory Used: 145 MB
```
