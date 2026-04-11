# Week 2: Orchestration & Frameworks (Day 1 & 2)

## Objective

To transition from basic AI prompting to a **production-grade orchestration layer** . This phase focused on standardizing the "handshake" between software and LLMs through strict schema enforcement and implementing **Semantic Intelligence** to clean and deduplicate data conceptually.

## Key Technical Accomplishments

- **Native Structured Output:** Optimized the extraction pipeline by utilizing LangChain's `withStructuredOutput` method, replacing legacy string-parsing logic with native **Zod-backed** schema enforcement.
- **Semantic Intelligence (80/20 Principle):** Focused on the high-impact "20%" of logic— **Semantic Deduplication** . Utilizing `OpenAIEmbeddings` and **Cosine Similarity** , the orchestrator resolves duplicates based on meaning (e.g., catching "Fix bug" vs. "Resolve issue") rather than character matching.
- **Parallel Orchestration:** Engineered a `RunnableLambda` using the native `.batch()` method to handle concurrent LLM calls for multiple text chunks, significantly reducing latency compared to sequential processing.
- **Ditching Hardcoded Strings:** Migrated all system logic to **ChatPromptTemplates** , separating the "Brain" (System Instructions) from the "Data" (User Input) to ensure reusable and maintainable prompt logic.
- **Type-Safe Pipeline:** Leveraged TypeScript and `z.infer` to ensure 100% type safety from the moment the LLM responds to the final deduplicated object, preventing runtime "property undefined" errors.

## Technical Architecture

- **Orchestration:** [LangChain](https://js.langchain.com/) (TypeScript/LCEL) for functional composition.
- **Validation:** [Zod](https://zod.dev/) for strict schema enforcement.
- **Semantic Analysis:** `OpenAIEmbeddings` (text-embedding-3-small) for vector-based similarity checking.
- **Models:** GPT-4o for high-accuracy extraction and structured data generation.
- **Execution:** Node.js 20.x environment via `tsx` for rapid, type-safe development.

## Proof of Work

The system successfully processes overlapping, messy meeting segments and collapses them into a singular, high-confidence "Source of Truth":

| **Sequence** | **Input Chunks**                                       | **AI Response (Stateful Deduplication)**                              |
| ------------ | ------------------------------------------------------ | --------------------------------------------------------------------- |
| **Batch 1**  | "Robert needs to fix the API bug by Friday."           | **Unique Task:**Fix the API bug by Friday.                            |
| **Batch 2**  | "Robert must resolve the issue with the API endpoint." | **Status:**Corrected identified as a duplicate via Vector Similarity. |

## Execution Success (Console Log):

```
🚀 Running Professional Orchestrator...
{
  "summary": "The project is progressing well, but an API bug needs fixing by Friday.",
  "action_items": [
    {
      "task": "Fix the API bug by Friday.",
      "assignee": "Robert",
      "priority": "High"
    }
  ]
}
```
