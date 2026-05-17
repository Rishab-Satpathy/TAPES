"""Cross-Project Vector Grounding for TAPES v8.0.

Embeds user intent via API at the start of every run_plan.
Logs the vector to the ledger. Bypasses novelty detection for runs 1-5.
From run 6, computes cosine distance against the stored corpus and
triggers SIP (Stabilized Intent Protocol) or Hard Stop ask_user() if
flagged as an outlier.

Integrates with task_contract.py and plan.py.
"""

from __future__ import annotations

import math
from typing import Any


# ── Cosine distance ────────────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance = 1 - cosine_similarity. Range [0, 2]."""
    return 1.0 - cosine_similarity(a, b)


# ── Novelty detection ─────────────────────────────────────────────────────

# Bypass novelty detection for the first N runs
NOVELTY_BYPASS_RUNS = 5

# Distance thresholds for anomaly detection
SIP_THRESHOLD = 0.45       # Stabilized Intent Protocol (warning)
HARD_STOP_THRESHOLD = 0.65 # Hard stop with user confirmation


class NoveltyResult:
    """Result of novelty detection against the stored corpus."""
    __slots__ = ("is_novel", "severity", "min_distance", "mean_distance", "corpus_size", "message")

    def __init__(
        self,
        is_novel: bool,
        severity: str,
        min_distance: float,
        mean_distance: float,
        corpus_size: int,
        message: str,
    ) -> None:
        self.is_novel = is_novel
        self.severity = severity  # "none", "sip", "hard_stop"
        self.min_distance = min_distance
        self.mean_distance = mean_distance
        self.corpus_size = corpus_size
        self.message = message


def detect_novelty(
    intent_embedding: list[float],
    corpus_embeddings: list[list[float]],
    run_number: int,
) -> NoveltyResult:
    """Detect if the current intent is an outlier relative to the stored corpus.

    - Bypasses for runs 1-5 (not enough data)
    - From run 6, computes cosine distance against all stored embeddings
    - SIP warning if min distance > SIP_THRESHOLD
    - Hard stop if min distance > HARD_STOP_THRESHOLD
    """
    corpus_size = len(corpus_embeddings)

    # Bypass for early runs
    if run_number <= NOVELTY_BYPASS_RUNS or corpus_size == 0:
        return NoveltyResult(
            is_novel=False,
            severity="none",
            min_distance=0.0,
            mean_distance=0.0,
            corpus_size=corpus_size,
            message=f"Novelty bypass: run {run_number}/{NOVELTY_BYPASS_RUNS} (need {NOVELTY_BYPASS_RUNS} runs before detection)",
        )

    # Compute distances
    distances = [cosine_distance(intent_embedding, stored) for stored in corpus_embeddings]
    min_dist = min(distances)
    mean_dist = sum(distances) / len(distances)

    if min_dist >= HARD_STOP_THRESHOLD:
        return NoveltyResult(
            is_novel=True,
            severity="hard_stop",
            min_distance=min_dist,
            mean_distance=mean_dist,
            corpus_size=corpus_size,
            message=f"HARD STOP: Intent is highly anomalous (min cosine distance: {min_dist:.3f} > {HARD_STOP_THRESHOLD})",
        )

    if min_dist >= SIP_THRESHOLD:
        return NoveltyResult(
            is_novel=True,
            severity="sip",
            min_distance=min_dist,
            mean_distance=mean_dist,
            corpus_size=corpus_size,
            message=f"SIP WARNING: Intent appears novel (min cosine distance: {min_dist:.3f} > {SIP_THRESHOLD})",
        )

    return NoveltyResult(
        is_novel=False,
        severity="none",
        min_distance=min_dist,
        mean_distance=mean_dist,
        corpus_size=corpus_size,
        message=f"Intent within known corpus (min cosine distance: {min_dist:.3f})",
    )


# ── Grounding integration ─────────────────────────────────────────────────

def ground_intent(
    intent: str,
    ledger_embeddings: list[list[float]],
    run_number: int,
    embed_fn: Any = None,
) -> tuple[list[float], NoveltyResult]:
    """Embed intent, check novelty, return (embedding, novelty_result).

    Args:
        intent: User intent string
        ledger_embeddings: All prior embeddings from the ledger
        run_number: Current run number (1-indexed)
        embed_fn: Callable that takes a string and returns list[float].
                  If None, uses aitapes.llm.embed_text.

    Returns:
        (embedding, novelty_result)
    """
    # Embed the intent
    if embed_fn is None:
        from aitapes.llm import embed_text
        embedding = embed_text(intent)
    else:
        embedding = embed_fn(intent)

    # Detect novelty
    novelty = detect_novelty(embedding, ledger_embeddings, run_number)

    # Handle novelty actions
    if novelty.severity == "hard_stop":
        print(f"\n{'!'*60}")
        print(f"  {novelty.message}")
        print(f"  Corpus size: {novelty.corpus_size}")
        print(f"  [NOVELTY GUARD] Intent '{intent[:30]}...' is a high outlier (dist: {novelty.min_distance:.3f}).")
        from forest_tapes.tapes_core.interaction import ask_user
        if not ask_user("  Continue with this intent? (y/N): ", default=False):
            raise RuntimeError(f"TAPES Hard Stop: Intent rejected by user. {novelty.message}")

    elif novelty.severity == "sip":
        print(f"\n  [SIP] {novelty.message}")
        print(f"    Corpus size: {novelty.corpus_size}, Min distance: {novelty.min_distance:.3f}")

    return embedding, novelty
