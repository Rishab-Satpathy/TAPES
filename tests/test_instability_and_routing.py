from forest_tapes.tapes_core.instability_estimator import estimate_instability
from forest_tapes.tapes_core.models import Representation
from forest_tapes.tapes_core.representation_router import route_representation
from forest_tapes.tapes_core.task_contract import parse_task_contract


def test_missing_info_and_vague_terms_raise_hallucination_pressure() -> None:
    contract = parse_task_contract("Build some appropriate auth thing etc")
    instability = estimate_instability(contract)
    assert instability.score > 0.4
    assert "missing_information_pressure" in instability.sources
    assert "ambiguity_pressure" in instability.sources


def test_local_patch_routes_to_ast_source_window() -> None:
    contract = parse_task_contract(
        {
            "task": "Patch auth.py with exact search replace",
            "explicit_constraints": ["only one function"],
            "success_criteria": ["token refresh fixed"],
        }
    )
    representation = route_representation(contract, estimate_instability(contract))
    assert representation == Representation.AST_SOURCE_WINDOW


def test_runtime_bug_routes_to_execution_trace() -> None:
    contract = parse_task_contract("Fix crash using this runtime stack trace in auth.py")
    assert route_representation(contract, estimate_instability(contract)) == Representation.EXECUTION_TRACE


def test_dependency_issue_routes_to_topology_graph() -> None:
    contract = parse_task_contract("Fix dependency coupling between auth module and cache module")
    assert route_representation(contract, estimate_instability(contract)) == Representation.TOPOLOGY_GRAPH

