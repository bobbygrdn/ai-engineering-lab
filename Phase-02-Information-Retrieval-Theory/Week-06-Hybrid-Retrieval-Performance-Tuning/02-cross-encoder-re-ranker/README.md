# Part 2 Cross-Encoder Re-ranker

## Terms

- Cross‑Encoder
- Re‑ranker model (e.g., BGE‑Reranker, Cohere)
- Vector search / dense retrieval
- Embedding
- Latency vs. precision trade‑off
- Multi‑stage retrieval pipeline
- Similarity scoring
- Top‑k / top‑n filtering

## Key Concepts

- Two‑stage retrieval: fast vector search narrows candidates, then a slower cross‑encoder re‑ranks for accuracy.
- Precision vs. latency: higher‑quality scoring incurs more compute time; balance by limiting candidates passed to the re‑ranker.
- Cross‑encoder scoring: concatenates query and document, passes through a transformer to produce a relevance logit.
- Batch processing: re‑ranker can score multiple query‑doc pairs in parallel to mitigate latency.

## Implementation Overview

The project implements a two‑stage retrieval pipeline:

- **Fast vector search** retrieves the top‑k candidate documents using dense embeddings.
- **Cross‑encoder re‑ranker** scores each query‑document pair with a transformer model (`cross-encoder/ms-marco-MiniLM-L12-v2`).
- The highest‑scoring documents are fed to an LLM to generate the final answer.

Primary capabilities identified:

1. Asynchronous resource initialization (database, model caching).
2. Offline‑first model loading with HuggingFace caching.
3. Vector‑based similarity search via `vector_store`.
4. Cross‑encoder relevance scoring.
5. LLM response generation based on re‑ranked context.

## How It Works

1. User inputs a query via the console.
2. `embed_query` creates an embedding for the query.
3. `search_embeddings` performs a fast vector search, returning the top‑20 candidate documents.
4. Query‑document pairs are built and passed to the cached `CrossEncoder` model for scoring.
5. Candidates are sorted by relevance scores; the top‑3 are selected.
6. `generate_response` calls the LLM with the top‑3 texts and their scores to produce the final answer, which is printed to the console.

## Data Ingestion Pipeline

The ingestion process prepares raw Slack messages for vector storage:

1. **Load raw data** – `data_ingestion.py` reads `data/slack_messages.parquet` into a DataFrame.
2. **Clean text** – `clean_text` normalises Unicode, removes whitespace, lower‑cases, and strips non‑ASCII characters.
3. **Generate embeddings** – `ingest_data.py` calls `generate_embeddings` from `llm.py` on the cleaned texts.
4. **Insert into vector store** – embeddings and their corresponding texts are bulk‑inserted via `insert_embeddings`.
5. **Deduplication** – existing contents are fetched with `get_existing_contents` to avoid duplicate inserts.

Running `python ingest_data.py` populates the PostgreSQL vector database, ready for the retrieval stage.

## Example Usage

```python
# Run the interactive chatbot
python main.py
```

Typical console interaction:

```
=== How may I help you today? (type 'exit' to quit) ===
You: What are the health benefits of green tea?
Bot: Green tea contains antioxidants ... (LLM answer)
```

## Next Steps

- Enable GPU acceleration for the cross‑encoder to reduce latency.
- Tune `top_k` and the number of re‑ranked candidates based on workload characteristics.
- Add batch inference support to score larger candidate sets efficiently.
- Expose the pipeline as a REST API for external integration.
- Incorporate evaluation metrics (e.g., MAP, latency) to monitor precision‑latency trade‑offs.
