from forest_tapes.tapes_core.scope_enforcement import (
    enforce_source_window,
    enforce_topology,
    enforce_memory,
    enforce_token_budget,
    enforce_mutation_boundary,
    enforce_scope,
)
from forest_tapes.tapes_core.models import MutationType, ScopeAllocation


def test_source_window_clips_to_limit() -> None:
    source = "\n".join([f"line {i}" for i in range(100)])
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=4096,
    )
    lines, log = enforce_source_window(source, scope)
    assert len(lines) == 10
    assert any("clipped" in entry.lower() for entry in log)


def test_source_window_no_clip_when_within_limit() -> None:
    source = "\n".join(["line 1", "line 2"])
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=4096,
    )
    lines, log = enforce_source_window(source, scope)
    assert len(lines) == 2
    assert any("within" in entry.lower() for entry in log)


def test_topology_limits_nodes() -> None:
    nodes = [f"module_{i}" for i in range(20)]
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=4096,
    )
    limited, log = enforce_topology(nodes, scope)
    assert len(limited) <= 5  # radius 1 * 5
    assert any("limited" in entry.lower() for entry in log)


def test_memory_limits_items() -> None:
    items = [f"item_{i}" for i in range(10)]
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=3,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=4096,
    )
    limited, log = enforce_memory(items, scope)
    assert len(limited) == 3
    assert any("limited" in entry.lower() for entry in log)


def test_token_budget_clips_text() -> None:
    text = "x" * 10000  # ~2500 tokens
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=100,  # ~400 chars
    )
    clipped, log = enforce_token_budget(text, scope)
    assert len(clipped) <= 400
    assert any("clipped" in entry.lower() for entry in log)


def test_mutation_boundary_freezes_when_none() -> None:
    source = "old code"
    patch = "new code"
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.NONE,
        token_budget=4096,
    )
    enforced, log = enforce_mutation_boundary(source, patch, scope)
    assert enforced == ""
    assert any("frozen" in entry.lower() for entry in log)


def test_enforce_scope_applies_all_constraints() -> None:
    source = "\n".join([f"line {i}" for i in range(50)])
    patch = "new code"
    topology = [f"mod_{i}" for i in range(10)]
    memory = [f"mem_{i}" for i in range(5)]
    scope = ScopeAllocation(
        source_window_lines=10,
        topology_radius=1,
        memory_items=2,
        allowed_assumptions=1,
        max_subtasks=2,
        mutation_surface=MutationType.LOCAL_EDIT,
        token_budget=4096,
    )
    result = enforce_scope(source, patch, topology, memory, scope)
    assert result.enforced_line_count <= 10
    assert len(result.topology_nodes) <= 5
    assert len(result.memory_items) == 2
    assert len(result.enforcement_log) > 0
