from typing import Optional, List, Dict, Any
from .durable_memory import DurableMemoryStore, assemble_prompt_from_zones


class DurableMemoryManager:
    """Helper to integrate DurableMemoryStore with agent services.

    Usage:
      mgr = DurableMemoryManager(store=DurableMemoryStore())
      prompt_tail = mgr.build_memory_section(types=["preferences","past_issues"], max_tokens=4000)
      full_prompt = base + "\n\n" + prompt_tail
    """

    def __init__(self, store: Optional[DurableMemoryStore] = None):
        self.store = store or DurableMemoryStore()
        self._cache: dict = {}
        self._cache_ttl = 5.0

    def hydrate_cached(self, types: Optional[List[str]] = None, max_tokens: int = 4000, top_pct: float = 0.25, bottom_pct: float = 0.10):
        key = (tuple(types) if types else None, max_tokens, top_pct, bottom_pct)
        import time
        now = time.time()
        cached = self._cache.get(key)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]
        zones = self.store.hydrate(types=types, max_tokens=max_tokens, top_pct=top_pct, bottom_pct=bottom_pct)
        self._cache[key] = (now, zones)
        return zones

    def build_memory_section(self, types: Optional[List[str]] = None, max_tokens: int = 4000, top_pct: float = 0.25, bottom_pct: float = 0.10) -> str:
        zones = self.store.hydrate(types=types, max_tokens=max_tokens, top_pct=top_pct, bottom_pct=bottom_pct)
        return assemble_prompt_from_zones(zones)

    def apply_llm_writeback(self, text: str) -> Dict[str, Any]:
        # lazy import to avoid circulars
        from .durable_memory import parse_and_apply_response

        return parse_and_apply_response(self.store, text)


__all__ = ["DurableMemoryManager"]
