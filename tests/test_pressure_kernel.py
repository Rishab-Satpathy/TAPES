from forest_tapes.tapes_core.allocator import allocate_cognition
from forest_tapes.tapes_core.models import BoundaryAction, MutationType, ValidationLevel
from forest_tapes.tapes_core.pressure_kernel import (
    PressureAction,
    PressureAxis,
    RuntimeSignals,
    compute_pressure,
    decide_pressure_action,
)
from forest_tapes.tapes_core.representation_router import route_representation
from forest_tapes.tapes_core.scope_allocator import allocate_scope
from forest_tapes.tapes_core.task_contract import parse_task_contract
from forest_tapes.tapes_core.instability_estimator import estimate_instability
from forest_tapes.tapes_core.validation_intensity import select_validation


def test_pressure_reads_mutation_entropy_from_broad_generation() -> None:
    contract = parse_task_contract("full rewrite auth.py")
    instability = estimate_instability(contract)
    representation = route_representation(contract, instability)
    scope = allocate_scope(contract, instability, representation)
    validation = select_validation(contract, instability, scope)

    reading = compute_pressure(
        contract,
        instability,
        representation,
        scope,
        validation,
        RuntimeSignals(broad_rewrite_attempted=True, patch_attempts=2, patch_failures=2),
    )

    assert reading.axes[PressureAxis.MUTATION_ENTROPY] >= 0.55
    assert decide_pressure_action(reading).action == PressureAction.FREEZE_MUTATION


def test_allocator_freezes_mutation_under_entropy_pressure() -> None:
    result = allocate_cognition(
        "full rewrite auth.py",
        runtime_signals=RuntimeSignals(broad_rewrite_attempted=True, patch_attempts=3, patch_failures=2),
    )

    assert result.scope.mutation_surface == MutationType.NONE
    assert result.scope.allowed_assumptions == 0
    assert result.validation.level == ValidationLevel.ADVERSARIAL_CHECK


def test_scope_bleeding_shrinks_context_before_escalating() -> None:
    normal = allocate_cognition(
        {"task": "Patch auth.py token bug", "explicit_constraints": ["exact patch only"], "success_criteria": ["fixed"]}
    )
    pressured = allocate_cognition(
        {"task": "Patch auth.py token bug", "explicit_constraints": ["exact patch only"], "success_criteria": ["fixed"]},
        runtime_signals=RuntimeSignals(out_of_scope_references=5),
    )

    assert pressured.scope.token_budget < normal.scope.token_budget
    assert pressured.scope.allowed_assumptions == 0
    assert pressured.boundary.action != BoundaryAction.ESCALATE_BACKEND


def test_branch_pressure_collapses_subtasks() -> None:
    result = allocate_cognition(
        {"task": "Build some appropriate auth feature etc", "explicit_constraints": ["local only"]},
        runtime_signals=RuntimeSignals(unresolved_branches=8),
    )

    assert result.scope.max_subtasks == 1
    assert result.scope.allowed_assumptions == 0
    assert any(PressureAction.COLLAPSE_BRANCHES.value in line for line in result.rationale)


def test_validation_volatility_increases_validation() -> None:
    result = allocate_cognition(
        {"task": "Explain auth.py", "explicit_constraints": ["short"]},
        runtime_signals=RuntimeSignals(validation_failures=3),
    )

    assert result.validation.level in {ValidationLevel.FULL_VERIFY, ValidationLevel.ADVERSARIAL_CHECK}
    assert "contradiction_scan" in result.validation.checks

