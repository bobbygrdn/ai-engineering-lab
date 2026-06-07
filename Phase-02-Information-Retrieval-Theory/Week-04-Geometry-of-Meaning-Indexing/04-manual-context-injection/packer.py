from typing import List, Dict
from tokens import count_tokens

def group_neighborhoods(chunks: List[Dict]) -> List[Dict]:
    """
    Group contiguous chunks per document into neighborhoods.
    Each chunk: {'doc_id': str, 'chunk_id': int, 'text': str, 'score': float}
    Returns neighborhoods: {'doc_id','chunk_ids':[...], 'chunks':[...], 'score', 'text','token_count'}
    Deterministic ordering: sorted by doc_id then chunk_id.
    """
    chunks_sorted = sorted(chunks, key=lambda c: (c['doc_id'], c['chunk_id']))
    neighborhoods = []
    current = None

    for chunk in chunks_sorted:
        if current is None or chunk["doc_id"] != current["doc_id"] or chunk["chunk_id"] != current["chunk_ids"][-1] + 1:
            if current:
                neighborhoods.append(current)
            current = {
                "doc_id": chunk["doc_id"],
                "chunk_ids": [chunk["chunk_id"]],
                "chunks": [chunk],
                "score": chunk.get("score", 0.0),
            }
        else:
            current["chunk_ids"].append(chunk["chunk_id"])
            current["chunks"].append(chunk)
            current["score"] += chunk.get("score", 0.0)
    
    if current:
        neighborhoods.append(current)

    for n in neighborhoods:
        n["text"] = "\n\n".join(c["text"] for c in n["chunks"])
        n["token_count"] = count_tokens(n["text"])

    return neighborhoods

def trim_neighborhood_to_fit(neighborhood: Dict, max_tokens: int) -> Dict:
    """
    If the full neighborhood is too large, pick highest-score chunks deterministically
    until token budget fits. Returns a new neighborhood or None if nothing fits.
    """
    chunks = sorted(neighborhood["chunks"], key=lambda c: (-c.get("score", 0.0), c["chunk_id"]))
    selected = []
    total_tokens = 0

    for chunk in chunks:
        tokens = count_tokens(chunk["text"])
        if total_tokens + tokens > max_tokens:
            continue
        selected.append(chunk)
        total_tokens += tokens
    if not selected:
        return None
    
    new = {
        "doc_id": neighborhood["doc_id"],
        "chunk_ids": [c["chunk_id"] for c in selected],
        "chunks": selected,
        "score": sum(c.get("score", 0.0) for c in selected),
        "text": "\n\n".join(c["text"] for c in selected),
        "token_count": total_tokens
    }
    return new

def pack_neighborhoods(neighborhoods: List[Dict], budget_for_retrieved: int) -> List[Dict]:
    """
    Select neighborhoods to maximize utility under token budget.
    Strategy: sort by score_density = score / token_count, deterministic tie-breakers.
    If a neighborhood doesn't fit, attempt to trim it.
    """
    for n in neighborhoods:
        n["density"] = (n["score"] / n["token_count"]) if n["token_count"] > 0 else 0.0

    neighborhoods_sorted = sorted(
        neighborhoods, 
        key=lambda n: (-n["density"], -n["score"], n["doc_id"], n["chunk_ids"][0])
    )

    selected = []
    remaining = budget_for_retrieved
    for n in neighborhoods_sorted:
        if n["token_count"] <= remaining:
            selected.append(n)
            remaining -= n["token_count"]
            continue
        trimmed = trim_neighborhood_to_fit(n, remaining)
        if trimmed:
            selected.append(trimmed)
            remaining -= trimmed["token_count"]
    return selected