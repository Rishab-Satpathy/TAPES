"""Fast Draft Optimized for TAPES v8.0.

Cherry-picked from NovelIdeaEdition's forest_graph module.
Provides FastDraftOptimizer for quick patch generation with
branch speculation and token budget management.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DraftCandidate:
    """A candidate draft from speculative branch."""
    draft_id: int
    content: str
    patch_count: int
    token_cost: int
    quality_score: float = 0.0
    passed_lec: bool = False


@dataclass
class FastDraftOptimizer:
    """Optimizes draft generation with speculative branching.

    B12 fix: _L1_CACHE bounded to 1000 entries max.
    """
    max_branches: int = 3
    temperature_range: tuple[float, float] = (0.2, 0.8)
    _cache: dict[str, Any] = field(default_factory=dict)
    _L1_MAX = 1000
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cache_draft(self, key: str, draft: DraftCandidate) -> None:
        """Cache a draft with key."""
        with self._lock:
            if len(self._cache) >= self._L1_MAX:
                self._cache.clear()
            self._cache[key] = draft

    def get_cached(self, key: str) -> DraftCandidate | None:
        """Get a cached draft by key."""
        with self._lock:
            return self._cache.get(key)

    def generate_branch_configs(self) -> list[dict[str, Any]]:
        """Generate branch configurations with varied parameters."""
        configs = []
        temp_step = (self.temperature_range[1] - self.temperature_range[0]) / max(self.max_branches - 1, 1)
        for i in range(self.max_branches):
            temp = self.temperature_range[0] + (i * temp_step)
            configs.append({
                "branch_id": i + 1,
                "temperature": temp,
                "max_tokens": 2048,
            })
        return configs

    def select_winner(self, candidates: list[DraftCandidate]) -> DraftCandidate | None:
        """Select the winning candidate based on quality score."""
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.quality_score if c.passed_lec else 0.0)

    def estimate_cost(self, draft: str) -> int:
        """Estimate token cost of a draft."""
        return len(draft.split()) * 2  # rough estimate

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cached_drafts": len(self._cache),
                "max_branches": self.max_branches,
                "cache_limit": self._L1_MAX,
            }