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

The repository implements a **two‑stage hybrid retrieval pipeline** in Python:

1. **Data ingestion** – data_ingestion.py loads raw documents, cleans text, and prepares them for embedding.
2. **Embedding generation** – `llm.py` provides `generate_embeddings` and `embed_query` using a sentence‑transformer model.
3. **Vector store** – vector_store.py creates a PostgreSQL/pgvector store, inserts embeddings, and performs fast similarity search (`search_embeddings`).
4. **Cross‑encoder re‑ranking** – `main.py` loads `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")`; candidate pairs are scored and sorted.
5. **LLM response** – top‑k re‑ranked texts are passed to `generate_response` for final answer generation.

Primary capabilities:

- End‑to‑end async pipeline for ingestion, indexing, and interactive chat.
- Configurable candidate limits (`top_k` for vector search, `top_n` for final LLM context).
- PostgreSQL‑backed persistent vector store with pgvector.

## How It Works

1. **Database preparation** – `await wait_for_db()` and `await setup()` create the pgvector schema.
2. **Document loading** – `get_clean_texts()` reads and cleans raw data.
3. **Embedding & indexing** – `generate_embeddings` creates dense vectors; `insert_embeddings` bulk‑loads them into the vector store.
4. **User query** – `embed_query` encodes the query.
5. **Fast vector retrieval** – `search_embeddings` returns the top‑20 nearest documents by cosine similarity.
6. **Cross‑encoder re‑ranking** – each `(query, doc)` pair is scored with `cross_encoder.predict`; results are sorted descending.
7. **Context selection** – the best 3 documents and their scores are packaged for the LLM.
8. **Answer generation** – `generate_response` produces a natural‑language reply displayed to the user.

## Example Usage

```python
python main.py
```

## Next Steps

- **Batch re‑ranking**: use `cross_encoder.predict` on batches to fully exploit GPU parallelism.
- **Configurable thresholds**: expose `top_k` (vector) and `top_n` (final) as CLI arguments or env variables.
- **Caching**: memoize cross‑encoder scores for frequent queries to reduce latency.
- **Evaluation**: add scripts to benchmark latency vs. precision (e.g., MAP, NDCG).
- **Containerization**: provide a Dockerfile and docker-compose.yml service for PostgreSQL and the app.
- **Model swapping**: allow plug‑in of alternative re‑ranker models (BGE‑Reranker, Cohere) via config.
