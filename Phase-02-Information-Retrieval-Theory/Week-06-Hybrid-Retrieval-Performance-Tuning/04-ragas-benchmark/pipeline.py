import argparse
import logging
import pandas as pd
from vector_store import _ensure_collection
from eval import run_evaluation, logger as eval_logger
from logger import get_logger

logger = get_logger(__name__)

def parse_args() -> argparse.Namespace:
    """Parse command‑line arguments."""
    parser = argparse.ArgumentParser(
        description="RAG benchmark pipeline – sample movies, upsert to Qdrant, and run DeepEval."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=300,
        help="Number of rows to sample for evaluation (0 = use full dataset).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=20,
        help="Size of each evaluation chunk (must match eval.run_evaluation).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Maximum concurrent LLM calls inside a chunk.",
    )
    parser.add_argument(
        "--throttle",
        type=float,
        default=4.0,
        help="Seconds to sleep between chunks (rate‑limit mitigation).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity for the pipeline.",
    )
    return parser.parse_args()


def main(max_samples: int = 300,
         chunk_size: int = 20,
         concurrency: int = 10,
         throttle: float = 4.0) -> None:
    """
    Core pipeline logic – kept separate from CLI parsing so it can be
    called programmatically (e.g., from notebooks or tests).
    """
    logger.info(f"Pipeline started – sampling up to {max_samples} items")
    csv_path = r"data/moviesTMBD.csv"
    df = pd.read_csv(csv_path)

    logger.info(f"Loaded {len(df)} rows from {csv_path}")

    _ensure_collection(df)
    logger.info(f"Collection ensured for {len(df)} rows")

    if max_samples and max_samples < len(df):
        df = df.sample(n=max_samples, random_state=42).reset_index(drop=True)
        print(f"🔎 Sampling {max_samples} rows for evaluation (out of {len(df)} total).")
        logger.info(f"Sampling {max_samples} rows for evaluation (out of {len(df)} total).")
    else:
        print(f"🔎 Using the full dataset ({len(df)} rows).")
        logger.info(f"Using the full dataset ({len(df)} rows).")

    logger.info("Starting evaluation...")
    run_evaluation(
        df,
        chunk_size=chunk_size,
        throttle_seconds=throttle,
        max_concurrency=concurrency,
    )
    logger.info("Evaluation completed.")


if __name__ == "__main__":
    args = parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    main(
        max_samples=args.samples,
        chunk_size=args.chunk_size,
        concurrency=args.concurrency,
        throttle=args.throttle,
    )