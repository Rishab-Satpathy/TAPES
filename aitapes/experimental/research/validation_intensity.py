from __future__ import annotations

from .models import InstabilityEstimate, MutationType, ScopeAllocation, Stakes, TaskContract, ValidationLevel, ValidationSpec

# Threshold provenance: validation intensity thresholds.
# These represent pressure levels at which validation is escalated.
# Lower thresholds = earlier escalation = more safety.
INSTABILITY_HIGH = 0.6          # Above this: high-impact validation
INSTABILITY_ADVERSARIAL = 0.55  # Above this with HIGH stakes: adversarial check
TOPOLOGY_RADIUS_HIGH = 2       # Above this: high-impact validation
MUTATION_INSTABILITY_HIGH = 0.22 # Above this with HIGH stakes: adversarial check
INSTABILITY_SKIP = 0.2         # Below this with NONE mutation: skip validation


def select_validation(contract: TaskContract, instability: InstabilityEstimate, scope: ScopeAllocation) -> ValidationSpec:
    """Scale validation with impact, not bureaucracy."""
    checks: list[str] = []
    if contract.allowed_mutation == MutationType.NONE and instability.score < INSTABILITY_SKIP:
        return ValidationSpec(level=ValidationLevel.NONE, checks=(), retry_budget=0)

    checks.extend(["format_check", "forbidden_assumption_check"])

    high_impact = (
        contract.stakes == Stakes.HIGH
        or instability.score >= INSTABILITY_HIGH
        or scope.topology_radius >= TOPOLOGY_RADIUS_HIGH
        or scope.mutation_surface in {MutationType.REFACTOR, MutationType.BROAD_REWRITE}
    )
    adversarial = contract.stakes == Stakes.HIGH and (instability.score >= INSTABILITY_ADVERSARIAL or instability.mutation_instability >= MUTATION_INSTABILITY_HIGH)

    if adversarial:
        checks.extend(["constraint_satisfaction", "patch_locality_check", "contradiction_scan", "hallucination_pressure_review"])
        return ValidationSpec(level=ValidationLevel.ADVERSARIAL_CHECK, checks=tuple(checks), retry_budget=3)
    if high_impact:
        checks.extend(["constraint_satisfaction", "patch_locality_check", "consistency_check"])
        return ValidationSpec(level=ValidationLevel.FULL_VERIFY, checks=tuple(checks), retry_budget=2)
    return ValidationSpec(level=ValidationLevel.SPOT_CHECK, checks=tuple(checks), retry_budget=1)
