# Part 1: The Weights Ecosystem (Hugging Face)

## Terms

- Hugging Face Hub
- Model families: Llama‑3, Mistral, Phi‑3
- Parameters (P) (billions)
- Bits per weight (Q)
- VRAM budgeting
- KV cache
- Activation memory
- Memory formula ($M \approx P \times \frac{Q}{8} \times 1.2$)

## Key Concepts

- Estimating model memory from parameter count and precision
- Impact of bit‑width on storage requirements
- 20% overhead for KV cache and activations
- Mapping estimated memory (M) to GPU VRAM limits
- Comparative analysis of model families based on size and precision

## Implementation Overview

This project implements a VRAM budgeting tool using a Jupyter Notebook to estimate the GPU memory required to load various Large Language Models (LLMs). By combining parameter counts with weight precision (quantization), the tool calculates the necessary VRAM while accounting for a 20% overhead for KV cache and activations.

Primary capabilities:

- Memory estimation for Llama-3, Mistral, and Phi-3 families.
- Support for multiple quantization levels (FP16, Q8, Q6, Q4).
- GPU fit validation against specific VRAM limits.

## How It Works

1. **Input Definition**: Model specifications (parameter count $P$ and bit-width $Q$) are stored in a dictionary.
2. **Calculation**: The `vram_estimate` function calculates the base memory by multiplying parameters by the byte-size of the weights ($\frac{Q}{8}$).
3. **Overhead Application**: A 1.2x multiplier is applied to the base memory to account for runtime overhead (KV cache and activations).
4. **Comparison**: The resulting estimate $M$ is compared against a target GPU's VRAM capacity to determine if the model fits.

## Example Usage

```python
# Modify this dictionary with any models you want to use for calculations
models = {
    "Llama-3-8B-fp16":   {"P": 8, "Q": 16},
    "Mistral-7B-fp16":   {"P": 7, "Q": 16},
    "Phi-3-mini-4B-fp16": {"P": 4, "Q": 16},
}

# Modify this variable to match the hardware of your device
gpu_vram_gb = 12

for name, spec in models.items():
    mem = vram_estimate(spec["P"], spec["Q"])
    fits = mem <= gpu_vram_gb
    print(f"{name} fits on GPU with {gpu_vram_gb}GB VRAM: {fits}")
# Output:
# Llama-3-8B-fp16 fits on GPU with 12GB VRAM: True
# Mistral-7B-fp16 fits on GPU with 12GB VRAM: True
# Phi-3-4B-fp16 fits on GPU with 12GB VRAM: True
```

## Next Steps

- **Automated Metadata**: Integrate the Hugging Face Hub API to automatically fetch parameter counts for new models.
- **Hardware Profiles**: Create a library of GPU profiles (e.g., RTX 4090, A100) for one-click compatibility checks.
- **Visualization**: Add Matplotlib charts to visualize the memory trade-offs between different quantization levels.
