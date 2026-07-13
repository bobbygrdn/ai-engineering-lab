# Part 2: Quantization Science

## Terms

- GGUF
- llama.cpp
- EXL2
- 4‑bit quantization
- Perplexity
- Model size (e.g., 70B, 8B)

## Key Concepts

- Trade‑off between precision and model breadth
- Impact of quantization on inference speed and memory footprint
- Relationship between perplexity and model quality
- Benefits of low‑bit formats for large language models

## Implementation Overview

This notebook benchmarks **13 B parameters quantized to 4‑bit (EXL2)** against a **7 B parameter model in full 16‑bit precision**.  
It downloads the models from Hugging Face, computes cross‑entropy loss (perplexity) on a small set of prompts, and prints side‑by‑side results. The goal is to illustrate the architectural trade‑off: whether a larger, low‑precision model can outperform a smaller, high‑precision model on consumer‑grade hardware.

Key points:

- **Models**:
  - `LoneStriker/LLaMA2-13B-Estopia-4.0bpw-h6-exl2` (EXL2 4‑bit)
  - `NousResearch/Llama-2-7b-hf` (FP16 baseline)
- **Metrics**: Perplexity (lower = better) computed with the same tokenization pipeline for both models.
- **Hardware target**: ≥ 15 GB VRAM (e.g., RTX 3090/4080/4090, Google Colab T4).

## How It Works

1. **Authentication** – The script first attempts to read a Hugging Face token from Google Colab secrets; if unavailable it falls back to the `HF_TOKEN` environment variable.
2. **Model download** – `snapshot_download` fetches the EXL2 checkpoint; the FP16 model is loaded directly by the `transformers` library.
3. **Perplexity functions** –
   - `calculate_exl2_perplexity` builds an `ExLlamaV2` instance, tokenizes the input, runs a forward pass, and computes cross‑entropy loss.
   - `calculate_fp16_perplexity` uses `AutoModelForCausalLM` with `torch.float16` and the same loss calculation.
4. **Benchmark loop** – A list of three representative sentences is processed; each model’s perplexity is printed.
5. **Cleanup** – GPU memory is cleared after each inference to stay within the VRAM budget.

### Hardware Requirements

- Minimum VRAM: **15 GB**.
- Tested on: Google Colab (Free Tier – T4 GPU) and local machines with RTX 3090/4080/4090.
- The unquantized 7 B model consumes ~13.5 GB; a full‑precision 13 B model would need ~26 GB and will OOM on the above hardware.

### Setup & Authentication

1. **Generate a Hugging Face token** (read‑only) from your account settings.
2. **Provide the token**:
   - In Colab, add a secret named `HF_TOKEN`.
   - Locally, export `HF_TOKEN` in your shell before launching Jupyter:

   ```bash
   # Bash (Linux/macOS)
   export HF_TOKEN="your_token_here"

   # Windows CMD
   set HF_TOKEN="your_token_here"

   # PowerShell
   $env:HF_TOKEN="your_token_here"
   ```

3. **Install dependencies** (uncomment the pip block in Cell 0 if running fresh).

## Example Usage

```python
samples = [
    "The quick brown fox jumps over the lazy dog.",
    "Artificial intelligence is transforming many industries.",
    "Quantization reduces model size while preserving performance."
]

for s in samples:
    exl2_ppl = calculate_exl2_perplexity(s)
    fp16_ppl = calculate_fp16_perplexity(s)
    print(f"Prompt: \"{s}\"")
    print(f"  EXL2 (13B 4‑bit) → PPL = {exl2_ppl:.2f}")
    print(f"  FP16 (7B 16‑bit) → PPL = {fp16_ppl:.2f}\n")
```

Running the notebook will output the perplexity scores for each prompt, allowing a direct comparison of the two configurations.

## Next Steps

- **Explore GGUF**: Convert the same model to GGUF using `llama.cpp` and benchmark against EXL2.
- **Vary bit‑widths**: Test 3‑bit, 5‑bit, or 8‑bit quantizations to map the precision‑breadth curve.
- **Scale up**: Apply the workflow to larger models (e.g., 70 B) to validate the hypothesis that a 4‑bit 70 B model can outperform a full‑precision 8 B model.
- **Automate reporting**: Log results to CSV/JSON for downstream analysis or visualization.
