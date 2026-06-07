# Part 4 Manual Context Injection

## Terms

- **System prompt**: Initial instructions given to the LLM to define its role and behavior.
- **Retrieved results**: Chunks of information fetched from a knowledge base (e.g., Pinecone) based on a user query.
- **Context window**: The maximum number of tokens an LLM can process in a single input.
- **Token budgeting**: The process of allocating and managing tokens within the context window for various prompt components.
- **Token counting**: Measuring the number of tokens in a given text string.
- **Sliding window / truncation**: Strategies for fitting large amounts of text into a fixed context window, often by selectively removing parts.
- **Neighborhood selection**: Grouping contiguous or related document chunks that are semantically close to a retrieved hit.
- **Relevance ranking**: Ordering retrieved information based on its perceived importance to the user's query.
- **RAG (Retrieval Augmented Generation), but non-framework**: Implementing RAG principles manually without relying on high-level RAG frameworks.
- **Prompt stuffing**: The practice of adding relevant context or data into the LLM's prompt.
- **Deduplication**: Removing redundant or identical pieces of information from retrieved results.
- **Chunking**: Breaking down larger documents into smaller, manageable segments (chunks) for easier processing and retrieval.
- **Headroom / reserve budget**: Tokens reserved within the context window for the LLM's reasoning and response generation, ensuring it has enough space to formulate an answer.

## Key Concepts

- **Deterministic context assembly**: You control exactly what enters the model. The process ensures that given the same inputs, the same context is always constructed.
- **Budgeted allocation**: Every token consumed by retrieval reduces room for reasoning and generation. Efficient allocation is crucial to maximize useful information.
- **Information hierarchy**: Not all retrieved text is equally valuable; prioritize what is most likely to change the answer.
- **Fail-closed behavior**: If the budget is too small, degrade gracefully by dropping lower-value neighborhoods, not by overflowing. This prevents prompt truncation by the LLM API.
- **Reproducible selection**: The same query and retrieval set should yield the same packed prompt, ensuring consistency in LLM behavior.
- **Proximity matters**: Nearby chunks around a relevant hit often carry more value than distant neighbors, suggesting the importance of "neighborhoods."
- **Tradeoff management**: Maximize useful evidence while preserving enough room for the model to respond. This involves balancing the amount of retrieved context against the LLM's reasoning capacity.

## Implementation Overview

This project provides a comprehensive solution for building context-aware prompts for Large Language Models (LLMs) by integrating a data processing pipeline with a vector database (Pinecone) and intelligent context packing algorithms. The goal is to maximize the utility of retrieved information within the LLM's context window while ensuring deterministic and reproducible prompt assembly.

### Components:

1. **Data Ingestion & Cleaning (`clean_customer_support_tickets.py`):**
   - Reads raw CSV data of customer support tickets.
   - Performs normalization, validation, and enrichment (e.g., `age_band`, `issue_family`, `issue_severity`).
   - Splits large text fields (`Ticket Subject`, `Ticket Description`) into smaller, manageable `chunks` suitable for embedding and retrieval.
   - Handles data quality by quarantining invalid rows.

2. **Vector Index Management (`create_pinecone_index.py`):**
   - Initializes a Pinecone vector index, if one does not exist, configured for text embedding.

3. **Data Upsert to Vector Database (`upsert_cleaned_data_to_pinecone.py`):**
   - Ingests the cleaned and chunked data into the Pinecone index. Each chunk is stored as a vector with associated metadata, enabling filtered and semantic search.

4. **Retrieval & Filtering (`query_with_filters.py`):**
   - Executes semantic search queries against the Pinecone index.
   - Supports advanced metadata filtering (e.g., `ticket_type`, `date_ts` range) to narrow down relevant results.
   - Normalizes and structures the retrieved matches.

5. **Context Packing & Token Budgeting (`tokens.py`, `packer.py`):**
   - `tokens.py`: Provides utilities for accurate token counting using `tiktoken`.
   - `packer.py`: Implements logic to `group_neighborhoods` (contiguous chunks from the same document) and `pack_neighborhoods` (selecting and potentially trimming neighborhoods based on relevance score density) to fit within a specified token budget.

6. **Prompt Composition (`prompt_composer.py`):**
   - Constructs the final LLM prompt by combining a base `SYSTEM_INSTRUCTIONS`, a directive for answering, and the dynamically selected retrieved evidence, clearly citing sources.

7. **Adapter & Orchestration (`adapter.py`):**
   - Serves as the main entry point for the end-to-end process.
   - Orchestrates querying the vector database, applying token budgeting, packing retrieved content, and composing the final prompt.
   - Optionally invokes an OpenAI model to generate a response based on the assembled context.

## How It Works

The system operates in two main phases: **Ingestion** and **Query/Context Assembly**.

### Ingestion Phase:

1. **Data Loading & Cleaning**:
   - `clean_customer_support_tickets.py` reads `customer_support_tickets.csv` from the `data/raw` directory.
   - It cleans, normalizes, and enriches each ticket, deriving new fields like `age_band`, `issue_family`, and `issue_severity`.
   - Ticket descriptions and subjects are split into smaller, overlapping chunks (e.g., using `CHUNK_WORD_LIMIT` in `clean_customer_support_tickets.py`) to optimize for embedding and retrieval granularity.
   - Valid processed data is written to `data/clean/customer_support_tickets.csv`, while invalid rows are moved to `data/quarantine/customer_support_tickets.csv`.
2. **Pinecone Index Setup**:
   - `create_pinecone_index.py` ensures a Pinecone index (named by `INDEX_NAME` in `.env`) exists. It's configured to use a specific embedding model (`llama-text-embed-v2`) and to map `chunk_text` for embedding.
3. **Data Upsert**:
   - `upsert_cleaned_data_to_pinecone.py` reads the cleaned, chunked data.
   - It transforms each chunk into a record suitable for Pinecone, including metadata for filtering.
   - These records are then upserted in batches to the Pinecone index, within a specified `NAMESPACE`.

### Query & Context Assembly Phase:

1. **User Query & Initial Retrieval**:
   - The `adapter.py` script receives a user `query` and optional `filter_obj` (e.g., `{"ticket_type": {"$eq": "Billing inquiry"}}`).
   - `adapter.py` calls `query_index` from `query_with_filters.py` to perform a semantic search against the Pinecone index. This retrieves `top_k` most relevant chunks, potentially filtered by metadata.
2. **Token Budget Calculation**:
   - The `adapter.py` calculates the `budget_for_retrieved` tokens. This is `MODEL_CONTEXT_LIMIT` (e.g., 4096) minus `RESPONSE_RESERVE` (e.g., 512) and the token overhead of the `SYSTEM_INSTRUCTIONS` and the user's `query`. `tokens.py` is used for accurate token counting.
3. **Neighborhood Grouping**:
   - Retrieved chunks are passed to `group_neighborhoods` in `packer.py`. This function groups contiguous chunks belonging to the same document into "neighborhoods," preserving context around relevant hits. Each neighborhood gets a combined score and token count.
4. **Context Packing**:
   - The grouped `neighborhoods` are then passed to `pack_neighborhoods` in `packer.py`. This is a critical step for token budgeting:
     - Neighborhoods are sorted by "score density" (score / token_count) and deterministic tie-breakers.
     - The function iteratively selects neighborhoods until the `budget_for_retrieved` is met.
     - If a large neighborhood doesn't fit entirely, `trim_neighborhood_to_fit` attempts to select its highest-scoring chunks to fit the remaining budget.
5. **Prompt Composition**:
   - The `compose_system_prompt` function from `prompt_composer.py` takes the `SYSTEM_INSTRUCTIONS` and the `selected` (packed) neighborhoods.
   - It constructs a final system prompt, clearly separating system directives from retrieved evidence, and formatting each evidence chunk with its `doc_id` and `chunk_id`.
6. **LLM Invocation (Optional)**:
   - If the `--invoke-model` flag is used, `adapter.py` sends the composed `system_prompt` and the original user `query` to an OpenAI LLM (default `gpt-4o-mini`).
   - The LLM generates a response, citing evidence from the provided context.

## Getting Started

### Prerequisites

- Python 3.8+
- Pip.
- An OpenAI API key.
- A Pinecone API key and a configured Pinecone index.

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/bobbygrdn/ai-engineering-lab.git
   cd Phase-02-Information-Retrieval-Theory/Week-04-Geometry-of-Meaning-Indexing/04-manual-context-injection
   ```

2. **Set up environment variables:**
   Rename `.env.template` to `.env` and fill in your API keys and Pinecone index details:

   ```
   PINECONE_API_KEY=your-pinecone-api-key
   INDEX_NAME=your-pinecone-index-name
   NAMESPACE=your-pinecone-namespace
   OPENAI_API_KEY=your-openai-api-key
   ```

3. **Install dependencies:**

   ```python
   pip install -r requirement.txt
   ```

### Data Ingestion

1. **Clean and chunk the raw data:**

   ```bash
   python clean_customer_support_tickets.py
   ```

   This will process `data/raw/customer_support_tickets.csv`, creating `data/clean/customer_support_tickets.csv` and `data/quarantine/customer_support_tickets.csv`.

2. **Create the Pinecone index:**

   ```bash
   python create_pinecone_index.py
   ```

   This will create a Pinecone index if it doesn't already exist, using the `INDEX_NAME` from your `.env` file.

3. **Upsert cleaned data to Pinecone:**

   ```bash
   python upsert_cleaned_data_to_pinecone.py
   ```

   This will ingest the data from `data/clean/customer_support_tickets.csv` into your Pinecone index.

## Example Usage

### Querying and Context Building

To query the Pinecone index, build a contextual prompt, and optionally invoke an LLM:

```bash
python adapter.py --query "Why was the invoice wrong?" --topk 5 --invoke-model
```

**Parameters:**

- `--query`: The natural language query for the LLM.
- `--topk`: Number of top relevant chunks to retrieve from Pinecone.
- `--namespace`: The Pinecone namespace to query (defaults to `__default__` if not specified).
- `--filter-json`: Optional JSON string for metadata filtering (e.g., `'{"ticket_type": {"$eq": "Billing inquiry"}}'`).
- `--model`: Optional OpenAI model name (e.g., `gpt-4`). Defaults to `gpt-4o-mini`.
- `--write-prompt`: Path to write the composed system prompt to a file.
- `--invoke-model`: Flag to actually call the OpenAI model after building the prompt.

### Standalone Querying (for debugging/inspection)

You can also use `query_with_filters.py` directly to inspect search results:

```bash
python query_with_filters.py -q "payment issue" -f '{"ticket_priority": {"$eq": "critical"}}' -k 3 -C results.csv
```

**Parameters:**

- `-q`: Query string.
- `-f`: Filter JSON.
- `-k`: Top-k results.
- `-n`: Namespace.
- `-F`: Comma-separated list of fields to return.
- `-D`: Path to dump raw JSON response if no hits.
- `-C`: Path to dump normalized matches to CSV.
- `--date-from`, `--date-to`: Date range filters for `date_ts`.

## Next Steps

- **Dynamic Retrieval Integration:** Enhance `simulate_retrieval()` in `run_demo.py` to integrate with a real-time retrieval system, such as a full Pinecone implementation, for dynamic data fetching.
- **Advanced Packing Algorithms:** Explore and implement more sophisticated packing algorithms that consider factors like semantic diversity, redundancy checks, or varying scoring mechanisms beyond simple relevance to optimize context utility.
- **Performance Monitoring:** Integrate comprehensive logging and monitoring tools to track key performance metrics, including the latency of prompt composition, token usage per query, and the effectiveness of different retrieval and packing strategies.
- **User Interface (UI):** Develop an interactive user interface to visualize the context window, real-time token usage, and the impact of adjustments to retrieval and packing parameters on the final prompt.
- **Error Handling and Edge Cases:** Improve error handling for scenarios such as empty retrieval results, situations where the token budget is too small to accommodate any meaningful context, or handling malformed data chunks robustly.
- **Integration with Diverse LLM APIs:** Extend the `call_model` function in `adapter.py` to support various LLM providers (e.g., Google Gemini, Anthropic Claude) to test the portability and impact of the generated context across different models.
- **Automated Testing Enhancement:** Expand the existing test suites (`test_adapter.py`, `test_query_with_filters.py`) with more extensive unit and integration tests, particularly for the complex logic within the `packer.py` and `prompt_composer.py` modules, ensuring robustness and correctness.
- **Pre-computed Embeddings:** For large datasets, consider pre-computing and storing embeddings for all chunks to reduce latency during retrieval.
- **Adaptive Budgeting:** Implement dynamic adjustment of `RESPONSE_RESERVE` based on expected response length or query type.
