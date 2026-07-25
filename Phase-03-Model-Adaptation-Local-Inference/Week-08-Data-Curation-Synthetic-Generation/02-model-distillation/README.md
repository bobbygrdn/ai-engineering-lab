# Part 2: Model Distillation

## Terms

- Teacher model
- Student model
- Model distillation
- PII (Personally Identifiable Information)
- Synthetic data generation
- Edge cases (misspellings, foreign names, non-standard date formats)

## Key Concepts

- Teacher-student paradigm where a powerful model generates training data for a smaller model
- Diversification strategy: Ensuring training data covers diverse edge cases to prevent overfitting to narrow patterns
- PII redaction schema with specific tags ([NAME], [SSN], [ADDRESS], etc.) as defined in `schema.md`
- Synthetic data generation for domain-specific PII-heavy text (doctor notes, HR complaints, bank logs)

## Implementation Overview

The project implements a two-stage pipeline for creating synthetic PII data and training data for model distillation:

**Stage 1 - Synthetic PII Generation**: Creates PII-containing documents (doctor notes, HR complaints, bank logs) using a teacher model (NVIDIA's Mistral-Nemotron) with diversification strategies (misspellings, foreign names, date variations) to improve robustness. Generated texts adhere to a PII redaction schema with predefined tags.

**Stage 2 - Training Data Creation**: Takes the generated PII documents and creates redacted versions using a more aggressive teacher model, producing training examples in the format needed for fine-tuning a student model via distillation.

Primary capabilities:

- Synthetic generation of PII-laden documents across three domains (doctor notes, HR complaints, bank logs)
- Application of diversification strategies (misspellings, foreign names, date variations)
- PII redaction according to a predefined schema (`schema.md`) in both stages
- Two-stage pipeline: PII generation → PII redaction for training data
- Checkpointing and resumable generation for both stages
- Logging and cost/performance monitoring
- Integration with NVIDIA's Mistral-Nemotron via OpenAI-compatible API (different models for each stage)

## How It Works

**Stage 1: Synthetic PII Generation**

1. Execution starts at `run_generation.py` which parses command-line arguments (number of examples, output file, resume checkpoint).
2. If resuming, loads existing examples from a checkpoint file via `utils.load_checkpoint`.
3. Calls `generate_pii_dataset` (in `generate_pii.py`) to generate the specified number of examples.
4. Within `generate_pii_dataset`:
   - For each example, randomly selects a domain (doctor_notes, hr_complaints, bank_logs) and an optional edge-case strategy (misspelling, foreign_name, date_variation, or none).
   - Retrieves a base prompt template for the domain from `prompt_templates.py`.
   - If an edge-case strategy is selected, modifies the prompt accordingly via `apply_edge_case_strategy`.
   - Sends the prompt to the LLM via `llm.generate_response` (which calls the NVIDIA API with the Mistral-Nemotron model).
   - Validates the generated response contains required PII via `utils.validate_pii_content`.
   - If valid, adds the example to the batch with metadata (domain, edge_case, timestamp).
   - Every 25 valid examples, saves a checkpoint via `utils.save_checkpoint`.
   - After each batch (default 25 examples), pauses for 30 seconds to avoid rate limits.
5. After generation, saves the final dataset to JSONL via `utils.save_final_dataset`.

**Stage 2: Training Data Creation**

1. Execute `generate_training_dataset.py` which loads the generated PII dataset from Stage 1.
2. For each PII-containing document: - Loads the raw text from the dataset - Sends it to a more aggressive teacher model (nvidia/nemotron-3-nano-30b-a3b) with strict redaction instructions via `llm.generate_response` - The teacher model redacts all PII using standardized tags ([NAME], [SSN], [ADDRESS], etc.) following strict rules:
   _ Prose redaction: redacts PII anywhere in the text, not just headers
   _ Partial names: catches nicknames, titles, and partial names
   _ Silent output: returns only the redacted text without additional commentary - Validates the redaction was successful - Creates a fine-tuning example with:
   _ System message: Student model's redaction instructions
   _ User message: Original PII-containing text
   _ Assistant message: Teacher model's redacted version - Saves the example to JSONL format for training 8. Includes checkpointing/resume capability and error handling with retry logic.

## Example Usage

**Stage 1: Generate Synthetic PII Dataset**

```bash
# Modify the num-examples for testing (i.e., 20 or 50)
python run_generation.py --num-examples 1000 --output pii_dataset.jsonl
```

To resume from a checkpoint:

```bash
# Script will look at how many examples already exist and subtract it from the num-examples you put here (i.e., 100 total, 300 exist, 700 new ones will be created.)
# The resume-from cam be any checkpoint file in checkpoints directory
python run_generation.py --num-examples 1000 --output pii_dataset.jsonl --resume-from checkpoint_500.jsonl
```

**Stage 2: Create Training Data for Distillation**

```bash
# Script automatically checks pii_dataset.jsonl for which line it will start from (i.e., 356 lines exist, starting from 357)
python generate_training_dataset.py
```

## Next Steps

- Add support for more domains beyond doctor notes, HR complaints, and bank logs.
- Implement more sophisticated PII entities and redaction tags.
- Add unit tests for prompt validation and edge-case strategies.
- Optimize the checkpointing mechanism to reduce I/O overhead.
- Add support for other LLM providers beyond NVIDIA's API.
- Implement a dataset validation script to check generated synthetic data for quality and diversity.
- Create a fine-tuning script to distill the generated data into a smaller student model.
