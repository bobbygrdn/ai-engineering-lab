import argparse
import json
import os

from query_with_filters import query_index
from packer import group_neighborhoods, pack_neighborhoods
from prompt_composer import compose_system_prompt, system_overhead_tokens
from tokens import count_tokens

MODEL_CONTEXT_LIMIT = 4096
RESPONSE_RESERVE = 512
DEFAULT_MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_INSTRUCTIONS = (
    "You are an assistant that MUST cite evidence from RETRIEVED EVIDENCE.\n"
    "If no evidence is available, say you don't know.\n"
)


def _normalize_namespace(namespace):
    if namespace in (None, "", "__default__"):
        return None
    return namespace


def _chunk_from_match(match):
    fields = match.get("fields", {})
    text = fields.get("chunk_text")
    if not text:
        return None

    doc_id = fields.get("doc_id") or fields.get("ticket_id") or match.get("id")
    chunk_id = fields.get("chunk_id")
    if chunk_id is None:
        chunk_id = 0

    return {
        "doc_id": str(doc_id),
        "chunk_id": int(chunk_id),
        "text": text,
        "score": float(match.get("score") or 0.0),
    }


def build_context_prompt(query_text, filter_obj=None, top_k=10, namespace=None):
    matches = query_index(
        query_text,
        filter_obj=filter_obj or {},
        top_k=top_k,
        namespace=_normalize_namespace(namespace),
        fields=["doc_id", "chunk_id", "chunk_text", "ticket_type", "ticket_priority", "date_ts"],
    )

    chunks = []
    seen = set()
    for match in matches:
        chunk = _chunk_from_match(match)
        if chunk is None:
            continue
        key = (chunk["doc_id"], chunk["chunk_id"], chunk["text"])
        if key in seen:
            continue
        seen.add(key)
        chunks.append(chunk)

    neighborhoods = group_neighborhoods(chunks)
    budget_for_retrieved = (
        MODEL_CONTEXT_LIMIT
        - RESPONSE_RESERVE
        - system_overhead_tokens(SYSTEM_INSTRUCTIONS)
        - count_tokens(query_text)
    )
    selected = pack_neighborhoods(neighborhoods, budget_for_retrieved)
    system_prompt = compose_system_prompt(SYSTEM_INSTRUCTIONS, selected)

    return {
        "system_prompt": system_prompt,
        "selected": selected,
        "retrieved_tokens": sum(n["token_count"] for n in selected),
        "budget_for_retrieved": budget_for_retrieved,
        "matches": matches,
    }


def call_model(system_prompt, query_text, model_name=None):
    model_name = model_name or DEFAULT_MODEL_NAME
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "model": model_name,
            "content": None,
            "skipped": True,
            "reason": "OPENAI_API_KEY is not set",
        }

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install the openai package to enable model calls.") from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query_text},
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return {
        "model": model_name,
        "content": content,
        "skipped": False,
        "response": response,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--namespace", default=None)
    parser.add_argument("--filter-json", default="{}")
    parser.add_argument("--model", default=None, help="Optional OpenAI model name used for the final answer.")
    parser.add_argument("--write-prompt", default=None, help="Optional path to write the composed system prompt.")
    parser.add_argument("--invoke-model", action="store_true", help="Call the model after building the prompt.")
    args = parser.parse_args()

    filter_obj = json.loads(args.filter_json)
    result = build_context_prompt(
        args.query,
        filter_obj=filter_obj,
        top_k=args.topk,
        namespace=args.namespace,
    )

    if args.write_prompt:
        with open(args.write_prompt, "w", encoding="utf-8") as handle:
            handle.write(result["system_prompt"])
            handle.write("\n")

    print("=== budget ===")
    print(f"query_tokens={count_tokens(args.query)}")
    print(f"selected_retrieved_tokens={result['retrieved_tokens']}")
    print(f"budget_for_retrieved={result['budget_for_retrieved']}")
    print()
    print("=== system_prompt ===")
    print(result["system_prompt"])

    if args.invoke_model:
        model_result = call_model(result["system_prompt"], args.query, model_name=args.model)
        print()
        print("=== model ===")
        print(f"model={model_result['model']}")
        if model_result.get("skipped"):
            print(model_result["reason"])
        else:
            print(model_result["content"])


if __name__ == "__main__":
    main()