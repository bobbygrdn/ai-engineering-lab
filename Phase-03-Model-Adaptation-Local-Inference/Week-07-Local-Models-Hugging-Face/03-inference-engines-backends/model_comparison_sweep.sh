#!/bin/bash
# Model Comparison Sweep Script
# Tests multiple models that fit in VRAM across different GPU layer configurations

# Configuration
BASE_PORT=8080
CTX_SIZE=2048  # Reduced context size to save VRAM for multiple model tests
OUTPUT_DIR="./model_comparison_results"
COMBINED_CSV="$OUTPUT_DIR/combined_results.csv"

# Define models to test (all should fit in VRAM when quantized)
# Format: "model_name|model_path|description"
MODELS_TO_TEST=(
    "qwen3b|./models/qwen/qwen2.5-coder-3b-instruct-q4_k_m.gguf|Qwen2.5-Coder-3B-Instruct-Q4_K_M"
    "phi2|./models/phi/phi-2.Q4_K_M.gguf|Phi-2-Q4_K_M"
    "tinyllama|./models/tinyllama/tinyllama-1.1b-chat-v1.0.Q8_0.gguf|TinyLlama-1.1B-Chat-V1.0-Q8_0"
    "gemma|./models/gemma/gemma-2b-it.Q4_K_M.gguf|Gemma-2B-it-Q4_K_M"
    "stablelm|./models/stablelm/stablelm-zephyr-3b.Q6_K.gguf|StableLM-Zephyr-3B-Q6_K"
)

# GPU layer configurations to test
LAYERS_LIST="0 10 20 30 40 50"

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo "Model comparison results will be saved to: $OUTPUT_DIR"
echo "=========================================================="

# Function to run benchmark for a specific model/configuration
run_model_test() {
    local model_name="$1"
    local model_path="$2"
    local model_desc="$3"
    local gpu_layers="$4"
    local port="$5"
    local run_name="${model_name}_gpu_${gpu_layers}layers"
    local csv_file="$OUTPUT_DIR/${run_name}.csv"
    
    echo "Starting test: $model_desc"
    echo "  GPU Layers: $gpu_layers"
    echo "  Port: $port"
    echo "  Output: $csv_file"
    
    # Start the server
    python -m llama_cpp.server --model "$model_path" --host 127.0.0.1 --port $port --n_gpu_layers $gpu_layers --n_ctx $CTX_SIZE &
    SERVER_PID=$!
    
    # Wait for server to start
    echo "  Waiting for server to initialize..."
    sleep 5
    
    # Run benchmark
    echo "  Running benchmark..."
    python benchmark.py \
        --run-name "$run_name" \
        --model "$(basename "$model_path")" \
        --model-path "$model_path" \
        --n-gpu-layers $gpu_layers \
        --ctx-size $CTX_SIZE \
        --port $port \
        --csv-path "$csv_file"
    
    # Stop server
    echo "  Stopping server..."
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "  ✓ Completed test for $model_name with $gpu_layers GPU layers"
    echo "----------------------------------------"
}

# Main execution loop
echo "Starting model comparison sweep..."
echo "Context size: $CTX_SIZE"
echo "GPU layers to test: $LAYERS_LIST"
echo ""

# Track overall start time
START_TIME=$(date +%s)

# Test each model
for model_spec in "${MODELS_TO_TEST[@]}"; do
    # Parse model specification
    IFS='|' read -r model_name model_path model_desc <<< "$model_spec"
    
    # Check if model file exists
    if [[ ! -f "$model_path" ]]; then
        echo "⚠️  Model file not found: $model_path"
        echo "   Skipping $model_name"
        echo "----------------------------------------"
        continue
    fi
    
    echo "Testing model: $model_desc"
    echo "File: $model_path"
    
    # Test each GPU layer configuration
    port_offset=0
    for layers in $LAYERS_LIST; do
        PORT=$((BASE_PORT + port_offset))
        run_model_test "$model_name" "$model_path" "$model_desc" "$layers" "$PORT"
        ((port_offset++))
    done
    
    echo "Completed all tests for $model_name"
    echo ""
done

# Combine all results
echo "Combining all results into: $COMBINED_CSV"
echo "run_date,run_name,prompt_id,prompt_text,model,model_path,command,n_gpu_layers,context_size,port,prompt_tokens,generated_tokens,time_to_first_token,total_response_time,tokens_per_sec,peak_vram,result,notes" > "$COMBINED_CSV"

# Find all CSV files and concatenate them (skipping headers after first)
first_file=true
for csv_file in "$OUTPUT_DIR"/*.csv; do
    if [[ "$csv_file" != "$COMBINED_CSV" ]]; then
        if [ "$first_file" = true ]; then
            # Include header for first file
            cat "$csv_file" >> "$COMBINED_CSV"
            first_file=false
        else
            # Skip header for subsequent files
            tail -n +2 "$csv_file" >> "$COMBINED_CSV"
        fi
    fi
done

# Calculate total time
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))
HOURS=$((ELAPSED_TIME / 3600))
MINUTES=$(( (ELAPSED_TIME % 3600) / 60 ))
SECONDS=$((ELAPSED_TIME % 60))

echo ""
echo "✅ Model comparison sweep completed!"
echo "📊 Combined results saved to: $COMBINED_CSV"
echo "⏱️  Total time: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "Next steps:"
echo "1. Generate visualizations: python visualize_results.py --input $COMBINED_CSV --output ./model_comparison_visualizations"
echo "2. Analyze results to find optimal GPU layer configuration for each model on your device."
