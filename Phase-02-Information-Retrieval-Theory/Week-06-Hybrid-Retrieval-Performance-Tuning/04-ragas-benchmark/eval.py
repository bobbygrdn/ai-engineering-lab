import os
import time
import json
import csv
import uuid
from pathlib import Path
from datetime import datetime
from itertools import islice
from typing import Iterable, List

import pandas as pd
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    ContextualPrecisionMetric,
    AnswerRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.evaluate import AsyncConfig, CacheConfig, DisplayConfig

from llm import complete
from vector_store import retrieve_similar
from logger import get_logger

os.environ["DEEPEVAL_TIMEOUT"] = "300"
logger = get_logger(__name__)

CACHE_PATH = Path("cached_test_cases.json")


def _load_cached_cases() -> list[dict] | None:
    if CACHE_PATH.is_file():
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cached_cases(cases: list[dict]) -> None:
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)


def build_eval_set(
    df: pd.DataFrame,
    *,
    max_cases: int | None = None,
) -> tuple[list[LLMTestCase], list[dict]]:
    """
    Build LLMTestCase objects and a parallel list of metadata for debugging.
    """
    cached = _load_cached_cases()
    if cached:
        if max_cases is not None and len(cached) > max_cases:
            logger.info(
                f"Loaded {len(cached)} cached test cases – truncating to {max_cases} "
                f"as requested."
            )
            cached = cached[:max_cases]
        else:
            logger.info(f"Loaded {len(cached)} cached test cases.")

        print(f"Loaded {len(cached)} cached test cases.")
        cases = [LLMTestCase(**c["case"]) for c in cached]
        metas = [c["meta"] for c in cached]
        return cases, metas

    test_cases: list[LLMTestCase] = []
    meta_infos: list[dict] = []
    logger.info(f"Building evaluation set from {len(df)} rows.")
    for _, row in df.iterrows():
        retrieved = retrieve_similar(
            question=f"What is the plot of {row.title}?",
            top_k=5,
        )
        retrieved_texts = [doc["text"] for doc in retrieved]

        context = "\n".join(retrieved_texts)
        prompt = f"Context:\n{context}\n\nQuestion: What is the plot of {row.title}?\nAnswer:"
        answer = complete(prompt)

        case = LLMTestCase(
            input=f"What is the plot of {row.title}?",
            actual_output=answer,
            expected_output=row.overview,
            retrieval_context=retrieved_texts,
        )
        test_cases.append(case)

        meta_infos.append(
            {
                "title": row.title,
                "query": f"What is the plot of {row.title}?",
                "retrieved_context": json.dumps(retrieved_texts, ensure_ascii=False),
                "actual_output": answer,
                "expected_output": row.overview,
            }
        )

    _save_cached_cases(
        [{"case": c.dict(), "meta": m} for c, m in zip(test_cases, meta_infos)]
    )
    logger.info(f"Cached {len(test_cases)} test cases for future runs.")
    print(f"Cached {len(test_cases)} test cases for future runs.")
    return test_cases, meta_infos


def chunked(seq: Iterable, size: int) -> Iterable[List]:
    """Yield successive `size`‑length chunks from `seq`."""
    it = iter(seq)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk


def run_evaluation(
    df: pd.DataFrame,
    *,
    chunk_size: int = 20,
    throttle_seconds: float = 4.0,
    max_concurrency: int = 10,
) -> None:
    """
    Run DeepEval on the supplied DataFrame.
    """
    logger.info(f"Running evaluation on {len(df)} test cases.")

    test_cases, meta_infos = build_eval_set(df, max_cases=len(df))

    run_id = uuid.uuid4().hex

    async_cfg = AsyncConfig(max_concurrent=max_concurrency)
    cache_cfg = CacheConfig(use_cache=True, write_cache=True)
    display_cfg = DisplayConfig(print_results=False)

    all_chunk_results = []

    for i, chunk in enumerate(chunked(test_cases, chunk_size), start=1):
        logger.info(f"▶️  Evaluating chunk {i} ({len(chunk)} cases)…")
        print(f"Evaluating chunk {i} ({len(chunk)} cases)…")

        chunk_result = evaluate(
            test_cases=chunk,
            metrics=[
                FaithfulnessMetric(model="gpt-4o-mini"),
                AnswerRelevancyMetric(model="gpt-4o-mini"),
                ContextualPrecisionMetric(model="gpt-4o-mini"),
            ],
            async_config=async_cfg,
            cache_config=cache_cfg,
            display_config=display_cfg,
        )

        all_chunk_results.append(chunk_result)
        logger.info(f"Chunk {i} finished.")

        if len(test_cases) > chunk_size and i * chunk_size < len(test_cases):
            logger.info(f"Sleeping for {throttle_seconds} seconds.")
            print(f"Sleeping for {throttle_seconds} seconds...")
            time.sleep(throttle_seconds)

    if not all_chunk_results:
        logger.error("No chunk succeeded – nothing to aggregate.")
        print("Evaluation failed – no results.")
        return

    faithfulness_vals = []
    answer_relevancy_vals = []
    contextual_precision_vals = []
    csv_rows: list[dict] = []

    meta_iter = iter(meta_infos)

    for r in all_chunk_results:
        for case_result in r.test_results:
            scores = {m.name: m.score for m in case_result.metrics_data}
            f_score = scores.get("Faithfulness", 0.0)
            a_score = scores.get("Answer Relevancy", 0.0)
            c_score = scores.get("Contextual Precision", 0.0)

            faithfulness_vals.append(f_score)
            answer_relevancy_vals.append(a_score)
            contextual_precision_vals.append(c_score)

            meta = next(meta_iter)
            csv_rows.append(
                {
                    "sample_id": len(csv_rows) + 1,
                    "title": meta["title"],
                    "query": meta["query"],
                    "retrieved_context": meta["retrieved_context"],
                    "actual_output": meta["actual_output"],
                    "expected_output": meta["expected_output"],
                    "faithfulness": f_score,
                    "answer_relevancy": a_score,
                    "context_precision": c_score,
                    "chunk_id": i,
                    "run_id": run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "model": "gpt-4o-mini",
                }
            )

    agg = {
        "faithfulness": sum(faithfulness_vals) / len(faithfulness_vals),
        "answer_relevance": sum(answer_relevancy_vals) / len(answer_relevancy_vals),
        "context_precision": sum(contextual_precision_vals) / len(contextual_precision_vals),
    }

    csv_path = Path("evaluation_results.csv")
    fieldnames = [
        "sample_id",
        "title",
        "query",
        "retrieved_context",
        "actual_output",
        "expected_output",
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "chunk_id",
        "run_id",
        "timestamp",
        "model",
    ]

    write_header = not csv_path.is_file()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)

        summary_row = {
            "sample_id": "AVERAGE",
            "title": "",
            "query": "",
            "retrieved_context": "",
            "actual_output": "",
            "expected_output": "",
            "faithfulness": agg["faithfulness"],
            "answer_relevancy": agg["answer_relevance"],
            "context_precision": agg["context_precision"],
            "chunk_id": "",
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "model": "gpt-4o-mini",
        }
        writer.writerow(summary_row)

    print(f"Evaluation completed. Results written to {csv_path}.")

    logger.info(
        f"Overall scores – Faithfulness: {agg['faithfulness']:.3f}, "
        f"Answer Relevance: {agg['answer_relevance']:.3f}, "
        f"Context Precision: {agg['context_precision']:.3f}"
    )