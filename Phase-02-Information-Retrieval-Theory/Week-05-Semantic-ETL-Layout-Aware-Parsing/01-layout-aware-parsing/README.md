# Part 1 Layout Aware Parsing

## Terms

- Docling / Marker – Deep‑learning libraries for converting PDFs to Markdown while preserving layout.
- High‑Fidelity Markdown – Markdown that reflects visual hierarchy (e.g., bold centered text → # Header).
- Unstructured PDF – PDFs where text is stored as coordinates rather than a logical flow.
- Layout‑Aware Parsing – Recognizing visual cues (whitespace, font size, indentation) to infer semantic roles.
- OCR (Optical Character Recognition) – Converting pixel‑based text into characters, essential for scanned PDFs.

## Key Concepts

- Structure Preservation – Maintaining parent‑child relationships between sections in Markdown.
- PDF as a Tree – Document → Page → Block → Line → Word hierarchy.
- Semantic ETL – Extract‑Transform‑Load driven by meaning and layout, not regex.
- Document Layout Analysis (DLA) – CV task of segmenting a page into semantic regions (tables, footers, captions).

## Implementation Overview

- Primary Capabilities
  - Batch and single‑document processing pipelines (process_batch_documents.py, process_single_document.py).
  - PDF parsing via Docling (core, slim, and IBM models) with optional OCR (rapidocr).
  - Markdown generation that preserves visual hierarchy.
  - Structured output (JSON) for downstream analytics.
  - Dependency‑heavy Python stack (PyTorch, Transformers, OpenCV, etc.).

## How It Works

1. Input – PDF file(s) or scanned images.
1. OCR (optional) – rapidocr extracts text from pixel data.
1. Layout Analysis – Docling segments pages into blocks, classifying them (text, table, figure).
1. Semantic Transformation – Blocks are converted to Markdown, preserving hierarchy and formatting.
1. Output – Markdown files and optional JSON metadata for each document.

## Example Usage

```python
# Activate virtual environment
source venv/Scripts/activate

# Process a single PDF
python process_single_document.py \
  --input "northwind_data/purchase_orders_10248.pdf" \
  --output "northwind_data_md/purchase_orders_10248.md"

# Process all PDFs in a directory
python process_batch_documents.py \
  --input_dir "northwind_data" \
  --output_dir "northwind_data_md"
```

## Next Steps

- Performance Profiling – Measure OCR and Docling inference times; consider GPU acceleration or batch inference.
- Error Handling – Add robust logging for failed OCR or parsing steps.
- Unit Tests – Expand tests to cover edge cases (tables, footers, multi‑column layouts).
- CI Pipeline – Automate linting, type‑checking, and test execution on PRs.

## Performance

Initial implementation processed a single document in **20‑30 seconds**.  
After optimizations, primarily streamlining OCR and Docling inference pipelines, the processing time dropped to **10‑15 seconds**, achieving a **~50 % latency reduction**.
