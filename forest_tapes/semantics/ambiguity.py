"""Unified ambiguity and pressure detection for TAPES pressure scoring.

Replaces the divergent _contains_any implementations scattered across
task_contract.py and instability_estimator.py with a single ontology-aware
pressure scorer.
"""

from __future__ import annotations

from .matching import contains_any_token, count_tokens
from .ontology import SemanticCategory, get_words


def score_ambiguity(text: str) -> float:
    """Score ambiguity pressure from 0.0 (precise) to 1.0 (highly ambiguous).
    Uses word-boundary matching to prevent false positives like 'awesome' matching 'some'."""
    count = count_tokens(text, get_words(SemanticCategory.AMBIGUITY))
    return min(1.0, count * 0.12)


def score_subjectivity(text: str) -> float:
    """Score subjective pressure from 0.0 to 1.0."""
    if contains_any_token(text, get_words(SemanticCategory.SUBJECTIVITY)):
        return 0.12
    return 0.0


def has_vagueness(text: str) -> bool:
    """Detect vague terms that need clarification."""
    return contains_any_token(text, get_words(SemanticCategory.VAGUENESS))


def has_cross_scope(text: str) -> bool:
    """Detect scope-expanding terms."""
    return contains_any_token(text, get_words(SemanticCategory.CROSS_SCOPE))


def has_high_stakes(text: str) -> bool:
    """Detect high-consequence domain terms."""
    return contains_any_token(text, get_words(SemanticCategory.HIGH_STAKES))


def has_medium_stakes(text: str) -> bool:
    """Detect elevated stakes terms."""
    return contains_any_token(text, get_words(SemanticCategory.MEDIUM_STAKES))


def detect_instability_signal(text: str) -> str | None:
    """Detect instability signals. Returns 'high', 'moderate', or None."""
    if contains_any_token(text, get_words(SemanticCategory.INSTABILITY_HIGH)):
        return "high"
    if contains_any_token(text, get_words(SemanticCategory.INSTABILITY_MODERATE)):
        return "moderate"
    return None


def detect_mutation_scope(text: str) -> str | None:
    """Detect mutation scope signals. Returns 'broad', 'exact', 'local', or None."""
    from .matching import contains_any_phrase
    if contains_any_phrase(text, get_words(SemanticCategory.MUTATION_BROAD)):
        return "broad"
    if contains_any_phrase(text, get_words(SemanticCategory.MUTATION_EXACT)):
        return "exact"
    if contains_any_phrase(text, get_words(SemanticCategory.MUTATION_LOCAL)):
        return "local"
    return None


def needs_decomposition(text: str) -> bool:
    """Detect if task should be decomposed into subtasks."""
    return contains_any_token(text, get_words(SemanticCategory.DECOMPOSITION_NEEDED))


def blocks_decomposition(text: str) -> bool:
    """Detect if task explicitly blocks decomposition."""
    from .matching import contains_any_phrase
    return contains_any_phrase(text, get_words(SemanticCategory.DECOMPOSITION_BLOCKED))


def signals_escalation(text: str) -> bool:
    """Detect if text signals need for backend escalation."""
    from .matching import contains_any_phrase
    return contains_any_phrase(text, get_words(SemanticCategory.PRESSURE_ESCALATION))


def signals_scope_widen(text: str) -> bool:
    """Detect if text signals need for scope widening."""
    from .matching import contains_any_phrase
    return contains_any_phrase(text, get_words(SemanticCategory.SCOPE_WIDEN))


def signals_scope_shrink(text: str) -> bool:
    """Detect if text signals need for scope narrowing."""
    from .matching import contains_any_phrase
    return contains_any_phrase(text, get_words(SemanticCategory.SCOPE_SHRINK))
