import json
import os
import threading
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from modules.utils.interactions import record_event


DEFAULT_MEMORY_PATH = os.path.join("logs", "memories.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Instruction to request structured JSON write-backs from the LLM.
WRITEBACK_INSTRUCTION = (
    "If you want to persist updates to the agent's durable memory, output a JSON array of patches"
    " prefixed by the token `PATCHES:`. Each patch must be one of:\n"
    "  {\"op\":\"upsert\", \"type\":\"preferences\", \"content\": {...}, \"importance\":0.7}\n"
    "  {\"op\":\"delete\", \"id\": \"...\"}\n"
    "Only output the PATCHES array when you intend to modify durable state."
)


@dataclass
class TypedMemory:
    id: str
    type: str
    content: Dict[str, Any]
    created_at: str
    last_accessed: str
    importance: float
    tags: List[str]
    token_count: int
    version: int = 1


class DurableMemoryStore:
    """A simple single-file durable typed-memory store.

    - Persists to a JSON list at DEFAULT_MEMORY_PATH by default.
    - Provides add/upsert/delete, hydration with attention zones, and
      probabilistic retrieval based on recency+importance.
    """

    def __init__(self, path: str = DEFAULT_MEMORY_PATH, token_budget: int = 4000):
        self.path = path
        self.token_budget = token_budget
        self._lock = threading.Lock()
        self._memories: List[TypedMemory] = []
        self._load()

    def _ensure_dir(self):
        d = os.path.dirname(self.path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    def _persist(self):
        self._ensure_dir()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([asdict(m) for m in self._memories], f, indent=2)

    def _load(self):
        if not os.path.exists(self.path):
            self._memories = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._memories = [TypedMemory(**item) for item in data]
        except Exception:
            self._memories = []

    def add_memory(
        self,
        mtype: str,
        content: Dict[str, Any],
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        token_count: int = 0,
        id: Optional[str] = None,
    ) -> TypedMemory:
        with self._lock:
            mid = id or str(uuid.uuid4())
            now = _now_iso()
            mem = TypedMemory(
                id=mid,
                type=mtype,
                content=content,
                created_at=now,
                last_accessed=now,
                importance=float(importance),
                tags=tags or [],
                token_count=int(token_count),
            )
            self._memories.append(mem)
            self._persist()
            return mem

    def upsert_memory_by_id(self, id: str, **kwargs) -> Optional[TypedMemory]:
        with self._lock:
            for i, m in enumerate(self._memories):
                if m.id == id:
                    for k, v in kwargs.items():
                        if hasattr(m, k):
                            setattr(m, k, v)
                    m.last_accessed = _now_iso()
                    m.version += 1
                    self._memories[i] = m
                    self._persist()
                    return m
            return None

    def delete_memory(self, id: str) -> bool:
        with self._lock:
            for i, m in enumerate(self._memories):
                if m.id == id:
                    del self._memories[i]
                    self._persist()
                    return True
            return False

    def list_memories(self, types: Optional[List[str]] = None) -> List[TypedMemory]:
        if types is None:
            return list(self._memories)
        return [m for m in self._memories if m.type in types]

    def _recency_score(self, mem: TypedMemory) -> float:
        try:
            created = datetime.fromisoformat(mem.created_at)
            age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
            # recent -> score near 1. older -> approaches 0
            return 1.0 / (1.0 + age_seconds / 3600.0)
        except Exception:
            return 0.0

    def _score(self, mem: TypedMemory) -> float:
        # weighted combination
        recency = self._recency_score(mem)
        return 0.6 * float(mem.importance) + 0.4 * recency

    def hydrate(
        self,
        types: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        top_pct: float = 0.25,
        bottom_pct: float = 0.10,
    ) -> Dict[str, List[TypedMemory]]:
        """Return memories organized into attention zones: top, middle, bottom.

        - top: highest-scoring items up to top_pct of token budget
        - bottom: additional high-importance items reserved at end (bottom_pct)
        - middle: fill the remaining budget
        """
        if max_tokens is None:
            max_tokens = self.token_budget

        candidates = self.list_memories(types)
        scored = sorted(candidates, key=lambda m: self._score(m), reverse=True)

        top_tokens = int(max_tokens * float(top_pct))
        bottom_tokens = int(max_tokens * float(bottom_pct))
        middle_tokens = max_tokens - top_tokens - bottom_tokens

        top: List[TypedMemory] = []
        middle: List[TypedMemory] = []
        bottom: List[TypedMemory] = []

        tcur = 0
        for m in scored:
            if tcur < top_tokens and (tcur + m.token_count) <= top_tokens:
                top.append(m)
                tcur += m.token_count

        # assign bottom: select highest-importance items not already in top
        remaining = [m for m in scored if m not in top]
        bcur = 0
        for m in remaining:
            if bcur < bottom_tokens and (bcur + m.token_count) <= bottom_tokens:
                bottom.append(m)
                bcur += m.token_count

        # middle: fill from remaining after removing bottom
        used = set([m.id for m in top + bottom])
        mcur = 0
        for m in scored:
            if m.id in used:
                continue
            if (mcur + m.token_count) <= middle_tokens:
                middle.append(m)
                mcur += m.token_count

        ordered = top + middle + bottom
        # update last_accessed for returned items
        now = _now_iso()
        with self._lock:
            idset = {m.id for m in ordered}
            for mem in self._memories:
                if mem.id in idset:
                    mem.last_accessed = now
            self._persist()

        return {"top": top, "middle": middle, "bottom": bottom, "ordered": ordered}

    def retrieve_probabilistic(self, types: Optional[List[str]] = None, k: int = 5) -> List[TypedMemory]:
        """Return up to k memories sampled by score-weighted probability.

        Simple softmax over scores to produce sampling distribution.
        """
        import math
        candidates = self.list_memories(types)
        scored = [(m, self._score(m)) for m in candidates]
        if not scored:
            return []
        max_s = max(s for _, s in scored)
        exps = [(m, math.exp(s - max_s)) for m, s in scored]
        total = sum(e for _, e in exps)
        probs = [(m, e / total) for m, e in exps]
        # deterministic: pick top-k by probability mass
        probs_sorted = sorted(probs, key=lambda p: p[1], reverse=True)
        return [m for m, _ in probs_sorted[:k]]

    def apply_patches(self, patches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply structured JSON patches produced by LLM.

        Patch format examples:
          {"op":"upsert","type":"preferences","id":"...","content":{...},"importance":0.7}
          {"op":"delete","id":"..."}

        Returns list of results for each patch.
        """
        results = []
        for p in patches:
            op = p.get("op")
            if op == "upsert":
                mid = p.get("id")
                if mid:
                    m = self.upsert_memory_by_id(mid, content=p.get("content", {}), importance=p.get("importance", 0.5), token_count=p.get("token_count", 0))
                    results.append({"op": "upsert", "id": mid, "ok": bool(m)})
                else:
                    mem = self.add_memory(p.get("type", "preferences"), p.get("content", {}), importance=p.get("importance", 0.5), tags=p.get("tags", []), token_count=p.get("token_count", 0))
                    results.append({"op": "upsert", "id": mem.id, "ok": True})
            elif op == "delete":
                mid = p.get("id")
                ok = False
                if mid:
                    ok = self.delete_memory(mid)
                results.append({"op": "delete", "id": mid, "ok": ok})
            else:
                results.append({"op": op, "ok": False, "reason": "unsupported"})
        return results


__all__ = ["TypedMemory", "DurableMemoryStore"]

    
def _truncate_text_by_tokens(text: str, max_tokens: int) -> str:
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max(1, max_tokens)]) + " ..."


def assemble_prompt_from_zones(zones: Dict[str, List[TypedMemory]], max_tokens: Optional[int] = None, max_items: int = 50) -> str:
    """Render an attention-optimized prompt section from hydrate zones.

    This places `top` items first, then `middle`, then `bottom` to respect
    the Attention Peaks (top/bottom) and Low-Attention Zone (middle). It is
    token-aware and will truncate long memory contents to avoid exceeding
    the `max_tokens` budget when possible.
    """
    if max_tokens is None:
        max_tokens = 0

    parts: List[str] = []

    def render_list(title: str, items: List[TypedMemory], token_budget: int):
        if not items:
            return 0
        parts.append(f"### {title}")
        used = 0
        for m in items[:max_items]:
            if token_budget and used >= token_budget:
                break
            content_text = json.dumps(m.content, ensure_ascii=False)
            # estimate tokens by words
            allowed = token_budget - used if token_budget else None
            if allowed and m.token_count > allowed:
                # truncate by tokens
                truncated = _truncate_text_by_tokens(content_text, max(1, allowed))
                parts.append(f"- [{m.type}] {truncated}")
                used += allowed
                break
            else:
                parts.append(f"- [{m.type}] {content_text}")
                used += m.token_count or len(content_text.split())
        return used

    top_budget = int(max_tokens * 0.25) if max_tokens else 0
    bottom_budget = int(max_tokens * 0.10) if max_tokens else 0
    middle_budget = max(0, (max_tokens - top_budget - bottom_budget)) if max_tokens else 0

    used_top = render_list("Memory Peak (Top)", zones.get("top", []), top_budget)
    used_middle = render_list("Low-Attention Zone (Middle)", zones.get("middle", []), middle_budget)
    used_bottom = render_list("Memory Peak (Bottom)", zones.get("bottom", []), bottom_budget)

    return "\n".join(parts)


def parse_and_apply_response(store: DurableMemoryStore, text: str) -> Dict[str, Any]:
    """Try to parse structured JSON patches from LLM output and apply them.

    Expects the LLM to emit either a JSON array or an object with `patches`.
    Returns the apply_patches result or raises ValueError when parsing fails.
    """
    patches = extract_patches_from_text(text)
    results = store.apply_patches(patches)
    try:
        record_event("writeback_applied", {"patch_count": len(patches), "results": results})
    except Exception:
        pass
    return {"applied": results}


def extract_patches_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract write-back patches from a model response.

    Accepts either a top-level JSON array or an object with a `patches` field.
    """
    import json

    try:
        record_event("writeback_parse_started", {"snippet": text[:200]})
    except Exception:
        pass

    cleaned = text
    if "PATCHES:" in cleaned:
        cleaned = cleaned.split("PATCHES:", 1)[1].strip()

    cleaned = cleaned.lstrip()
    if cleaned.startswith("["):
        search_order = ("[", "{")
    else:
        search_order = ("{", "[")

    idx = None
    for ch in search_order:
        p = cleaned.find(ch)
        if p != -1:
            idx = p
            break
    if idx is None:
        try:
            record_event("writeback_parse_failed", {"reason": "no_json"})
        except Exception:
            pass
        raise ValueError("No JSON found in response")
    try:
        payload = json.loads(cleaned[idx:])
    except Exception as e:
        try:
            record_event("writeback_parse_failed", {"error": str(e)[:500]})
        except Exception:
            pass
        raise ValueError(f"Failed to parse JSON: {e}")

    if isinstance(payload, dict) and "patches" in payload:
        patches = payload["patches"]
    elif isinstance(payload, list):
        patches = payload
    else:
        raise ValueError("Unsupported patch format")

    if not isinstance(patches, list):
        raise ValueError("Patches must be a list")
    return patches

