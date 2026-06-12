# Part 2 Semantic Chunking & Parent-Child Relationships

## Terms

- **Semantic Splitter**: A text splitting strategy that determines boundaries based on the meaning of the content rather than fixed character or token counts.
- **Embedding Model**: A model (e.g., OpenAI `text-embedding-3-small`) that converts text into high-dimensional vectors representing semantic meaning.
- **Topic Shift**: The point in a document where the semantic distance between consecutive segments exceeds a certain threshold, indicating a change in subject.
- **Parent-Child Retrieval**: A hierarchical indexing pattern where small segments (children) are used for retrieval, but larger segments (parents) are provided to the LLM.
- **Child Chunks**: Granular pieces of text (e.g., single sentences) optimized for high-precision vector search.
- **Parent Chunks**: Larger blocks of text (e.g., paragraphs or sections) that provide the necessary context for the LLM to generate an accurate answer.

## Key Concepts

- **Cosine Similarity**: The mathematical measure used to determine how similar two embedding vectors are.
- **Distance Thresholding**: The process of setting a "breakpoint" value; if the similarity between two chunks drops below this value, a new chunk is started.
- **Precision vs. Recall Trade-off**: Child chunks increase precision (finding the exact sentence), while parent chunks increase recall/context (providing the surrounding meaning).
- **Hierarchical Indexing**: The architectural mapping (usually via a `parent_id` in a database) that links a child chunk back to its originating parent.

## Implementation Overview

This project implements a **Semantic ETL pipeline** designed to solve the "lost in the middle" and "lack of context" problems common in standard RAG systems. By combining a **Semantic Splitter** with a **Parent-Child Retrieval** architecture, the system ensures that search is performed on highly specific atomic units (Children) while the LLM receives the full semantic block (Parent) for generation.

**Primary Capabilities:**

- **Layout-Aware Parsing**: Converts PDFs to high-fidelity Markdown using `docling`, preserving tables and headers.
- **Meaning-Based Splitting**: Uses cosine similarity between sentence embeddings to detect topic shifts, avoiding arbitrary character limits.
- **Hybrid Chunking**: Preserves structural boundaries (headers/tables) while applying semantic splitting to prose.
- **Hierarchical Storage**: Dual-database approach using **Qdrant** for vector search (Children) and **SQLite** for document storage (Parents).
- **Fragment Merging**: Intelligent sentence tokenization that merges meaningless fragments (e.g., list markers like "1.") with subsequent text to maintain embedding quality.

## How It Works

1. **PDF $\rightarrow$ Markdown**: The `parse_pdf_to_markdown` utility uses `docling` to transform raw PDFs into structured Markdown files.
2. **Atomic Unit Extraction**: `split_into_units` breaks the Markdown into headers, tables, and sentences. It applies a merging loop to ensure short fragments are combined with the next meaningful sentence.
3. **Semantic Boundary Detection**: `semantic_chunking` calculates the cosine similarity between the embeddings of consecutive units. If the similarity falls below a user-defined threshold, a boundary is created, forming a new **Parent Chunk**.
4. **Hierarchical Indexing**:
   - **Children**: Each atomic unit within a parent is embedded via `text-embedding-3-small` and stored in **Qdrant** with a reference to its `parent_id`.
   - **Parents**: The full text of the parent chunk is stored in a **SQLite** database (parents.db) keyed by `parent_id`.
5. **Retrieval & Generation**:
   - A query is embedded and searched against Qdrant to find the top-k most similar **Child Chunks**.
   - The system resolves the `parent_id`s of these hits to fetch the corresponding **Parent Chunks** from SQLite.
   - These parents are injected into a prompt and sent to `gpt-4o-mini` to generate a grounded response.

## Example Usage

The system is orchestrated via an interactive CLI.

```bash
# Run the interactive pipeline
python -m cli.main
```

**CLI Workflow:**

1. **Option 1**: Convert PDF to Markdown.
2. **Option 2**: Chunk Markdown (defines the semantic boundaries).
3. **Option 3**: Store vectors (upserts to Qdrant and SQLite).
4. **Option 4**: Search (finds child hits and resolves parents).
5. **Option 5**: Ask (end-to-end RAG: Search $\rightarrow$ Resolve $\rightarrow$ LLM).

## Next Steps

- **Dynamic Thresholding**: Implement an adaptive similarity threshold that adjusts based on the document's overall semantic variance.
- **Re-ranking Stage**: Introduce a Cross-Encoder re-ranker after the initial child retrieval to further refine the parent selection.
- **Multi-modal Parsing**: Extend the `docling` integration to handle images and charts within PDFs as separate semantic units.
- **Evaluation Framework**: Implement a RAGAS or TruLens pipeline to quantitatively compare Parent-Child retrieval against standard recursive character splitting.
