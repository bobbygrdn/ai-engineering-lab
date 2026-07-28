# Part 3: Hyperparameter Tuning

## Terms

- LoraConfig
- Rank (r)
- Alpha (α)
- QLoRA
- Overfitting
- Plasticity

## Key Concepts

- Rank (r)
- Alpha (α)
- Overfitting vs. Underfitting Trade-off
- Determinism in Adaptation

## Implementation Overview

This notebook demonstrates the process of adapting a Mistral 7B Instruct model for PII redaction using Quantized Low-Rank Adaptation (QLoRA). The focus is on configuring and training Low-Rank Adapters (LoRA) with specific hyperparameters to balance model plasticity and prevent overfitting. The implementation covers model quantization, LoRA adapter attachment, dataset formatting, and supervised fine-tuning setup.

Primary capabilities:

- 4-bit quantization using BitsAndBytes
- Gradient checkpointing for VRAM efficiency
- LoRA adapter configuration with rank (r=16) and alpha (α=32)
- Targeted adaptation of all transformer projection layers
- Supervised fine-tuning with SFTTrainer
- Checkpoint saving during training

## How It Works

1. **Model Preparation**: The base model is loaded in 4-bit precision and prepared for k-bit training by enabling gradient checkpointing and applying `prepare_model_for_kbit_training`.

2. **LoRA Adapter Configuration**: A `LoraConfig` is defined with:
   - Rank (r) = 16: Controls the dimensionality of the update matrices
   - Alpha (α) = 32: Scaling factor for the LoRA updates (typically 2× rank)
   - Target modules: All query, key, value, output, and feed-forward projection layers
   - Dropout (0.05): Applied to prevent overfitting during adaptation
   - Bias settings: No bias terms adapted
   - Task type: Causal language modeling

3. **Adapter Attachment**: The LoRA adapters are attached to the quantized model using `get_peft_model`, creating a PEFT model where only the adapter weights are trainable.

4. **Dataset Formatting**: The training dataset is formatted using the tokenizer's chat template to match the model's expected input structure, creating a text field for training.

5. **Trainer Initialization**: The SFTTrainer is configured with:
   - Output directory for checkpoints
   - Training hyperparameters (epochs, batch size, learning rate, etc.)
   - Mixed precision training (bf16)
   - Gradient accumulation and max grad norm for stability
   - Sampling strategy grouped by sequence length

6. **Training Execution**: The supervised fine-tuning process begins, updating only the LoRA adapter weights while keeping the base model frozen in 4-bit precision.

## Example Usage

```python
# Cell 6: Prepare for k-bit Training
from peft import prepare_model_for_kbit_training, LoraConfig, get_peft_model

# Enable gradient checkpointing to save massive amounts of VRAM
model.gradient_checkpointing_enable()

# Prep the model for quantized training
model = prepare_model_for_kbit_training(model)
print("✅ Model prepped for gradient calculations.")
```

```python
# Cell 7: Define and Attach the LoRA Adapters
peft_config = LoraConfig(
    r=16,                       # The rank of the update matrices
    lora_alpha=32,              # The scaling factor (usually 2x the rank)
    target_modules=[            # Target all linear layers for maximum intelligence
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,          # Drop 5% of neurons randomly to prevent overfitting
    bias="none",
    task_type="CAUSAL_LM"
)

# Attach the adapters to the 4-bit base model
model = get_peft_model(model, peft_config)

# Let's see exactly how many parameters we are actually training
model.print_trainable_parameters()
```

```python
# Cell 8: Dataset Formatting
def format_chat_template(row):
    # This uses the tokenizer to apply Llama-3's native <|start_header_id|> tags
    chat = row['messages']
    formatted_prompt = tokenizer.apply_chat_template(chat, tokenize=False)
    return {"text": formatted_prompt}

print("Formatting dataset to match Llama-3's prompt structure...")
formatted_dataset = dataset.map(format_chat_template)
print("✅ Formatting complete!")
```

```python
# Cell 9: Set up Training Arguments and Trainer
from trl import SFTConfig, SFTTrainer

training_arguments = SFTConfig(
    output_dir="./pii_redactor_checkpoints",
    num_train_epochs=1,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    optim="paged_adamw_32bit",
    save_steps=25,
    logging_steps=5,
    learning_rate=2e-4,
    weight_decay=0.001,
    fp16=False,
    bf16=True,
    max_grad_norm=0.3,
    lr_scheduler_type="constant",
    train_sampling_strategy="group_by_length",
    dataset_text_field="text",
    max_length=1024
)

print("Initializing SFTTrainer...")
trainer = SFTTrainer(
    model=model,
    train_dataset=formatted_dataset,
    processing_class=tokenizer,
    args=training_arguments,
)
print("✅ Trainer ready.")
```

```python
# Cell 10: TRAIN
print("🚀 Commencing Neural Surgery (Training Started)...")
trainer.train()
```

## Next Steps

- Experiment with different rank (r) and alpha (α) values to study their impact on adaptation performance and overfitting.
- Implement validation loops to monitor overfitting vs. underfitting trade-offs during training.
- Explore deterministic adaptation techniques by fixing random seeds for reproducible LoRA weight updates.
- Investigate plasticity preservation by comparing adapter-only updates versus full fine-tuning on downstream PII redaction tasks.
- Scale the approach to larger models or different architectures by adjusting target modules and quantization settings.
