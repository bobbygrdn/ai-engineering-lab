# Part 4 RAGAS Benchmark

## Terms

- RAGAS (RAG Assessment) framework
- Faithfulness
- Answer Relevance
- Context Precision
- Retrieval‑augmented generation (RAG) pipeline
- Ground‑truth context
- Evaluation dataset (questions & reference answers)
- Metric aggregation (mean, median, percentile)

## Key Concepts

- Quantitative evaluation of RAG systems
- Metric definitions and mathematical formulas
- Alignment between generated answer and source documents
- Statistical significance testing for metric comparisons
- Visualization of metric distributions (e.g., bar charts, line plots)

## Implementation Overview

This project implements a **reproducible** Retrieval‑Augmented Generation (RAG) benchmark on a ~10 k‑movie dataset. The core components are:

- **Vector store** – Qdrant (Docker) holds dense embeddings generated with `sentence‑transformers/all‑MiniLM‑L6‑v2`.
- **LLM** – OpenAI `gpt‑4o‑mini` (wrapped in `llm.py`).
- **Metrics** – DeepEval’s three RAG metrics: **Faithfulness**, **Answer Relevancy**, **Contextual Precision**.
- **Output** – Per‑sample CSV (`evaluation_results.csv`) plus an aggregated summary and a ready‑to‑use chart (`evaluation_metrics.png`).

The pipeline is **modular, idempotent, and observable**, supporting **batching** and **throttling** to stay within API rate limits.

**Primary Capabilities:**

- **Automated Test Case Generation** – Dynamically creates query‑answer pairs from the movie dataset.
- **RAG Pipeline Benchmarking** – Evaluates retrieval and generation quality using the three core metrics.
- **Performance Tracking** – Persists evaluation results to CSV for longitudinal analysis.
- **Metric Visualization** – Generates statistical summaries and bar charts to visualize average performance and variance.

## How It Works

1. **Data Indexing** – The pipeline loads `moviesTMBD.csv` and upserts the movie overviews into a Qdrant collection via `vector_store.py`.
2. **Test Set Construction** – `eval.py` builds `LLMTestCase` objects: for each movie it creates a query (e.g., _"What is the plot of [Movie]?"_), retrieves the top‑k passages, and generates an answer using the LLM.
3. **Metric Computation** – DeepEval computes:
   - **Faithfulness** – Does the answer stem solely from the retrieved context?
   - **Answer Relevancy** – How well does the answer address the query?
   - **Contextual Precision** – Signal‑to‑noise ratio of the retrieved documents.
4. **Aggregation & Storage** – Results are processed in configurable chunks (to respect rate limits) and written to `evaluation_results.csv`.
5. **Visualization** – `plot_results.py` reads the CSV, computes mean ± standard‑deviation for each metric, and saves a bar chart (`evaluation_metrics.png`) with error bars.

## Example Usage

### Setup (once)

```bash
# After you clone the repo, standup a venv and install dependencies
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Start Qdrant (Docker)
docker compose up -d
```

### Run the benchmark

```bash
# Adjust these argumetns as necessary based on hardware and api limitations
python pipeline.py --samples 100 --concurrency 10 --throttle 4.0
```

The script will:

- Ensure the Qdrant collection exists and upsert embeddings.
- Sample the requested number of movies.
- Build or reuse cached test cases.
- Evaluate the three DeepEval metrics in chunks.
- Write per‑sample results to `evaluation_results.csv`.

### Visualize results

```bash
python plot_results.py
```

This generates `evaluation_metrics.png`, a bar chart showing the mean ± standard‑deviation for Faithfulness, Answer Relevancy, and Contextual Precision.

## Next Steps

- **Hybrid Search Implementation** – Integrate BM25 keyword search with vector search to improve `Contextual Precision`.
- **Reranking Stage** – Introduce a Cross‑Encoder reranker after the initial retrieval to filter out irrelevant documents.
- **Hyperparameter Tuning** – Experiment with different `top_k` values and chunking strategies to optimize the trade‑off between Faithfulness and Answer Relevancy.
- **Advanced Statistical Analysis** – Implement t‑tests or ANOVA in `plot_results.py` to determine if performance gains between different pipeline versions are statistically significant.
