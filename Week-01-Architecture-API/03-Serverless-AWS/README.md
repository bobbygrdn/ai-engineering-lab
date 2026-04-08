# Part 2: Serverless Deployment (Lambda & Function URLs)

## Objective

To transition AI logic from a local development environment to a secure, scalable, and globally accessible cloud API.

## Key Technical Accomplishments

- **Serverless Infrastructure:** Deployed a production-ready **AWS Lambda** function using a **Function URL** for low-latency, zero-config HTTP access.
- **Secure Credential Management:** Integrated **AWS Secrets Manager** to decouple sensitive API keys from the codebase, utilizing the `@aws-sdk/client-secrets-manager` for runtime retrieval.
- **Advanced Bundling:** Configured `esbuild` with a custom **ESM Banner Shim** (`createRequire`) to allow legacy CommonJS dependencies to function within a modern Node.js 20+ `.mjs` environment.
- **Optimized Build Pipeline:** Engineered a "Flat-Archive" build script in `package.json` to automate the transition from a multi-gigabyte project root to a lean, **<2MB** deployment package.
- **Type-Safe Handshakes:** Leveraged **Zod** schemas in conjunction with LangChain's `withStructuredOutput` to ensure cloud responses adhere to strict interface contracts.

### **Technical Architecture**

- **Runtime:** Node.js 20.x on AWS Lambda (arm64).
- **Orchestration:** [LangChain](https://js.langchain.com/docs/get_started/introduction) for LLM chaining and prompt management.
- **Validation:** [Zod](https://zod.dev/) for strict schema enforcement of AI outputs.
- **Security:** [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) for encrypted API key storage with IAM-restricted access.
- **Deployment:** Lambda Function URLs for high-timeout, cost-effective API access.

## Proof of Work

The API successfully processes natural language project descriptions via **Postman** and returns a fully structured task breakdown:

| **Task Name**                      | **Category** | **Urgency** | **Assigned To** |
| ---------------------------------- | ------------ | ----------- | --------------- |
| Book a venue for the pizza party   | Logistics    | high        | null            |
| Order pizzas (vegan, GF, standard) | Catering     | high        | null            |
| Arrange drinks and utensils        | Catering     | medium      | null            |
| Set up the venue for the party     | Logistics    | medium      | null            |

## CloudWatch Execution Success:

```
INFO  Attempting to fetch secret...
INFO  Secret Keys Found: [ 'OPENAI_API_KEY' ]
INFO  EVENT RECEIVED: {"project_description": "Organize a 50-person company pizza party..."}
REPORT RequestId: ...  Duration: 535.52 ms  Memory Used: 116 MB
```
<img width="1576" height="894" alt="03-Serverless-LangChain-Diagram" src="https://github.com/user-attachments/assets/511bb77a-c23d-4a57-9050-3faacbbde36c" />
