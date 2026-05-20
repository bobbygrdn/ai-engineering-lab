from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
import difflib

from modules.logic.agentic_logic import classify_support_ticket_with_retries
from modules.utils.exceptions import EmptyPromptError, RateLimitExceededError, RefusalError
from modules.utils.helpers import log_invalid_output
from modules.utils.logging import logger


DEFAULT_INPUT_NAME = "benchmark_emails.json"
DEFAULT_SUMMARY_NAME = "benchmark.md"
DEFAULT_TRACE_NAME = "benchmark_trace.jsonl"
DEFAULT_EMAIL_TIMEOUT_SECONDS = 30
DEFAULT_BATCH_SIZE = 10
DEFAULT_BATCH_PAUSE_SECONDS = 15
DEFAULT_MAX_RETRIES = 3


@dataclass
class BenchmarkResult:
    index: int
    email_text: str
    valid: bool
    cost: float
    error: str | None
    metadata: dict | None
    ground_truth: dict | None = None
    match_priority: bool | None = None
    match_department: bool | None = None
    match_summary: bool | None = None
    exact_match: bool | None = None


def load_emails(input_path: Path) -> list[dict]:
    """Load emails and optional ground-truth labels.

    Returns a list of dicts with keys: `email_text` and `ground_truth` (or None).
    Accepts JSON, JSONL, plain text, and legacy list-of-strings formats.
    """
    raw_text = input_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    def _normalize(item: object) -> dict:
        if isinstance(item, str):
            return {"email_text": item.strip(), "ground_truth": None}
        if isinstance(item, dict):
            text = item.get("email_text") or item.get("text") or ""
            gt = item.get("ground_truth") or item.get("label") or None
            return {"email_text": str(text).strip(), "ground_truth": gt}
        return {"email_text": str(item).strip(), "ground_truth": None}

    normalized: list[dict]
    if input_path.suffix.lower() == ".jsonl":
        items: list[dict] = []
        for line in raw_text.splitlines():
            item = line.strip()
            if not item:
                items.append("")
                continue
            parsed = json.loads(item)
            items.append(parsed)
        normalized = [_normalize(item) for item in items]
    else:
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            normalized = [_normalize(line) for line in raw_text.splitlines()]
        else:
            if isinstance(parsed, list):
                normalized = [_normalize(item) for item in parsed]
            elif isinstance(parsed, dict) and "emails" in parsed and isinstance(parsed["emails"], list):
                normalized = [_normalize(item) for item in parsed["emails"]]
            else:
                normalized = [_normalize(parsed)]

    # Backwards compatibility: if no ground-truth labels are present, return list[str]
    if all(item.get("ground_truth") is None for item in normalized):
        return [item.get("email_text", "") for item in normalized]

    return normalized


def _extract_email_text(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        email_text = item.get("email_text", "")
        return str(email_text).strip()
    return str(item).strip()


def _sanitize_cell(value: str) -> str:
    if not value.strip():
        return "<empty>"
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _append_jsonl(log_path: Path, payload: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _chunked(items: list[str], chunk_size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def _process_email(email_text: str, max_retries: int) -> tuple[bool, float, str | None, dict | None, dict | None]:
    response, metadata = classify_support_ticket_with_retries(
        email_text,
        max_retries=max_retries,
        raise_on_failure=True,
    )

    metadata_dict = metadata.model_dump() if metadata is not None else None
    cost = float(metadata.usage.interaction_price) if metadata is not None else 0.0

    ticket_dict = None
    if response is not None:
        try:
            ticket_dict = response.model_dump() if hasattr(response, "model_dump") else (response if isinstance(response, dict) else None)
        except Exception:
            ticket_dict = None

    if response is not None:
        return True, cost, None, metadata_dict, ticket_dict

    return False, cost, "Invalid output from LLM", metadata_dict, ticket_dict


def _summary_similar(a: str, b: str, threshold: float = 0.80) -> bool:
    if not a or not b:
        return False
    ratio = difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()
    return ratio >= threshold


def _compare_ticket_to_ground_truth(ticket: dict, ground_truth: dict) -> tuple[Optional[bool], Optional[bool], Optional[bool], Optional[bool]]:
    if not ground_truth:
        return None, None, None, None

    gt_priority = (ground_truth.get("priority") or "").strip().lower()
    gt_department = (ground_truth.get("department") or "").strip().lower()
    gt_summary = (ground_truth.get("summary") or "").strip()

    prio = (ticket.get("priority") or "").strip().lower()
    dept = (ticket.get("department") or "").strip().lower()
    summary = (ticket.get("summary") or "").strip()

    match_priority = bool(gt_priority and prio == gt_priority)
    match_department = bool(gt_department and dept == gt_department)
    match_summary = _summary_similar(summary, gt_summary)
    exact_match = bool(match_priority and match_department and match_summary)
    return match_priority, match_department, match_summary, exact_match


def run_benchmark(
    emails: Iterable[str],
    summary_path: Path,
    trace_log_path: Path,
    max_retries: int = 3,
    email_timeout_seconds: int = 120,
    batch_size: int = 10,
    batch_pause_seconds: int = 15,
) -> dict:
    # Normalize emails to dict items with optional ground-truth
    email_items: list[dict] = []
    for item in emails:
        if isinstance(item, str):
            email_items.append({"email_text": item, "ground_truth": None})
        elif isinstance(item, dict):
            email_items.append({"email_text": item.get("email_text") or item.get("text") or "", "ground_truth": item.get("ground_truth") or item.get("label") or None})
        else:
            email_items.append({"email_text": str(item), "ground_truth": None})

    email_list = email_items
    results: list[BenchmarkResult] = []
    valid_count = 0
    valid_cost_total = 0.0
    # ground-truth counters
    gt_total = 0
    match_priority_total = 0
    match_department_total = 0
    match_summary_total = 0
    exact_match_total = 0

    total_batches = max(1, (len(email_list) + batch_size - 1) // batch_size)

    for batch_number, batch in enumerate(_chunked(email_list, batch_size), start=1):
        if batch_number > 1 and batch_pause_seconds > 0:
            logger.info(f"Pausing {batch_pause_seconds}s before batch #{batch_number}")
            print(f"[batch {batch_number}] Cooling down for {batch_pause_seconds}s before the next batch...")
            time.sleep(batch_pause_seconds)

        logger.info(f"Starting batch {batch_number}/{total_batches} with {len(batch)} emails")
        print(f"[batch {batch_number}/{total_batches}] Processing {len(batch)} emails...")

        for batch_index, email_item in enumerate(batch, start=1):
            email_text = email_item.get("email_text", "")
            index = len(results) + 1
            trace_start = {
                "timestamp": datetime.now().isoformat(),
                "event": "email_start",
                "batch_number": batch_number,
                "batch_index": batch_index,
                "index": index,
                "email_text": email_text,
                "ground_truth": email_item.get("ground_truth"),
            }
            _append_jsonl(trace_log_path, trace_start)
            logger.info(f"Benchmark start #{index} (batch {batch_number}, item {batch_index}): {email_text}")
            print(f"[{index}] Processing email...")

            valid = False
            cost = 0.0
            error: str | None = None
            metadata_dict: dict | None = None

            try:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(_process_email, email_text, max_retries)
                try:
                    valid, cost, error, metadata_dict, ticket_dict = future.result(timeout=email_timeout_seconds)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

                if valid:
                    valid_count += 1
                    valid_cost_total += cost
                else:
                    log_invalid_output(email_text, None, error or "Invalid output from LLM")
                print(f"[{index}] Done: {'valid' if valid else 'invalid'}")
            except EmptyPromptError as exc:
                error = str(exc)
                log_invalid_output(email_text, None, error)
            except RefusalError as exc:
                error = str(exc)
                log_invalid_output(email_text, None, error)
            except RateLimitExceededError as exc:
                error = str(exc)
                log_invalid_output(email_text, None, error)
            except concurrent.futures.TimeoutError:
                error = f"Timed out after {email_timeout_seconds} seconds"
                log_invalid_output(email_text, None, error)
                print(f"[{index}] Timeout after {email_timeout_seconds}s, moving on.")
            except Exception as exc:
                error = str(exc)
                log_invalid_output(email_text, None, f"Unexpected benchmark error: {error}")

            # compare to ground-truth if available
            ground_truth = email_item.get("ground_truth")
            match_priority = match_department = match_summary = exact_match = None
            if ground_truth and ticket_dict:
                mp, md, ms, em = _compare_ticket_to_ground_truth(ticket_dict, ground_truth)
                match_priority, match_department, match_summary, exact_match = mp, md, ms, em
                gt_total += 1
                match_priority_total += 1 if mp else 0
                match_department_total += 1 if md else 0
                match_summary_total += 1 if ms else 0
                exact_match_total += 1 if em else 0

            result = BenchmarkResult(
                index=index,
                email_text=email_text,
                valid=valid,
                cost=cost,
                error=error,
                metadata=metadata_dict,
                ground_truth=ground_truth,
                match_priority=match_priority,
                match_department=match_department,
                match_summary=match_summary,
                exact_match=exact_match,
            )
            results.append(result)

            _append_jsonl(
                trace_log_path,
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": "email_result",
                    "batch_number": batch_number,
                    "batch_index": batch_index,
                    **asdict(result),
                },
            )

    total = len(results)
    invalid_count = total - valid_count
    accuracy = (valid_count / total) if total else 0.0
    average_cost = (valid_cost_total / valid_count) if valid_count else 0.0

    # ground-truth aggregate metrics
    priority_accuracy = (match_priority_total / gt_total) if gt_total else None
    department_accuracy = (match_department_total / gt_total) if gt_total else None
    summary_similarity = (match_summary_total / gt_total) if gt_total else None
    exact_match_rate = (exact_match_total / gt_total) if gt_total else None

    summary_markdown = _build_summary_markdown(
        results,
        total,
        valid_count,
        invalid_count,
        accuracy,
        average_cost,
        gt_total,
        priority_accuracy,
        department_accuracy,
        summary_similarity,
        exact_match_rate,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_markdown, encoding="utf-8")

    _append_jsonl(
        trace_log_path,
        {
            "timestamp": datetime.now().isoformat(),
            "event": "benchmark_summary",
            "total": total,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "accuracy": accuracy,
            "average_cost_per_valid_ticket": average_cost,
            "labeled_count": gt_total,
            "priority_accuracy": priority_accuracy,
            "department_accuracy": department_accuracy,
            "summary_similarity_rate": summary_similarity,
            "exact_match_rate": exact_match_rate,
            "summary_path": str(summary_path),
        },
    )

    return {
        "total": total,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "accuracy": accuracy,
        "average_cost_per_valid_ticket": average_cost,
        "labeled_count": gt_total,
        "priority_accuracy": priority_accuracy,
        "department_accuracy": department_accuracy,
        "summary_similarity_rate": summary_similarity,
        "exact_match_rate": exact_match_rate,
        "results": results,
        "summary_path": summary_path,
        "trace_log_path": trace_log_path,
    }


def _build_summary_markdown(
    results: list[BenchmarkResult],
    total: int,
    valid_count: int,
    invalid_count: int,
    accuracy: float,
    average_cost: float,
    gt_total: int = 0,
    priority_accuracy: float | None = None,
    department_accuracy: float | None = None,
    summary_similarity: float | None = None,
    exact_match_rate: float | None = None,
) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        f"- Total emails: {total}",
        f"- Valid outputs: {valid_count}",
        f"- Invalid outputs: {invalid_count}",
        f"- Accuracy: {accuracy:.2%}",
        f"- Average cost per valid ticket: ${average_cost:.6f}",
        "",
        "## Results",
        "",
        "| # | Email | Valid | Cost | Error |",
        "| --- | --- | --- | ---: | --- |",
    ]

    for result in results:
        email_preview = _sanitize_cell(result.email_text)
        if len(email_preview) > 80:
            email_preview = f"{email_preview[:77]}..."
        error_preview = _sanitize_cell(result.error or "")
        if len(error_preview) > 80:
            error_preview = f"{error_preview[:77]}..."
        lines.append(
            f"| {result.index} | {email_preview} | {'Yes' if result.valid else 'No'} | ${result.cost:.6f} | {error_preview} |"
        )

    if gt_total:
        lines.extend([
            "",
            "## Ground-truth Metrics",
            f"- Labeled items: {gt_total}",
            f"- Priority accuracy: {priority_accuracy:.2%}",
            f"- Department accuracy: {department_accuracy:.2%}",
            f"- Summary similarity rate: {summary_similarity:.2%}",
            f"- Exact-match rate (all fields): {exact_match_rate:.2%}",
        ])

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run support ticket benchmark over an email dataset.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default=DEFAULT_INPUT_NAME,
        help="Path to a JSON, JSONL, or plain-text email dataset.",
    )
    parser.add_argument("--summary", default=DEFAULT_SUMMARY_NAME, help="Path to write the markdown summary.")
    parser.add_argument("--trace-log", default=DEFAULT_TRACE_NAME, help="Path to write traceability logs.")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Maximum retry attempts per email.")
    parser.add_argument(
        "--email-timeout",
        type=int,
        default=DEFAULT_EMAIL_TIMEOUT_SECONDS,
        help="Timeout in seconds for each email.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of emails to process per batch.",
    )
    parser.add_argument(
        "--batch-pause",
        type=int,
        default=DEFAULT_BATCH_PAUSE_SECONDS,
        help="Pause in seconds between batches.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input_path)
    summary_path = Path(args.summary)
    trace_log_path = Path(args.trace_log)

    emails = load_emails(input_path)
    if not emails:
        raise SystemExit(f"No emails found in {input_path}")

    summary = run_benchmark(
        emails,
        summary_path,
        trace_log_path,
        max_retries=args.max_retries,
        email_timeout_seconds=args.email_timeout,
        batch_size=args.batch_size,
        batch_pause_seconds=args.batch_pause,
    )
    print(f"Benchmark complete. Summary written to {summary['summary_path']}")
    print(f"Trace log written to {summary['trace_log_path']}")
    print(f"Accuracy: {summary['accuracy']:.2%}")
    print(f"Average cost per valid ticket: ${summary['average_cost_per_valid_ticket']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())