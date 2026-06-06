import os
import time
import json
import csv
import argparse
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from pinecone import Pinecone
from datetime import datetime, timezone

load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
INDEX_NAME = os.environ.get("INDEX_NAME")
NAMESPACE = os.environ.get("NAMESPACE", None)

if not PINECONE_API_KEY or not INDEX_NAME:
    raise SystemExit("Set PINECONE_API_KEY and INDEX_NAME environment variables.")

client = Pinecone(api_key=PINECONE_API_KEY)
index_info = client.describe_index(INDEX_NAME)
index = client.Index(host=index_info.host)

# Default fields to return when user does not specify --fields
DEFAULT_FIELDS = ["ticket_type", "ticket_priority", "chunk_text", "date_ts"]


def _normalize_match(m: Any) -> Dict:
    # Support different SDK shapes: {'id'|'_id'}, 'score'|'_score', 'metadata', 'fields'
    if isinstance(m, dict):
        mid = m.get("id") or m.get("_id")
        score = m.get("score") or m.get("_score")
        fields = m.get("fields") or m.get("metadata") or {}
    else:
        mid = getattr(m, "id", None) or getattr(m, "_id", None)
        score = getattr(m, "score", None) or getattr(m, "_score", None)
        fields = getattr(m, "fields", None) or getattr(m, "metadata", None) or {}
    norm_fields = _normalize_metadata_values(fields or {})
    return {"id": mid, "score": score, "fields": norm_fields}


def _search_with_search_method(index, query_text, top_k, filter_obj, namespace, fields: Optional[List[str]]):
    query_payload = {"inputs": {"text": query_text}, "top_k": top_k, "filter": filter_obj or {}}
    # If namespace is None -> omit namespace argument so Pinecone uses the empty/default namespace.
    if namespace is None:
        if fields:
            return index.search(query=query_payload, fields=fields)
        return index.search(query=query_payload)
    ns = namespace or "__default__"
    if fields:
        return index.search(namespace=ns, query=query_payload, fields=fields)
    return index.search(namespace=ns, query=query_payload)


def _search_with_query_body(index, query_text, top_k, filter_obj, namespace, fields: Optional[List[str]]):
    query_part = {"inputs": {"text": query_text}, "top_k": top_k, "filter": filter_obj or {}}
    if fields:
        query_part["fields"] = fields
    body = {"query": query_part}
    # Include namespace only when explicitly provided (non-None)
    if namespace is not None:
        body["namespace"] = namespace or "__default__"
    try:
        return index.query(body)
    except TypeError:
        return index.query(json.dumps(body))


def _extract_hits(resp: Any) -> List[Any]:
    # Handle multiple SDK/response shapes
    if isinstance(resp, dict):
        if "matches" in resp:
            return resp["matches"] or []
        if "result" in resp and isinstance(resp["result"], dict):
            return resp["result"].get("hits", []) or []
    else:
        # object with attributes (e.g., SearchRecordsResponse)
        if hasattr(resp, "matches"):
            return getattr(resp, "matches") or []
        if hasattr(resp, "result") and getattr(resp, "result") and isinstance(getattr(resp, "result"), dict):
            return (getattr(resp, "result") or {}).get("hits", []) or []
        if hasattr(resp, "result") and getattr(resp, "result") and hasattr(getattr(resp, "result"), "hits"):
            return getattr(getattr(resp, "result"), "hits") or []
    return []


def _normalize_metadata_values(d: Dict[str, Any]) -> Dict[str, Any]:
    # Convert string booleans "true"/"false" to True/False, convert numeric-ish date_ts to int
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            low = v.strip().lower()
            if low == "true":
                out[k] = True
                continue
            if low == "false":
                out[k] = False
                continue
            # numeric-looking date_ts
            if k == "date_ts":
                if v.isdigit():
                    out[k] = int(v)
                    continue
            # try to parse ISO date to epoch for date_ts
            if k == "date_ts":
                try:
                    # accept ISO dates like "2024-01-02" or full isoformat
                    dt = datetime.fromisoformat(v)
                    out[k] = int(dt.replace(tzinfo=timezone.utc).timestamp())
                    continue
                except Exception:
                    pass
        # keep as-is for all other cases
        out[k] = v
    return out


def query_index(
    query_text: str,
    filter_obj: Dict = None,
    top_k: int = 10,
    namespace: str = None,
    fields: Optional[List[str]] = None,
    dump_json_path: Optional[str] = None,
    dump_csv_path: Optional[str] = None,
) -> List[Dict]:
    start = time.time()
    if hasattr(index, "search"):
        resp = _search_with_search_method(index, query_text, top_k, filter_obj, namespace, fields)
    else:
        resp = _search_with_query_body(index, query_text, top_k, filter_obj, namespace, fields)

    hits = _extract_hits(resp)
    matches = [_normalize_match(h) for h in hits]

    elapsed_ms = int((time.time() - start) * 1000)
    print(f"Query: {query_text!r}")
    print(f"Filter: {json.dumps(filter_obj or {}, ensure_ascii=False)}")
    print(f"Fields requested: {fields or []}")
    print(f"Top-k requested: {top_k}, returned: {len(matches)}, latency_ms: {elapsed_ms}")
    for i, m in enumerate(matches[:top_k], start=1):
        print(
            f" {i}. id={m['id']} score={m['score']} fields={json.dumps(m['fields'], ensure_ascii=False, default=str)}"
        )

    # If no hits, print raw response and optionally dump to file for auditing
    if not hits:
        try:
            raw_json = json.dumps(resp, default=lambda o: getattr(o, "__dict__", str(o)), ensure_ascii=False, indent=2)
            print("RAW_RESPONSE:", raw_json)
        except Exception:
            print("RAW_RESPONSE_REPR:", repr(resp))
        if dump_json_path:
            try:
                with open(dump_json_path, "w", encoding="utf-8") as fh:
                    json.dump(resp, fh, default=lambda o: getattr(o, "__dict__", str(o)), ensure_ascii=False, indent=2)
                print(f"Wrote raw response to {dump_json_path}")
            except Exception as e:
                print("Failed to write raw response:", e)

    # If dump_csv_path provided, write normalized matches to CSV (one row per match)
    if dump_csv_path and matches:
        try:
            # Build CSV header: id, score, then requested fields (or default fields)
            csv_fields = fields or DEFAULT_FIELDS
            header = ["id", "score"] + csv_fields
            with open(dump_csv_path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
                writer.writeheader()
                for m in matches:
                    row = {"id": m["id"], "score": m["score"]}
                    for f in csv_fields:
                        val = m["fields"].get(f)
                        # convert lists/dicts to JSON string for CSV readability
                        if isinstance(val, (dict, list)):
                            row[f] = json.dumps(val, ensure_ascii=False)
                        else:
                            row[f] = val
                    writer.writerow(row)
            print(f"Wrote {len(matches)} matches to CSV: {dump_csv_path}")
        except Exception as e:
            print("Failed to write CSV:", e)

    return matches


def parse_filter(s: str) -> Dict:
    if not s:
        return {}
    return json.loads(s)


def parse_fields(s: str) -> List[str]:
    if not s:
        return []
    return [f.strip() for f in s.split(",") if f.strip()]


def parse_date_arg(s: Optional[str]) -> Optional[int]:
    """
    Accept either an integer epoch string, or an ISO date string 'YYYY-MM-DD' or full ISO.
    Returns epoch seconds (int) or None.
    """
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    try:
        dt = datetime.fromisoformat(s)
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid date value: {s}")


def merge_date_range_into_filter(filter_obj: Dict, from_ts: Optional[int], to_ts: Optional[int]) -> Dict:
    if not from_ts and not to_ts:
        return filter_obj
    date_clause: Dict[str, Any] = {}
    if from_ts is not None:
        date_clause["$gte"] = from_ts
    if to_ts is not None:
        date_clause["$lte"] = to_ts
    merged = dict(filter_obj or {})
    merged["date_ts"] = date_clause
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", "-q", required=True, help="Natural language query string.")
    parser.add_argument(
        "--filter-json",
        "-f",
        default="{}",
        help='Filter JSON (e.g. \'{"ticket_type":{"$eq":"Billing inquiry"}}\').',
    )
    parser.add_argument("--topk", "-k", type=int, default=10)
    parser.add_argument(
        "--namespace",
        "-n",
        default=NAMESPACE,
        help="Namespace string; omit or set to '__default__' or empty to use the index empty/default namespace.",
    )
    parser.add_argument(
        "--fields",
        "-F",
        default="",
        help="Comma-separated list of fields to return (e.g. ticket_type,ticket_priority,chunk_text). Defaults to a small audit set.",
    )
    parser.add_argument("--dump-json", "-D", default=None, help="Optional path to save raw response JSON when 0 hits are returned.")
    parser.add_argument("--dump-csv", "-C", default=None, help="Optional path to save normalized matches as CSV (one row per match).")
    parser.add_argument("--date-from", default=None, help="Filter: start date for date_ts (ISO YYYY-MM-DD or epoch seconds).")
    parser.add_argument("--date-to", default=None, help="Filter: end date for date_ts (ISO YYYY-MM-DD or epoch seconds).")
    args = parser.parse_args()

    filter_obj = parse_filter(args.filter_json)
    fields = parse_fields(args.fields) or DEFAULT_FIELDS

    # Map '__default__' or empty string -> None to omit namespace param (use empty/default namespace)
    ns_arg = args.namespace
    if ns_arg == "__default__" or ns_arg == "":
        namespace = None
    else:
        namespace = ns_arg

    # Parse date-from / date-to into epoch seconds and merge into filter
    date_from_ts = parse_date_arg(args.date_from) if args.date_from else None
    date_to_ts = parse_date_arg(args.date_to) if args.date_to else None
    if date_from_ts or date_to_ts:
        filter_obj = merge_date_range_into_filter(filter_obj, date_from_ts, date_to_ts)

    # Print basic info for debugging so you can verify index/host/namespace used
    print(f"INDEX_NAME={INDEX_NAME!r} host={index_info.host!r} using namespace={namespace!r}")

    query_index(
        args.query,
        filter_obj=filter_obj,
        top_k=args.topk,
        namespace=namespace,
        fields=fields,
        dump_json_path=args.dump_json,
        dump_csv_path=args.dump_csv,
    )