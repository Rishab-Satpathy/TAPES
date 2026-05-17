"""Model Router for TAPES v8.0.

Cherry-picked from NovelIdeaEdition's scope_allocator module.
Provides CostTracker, complexity estimation, and model selection.

F9 fix: removed duplicate "complexity" keyword.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CostTracker:
    """Tracks token usage and cost across model calls.

    B9 fix: thread-safe with Lock.
    """
    _generation_used: int = 0
    _debate_used: int = 0
    _generation_limit: int = 70000
    _debate_limit: int = 30000
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, tokens: int, partition: str) -> None:
        """Record token usage for a partition."""
        with self._lock:
            if partition == "generation":
                self._generation_used += tokens
            elif partition == "debate":
                self._debate_used += tokens

    def remaining(self, partition: str) -> int:
        """Get remaining tokens for a partition."""
        with self._lock:
            if partition == "generation":
                return max(0, self._generation_limit - self._generation_used)
            return max(0, self._debate_limit - self._debate_used)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "generation": {
                    "used": self._generation_used,
                    "limit": self._generation_limit,
                    "remaining": self._generation_limit - self._generation_used,
                },
                "debate": {
                    "used": self._debate_used,
                    "limit": self._debate_limit,
                    "remaining": self._debate_limit - self._debate_used,
                },
            }


def estimate_complexity(intent: str, source_files: dict[str, str]) -> int:
    """Estimate complexity of a task.

    F9 fix: removed duplicate keyword.
    """
    score = 0

    high_stakes_keywords = ["security", "payment", "auth", "critical", "production", "database"]
    if any(kw in intent.lower() for kw in high_stakes_keywords):
        score += 30

    if len(source_files) > 10:
        score += 20
    elif len(source_files) > 5:
        score += 10

    for path, content in source_files.items():
        lines = content.splitlines()
        if len(lines) > 300:
            score += 15
        elif len(lines) > 100:
            score += 5

    mutation_keywords = ["refactor", "rewrite", "broad", "architecture"]
    if any(kw in intent.lower() for kw in mutation_keywords):
        score += 25

    return min(score, 100)


def select_model(complexity: int) -> str:
    """Select appropriate model based on complexity score."""
    if complexity >= 70:
        return "ibm/granite-13b-chat-v2"
    elif complexity >= 40:
        return "ibm/granite-13b-instruct-v2"
    else:
        return "ibm/granite-13b-instruct-v2"


def route_task(intent: str, source_files: dict[str, str]) -> dict[str, Any]:
    """Route a task to appropriate model and configuration."""
    complexity = estimate_complexity(intent, source_files)
    model = select_model(complexity)

    return {
        "complexity": complexity,
        "model": model,
        "estimated_tokens": complexity * 100,
        "debate_required": complexity >= 50,
    }