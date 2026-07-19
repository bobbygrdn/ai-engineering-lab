import csv
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
import argparse

import requests
from llama_cpp import Llama

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run llama.cpp benchmarks with configurable parameters')
    
    # Model arguments
    parser.add_argument('--model', type=str, default='mistral-7b-instruct-v0.2.Q4_K_M.gguf',
                        help='Model filename')
    parser.add_argument('--model-path', type=str, default='./models/mistral/mistral-7b-instruct-v0.2.Q4_K_M.gguf',
                        help='Path to model file')
    
    # Performance arguments
    parser.add_argument('--n-gpu-layers', type=int, default=0,
                        help='Number of layers to offload to GPU (0 = CPU only)')
    parser.add_argument('--ctx-size', type=int, default=4096,
                        help='Context size')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for the server')
    
    # Run identification
    parser.add_argument('--run-name', type=str, default='baseline',
                        help='Name for this test run')
    
    # Other options
    parser.add_argument('--csv-path', type=str, default='llama.cpp_run_log.csv',
                        help='Path to CSV output file')
    
    return parser.parse_args()


# These will be set from arguments in main()
API_URL = "http://127.0.0.1:8080/v1/chat/completions"
CSV_PATH = Path("llama.cpp_run_log.csv")
RUN_NAME = "baseline"
MODEL = "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
MODEL_PATH = "./models/mistral/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
COMMAND = (
    "python -m llama_cpp.server --model ./models/mistral/mistral-7b-instruct-v0.2.Q4_K_M.gguf "
    "--host 127.0.0.1 --port 8080 --n_gpu_layers 0 --n_ctx 4096"
)
N_GPU_LAYERS = 0
CONTEXT_SIZE = 4096
PORT = 8080

PROMPTS = [
    (
        1,
        "Write a Python function that takes a sentence and returns the words in reverse order, "
        "preserving punctuation as much as possible. Include one short example.",
    ),
    (
        2,
        "Write a small Python script that reads a text file, counts word frequency, and prints "
        "the top 10 most common words. Keep it simple and readable.",
    ),
    (
        3,
        "Explain the difference between latency and throughput in the context of local LLM inference, "
        "then give one practical example of each.",
    ),
]

CSV_HEADER = [
    "run_date",
    "run_name",
    "prompt_id",
    "prompt_text",
    "model",
    "model_path",
    "command",
    "n_gpu_layers",
    "context_size",
    "port",
    "prompt_tokens",
    "generated_tokens",
    "time_to_first_token",
    "total_response_time",
    "tokens_per_sec",
    "peak_vram",
    "result",
    "notes",
]

TOKENIZER = None


def ensure_csv_header():
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def append_row(row):
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def get_tokenizer():
    global TOKENIZER
    if TOKENIZER is None:
        TOKENIZER = Llama(
            model_path=MODEL_PATH,
            vocab_only=True,
            verbose=False,
        )
    return TOKENIZER


def count_tokens(text, add_bos=False):
    tokenizer = get_tokenizer()
    tokens = tokenizer.tokenize(text.encode("utf-8"), add_bos=add_bos)
    return len(tokens)


def sample_gpu_memory(stop_event, peak_holder):
    while not stop_event.is_set():
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            ).strip()

            if output:
                used_values = [
                    int(value.strip())
                    for value in output.splitlines()
                    if value.strip()
                ]
                if used_values:
                    current_peak = max(used_values)
                    if current_peak > peak_holder["peak_vram"]:
                        peak_holder["peak_vram"] = current_peak
        except Exception:
            pass

        time.sleep(0.2)


def run_prompt(prompt_text):
    payload = {
        "model": "local-model",
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": 0.7,
        "max_tokens": 256,
        "stream": True,
    }

    start = time.perf_counter()
    first_token_time = None
    full_text = []
    usage = {}
    result = "success"
    notes = ""

    stop_event = threading.Event()
    peak_holder = {"peak_vram": 0}
    sampler = threading.Thread(
        target=sample_gpu_memory,
        args=(stop_event, peak_holder),
        daemon=True,
    )
    sampler.start()

    try:
        with requests.post(API_URL, json=payload, stream=True, timeout=600) as response:
            response.raise_for_status()

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                line = raw_line.strip()
                if not line.startswith("data: "):
                    continue

                data = line[6:].strip()
                if data == "[DONE]":
                    break

                chunk = json.loads(data)

                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    token_piece = delta.get("content")
                    if token_piece:
                        full_text.append(token_piece)
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - start

                if "usage" in chunk and chunk["usage"]:
                    usage = chunk["usage"]

    except Exception as exc:
        result = "error"
        notes = str(exc)

    finally:
        stop_event.set()
        sampler.join(timeout=1)

    total_time = time.perf_counter() - start
    generated_text = "".join(full_text).strip()

    prompt_tokens = usage.get("prompt_tokens", "")
    generated_tokens = usage.get("completion_tokens", "")

    if not prompt_tokens:
        prompt_tokens = count_tokens(prompt_text, add_bos=True)
        if notes:
            notes += " | "
        notes += "prompt_tokens estimated with tokenizer fallback"
    if not generated_tokens:
        generated_tokens = count_tokens(generated_text, add_bos=False)
        if notes:
            notes += " | "
        notes += "generated_tokens estimated with tokenizer fallback"

    if first_token_time is None:
        first_token_time = total_time

    tokens_per_sec = ""
    try:
        if generated_tokens != "" and total_time > 0:
            tokens_per_sec = round(float(generated_tokens) / total_time, 4)
    except Exception:
        tokens_per_sec = ""

    return {
        "prompt_tokens": prompt_tokens,
        "generated_tokens": generated_tokens,
        "time_to_first_token": round(first_token_time, 4),
        "total_response_time": round(total_time, 4),
        "tokens_per_sec": tokens_per_sec,
        "peak_vram": peak_holder["peak_vram"] or "",
        "result": result,
        "notes": notes,
        "generated_text": generated_text,
    }


def main():
    global API_URL, CSV_PATH, RUN_NAME, MODEL, MODEL_PATH, COMMAND, N_GPU_LAYERS, CONTEXT_SIZE, PORT
    
    args = parse_arguments()

    # Update global variables from arguments
    CSV_PATH = Path(args.csv_path)
    RUN_NAME = args.run_name
    MODEL = args.model
    MODEL_PATH = args.model_path
    N_GPU_LAYERS = args.n_gpu_layers
    CONTEXT_SIZE = args.ctx_size
    PORT = args.port
    API_URL = f"http://127.0.0.1:{PORT}/v1/chat/completions"

    COMMAND = (
        f"python -m llama_cpp.server --model {MODEL_PATH} "
        f"--host 127.0.0.1 --port {PORT} --n_gpu_layers {N_GPU_LAYERS} --n_ctx {CONTEXT_SIZE}"
    )

    ensure_csv_header()
    run_date = datetime.now().strftime("%Y-%m-%d")

    for prompt_id, prompt_text in PROMPTS:
        metrics = run_prompt(prompt_text)

        row = [
            run_date,
            RUN_NAME,
            prompt_id,
            prompt_text,
            MODEL,
            MODEL_PATH,
            COMMAND,
            N_GPU_LAYERS,
            CONTEXT_SIZE,
            PORT,
            metrics["prompt_tokens"],
            metrics["generated_tokens"],
            metrics["time_to_first_token"],
            metrics["total_response_time"],
            metrics["tokens_per_sec"],
            metrics["peak_vram"],
            metrics["result"],
            metrics["notes"],
        ]
        append_row(row)

        print(f"\nPrompt {prompt_id} completed.")


if __name__ == "__main__":
    main()
