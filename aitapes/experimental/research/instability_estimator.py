from __future__ import annotations
import re

from ..semantics import has_cross_scope, has_high_stakes, has_medium_stakes, score_ambiguity, score_subjectivity
from .models import InstabilityEstimate, MutationType, Stakes, TaskContract, TaskType


# Threshold provenance: all values are empirical pressure-shaping constants
# tuned against instability overshoot cases in the TAPES prototype.
# They represent per-factor weight contributions to the composite instability score.
MISSING_INFO_WEIGHT = 0.18       # Each missing info item adds ~18% pressure
MUTATION_BROAD_WEIGHT = 0.35     # Broad rewrite instability
MUTATION_REFACTOR_WEIGHT = 0.22  # Refactor instability
MUTATION_LOCAL_WEIGHT = 0.12     # Local edit instability
MUTATION_PATCH_WEIGHT = 0.05     # Exact patch instability
PRIOR_FAILURE_WEIGHT = 0.05      # Per prior failure
PRIOR_FAILURE_CAP = 0.20         # Max prior failure contribution
TASK_PRESSURE_WEIGHT = 0.10      # Feature/refactor tasks add base pressure
STAKES_HIGH_WEIGHT = 0.10        # High stakes add pressure
STAKES_MEDIUM_WEIGHT = 0.05      # Medium stakes add pressure


def estimate_instability(contract: TaskContract, prior_failure_count: int = 0) -> InstabilityEstimate:
    """Estimate hallucination pressure, not truth or model confidence."""
    text = contract.raw_intent.lower()
    missing_risk = _clamp(MISSING_INFO_WEIGHT * len(contract.missing_information))
    ambiguity_pressure = score_ambiguity(text)
    cross_scope = 0.25 if has_cross_scope(text) else 0.0
    mutation_instability = _mutation_instability(contract.allowed_mutation)
    subjective = score_subjectivity(text)
    stakes = STAKES_HIGH_WEIGHT if contract.stakes == Stakes.HIGH else STAKES_MEDIUM_WEIGHT if contract.stakes == Stakes.MEDIUM else 0.0
    prior = min(PRIOR_FAILURE_CAP, prior_failure_count * PRIOR_FAILURE_WEIGHT)
    task_pressure = TASK_PRESSURE_WEIGHT if contract.task_type in {TaskType.FEATURE, TaskType.REFACTOR} else 0.0

    score = _clamp(
        missing_risk
        + ambiguity_pressure
        + cross_scope
        + mutation_instability
        + subjective
        + stakes
        + prior
        + task_pressure
    )

    sources: list[str] = []
    if missing_risk:
        sources.append("missing_information_pressure")
    if ambiguity_pressure:
        sources.append("ambiguity_pressure")
    if cross_scope:
        sources.append("cross_scope_coupling_pressure")
    if mutation_instability:
        sources.append("mutation_blast_radius")
    if subjective:
        sources.append("subjective_open_ended_pressure")
    if prior:
        sources.append("prior_failure_pattern")

    return InstabilityEstimate(
        score=score,
        sources=tuple(sources),
        hallucination_pressure=_clamp(missing_risk + ambiguity_pressure + subjective),
        reasoning_spread_risk=_clamp(cross_scope + task_pressure),
        missing_information_risk=missing_risk,
        mutation_instability=mutation_instability,
    )


def _mutation_instability(mutation: MutationType) -> float:
    if mutation == MutationType.BROAD_REWRITE:
        return MUTATION_BROAD_WEIGHT
    if mutation == MutationType.REFACTOR:
        return MUTATION_REFACTOR_WEIGHT
    if mutation == MutationType.LOCAL_EDIT:
        return MUTATION_LOCAL_WEIGHT
    if mutation == MutationType.EXACT_PATCH:
        return MUTATION_PATCH_WEIGHT
    return 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))
