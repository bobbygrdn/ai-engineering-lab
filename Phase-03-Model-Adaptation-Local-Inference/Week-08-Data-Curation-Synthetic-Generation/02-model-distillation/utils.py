import json
import os
import re
from datetime import datetime

def save_checkpoint(examples, count, checkpoint_dir='checkpoints'):
    """Save progress checkpoint"""
    if not os.path.exists(checkpoint_dir):
        os.makedirs(checkpoint_dir)
    
    filename = os.path.join(checkpoint_dir, f'checkpoint_{count}.jsonl')
    with open(filename, 'w') as f:
        for example in examples:
            f.write(json.dumps(example) + '\n')
    print(f"Checkpoint saved: {count} examples to {filename}")

def load_checkpoint(checkpoint_file):
    """Load examples from checkpoint"""
    examples = []
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"Warning: Could not parse line in checkpoint: {line[:50]}... Error: {e}")
    return examples

def save_final_dataset(examples, filename='pii_dataset.jsonl'):
    """Save final dataset"""
    with open(filename, 'w') as f:
        for example in examples:
            f.write(json.dumps(example) + '\n')
    print(f"Dataset saved: {len(examples)} examples to {filename}")

def validate_pii_content(text):
    """Check that generated text contains sufficient PII"""
    patterns = {
        'name': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
        'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        'address': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b',
        'mrn': r'\b\d{3}-?\d{2}-?\d{4}\b',
    }
    found_types = []
    for p_type, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            found_types.append(p_type)
    return len(found_types) >= 2