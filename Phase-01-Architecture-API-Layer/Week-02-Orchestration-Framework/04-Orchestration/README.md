# Part 4: Serverless AI Orchestration

## Objective

The final goal of Week 2 was to package the "Fresh Start" logic—including prompt templates, document loaders, and structured output parsers—into a dedicated, production-ready AWS Lambda function.

## Architecture: The "Extractor" Microservice

Rather than bloating the existing project-manager-api, a new specialized Lambda function, `Job-Listing-Extractor`, was created to handle high-latency web scraping and extraction tasks.

### Infrastructure Details

- **Runtime:** Node.js 20.x (ESM/NodeNext).
- **Compute:** 512MB RAM / 30-second Timeout (Optimized for LLM processing times).
- **Trigger:** Lambda Function URL (Auth Type: AWS_IAM).
- **Security:** MFA-enforced SigV4 authentication via Postman and AWS Secrets Manager for OpenAI credential rotation.

## Lessons Learned

### 1. Dependency Resolution in Rapid Ecosystems

The LangChain ecosystem moves quickly, often leading to `ERESOLVE` dependency tree errors during scaffolding. The fix for this environment was setting `legacy-peer-deps=true` in the NPM configuration, allowing the build to proceed without strict version-matching failures that hinder rapid development.

### 2. Hallucination Mitigation through Grounding

Probabilistic models tend to "fill in the blanks" when data is missing (e.g., imagining tech stacks for non-technical roles). To eliminate this, the pipeline was updated to require **Verbatim Evidence Quotes** . By forcing the model to provide a direct string from the source text, we created an automated audit trail that ensures 100% grounding in reality.

### 3. Resource Allocation for Scrapers

Standard Lambda defaults (3s timeout/128MB RAM) are insufficient for the multi-step process of loading external URLs, parsing HTML, and executing LLM extractions. Increasing resources to 512MB and a 30-second timeout provided the necessary headroom for consistent performance.

## Technical Accomplishments

- **Remote Document Loading:** Integrated `CheerioWebBaseLoader` into the serverless environment to fetch live HTML directly from the cloud.
- **Verified Extraction Logic:** Implemented a self-correcting prompt that requires verbatim "Evidence Quotes" for every extracted tech stack, eliminating model hallucinations.
- **Warm-Start Optimization:** Strategically placed the `SecretsManagerClient` initialization outside the main handler to reduce latency across concurrent requests.
- **Schema Enforcement:** Leveraged Zod and `withStructuredOutput` to ensure 100% data integrity for downstream services.

## Tech Stack

- **Language:** [TypeScript](https://www.typescriptlang.org/) (ESM / NodeNext)
- **Cloud Infrastructure:** [AWS Lambda](https://aws.amazon.com/lambda/) (Function URLs), [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- **AI Framework:** [LangChain](https://js.langchain.com/) (Core, Community, OpenAI)
- **LLM Model:** [OpenAI gpt-4o-mini](https://www.google.com/search?q=https://openai.com/index/gpt-4o-mini/)
- **Data Ingestion:** [Cheerio](https://cheerio.js.org/) (Web Scraping)
- **Validation:** [Zod](https://zod.dev/) (Schema Enforcement)
- **Development Tools:** [npm](https://www.npmjs.com/), [esbuild](https://esbuild.github.io/) (Bundling)

## Production Verification

**Endpoint:** `<YOUR_LAMBDA_FUNCTION_URL>`

### Sample Request

```
{
    "targetUrl": "https://jobs.sevendaysvt.com/tech-jobs-vermont/"
}
```

### Sample Verified Output

```
{
  "source": "https://jobs.sevendaysvt.com/tech-jobs-vermont/",
  "data": {
    "postings": [
      {
        "company": "NEK Broadband",
        "role": "Telecommunications Service Technician",
        "tech_stack": ["broadband", "internet service"],
        "evidence": "...ensure high-speed broadband internet service..."
      }
    ]
  }
}
```
