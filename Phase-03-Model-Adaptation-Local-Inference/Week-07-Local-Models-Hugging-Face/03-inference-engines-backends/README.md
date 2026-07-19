# Part 3: Inference Engines & Backends

## Terms

- vLLM
- llama.cpp
- Inference engine
- Backend server
- Latency
- Throughput
- Batching
- Concurrency
- GPU/CPU utilization
- Model quantization

## Key Concepts

- Latency – time from request receipt to response delivery (per‑user experience).
- Throughput – number of requests processed per unit time (overall server capacity).
- Batching – grouping multiple inputs to a single forward pass to improve GPU utilization.
- Concurrency – handling multiple requests simultaneously, often via async I/O or multiple worker processes.
- Quantization – reducing model precision to trade accuracy for speed and memory savings.

## Implementation Overview

This project benchmarks and compares different LLM inference backends (primarily llama.cpp based on the GGUF model format) across various models and GPU offload levels. It measures key performance metrics such as latency (time to first token, total response time), throughput (tokens per second), and VRAM usage to evaluate the trade-offs between model size, quantization level, and hardware acceleration.

Primary capabilities:

- Running automated benchmarks for multiple models (Gemma-2B, Phi-2, Qwen2.5-Coder-3B, StableLM-Zephyr-3B, TinyLlama) with varying GPU layer offloads (0 to 50 layers)

- Collecting detailed metrics including prompt tokens, generated tokens, time to first token, total response time, tokens per second, and peak VRAM usage

- Generating individual CSV logs for each experimental run and combined results for comparison

- Creating comprehensive visualizations comparing performance metrics across GPU layer configurations

Key Components:

- **benchmark.py**: Main benchmarking script that starts llama.cpp server, sends prompts via API, measures performance metrics, and logs results

- **model_comparison_sweep.sh**: Tests multiple models that fit in VRAM across different GPU layer configurations (0, 10, 20, 30, 40, 50 layers)

- **single_model_sweep.sh**: Tests one model across multiple GPU layer configurations (defaults to Qwen2.5-Coder-3B)

- **visualize_results.py**: Generates publication-quality visualizations from benchmark results

- **model_comparison_results/**: Directory containing individual and combined CSV results

- **model_comparison_visualizations/**: Directory containing generated plots and charts

- **models/**: Directory containing downloaded large language models for testing

## How It Works

- **Experiment Execution**: Shell scripts (`model_comparison_sweep.sh`, `single_model_sweep.sh`) invoke the benchmarking script (`benchmark.py`) with different model paths and GPU layer counts

- **Benchmarking**: The benchmark script launches the llama.cpp server with specified parameters, sends standardized prompts to the server's API endpoint, and measures:
  - Time to first token (TTFT) - measures latency
  - Total response time - measures end-to-end latency
  - Tokens generated per second - measures throughput
  - Peak VRAM consumption monitored via nvidia-smi in a background thread Results are appended to CSV files in `model_comparison_results/`

- **Result Visualization**: The `visualize_results.py` script reads the aggregated CSV files and generates plots to compare:
  - Latency (time to first token) vs GPU layers for each model
  - Throughput (tokens per second) vs GPU layers for each model
  - VRAM usage vs GPU layers (with visual indicators for 4GB, 6GB, 8GB limits)
  - Combined latency/throughput views and normalized metrics

- **Analysis**: Generated plots in `model_comparison_visualizations/` help identify optimal GPU offload levels for each model

## Example Usage

Based on the CSV structure, a typical benchmark run might execute a command like:

```bash
# Tests multiple models across GPU layers 0-50
./model_comparison_sweep.sh

# Single model sweep (defaults to Qwen2.5-Coder-3B)
./single_model_sweep.sh

# Direct benchmark usage example
python benchmark.py \
  --model ./models/qwen/qwen2.5-coder-3b-instruct-q4_k_m.gguf \
  --model-path ./models/qwen/qwen2.5-coder-3b-instruct-q4_k_m.gguf \
  --n-gpu-layers 20 \
  --ctx-size 4096 \
  --port 8080 \
  --run-name qwen_20layers \
  --csv-path ./results/qwen_20layers.csv

# Generate visualizations from combined results
python visualize_results.py --input ./model_comparison_results/combined_results.csv --output ./model_comparison_visualizations

```

## Key Findings

- **Latency vs GPU Layers**: Generally decreases as more layers are offloaded to GPU, with diminishing returns beyond ~30-40 layers for most models

- **Throughput vs GPU Layers**: Shows similar trends to latency, with improvements plateauing at higher GPU layer counts

- **VRAM Usage**: Increases linearly with GPU layers, allowing users to find the optimal balance between performance and memory usage for their specific hardware

- **Model Differences**: Different models show varying sensitivity to GPU offloading, with some benefiting more from partial GPU acceleration than others

## Next Steps

- Integrate additional inference backends (e.g., vLLM, TensorRT-LLM) for broader comparison

- Extend benchmarking to include more diverse prompts and sampling parameters (temperature, top-p, etc.)

- Implement automated report generation (PDF or HTML) summarizing benchmark results with key insights

- Add support for dynamic batching and concurrent request simulation to better reflect real-world usage

- Containerize the benchmarking environment using Docker for easier reproducibility and sharing

- Add power consumption monitoring if available on the hardware

- Implement statistical significance testing for performance comparisons
