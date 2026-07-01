# Part 1 Hybrid Search

## Terms

- BM25
- Vector search / embeddings
- Reciprocal Rank Fusion (RRF)
- Rank, reciprocal rank
- Hybrid search
- Specific term problem
- Retrieval‑augmented generation (RAG)

## Key Concepts

- Probabilistic keyword matching vs. semantic similarity
- Ranking fusion and score normalization
- Handling sparse vs. dense signals
- Importance of recall for specific identifiers
- Weighted averaging of reciprocal ranks

## Implementation Overview

The script implements an end‑to‑end hybrid retrieval pipeline:

1. **Dataset loading** – reads startups_demo.json.
2. **Deterministic IDs** – `uuid5` based on name | description | city ensures idempotent uploads.
3. **Qdrant collection** – creates a hybrid collection with a dense 384‑dim vector (cosine) and a sparse BM25 index (`Modifier.IDF`).
4. **Dense encoding** – uses `sentence‑transformers/all‑MiniLM‑L6‑v2` to embed all documents.
5. **Idempotent upload** – only new points are uploaded via `client.upload_points`.
6. **Hybrid query** – `Prefetch` runs an on‑the‑fly BM25 query and a dense vector query; results are fused with **Reciprocal Rank Fusion (RRF)**.
7. **Result logging** – each run is appended to hybrid_search.log as a JSON‑Lines entry (run‑id, timestamp, query, top‑k, results).

## How It Works

1. **Load records** → build a single text field per record.
2. **Generate stable UUIDs** → `deterministic_id(record)`.
3. **Create collection** (if absent) with:
   - `vectors_config["dense"]` → `VectorParams(size=384, distance=COSINE)`.
   - `sparse_vectors_config["sparse"]` → `SparseVectorParams(modifier=IDF)`.
4. **Encode all texts** → `dense_vectors = model.encode(texts)`.
5. **Scroll existing IDs** → `client.scroll` paginates through the collection.
6. **Upload only new points** → `models.PointStruct(id, vector={"dense": …}, payload=doc)`.
7. **Hybrid search** (`hybrid_search(query, top_k)`):
   - Encode query → dense vector.
   - `Prefetch`:
     - BM25 on‑the‑fly (`models.Document(text=query, model="Qdrant/bm25")`).
     - Dense vector query.
   - `FusionQuery(fusion=Fusion.RRF)` combines the two rank lists; RRF assigns scores `1/(k+rank)` (k=1), yielding the identical numeric pattern `[0.5, 0.33…, 0.25, …]` for every query while the ordering reflects the underlying relevance.
8. **Log the run** → JSON‑Lines with UTC timestamp and query.

## Example Usage

```python
from main import hybrid_search, write_run_log

query = "web-based startups in Chicago"
top_k = 10

# Execute hybrid retrieval
results = hybrid_search(query, top_k=top_k)

# Persist the run
write_run_log(query, top_k, results)

# Print ranked results
for pt in results:
    print(f"{pt.id}\t{pt.score:.3f}\t{pt.payload['text']}")
```

## Next Steps

- **Add payload filters** (e.g., `payload["city"] == "Chicago"`) to guarantee location‑only candidates before fusion.
- **Record model & collection metadata** (model version, Qdrant schema) in the log for full reproducibility.
- **Experiment with alternative fusion** such as `WeightedSum` or `CombSUM` to obtain query‑specific similarity scores instead of rank‑only RRF values.
- **Benchmark recall vs. precision** for specific‑term queries to quantify the “specific term problem” and tune BM25 parameters (k1, b).
- **Integrate with a RAG pipeline**: feed the top‑k retrieved texts into a language model prompt for answer generation.
