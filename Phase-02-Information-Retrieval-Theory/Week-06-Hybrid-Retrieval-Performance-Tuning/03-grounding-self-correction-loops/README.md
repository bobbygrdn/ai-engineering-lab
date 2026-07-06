# Part 3 Grounding & Self-Correction Loops

## Terms

- LLM (Large Language Model)
- Verification Chain
- Self‑Correction Loop
- Hallucination Mitigation
- Internal Critic
- Prompt Engineering
- Retrieval‑Augmented Generation (RAG)
- Fact‑Checking Prompt
- Confidence Scoring
- “I don’t know” fallback

## Key Concepts

- Prompt the model to generate an answer and a separate evidence request.
- Retrieve or locate supporting sentences from the provided context.
- Compare claimed facts with retrieved evidence to assess validity.
- Use a confidence threshold to decide whether to accept the answer or return “I don’t know”.
- Iteratively refine the answer based on the critic’s feedback (self‑consistency).
- Design prompts that encourage the model to admit uncertainty rather than guess.

## Implementation Overview

The repository implements a **Verification Chain** for Retrieval‑Augmented Generation (RAG):

1. User query → embed → vector search → top‑k candidates.
2. Cross‑encoder re‑ranks candidates; best three are passed as context.
3. `generate_response` creates an answer using the context.
4. `critique_response` (Internal Critic) receives the answer and the same context, returns a structured list of claims with `supported`, `evidence`, and `confidence`.
5. The chat loop displays the answer only if **all** claim confidences ≥ 0.8; otherwise it falls back to “I don’t know”.

## How It Works

1. **Embed query** – `embed_query` produces a dense vector.
2. **Vector retrieval** – `search_embeddings` returns up to 20 documents.
3. **Re‑ranking** – Cross‑encoder scores each (query, doc) pair; top 3 are selected.
4. **Answer generation** – `generate_response` builds a prompt with the three results and asks the LLM for a concise answer.
5. **Critique** – `critique_response` sends the answer and the same context to the model with a fact‑checking prompt, parsing the output into `ClaimResult` objects.
6. **Decision** – The chat loop checks each claim’s `confidence`; if any < 0.8, it returns “I don’t know”, otherwise it prints the answer and the supporting evidence.

## Example Usage

```python
# Inside main.py
query = "What is RAG?"
query_emb = embed_query(query)
candidates = await search_embeddings(query_emb, top_k=20)

# Re‑rank and select top‑3
pairs = [(query, doc) for doc, _ in candidates]
scores = get_cross_encoder().predict(pairs)
ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
top_texts = [doc for (doc, _), _ in ranked[:3]]
top_scores = [score for _, score in ranked[:3]]

# Generate and verify answer
llm_reply = generate_response(query, list(zip(top_texts, top_scores)))
critique = critique_response(llm_reply, list(zip(top_texts, top_scores)))

if any(claim.confidence < 0.8 for claim in critique.claims):
    print("Bot: I don't know. No supporting context available.")
else:
    print(f"Bot: {llm_reply}")
    for claim in critique.claims:
        print(f"- Claim: {claim.claim}")
        print(f"  Supported: {claim.supported}")
        print(f"  Evidence: {claim.evidence}")
        print(f"  Confidence: {claim.confidence:.2f}")
```

## Next Steps

- **Token‑budget handling:** truncate or summarize each retrieved passage to stay within the model’s context window.
- **Model selection:** use a larger model (e.g., `gpt‑4o`) for the critique step to improve fact‑checking accuracy.
- **Multi‑claim parsing:** extend `CritiqueResponse` to include claim identifiers for easier downstream processing.
- **Configurable threshold:** expose the confidence cutoff (default 0.8) as a command‑line or environment variable.
- **Batch critique:** parallelize critique for multiple user queries to improve throughput.
