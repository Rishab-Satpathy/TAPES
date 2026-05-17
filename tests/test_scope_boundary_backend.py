from forest_tapes.tapes_core.allocator import allocate_cognition
from forest_tapes.tapes_core.backend_selector import select_backend
from forest_tapes.tapes_core.boundary_widener import decide_boundary
from forest_tapes.tapes_core.instability_estimator import estimate_instability
from forest_tapes.tapes_core.models import BackendKind, BoundaryAction, Representation
from forest_tapes.tapes_core.representation_router import route_representation
from forest_tapes.tapes_core.scope_allocator import allocate_scope
from forest_tapes.tapes_core.task_contract import parse_task_contract


def test_scope_limits_assumptions_when_info_missing() -> None:
    contract = parse_task_contract("Fix some auth issue")
    instability = estimate_instability(contract)
    representation = route_representation(contract, instability)
    scope = allocate_scope(contract, instability, representation)
    assert scope.allowed_assumptions == 0
    assert scope.token_budget <= 8192


def test_boundary_clarifies_before_escalating_backend() -> None:
    contract = parse_task_contract("Build some appropriate auth thing etc")
    instability = estimate_instability(contract)
    representation = route_representation(contract, instability)
    scope = allocate_scope(contract, instability, representation)
    boundary = decide_boundary(contract, instability, representation, scope)
    assert boundary.action == BoundaryAction.CLARIFY_INTENT


def test_backend_uses_smallest_sufficient_choice() -> None:
    contract = parse_task_contract({"task": "explain this small function", "explicit_constraints": ["one paragraph"]})
    instability = estimate_instability(contract)
    scope = allocate_scope(contract, instability, Representation.DIRECT)
    boundary = decide_boundary(contract, instability, Representation.DIRECT, scope)
    backend = select_backend(
        instability,
        scope,
        boundary,
        environment={"local_models": ["llama.cpp/tiny"], "api_models": ["api/standard"]},
    )
    assert backend.kind in {BackendKind.HEURISTIC, BackendKind.LOCAL_MODEL}


def test_allocator_pipeline_contains_prompt_anchor() -> None:
    result = allocate_cognition(
        {
            "task": "Patch auth.py token refresh bug",
            "explicit_constraints": ["exact patch only"],
            "success_criteria": ["stale token removed"],
        },
        environment={"local_models": ["llama.cpp/local"], "api_models": ["ibm/granite-13b-chat-v2"]},
    )
    assert result.scope.token_budget <= 8192
    assert any("TAPES COGNITION ANCHOR" in line for line in result.rationale)
    assert result.representation == Representation.AST_SOURCE_WINDOW

