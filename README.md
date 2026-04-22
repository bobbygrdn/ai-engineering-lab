# 12-Week AI Engineering Intensive

This repository tracks my transition from a Full Stack Developer into AI Engineering.
The goal is to move beyond simple chat interfaces and master the architecture, deployment, and orchestration of LLM-powered applications.

## 🚀 The Roadmap

- Phase 1 - The Control Layer
  - **_Week 1: Type-Safety & Tokenomics_**
  - **Week 2: State & Memory Architecture**
  - **Week 3: Agentic Reasoning & Tool Use**
- Phase 2 - Information Retrieval Theory
  - **Week 4: The Geometry of Meaning & Indexing**
  - **Week 5: Semantic ETL & Layout-Aware Parsing**
  - **Week 6: Hybrid Retrieval & Performance Tuning**
- Phase 3 - Model Adaptation & Local Inference
  - **Week 7: Local Models & Hugging Face**
  - **Week 8: Data Curation & Synthetic Generation**
  - **Week 9: QLoRA & Weight Adaptation**
- Phase 4 - Systems Reliability & MLOps
  - **Week 10: AI Containerization & Portability**
  - **Week 11: Enterprise Cloud AI & MLOps**
  - **Week 12: Quality Assurance & Technical Authority**

## 🛠️ Tech Stack

- **Languages:**
- **Runtime:**
- **AI:**
- **Cloud:**
- **Tooling:**

## 📚 Phase 01: The Control Layer

High-level focus areas covered in `Phase-01-The-Control-layer/`:

- **Schema Enforcement & Type-Safety:** Implementing strict Pydantic-driven validation to convert probabilistic LLM outputs into deterministic software objects, including automated retry logic for self-correction.
- **Intelligent Model Routing:** Designing a multi-tier logic gate to optimize the "Intelligence-per-Dollar" ratio, routing requests between Small Language Models (SLMs) and Frontier models based on intent complexity.
- **Cognitive Memory Architecture:** Engineering a dual-layer memory stack that manages working context through **Attention-Aware Hydration** (solving "Lost in the Middle") and long-term persistence via recursive summarization.
- **Agentic Reasoning Patterns:** Building manual **ReAct (Reason + Act)** loops and multi-agent **Reflection (Critic)** workflows to enable autonomous task execution without reliance on "black-box" frameworks.
- **Defensive AI Engineering:** Implementing structural **Data/Instruction Firewalls** using delimited context framing to sanitize untrusted user input and prevent indirect prompt injection attacks.

## 📚 Phase 02: Information Retrieval Theory (RAG)

High-level focus areas covered in `Phase-02-Information-Retrieval-Theory/`:

- **Information Retrieval (IR) Theory:** Mastering the geometry of high-dimensional vector spaces, including the trade-offs between **HNSW (Hierarchical Navigable Small Worlds)** and flat indexing for production-scale semantic search.
- **Semantic Data Engineering:** Implementing **Layout-Aware Parsing** to convert unstructured documents into hierarchical Markdown, ensuring structural integrity (headers, tables, lists) is preserved for model consumption.
- **Advanced Retrieval Architectures:** Engineering **Parent-Child Retrieval** patterns—indexing granular "child" sentences for high-precision hits while retrieving broader "parent" contexts to maximize model comprehension.
- **Hybrid Search & Fusion:** Combining deterministic keyword matching (BM25) with probabilistic vector search using **Reciprocal Rank Fusion (RRF)** to eliminate "Vector Drift" on technical terms and part numbers.
- **Precision Tuning via Re-ranking:** Implementing a two-stage retrieval pipeline using **Cross-Encoders** to re-score and filter retrieved candidates, drastically reducing noise and hallucination risks.
- **Automated RAG Evaluation (RAGAS):** Moving beyond "vibes-based" testing to programmatic benchmarking of **Faithfulness** , **Answer Relevance** , and **Context Precision** using AI-on-AI evaluation frameworks.

## 📚 Phase 03: Model Adaptation & Local Inference

High-level focus areas covered in `Phase-03-Model-Adaptation/`:

- **Model Weight & Quantization Science:** Mastering the mathematical compression of neural networks (GGUF, EXL2, AWQ) to optimize the hardware-software link, enabling high-reasoning capabilities on consumer-grade VRAM.
- **Knowledge Distillation:** Implementing **Teacher-Student** patterns to "distill" the intelligence of frontier models (GPT-4o) into specialized, local Small Language Models (SLMs) using synthetic dataset curation.
- **Parameter-Efficient Fine-Tuning (PEFT):** Performing "weight surgery" using **QLoRA (Quantized Low-Rank Adaptation)** to train specialized adapters (**$r$**, **$\alpha$** tuning) without the multi-million dollar compute overhead of full-parameter training.
- **Inference Engineering:** Architecting high-performance local serving environments using backends like **vLLM** and **llama.cpp** , with a focus on optimizing the trade-off between **Inference Latency** and **System Throughput** .
- **Dataset Alignment & Diversity:** Engineering instruction-tuning datasets in **JSONL** format, focused on **Diversity Scaling** and edge-case coverage to ensure model robustness in specialized domains (e.g., PII Redaction).
- **Privacy-First AI Architecture:** Building "Air-Gapped" intelligence layers that process sensitive data entirely on-premises, eliminating third-party data leakage and ensuring 100% compliance with strict data residency requirements.

## 📚 Phase 04: Systems Reliability & MLOps

High-level focus areas covered in `Phase-04-Systems-Reliability-and-MLOps/`:

- **Inference Portability & Optimization:** Mastering **Multi-Stage Docker builds** to create lightweight, immutable artifacts. Implementing **GPU Passthrough** (NVIDIA-Container-Toolkit) to ensure high-performance, bit-for-bit identical inference across local and cloud environments.
- **Enterprise Model Orchestration:** Architecting secure model consumption via **Amazon Bedrock**, utilizing the latest **Claude Opus 4.7** models. **Implementing **Z**ero-Operator Data Access** protocols to ensure sensitive data remains encrypted and invisible to service providers.
- **Identity & Access Management (IAM) for AI:** Designing **Least Privilege** security policies and session-based cost attribution. Ensuring that AI agents have scoped permissions only to the specific models and databases required for the task.
- **Automated MLOps Pipelines:** Engineering **CI/CD/CT (Continuous Testing)** workflows using GitHub Actions. Implementing **Blue/Green Deployment** strategies to shift traffic safely between model versions without downtime or regression.
- **Agnostic Tracing & Observability:** Integrating **OpenTelemetry** and **Arize Phoenix** for distributed tracing. Analyzing "Spans" to identify latency bottlenecks in the firewall, router, or inference layers.
- **Compliance-Grade Evaluation:** Moving beyond "vibes" to mathematical verification using **F1-Score (Precision vs. Recall)** for PII redaction and **RAGAS** for retrieval faithfulness. Benchmarking the system against specialized 2026 evaluation datasets to prove 100% compliance readiness.
