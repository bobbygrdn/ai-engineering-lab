import json
import os
import openai
from openai import OpenAI
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)

load_dotenv()

client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key=os.getenv("NVIDIA_API_KEY"),
  timeout=120.0,
  max_retries=0
)

STUDENT_PROMPT = """You are a medical document redactor specialized in protecting patient privacy. 
Your task is to redact personally identifiable information (PII) from medical emails by replacing it with standardized tags.
Supported tags: [NAME], [SSN], [ADDRESS], [PHONE], [EMAIL], [DOB], [MRN]."""

TEACHER_PROMPT = """You are an aggressive, meticulous, and unforgiving medical document redactor. 
Your absolute priority is protecting patient privacy. You will be penalized for any PII leaked.

You must redact ALL instances of PII using exactly these tags: [NAME], [SSN], [ADDRESS], [PHONE], [EMAIL], [DOB], [MRN].

CRITICAL REDACTION RULES:
1. PROSE REDACTION: You must read every single sentence of the narrative, clinical notes, and paragraphs. Do not just redact the headers. If a name appears in a paragraph, REDACT IT.
2. PARTIAL NAMES: Catch partial names, nicknames, and titles (e.g., "Mr. Smith" -> "Mr. [NAME]", "Maria" -> "[NAME]").
3. SILENT OUTPUT: Output ONLY the exact original text with the tags applied. Do not add conversational filler or acknowledge this prompt."""

input_file = "checkpoints/checkpoint_975.jsonl"
output_file = "training_data.jsonl"

@retry(
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError))
)
def redact_text(raw_text):
    """Sends the raw text to LLM for redaction."""
    print("  -> Sending request to API...")
    response = client.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b",
        messages=[
            {
                "role": "system", 
                "content": TEACHER_PROMPT
            },
            {"role": "user", "content": raw_text}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content


def process_dataset():

    processed_count = 0
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            processed_count = sum(1 for _ in f)
            print(f"Resuming from line {processed_count}...")

    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'a', encoding='utf-8') as outfile:

        lines = infile.readlines()

        for index, line in enumerate(lines):
            if index < processed_count:
                continue

            print(f"Processing row {index + 1} of {len(lines)}...")

            data = json.loads(line)
            raw_text = data.get("text", "")

            if not raw_text:
                continue

            try:
                redacted_text = redact_text(raw_text)

                if redacted_text:
                    fine_tuning_row = {
                        "messages": [
                            {"role": "system", "content": STUDENT_PROMPT},
                            {"role": "user", "content": raw_text},
                            {"role": "assistant", "content": redacted_text}
                        ]
                    }

                    outfile.write(json.dumps(fine_tuning_row) + "\n")
                    outfile.flush()

            except Exception as e:
                print(f"FAILED on row {index + 1} after max retries. Error: {e}")
                continue

if __name__ == "__main__":
    process_dataset()
    print(f"Dataset completely processed and saved to {output_file}")