# Part 3 Metadata Gate

## Terms

- Metadata filtering
- Boolean filters
- Structured search
- Unstructured search
- Vector drift
- User tier
- Date range filter
- Retrieval gate
- Relevant subset
- Query planner
- Document metadata

## Key Concepts

- Retrieval should be constrained before ranking, not after.
- Metadata acts like a hard eligibility layer: a document must qualify structurally before semantic similarity matters.
- Boolean filters reduce false positives by removing documents that are obviously out of scope.
- Date and tier are examples of high-signal metadata because they encode freshness and audience.
- “Structured + unstructured” search means combining exact constraints with fuzzy semantic matching.
- The danger is not just irrelevant results, but stale results that look semantically plausible.
- Good retrieval systems separate “can this document be considered?” from “how similar is it?”

## Implementation Overview

- Stack: Python 3.x using `python-dotenv` and the `pinecone` Python client (see `requirements.txt`).
- Entry points:
  - Retrieval CLI: `query_with_filters.py`
  - Index creation: `create_pinecone_index.py`
  - Data ingestion/upsert: `upsert_cleaned_data_to_pinecone.py`
- Primary capabilities:
  - Hard metadata gating using structured Boolean-style filter JSON merged with optional date-range constraints.
  - Type normalization at ingest (ints, booleans, epoch conversion) to make metadata filters reliable.
  - SDK-response normalization to handle different Pinecone client shapes and return consistent `id`, `score`, `fields`.
  - Audit support: optional raw JSON and CSV dumps when queries return no hits or for offline analysis.

## How It Works

1. Load environment variables from a `.env` file: `PINECONE_API_KEY`, `INDEX_NAME`, and optional `NAMESPACE`.
2. Ingestion: read cleaned CSV rows, normalize scalar metadata (`int`, boolean, `date_ts`), and upsert records into Pinecone with `chunk_text` as the embedding source. See `upsert_cleaned_data_to_pinecone.py`.
3. Index creation maps an embedding model to the `chunk_text` field so that embedding generation and upserts are aligned. See `create_pinecone_index.py`.
4. Querying: the CLI composes a structured `filter` (from `--filter-json`) and merges a date-range clause if provided (`--date-from` / `--date-to`). This filter is passed to Pinecone together with the semantic query so that only eligible documents are considered for scoring. See `query_with_filters.py`.
5. Results are normalized and printed. When zero hits are returned, raw responses can be dumped for debugging to inspect whether the filter removed expected candidates or whether vector drift occurred.

## Example Usage

- Constrained semantic query (Boolean filter + date range):

```bash
python query_with_filters.py \
	--query "How do I cancel my subscription?" \
	--filter-json '{"ticket_type":{"$eq":"Account Management"},"ticket_priority":{"$eq":"High"}}' \
	--date-from 2024-01-01 \
	--date-to 2024-12-31 \
	--topk 5 \
	--fields ticket_type,ticket_priority,chunk_text \
	--dump-json debug_response.json
```

- Upsert cleaned CSV into Pinecone (uses `INDEX_NAME` and `PINECONE_API_KEY` from env):

```bash
python upsert_cleaned_data_to_pinecone.py
```

## Design Rationale

- Treat metadata as an eligibility gate. Filters should reduce the candidate set before semantic scoring to lower false positives and surface fresher, tier-appropriate content.
- Use typed metadata (ints, booleans, epoch timestamps) to ensure filter comparisons behave predictably across SDKs and response shapes.
- Keep auditing and observability (raw dumps, CSV exports) so you can detect vector drift when semantically plausible but incorrect results appear.

## Next Steps & Recommendations

- Add a formal metadata schema file and enforce it at ingest time (e.g., `metadata_schema.json`).
- Add `user_tier` to ingestion and example queries to demonstrate access control by tier.
- Implement a lightweight `query_planner.py` that validates filters, compiles safe filters from user inputs, and returns candidate counts before executing full semantic queries.
- Add unit tests that assert filters exclude out-of-scope documents prior to similarity ranking (extend `test_query_with_filters.py`).
- Create periodic vector-drift checks: run a set of canned queries and assert expected top-k ids remain stable within tolerance.
