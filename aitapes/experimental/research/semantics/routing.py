"""Deterministic routing with confidence scores for TAPES representation selection.

Replaces the ad-hoc substring matching in representation_router.py with
ontology-aware routing that provides:
    - deterministic precedence (first match wins, order is explicit)
    - confidence scores (how strongly the evidence supports the route)
    - explainability traces (why each route was considered)
"""

from __future__ import annotations

from dataclasses import dataclass

from .matching import contains_any_token, contains_token
from .ontology import SemanticCategory, get_words


@dataclass(frozen=True)
class RouteCandidate:
    category: SemanticCategory
    confidence: float
    matched_words: tuple[str, ...]


@dataclass(frozen=True)
class RoutingTrace:
    candidates: tuple[RouteCandidate, ...]
    winner: SemanticCategory | None
    total_evidence: float


def trace_routing(text: str) -> RoutingTrace:
    """Evaluate all routing categories and return ranked candidates with confidence."""
    candidates: list[RouteCandidate] = []

    for category in (
        SemanticCategory.RUNTIME_EVIDENCE,
        SemanticCategory.DEPENDENCY_EVIDENCE,
        SemanticCategory.INTERFACE_EVIDENCE,
        SemanticCategory.COMPONENT_EVIDENCE,
        SemanticCategory.SECURITY_EVIDENCE,
    ):
        words = get_words(category)
        matched = tuple(w for w in words if contains_token(text, w))
        if matched:
            confidence = min(1.0, len(matched) * 0.35)
            candidates.append(RouteCandidate(category=category, confidence=confidence, matched_words=matched))

    winner = candidates[0].category if candidates else None
    total = sum(c.confidence for c in candidates)

    return RoutingTrace(candidates=tuple(candidates), winner=winner, total_evidence=total)
