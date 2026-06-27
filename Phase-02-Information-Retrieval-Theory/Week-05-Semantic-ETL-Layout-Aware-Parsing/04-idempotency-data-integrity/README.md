# Part 4 Idempotency & Data Integrity

## Terms

- **Idempotency** – Running the ingestion pipeline multiple times yields the same final state as a single run.
- **Data Integrity** – Guarantees accuracy and consistency of data throughout its lifecycle.
- **Hashing (MD5/SHA‑256)** – Cryptographic functions that produce a fixed‑size fingerprint from any input; a single‑character change results in a completely different hash.
- **Vector DB (Qdrant)** – Stores and queries high‑dimensional embedding vectors.
- **Deduplication** – Eliminates duplicate data copies.

## Key Concepts

- **Content‑Addressable Storage** – Data is identified by its content hash rather than by a location‑based identifier.
- **Deterministic ID Generation** – Identical content always yields the same ID, enabling idempotent operations.
- **Upsert (Update or Insert)** – Inserts a record if absent or updates it if present; with deterministic IDs this becomes an idempotent “insert”.
- **System Reliability** – The system tolerates retries and failures without creating duplicate or corrupt data.

## Implementation Overview

The repository implements a **Python‑based ingestion pipeline** that:

1. **Normalises** raw markdown (Unicode NFKC, NBSP → space, ASCII‑only).
2. **Splits** text into atomic units (headers, tables, sentences) and **filters** citation‑only fragments such as “Sections … et seq.”.
3. **Generates deterministic IDs** for each unit and chunk using SHA‑256‑derived UUIDs `hash.py`.
4. **Obtains embeddings** from OpenAI’s `text‑embedding‑3‑small` model in a single batch call.
5. **Creates hierarchical chunks** and stores child vectors in **Qdrant** via an upsert operation.
6. **Persists parent texts** in a local SQLite database for fast retrieval.
7. **Deduplicates** vectors by checking existing IDs before upserting, ensuring idempotent storage.

**Primary capabilities**

- Deterministic, content‑addressable chunk IDs.
- Idempotent upsert of embeddings into Qdrant.
- Automatic deduplication of vectors and parent metadata.
- Safe handling of problematic Unicode and citation fragments.
- Simple CLI for conversion, chunking, storage, search, and LLM‑augmented Q&A.

## How It Works

1. **User invokes the CLI** (`python -m cli.main`).
2. **Chunking** (`action_chunk`):
   - Reads the markdown file with tolerant UTF‑8 decoding.
   - Normalises text (`_normalize_text`).
   - Calls `semantic_chunking` → splits, filters citations, embeds, builds hierarchical chunks, assigns deterministic IDs.
   - Optionally saves the hierarchy JSON.
3. **Storing** (`action_store`):
   - Loads hierarchy (or re‑chunks).
   - Extracts all child IDs.
   - Calls `check_existing_ids` → Qdrant scroll returns existing IDs; they are excluded.
   - Calls `store_vectors` → upserts new vectors, stores parent texts in SQLite.
   - Deletes the temporary hierarchy file only if it exists.
4. **Search** (`action_search`):
   - Embeds the query, queries Qdrant for top‑k similar vectors.
   - Retrieves corresponding parent texts from SQLite.
   - Displays results.
5. **Ask** (`action_ask`):
   - Generates a hypothetical answer, searches for relevant chunks, gathers parent contexts, and queries the LLM for a final answer.

## Example Usage

```bash
$ python -m cli.main
=== Semantic Chunking CLI ===
  1. Convert PDF → Markdown
  2. Chunk Markdown file
  3. Create metadata for chunk
  4. Store vectors in Qdrant
  5. Search vector store
  6. Ask a question (search + LLM)
  q. Quit
Select an option: 2
Markdown file to chunk: raw_files_md/QuakerChemicalCorporation-NONCOMPETITIONANDNONSOLICITATIONAGREEMENT.md
Similarity threshold [0.7]:
Created 12 parent chunks.
Save hierarchy to JSON? (leave empty to skip): hierarchy.json
Hierarchy saved to hierarchy.json

# Later, store the vectors
Select an option: 4
Collection name [02-semantic-chunking]:
JSON hierarchy file (leave empty to re‑chunk): hierarchy.json
Vectors stored in collection '02-semantic-chunking'.
Deleted hierarchy file hierarchy.json.
```

## Next Steps

- Add a comprehensive test suite (unit tests for `semantic_chunking`, `check_existing_ids`, and CLI flows).
- Introduce configurable vector size and embedding model via a YAML/JSON config file.
- Implement batch upserts with progress reporting for very large corpora.
- Extend citation filtering to a configurable regex list for broader legal‑text handling.
- Provide optional logging (structured JSON) for auditability and performance metrics (latency, token usage).
