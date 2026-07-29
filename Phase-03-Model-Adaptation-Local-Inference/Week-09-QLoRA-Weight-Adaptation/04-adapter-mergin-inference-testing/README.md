# Part 4: Adapter Merging and Inference Testing

## Terms

- QLoRA (Quantized Low-Rank Adaptation)
- PII (Personally Identifiable Information)
- Adapter merging
- Base model (Mistral-7B-Instruct-v0.3)
- PEFT (Parameter-Efficient Fine-Tuning)

## Key Concepts

- Efficient fine-tuning of large language models using low-rank adaptation and quantization
- Merging adapter weights into the base model for efficient inference without adapter overhead
- Evaluating model performance on PII redaction tasks by comparing base and adapted model outputs

## Implementation Overview

This notebook demonstrates the process of loading a pre-trained Mistral-7B model, loading a QLoRA adapter trained for PII redaction, merging the adapter into the base model, and testing the merged model's ability to redact PII in sample texts. It compares outputs from the base model and merged model to show the adaptation effect. The workflow includes dataset loading, tokenizer setup, model quantization, adapter loading, merging, and inference testing.

## How It Works

1. Load the training dataset from Hugging Face containing PII redaction examples
2. Load the tokenizer for Mistral-7B-Instruct-v0.3 and configure padding
3. Set up 4-bit quantization configuration for efficient model loading
4. Load the quantized base model and the PEFT adapter (trained weights for PII redaction)
5. Merge the adapter weights into the base model and save the merged model
6. Test the merged model on sample inputs containing PII (email, phone, name, etc.)
7. Test the base model on the same inputs for comparison
8. Compare outputs to evaluate the model's PII redaction capability

## Example Usage

```python
# Cell 11: Save the Proprietary Brain
ADAPTER_NAME = "pii-redactor-mistral-lora-v1"

print(f"Saving the LoRA adapters to {ADAPTER_NAME}...")
trainer.model.save_pretrained(ADAPTER_NAME)
tokenizer.save_pretrained(ADAPTER_NAME)

print("✅ Adapters successfully extracted and saved to disk!")
```

```python
# Cell 12: The Batch Evaluation Matrix
from datasets import load_dataset
import torch
from tqdm.notebook import tqdm
import re

DATASET_ID = "Your-Username/pii-redactor-training-v1"
print(f"Downloading Holdout Test Set from {DATASET_ID}...")
test_dataset = load_dataset(DATASET_ID, split="test")
print(f"Loaded {len(test_dataset)} test examples.\n")

exact_matches = 0
total_examples = len(test_dataset)
leak_failures = 0

print("Commencing Batch Inference on Test Set...")

for i, row in enumerate(tqdm(test_dataset, desc="Evaluating")):
    messages = row['messages']

    # Extract Ground Truth
    system_prompt = messages[0]['content']
    raw_text = messages[1]['content']
    ground_truth = messages[2]['content'].strip()

    # Format for Mistral inference
    eval_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_text}
    ]
    prompt = tokenizer.apply_chat_template(eval_messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    # Generate Prediction
    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=250,
            temperature=0.1,             # Prevent deterministic loops
            repetition_penalty=1.1,      # Break asterisk repetition
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    input_length = inputs["input_ids"].shape[1]
    prediction = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()

    # --- METRIC 1: Exact Match ---
    if prediction == ground_truth:
        exact_matches += 1

    # --- METRIC 2: Tag Recall (Leak Detection) ---
    tags_pattern = r'\[(?:NAME|SSN|ADDRESS|PHONE|EMAIL|DOB|MRN)\]'
    gt_tags = re.findall(tags_pattern, ground_truth)
    pred_tags = re.findall(tags_pattern, prediction)

    if len(pred_tags) < len(gt_tags):
        leak_failures += 1

# Calculate Final Metrics
exact_match_accuracy = (exact_matches / total_examples) * 100
leak_rate = (leak_failures / total_examples) * 100
safe_rate = 100 - leak_rate

print("\n" + "="*40)
print("🏆 RE-EVALUATION METRICS 🏆")
print("="*40)
print(f"Total Test Examples: {total_examples}")
print(f"Strict Exact Match:  {exact_match_accuracy:.2f}%")
print(f"Data Safety Rate:    {safe_rate:.2f}% (Rows with zero tag leaks)")
print(f"Critical Leak Rate:  {leak_rate:.2f}% (Rows where PII was potentially missed)")
print("="*40)
```

```python
# Cell 13: The Failure Inspector
print("🔍 INSPECTING THE LEAKS 🔍\n")

failures_logged = 0
max_failures_to_print = 5 # We only want to look at a few to diagnose the issue

for i, row in enumerate(test_dataset):
    if failures_logged >= max_failures_to_print:
        break

    messages = row['messages']
    raw_text = messages[1]['content']
    ground_truth = messages[2]['content'].strip()

    # Format and Generate (Using the safe parameters)
    eval_messages = [{"role": "system", "content": messages[0]['content']}, {"role": "user", "content": raw_text}]
    prompt = tokenizer.apply_chat_template(eval_messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=250,
            temperature=0.1,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id
        )

    input_length = inputs["input_ids"].shape[1]
    prediction = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()

    # Tag Counting Logic
    tags_pattern = r'\[(?:NAME|SSN|ADDRESS|PHONE|EMAIL|DOB|MRN)\]'
    gt_tags = re.findall(tags_pattern, ground_truth)
    pred_tags = re.findall(tags_pattern, prediction)

    # If the model missed a tag, PRINT THE EVIDENCE
    if len(pred_tags) < len(gt_tags):
        print(f"--- FAILURE CAUGHT (Row {i}) ---")
        print(f"Missing Tags: Ground Truth expected {len(gt_tags)}, Model provided {len(pred_tags)}")
        print("\nGROUND TRUTH EXPECTED:")
        print(ground_truth[:300] + "...") # Print first 300 chars to save screen space
        print("\nMODEL PREDICTION:")
        print(prediction[:300] + "...")
        print("="*50 + "\n")
        failures_logged += 1
```

```python
# Cell 14: Push the Adapters to the Hub
# Replace 'your-username' with your actual Hugging Face username
REPO_ID = "your-hugging-face-username/pii-redactor-mistral-lora-v1"

print(f"Pushing adapters to Hugging Face Hub at {REPO_ID}...")

# Push the model weights
trainer.model.push_to_hub(REPO_ID, private=True)

# Push the tokenizer
tokenizer.push_to_hub(REPO_ID, private=True)

print("✅ SUCCESS! Your proprietary AI is now safely stored in the cloud.")
```

## Next Steps

- Experiment with different base models or adapter ranks for performance trade-offs
- Deploy the merged model for production inference in PII redaction applications
- Explore quantization techniques for further inference optimization
- Implement batch processing for improved throughput in production settings
