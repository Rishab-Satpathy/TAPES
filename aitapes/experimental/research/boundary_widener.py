from __future__ import annotations

from .models import BoundaryAction, BoundaryDecision, InstabilityEstimate, Representation, ScopeAllocation, TaskContract

# Threshold provenance: boundary decision thresholds.
# These represent pressure levels at which the system decides to widen
# the reasoning surface. Lower thresholds = earlier widening.
HALLUCINATION_PRESSURE_CLARIFY = 0.25   # Missing info + hallucination pressure triggers clarification
REASONING_SPREAD_WIDEN = 0.25          # Reasoning spread risk triggers topology widening
MUTATION_INSTABILITY_VALIDATE = 0.22    # Mutation instability triggers increased validation
INSTABILITY_ESCALATE = 0.75            # High instability triggers backend escalation
TOPOLOGY_RADIUS_MAX = 2                # Maximum topology radius before widening is skipped


def decide_boundary(contract: TaskContract, instability: InstabilityEstimate, representation: Representation, scope: ScopeAllocation) -> BoundaryDecision:
    """Widen only when the local reasoning surface is insufficient."""
    if contract.missing_information and instability.hallucination_pressure >= HALLUCINATION_PRESSURE_CLARIFY:
        return BoundaryDecision(
            action=BoundaryAction.CLARIFY_INTENT,
            rationale="Intent has missing information that would force guessing.",
        )
    if "target_artifact" in contract.missing_information:
        return BoundaryDecision(
            action=BoundaryAction.FETCH_EVIDENCE,
            rationale="Target artifact is unknown; fetch evidence before mutation.",
        )
    if instability.reasoning_spread_risk >= REASONING_SPREAD_WIDEN and scope.topology_radius < TOPOLOGY_RADIUS_MAX:
        return BoundaryDecision(
            action=BoundaryAction.WIDEN_TOPOLOGY,
            rationale="Coupling pressure suggests local scope may be insufficient.",
        )
    if instability.mutation_instability >= MUTATION_INSTABILITY_VALIDATE:
        return BoundaryDecision(
            action=BoundaryAction.INCREASE_VALIDATION,
            rationale="Mutation blast radius is high; increase validation before reintegration.",
        )
    if instability.score >= INSTABILITY_ESCALATE and representation == Representation.SCAFFOLDED_REASONING:
        return BoundaryDecision(
            action=BoundaryAction.ESCALATE_BACKEND,
            rationale="Instability remains high after scaffolding; stronger cognition may be justified.",
        )
    return BoundaryDecision(action=BoundaryAction.NONE, rationale="Local bounded cognition appears sufficient.")
