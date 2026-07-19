#!/bin/bash
# Single Model Sweep Script
# Tests one model across multiple GPU layer configurations
# Use model_comparison_sweep.sh for testing multiple models

# Configuration
MODEL="./models/qwen/qwen2.5-coder-3b-instruct-q4_k_m.gguf"
BASE_PORT=8080
CTX_SIZE=4096
OUTPUT_DIR="./results"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Test configurations
LAYERS_LIST="0 10 20 30 40 50"

echo "Starting GPU layer sweep tests..."
echo "Model: $MODEL"
echo "Context size: $CTX_SIZE"
echo "Testing GPU layers: $LAYERS_LIST"
echo "Results will be saved to: $OUTPUT_DIR"
echo "========================================"

for layers in $LAYERS_LIST; do
    PORT=$((BASE_PORT + layers))  # Use different port for each test to avoid conflicts
    RUN_NAME="qwen_gpu_${layers}layers"
    CSV_FILE="$OUTPUT_DIR/llama_cpp_run_log_${RUN_NAME}.csv"
    
    echo "Starting server with $layers GPU layers on port $PORT..."
    python -m llama_cpp.server --model "$MODEL" --host 127.0.0.1 --port $PORT --n_gpu_layers $layers --n_ctx $CTX_SIZE &
    SERVER_PID=$!
    
    # Wait for server to start
    echo "Waiting for server to initialize..."
    sleep 5
    
    # Run benchmark
    echo "Running benchmark for $layers GPU layers..."
    python benchmark.py \
        --run-name "$RUN_NAME" \
        --n-gpu-layers $layers \
        --ctx-size $CTX_SIZE \
        --port $PORT \
        --csv-path "$CSV_FILE"
    
    # Stop server
    echo "Stopping server..."
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "Completed test with $layers GPU layers"
    echo "Results saved to: $CSV_FILE"
    echo "----------------------------------------"
done

echo "All tests completed!"
echo "Individual results saved in: $OUTPUT_DIR"
echo "To combine results: cat $OUTPUT_DIR/llama_cpp_run_log_*.csv > combined_results.csv"
