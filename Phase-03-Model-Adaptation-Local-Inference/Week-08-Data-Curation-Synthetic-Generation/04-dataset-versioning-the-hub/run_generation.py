from generate_pii import generate_pii_dataset
from utils import load_checkpoint, save_final_dataset
import argparse
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate PII synthetic dataset')
    parser.add_argument('--num-examples', type=int, default=1000, help='Number of examples to generate')
    parser.add_argument('--output', type=str, default='pii_dataset.jsonl', help='Output file')
    parser.add_argument('--resume-from', type=str, help='Checkpoint file to resume from')
    args = parser.parse_args()

    # Load checkpoint if resuming
    examples = []
    start_idx = 0
    if args.resume_from:
        if os.path.exists(args.resume_from):
            examples = load_checkpoint(args.resume_from)
            loaded_count = len(examples)
            start_idx = loaded_count
            print(f"Resuming from checkpoint: {loaded_count} examples loaded from {args.resume_from}")
            if loaded_count == 0:
                print(f"WARNING: Checkpoint file {args.resume_from} exists but contains 0 examples!")
        else:
            print(f"ERROR: Checkpoint file {args.resume_from} not found! Starting from scratch.")
            print(f"WARNING: Ignoring --resume-from argument and starting from 0 examples.")
    else:
        print("Starting fresh generation (no resume file specified).")

    # Generate remaining examples
    remaining = args.num_examples - len(examples)
    if remaining > 0:
        print(f"Generating {remaining} more examples...")
        examples = generate_pii_dataset(remaining, start_index=start_idx, initial_examples=examples)

    # Save final dataset
    save_final_dataset(examples, args.output)
