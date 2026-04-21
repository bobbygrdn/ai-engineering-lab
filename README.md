# 12-Week AI Engineering Intensive

This repository tracks my transition from a Full Stack Developer into AI Engineering.
The goal is to move beyond simple chat interfaces and master the architecture, deployment,
and orchestration of LLM-powered applications.

## 🚀 The Roadmap

- **Week 1: Architecture & API Layer** (Structured Outputs, AWS Lambda, DynamoDB)
- **Week 2: Orchestration Framework** (Prompt Templates, Chains + Memory, Document Loaders, Verified Extraction)
- **Week 3: Tools & Agent** (Custom Tools, ReAct Framework, Cloud Native Actions, Phase 1 Capstone)

## 🛠️ Tech Stack

- **Languages:** Python, TypeScript
- **Runtime:** Node.js (v20)
- **AI:** OpenAI API, LangChain
- **Cloud:** AWS (Lambda, API Gateway, DynamoDB, Secrets Manager, IAM)
- **Tooling:** Zod, Pydantic, esbuild, npm

## 📚 Phase 01: Architecture & API Layer

High-level focus areas covered in `Phase-01-Architecture-API-Layer/`:

- **Structured Outputs:** Enforcing reliable JSON contracts for LLM responses.
- **Orchestration:** Building reusable chains (LCEL), prompt templates, and parallel workflows.
- **Serverless APIs:** Deploying LLM-backed services on AWS Lambda (Function URLs).
- **Persistent Memory:** Session-based state using DynamoDB chat history.
- **Verified Extraction:** Grounding outputs with evidence quotes from ingested documents.
