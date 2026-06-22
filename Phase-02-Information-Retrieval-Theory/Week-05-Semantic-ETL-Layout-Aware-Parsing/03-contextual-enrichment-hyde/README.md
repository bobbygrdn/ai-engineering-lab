# Part 3 Contextual Enrichment & HyDE

## Terms

- **HyDE (Hypothetical Document Embeddings)** – A retrieval technique that uses an LLM to generate a synthetic “ideal” answer to a query, which is then used as the embedding for the vector search.
- **Contextual Enrichment** – The process of augmenting raw text chunks with synthetic metadata (summaries, questions) to increase their semantic surface area.
- **Semantic Gap** – The structural and linguistic difference between a user’s query (usually a short question) and the target document (usually a descriptive statement).
- **Metadata** – Structured information attached to a data chunk that can be used for filtering or, in this case, enhancing retrieval.
- **Vector Embedding** – A numerical representation of text that captures its semantic meaning.

## Key Concepts

- **Asymmetric Retrieval** – The principle that queries and documents are fundamentally different. HyDE transforms an asymmetric search (Question → Answer) into a symmetric search (Answer → Answer).
- **Synthetic Data Generation** – Using an LLM to create “fake” but plausible data to bridge the gap between user intent and stored information.
- **Semantic Surface Area** – Adding summaries and hypothetical questions to a chunk provides more “hooks” for a vector search to latch onto, making hard‑to‑find data more discoverable.

## Implementation Overview

- **Chunking** – `semantic_chunking` splits markdown into hierarchical parent/child units, embedding each unit.
- **Enrichment** – `create_metadata` generates a one‑sentence summary and three hypothetical questions per parent; the metadata is propagated to all child units.
- **Storage** – `store_vectors` writes the enriched hierarchy to Qdrant.
- **HyDE** – `generate_hypothetical_answer` creates a synthetic answer to a user query; the answer is used as the search vector.
- **Retrieval** – `search` finds child hits; `get_parent_texts` aggregates parent context; `ask` produces the final answer.

## How It Works

1. **Document Ingestion** – PDF → Markdown → Hierarchical chunking.
2. **Enrichment** – For each parent chunk, generate a summary and 3 questions; attach to all children.
3. **Vectorization** – Embed every unit (parent + children) and store in Qdrant.
4. **Query Handling** –
   1. User asks a question.
   2. `generate_hypothetical_answer` produces a synthetic answer.
   3. Search the vector store with this answer.
   4. Retrieve matching child chunks → aggregate parent text.
   5. Pass context to `ask` for the final LLM answer.

## Example Usage

1. Create a virtual environment using Python to run the program

```bash
python -m venv venv
```

2. Activate the virtual environment in the terminal

```bash
source venv/Scripts/Activate
```

3. Start the program using the `main.py` file

```bash
python -m cli.main
```

4. Use the program to convert PDF files into Markdown files using Hierarchical Parent-Child chunking strategies with attached metadata. Then store those chunks in a vector store to be able to query against.

```bash
# In the CLI choose the action you want to take.
# The prod workflow follows these steps:
# 1(Convert PDF to Markdown) ->
    # 2(Chunk new markdown file) ->
        # 4(Store chunks in vector store) ->
            # 6(Ask questions)
# Option 3 is used to test the chunking functionality on a single chunk
# Option 5 is used to look up specific chunks in the vector store
=== Semantic Chunking CLI ===
  1. Convert PDF → Markdown
  2. Chunk Markdown file
  3. Create metadata for chunk
  4. Store vectors in Qdrant
  5. Search vector store
  6. Ask a question (search + LLM)
  q. Quit
Select an option:
```

## Next Steps

- **Fine‑tune the LLM prompt** for `generate_hypothetical_answer` to reduce hallucination and improve relevance.
- **Cache synthetic answers** to avoid repeated LLM calls for identical queries.
- **Add evaluation metrics** (precision@k, recall@k) to quantify the benefit of HyDE vs. raw queries.
- **Explore multi‑turn retrieval** by chaining HyDE with context‑aware re‑ranking.
- **Automate pipeline**: integrate chunking, enrichment, and storage into a single script or CI job.
