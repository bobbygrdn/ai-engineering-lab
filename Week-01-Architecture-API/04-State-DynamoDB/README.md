# Part 4: Serverless Deployment (Lambda & Function URLs)

## Objective

To transition AI logic to a secure, scalable cloud API and implement **persistent session memory** , allowing the agent to maintain context across multiple interactions.

## Key Technical Accomplishments

- **Serverless Infrastructure:** Deployed a production-ready **AWS Lambda** function using a **Function URL** for low-latency, zero-config HTTP access.
- **Secure Credential Management:** Integrated **AWS Secrets Manager** to decouple sensitive API keys from the codebase, utilizing the `@aws-sdk/client-secrets-manager` for runtime retrieval.
- **Advanced Bundling:** Configured `esbuild` with a custom **ESM Banner Shim** (`createRequire`) to allow legacy CommonJS dependencies to function within a modern Node.js 20+ `.mjs` environment.
- **Optimized Build Pipeline:** Engineered a "Flat-Archive" build script in `package.json` to automate the transition from a multi-gigabyte project root to a lean, **<2MB** deployment package.
- **Type-Safe Handshakes:** Leveraged **Zod** schemas in conjunction with LangChain's `withStructuredOutput` to ensure cloud responses adhere to strict interface contracts.
- **Persistent State Management:** Integrated **Amazon DynamoDB** as an external memory store, utilizing LangChain's `DynamoDBChatMessageHistory` to overcome the stateless nature of AWS Lambda.
- **Session-Based Context:** Engineered a `sessionID` logic flow that isolates user conversations and enables the model to reference previous prompts (e.g., remembering "12 people" when asked for "vegan options").
- **Production-Grade Security:** Implemented an **MFA-Enforced IAM Policy** (EnforceMFA), requiring AWS Signature V4 authentication with temporary session tokens for all API interactions.
- **Automated Data Lifecycle:** Configured **Time-to-Live (TTL)** on DynamoDB records to automate data pruning and maintain a zero-cost storage footprint.

### **Technical Architecture**

- **Runtime:** Node.js 20.x on AWS Lambda (arm64).
- **Orchestration:** [LangChain](https://js.langchain.com/docs/get_started/introduction) for LLM chaining and prompt management.
- **Validation:** [Zod](https://zod.dev/) for strict schema enforcement of AI outputs.
- **Security:** [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) for encrypted API key storage with IAM-restricted access.
- **Deployment:** Lambda Function URLs for high-timeout, cost-effective API access.
- **Database:** [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) for serverless, low-latency state persistence.
- **Identity:** [AWS IAM](https://aws.amazon.com/iam/) with MFA enforcement for secure API authentication.

## Proof of Work

The API successfully processes natural language project descriptions via **Postman** and returns a fully structured task breakdown:

| **Sequence**  | **User Prompt**                     | **AI Response (State Awareness)**                         |
| ------------- | ----------------------------------- | --------------------------------------------------------- |
| **Request 1** | "Plan a pizza party for 12 people." | Generate tasks for**12 people.**                          |
| **Request 2** | "Add Hawaiian theme tasks."         | Adds themed tasks while**retaining the 12-person count**. |

### Security Note:

This API is protected by an explicit MFA-enforcement policy. All requests must be signed with temporary `ASIA` credentials generated via an MFA-authenticated session to prevent unauthorized usage of the long-term `AKIA` access keys.

## CloudWatch Execution Success:

```
## CloudWatch Execution Success (Sanitized)

# --- REQUEST 1: Initial Context ---
INIT_START Runtime Version: nodejs:20.vXX	Runtime Version ARN: arn:aws:lambda:us-east-1::runtime:[REDACTED]
START RequestId: [REQ_ID_1] Version: $LATEST
INFO  EVENT RECEIVED: {
    "requestContext": {
        "accountId": "**********",
        "authorizer": {
            "iam": {
                "accessKey": "ASIA****************",
                "userArn": "arn:aws:iam::*********:user/*********"
            }
        },
        "http": { "method": "POST", "sourceIp": "*********" }
    },
    "body": "{ \"sessionId\": \"party-001\", \"project_description\": \"Plan a pizza party for 12 people this Friday.\" }"
}
REPORT RequestId: [REQ_ID_1]	Duration: 3794.68 ms	Billed Duration: 4150 ms	Memory Size: 512 MB	Max Memory Used: 157 MB	Init Duration: 353.78 ms

# --- REQUEST 2: Stateful Follow-up (Hawaiian Theme) ---
START RequestId: [REQ_ID_2] Version: $LATEST
INFO  EVENT RECEIVED: {
    "requestContext": { "accountId": "*********" },
    "body": "{ \"sessionId\": \"party-001\", \"project_description\": \"We've decided to make it a Hawaiian theme. Add themed tasks.\" }"
}
INFO  DynamoDB: Successfully retrieved conversation history for session: party-001
REPORT RequestId: [REQ_ID_2]	Duration: 3561.82 ms	Billed Duration: 3562 ms	Memory Size: 512 MB	Max Memory Used: 157 MB
```
