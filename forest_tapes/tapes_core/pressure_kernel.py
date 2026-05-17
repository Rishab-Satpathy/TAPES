from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from ..semantics import contains_any_token, contains_token
from ..semantics.ontology import SemanticCategory, get_words
from .models import (
    BoundaryAction,
    BoundaryDecision,
    InstabilityEstimate,
    MutationType,
    Representation,
    ScopeAllocation,
    TaskContract,
    ValidationLevel,
    ValidationSpec,
)


# Threshold provenance: all values are empirical pressure-shaping constants
# tuned against instability overshoot cases. They represent ratio thresholds
# for triggering pressure actions. Relationships between thresholds:
#   - MUTATION_ENTROPY triggers at 0.55 (high before freeze)
#   - REPRESENTATION_MISMATCH triggers at 0.50 (moderate before force)
#   - SCOPE_BLEEDING triggers at 0.50 (moderate before shrink)
#   - REASONING_BRANCH triggers at 0.50 (moderate before collapse)
#   - CONTRADICTION/VALIDATION trigger at 0.45 (lower because these compound)
#   - TOPOLOGY/LEDGER trigger at 0.65 (high because backend escalation is expensive)

MUTATION_ENTROPY_THRESHOLD = 0.55
REPRESENTATION_MISMATCH_THRESHOLD = 0.50
SCOPE_BLEEDING_THRESHOLD = 0.50
REASONING_BRANCH_THRESHOLD = 0.50
CONTRADICTION_VALIDATION_THRESHOLD = 0.45
TOPOLOGY_LEDGER_THRESHOLD = 0.65

# Ratio denominator thresholds for pressure axis computation
# These normalize raw counts into [0, 1] ranges
CONTRADICTION_RATIO_DENOMINATOR = 4
BRANCH_RATIO_DENOMINATOR = 5
SCOPE_BLEEDING_RATIO_DENOMINATOR = 4
LEDGER_RATIO_DENOMINATOR = 4

# Pressure weighting coefficients from instability estimate
HALLUCINATION_PRESSURE_WEIGHT = 0.35
REASONING_SPREAD_WEIGHT = 0.40

# Token budget scaling
TOKEN_BUDGET_COLLAPSE_FACTOR = 0.65
TOKEN_BUDGET_SHRINK_FACTOR = 0.5
TOKEN_BUDGET_MIN = 256
SOURCE_LINES_SHRINK_MIN = 20


class PressureAxis(StrEnum):
    MUTATION_ENTROPY = "mutation_entropy"
    CONTRADICTION_PRESSURE = "contradiction_pressure"
    REASONING_BRANCH_PRESSURE = "reasoning_branch_pressure"
    SCOPE_BLEEDING = "scope_bleeding"
    REPRESENTATION_MISMATCH = "representation_mismatch"
    VALIDATION_VOLATILITY = "validation_volatility"
    TOPOLOGY_PRESSURE = "topology_pressure"
    LEDGER_PRESSURE = "ledger_pressure"


class PressureAction(StrEnum):
    MAINTAIN = "maintain"
    SHRINK_CONTEXT = "shrink_context"
    COLLAPSE_BRANCHES = "collapse_branches"
    FORCE_REPRESENTATION = "force_representation"
    FREEZE_MUTATION = "freeze_mutation"
    INCREASE_VALIDATION = "increase_validation"
    ESCALATE_BACKEND = "escalate_backend"


@dataclass(frozen=True)
class RuntimeSignals:
    """Observed generation pressure, not model truth or confidence."""

    patch_attempts: int = 0
    patch_failures: int = 0
    broad_rewrite_attempted: bool = False
    contradiction_count: int = 0
    unresolved_branches: int = 0
    out_of_scope_references: int = 0
    representation_switches: int = 0
    validation_failures: int = 0
    topology_nodes_touched: int = 1
    similar_failures: int = 0


@dataclass(frozen=True)
class PressureReading:
    axes: dict[PressureAxis, float]
    dominant_axis: PressureAxis
    total: float
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class PressureDecision:
    action: PressureAction
    intensity: float
    rationale: str
    forced_representation: Representation | None = None


@dataclass(frozen=True)
class PressurizedAllocation:
    scope: ScopeAllocation
    boundary: BoundaryDecision
    validation: ValidationSpec
    decision: PressureDecision
    reading: PressureReading


def compute_pressure(
    contract: TaskContract,
    instability: InstabilityEstimate,
    representation: Representation,
    scope: ScopeAllocation,
    validation: ValidationSpec,
    signals: RuntimeSignals | None = None,
) -> PressureReading:
    """Compute active cognition pressure across hallucination-relevant axes."""
    signals = signals or RuntimeSignals()
    axes = {
        PressureAxis.MUTATION_ENTROPY: _mutation_entropy(contract, scope, signals),
        PressureAxis.CONTRADICTION_PRESSURE: _ratio(signals.contradiction_count, CONTRADICTION_RATIO_DENOMINATOR),
        PressureAxis.REASONING_BRANCH_PRESSURE: _ratio(signals.unresolved_branches, BRANCH_RATIO_DENOMINATOR),
        PressureAxis.SCOPE_BLEEDING: _scope_bleeding(signals),
        PressureAxis.REPRESENTATION_MISMATCH: _representation_mismatch(contract, representation, signals),
        PressureAxis.VALIDATION_VOLATILITY: _validation_volatility(validation, signals),
        PressureAxis.TOPOLOGY_PRESSURE: _topology_pressure(scope, signals),
        PressureAxis.LEDGER_PRESSURE: _ratio(signals.similar_failures, LEDGER_RATIO_DENOMINATOR),
    }
    if instability.score > 0:
        axes[PressureAxis.REASONING_BRANCH_PRESSURE] = _clamp(
            axes[PressureAxis.REASONING_BRANCH_PRESSURE] + instability.hallucination_pressure * HALLUCINATION_PRESSURE_WEIGHT
        )
        axes[PressureAxis.SCOPE_BLEEDING] = _clamp(
            axes[PressureAxis.SCOPE_BLEEDING] + instability.reasoning_spread_risk * REASONING_SPREAD_WEIGHT
        )

    dominant_axis = max(axes, key=axes.get)
    total = _clamp(sum(axes.values()) / len(axes))
    rationale = tuple(
        f"{axis.value}={value:.2f}" for axis, value in axes.items() if value >= 0.2
    )
    return PressureReading(axes=axes, dominant_axis=dominant_axis, total=total, rationale=rationale)


def decide_pressure_action(reading: PressureReading) -> PressureDecision:
    """Convert pressure into a hard cognition constraint."""
    axis = reading.dominant_axis
    value = reading.axes[axis]

    if axis == PressureAxis.MUTATION_ENTROPY and value >= MUTATION_ENTROPY_THRESHOLD:
        return PressureDecision(
            action=PressureAction.FREEZE_MUTATION,
            intensity=value,
            rationale="Mutation entropy is high; freeze mutation to prevent broad generation.",
            forced_representation=Representation.AST_SOURCE_WINDOW,
        )
    if axis == PressureAxis.REPRESENTATION_MISMATCH and value >= REPRESENTATION_MISMATCH_THRESHOLD:
        return PressureDecision(
            action=PressureAction.FORCE_REPRESENTATION,
            intensity=value,
            rationale="Representation mismatch is creating abstraction instability.",
            forced_representation=Representation.SCAFFOLDED_REASONING,
        )
    if axis == PressureAxis.SCOPE_BLEEDING and value >= SCOPE_BLEEDING_THRESHOLD:
        return PressureDecision(
            action=PressureAction.SHRINK_CONTEXT,
            intensity=value,
            rationale="Reasoning is bleeding outside the allowed surface; shrink context.",
        )
    if axis == PressureAxis.REASONING_BRANCH_PRESSURE and value >= REASONING_BRANCH_THRESHOLD:
        return PressureDecision(
            action=PressureAction.COLLAPSE_BRANCHES,
            intensity=value,
            rationale="Too many unresolved inference branches; collapse reasoning branches.",
        )
    if axis in {PressureAxis.CONTRADICTION_PRESSURE, PressureAxis.VALIDATION_VOLATILITY} and value >= CONTRADICTION_VALIDATION_THRESHOLD:
        return PressureDecision(
            action=PressureAction.INCREASE_VALIDATION,
            intensity=value,
            rationale="Contradiction or validation volatility requires stronger checking.",
        )
    if axis in {PressureAxis.TOPOLOGY_PRESSURE, PressureAxis.LEDGER_PRESSURE} and value >= TOPOLOGY_LEDGER_THRESHOLD:
        return PressureDecision(
            action=PressureAction.ESCALATE_BACKEND,
            intensity=value,
            rationale="Pressure persists after structural constraints; backend escalation is justified.",
        )
    return PressureDecision(
        action=PressureAction.MAINTAIN,
        intensity=reading.total,
        rationale="Pressure is low enough to keep current constraints.",
    )


def apply_pressure_to_allocation(
    scope: ScopeAllocation,
    boundary: BoundaryDecision,
    validation: ValidationSpec,
    decision: PressureDecision,
) -> tuple[ScopeAllocation, BoundaryDecision, ValidationSpec]:
    """Apply a pressure decision by reducing freedom before adding power."""
    if decision.action == PressureAction.FREEZE_MUTATION:
        scope = replace(scope, mutation_surface=MutationType.NONE, allowed_assumptions=0, max_subtasks=1)
        boundary = BoundaryDecision(
            action=BoundaryAction.INCREASE_VALIDATION,
            rationale=decision.rationale,
        )
        validation = _raise_validation(validation, adversarial=True)
    elif decision.action == PressureAction.SHRINK_CONTEXT:
        scope = replace(
            scope,
            source_window_lines=max(SOURCE_LINES_SHRINK_MIN, scope.source_window_lines // 2),
            topology_radius=max(0, scope.topology_radius - 1),
            memory_items=max(0, scope.memory_items - 1),
            allowed_assumptions=0,
            max_subtasks=max(1, scope.max_subtasks - 1),
            token_budget=max(TOKEN_BUDGET_MIN, scope.token_budget // 2),
        )
    elif decision.action == PressureAction.COLLAPSE_BRANCHES:
        scope = replace(scope, allowed_assumptions=0, max_subtasks=1, token_budget=max(TOKEN_BUDGET_MIN, int(scope.token_budget * TOKEN_BUDGET_COLLAPSE_FACTOR)))
    elif decision.action == PressureAction.FORCE_REPRESENTATION:
        scope = replace(scope, allowed_assumptions=0, memory_items=max(1, scope.memory_items))
        boundary = BoundaryDecision(action=BoundaryAction.FETCH_EVIDENCE, rationale=decision.rationale)
    elif decision.action == PressureAction.INCREASE_VALIDATION:
        validation = _raise_validation(validation, adversarial=False)
    elif decision.action == PressureAction.ESCALATE_BACKEND:
        boundary = BoundaryDecision(action=BoundaryAction.ESCALATE_BACKEND, rationale=decision.rationale)
    return scope, boundary, validation


def pressurize_allocation(
    contract: TaskContract,
    instability: InstabilityEstimate,
    representation: Representation,
    scope: ScopeAllocation,
    boundary: BoundaryDecision,
    validation: ValidationSpec,
    signals: RuntimeSignals | None = None,
) -> PressurizedAllocation:
    reading = compute_pressure(contract, instability, representation, scope, validation, signals)
    decision = decide_pressure_action(reading)
    next_scope, next_boundary, next_validation = apply_pressure_to_allocation(scope, boundary, validation, decision)
    return PressurizedAllocation(
        scope=next_scope,
        boundary=next_boundary,
        validation=next_validation,
        decision=decision,
        reading=reading,
    )


def _mutation_entropy(contract: TaskContract, scope: ScopeAllocation, signals: RuntimeSignals) -> float:
    value = 0.0
    if contract.allowed_mutation == MutationType.BROAD_REWRITE:
        value += 0.45
    if scope.mutation_surface in {MutationType.REFACTOR, MutationType.BROAD_REWRITE}:
        value += 0.25
    if signals.broad_rewrite_attempted:
        value += 0.35
    if signals.patch_attempts:
        value += min(0.25, signals.patch_failures / max(1, signals.patch_attempts) * 0.25)
    return _clamp(value)


def _scope_bleeding(signals: RuntimeSignals) -> float:
    return _clamp(_ratio(signals.out_of_scope_references, SCOPE_BLEEDING_RATIO_DENOMINATOR))


def _representation_mismatch(contract: TaskContract, representation: Representation, signals: RuntimeSignals) -> float:
    value = _ratio(signals.representation_switches, 3)
    text = contract.raw_intent.lower()
    # Use ontology-backed matching instead of raw substring checks
    if contains_any_token(text, get_words(SemanticCategory.RUNTIME_EVIDENCE)) and representation != Representation.EXECUTION_TRACE:
        value += 0.35
    if contains_any_token(text, get_words(SemanticCategory.DEPENDENCY_EVIDENCE)) and representation != Representation.TOPOLOGY_GRAPH:
        value += 0.35
    if contains_any_token(text, get_words(SemanticCategory.PATCH_INTENT)) and representation != Representation.AST_SOURCE_WINDOW:
        value += 0.25
    return _clamp(value)


def _validation_volatility(validation: ValidationSpec, signals: RuntimeSignals) -> float:
    base = _ratio(signals.validation_failures, max(2, validation.retry_budget + 1))
    if validation.level == ValidationLevel.NONE and signals.validation_failures:
        base += 0.25
    return _clamp(base)


def _topology_pressure(scope: ScopeAllocation, signals: RuntimeSignals) -> float:
    value = _ratio(signals.topology_nodes_touched, max(3, scope.topology_radius + 2))
    if scope.topology_radius >= 2:
        value += 0.1
    return _clamp(value)


def _raise_validation(validation: ValidationSpec, *, adversarial: bool) -> ValidationSpec:
    checks = set(validation.checks)
    checks.update({"forbidden_assumption_check", "patch_locality_check", "contradiction_scan"})
    if adversarial:
        checks.add("hallucination_pressure_review")
        return ValidationSpec(level=ValidationLevel.ADVERSARIAL_CHECK, checks=tuple(sorted(checks)), retry_budget=max(validation.retry_budget, 3))
    if validation.level in {ValidationLevel.NONE, ValidationLevel.SPOT_CHECK}:
        return ValidationSpec(level=ValidationLevel.FULL_VERIFY, checks=tuple(sorted(checks)), retry_budget=max(validation.retry_budget, 2))
    return replace(validation, checks=tuple(sorted(checks)), retry_budget=max(validation.retry_budget, 2))


def _ratio(value: int | float, threshold: int | float) -> float:
    return _clamp(float(value) / max(1.0, float(threshold)))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))
