"""Structural scope enforcement for TAPES.

This module enforces the constraints computed by scope_allocator.py
on actual content. Without this, scope parameters are advisory only.

Enforcement types:
    - Source window clipping (limit lines of code visible)
    - Topology radius enforcement (limit dependency hops)
    - Memory item limiting (limit prior decisions exposed)
    - Token budget enforcement (limit reasoning tokens)
    - Mutation boundary enforcement (restrict change types)
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import MutationType, ScopeAllocation, TaskContract


@dataclass(frozen=True)
class EnforcedContent:
    """Content after scope enforcement has been applied."""
    source_lines: list[str]
    original_line_count: int
    enforced_line_count: int
    topology_nodes: list[str]
    memory_items: list[str]
    token_budget_remaining: int
    mutation_allowed: bool
    enforcement_log: tuple[str, ...]


def enforce_source_window(source: str, scope: ScopeAllocation) -> tuple[list[str], tuple[str, ...]]:
    """Clip source code to the allowed window.

    Returns the clipped lines and enforcement log entries.
    """
    lines = source.splitlines()
    original_count = len(lines)
    log: list[str] = []

    if scope.source_window_lines == 0:
        log.append(f"Source window disabled: returning 0 lines (was {original_count})")
        return [], tuple(log)

    if len(lines) <= scope.source_window_lines:
        log.append(f"Source within window: {len(lines)}/{scope.source_window_lines} lines")
        return lines, tuple(log)

    # Take the first N lines (conservative: show less, not more)
    clipped = lines[:scope.source_window_lines]
    log.append(f"Source clipped: {original_count} -> {scope.source_window_lines} lines")
    return clipped, tuple(log)


def enforce_topology(nodes: list[str], scope: ScopeAllocation) -> tuple[list[str], tuple[str, ...]]:
    """Limit topology traversal to the allowed radius.

    Returns the limited nodes and enforcement log entries.
    """
    log: list[str] = []

    if scope.topology_radius == 0:
        log.append("Topology disabled: returning 0 nodes")
        return [], tuple(log)

    # Topology radius limits how many nodes we include
    # radius 1 = immediate neighbors, radius 2 = neighbors of neighbors
    max_nodes = scope.topology_radius * 5  # Heuristic: ~5 nodes per radius level
    if len(nodes) <= max_nodes:
        log.append(f"Topology within radius: {len(nodes)}/{max_nodes} nodes")
        return nodes, tuple(log)

    limited = nodes[:max_nodes]
    log.append(f"Topology limited: {len(nodes)} -> {max_nodes} nodes (radius {scope.topology_radius})")
    return limited, tuple(log)


def enforce_memory(items: list[str], scope: ScopeAllocation) -> tuple[list[str], tuple[str, ...]]:
    """Limit memory items exposed to the model.

    Returns the limited items and enforcement log entries.
    """
    log: list[str] = []

    if len(items) <= scope.memory_items:
        log.append(f"Memory within limit: {len(items)}/{scope.memory_items} items")
        return items, tuple(log)

    # Take the most recent items (most relevant)
    limited = items[-scope.memory_items:]
    log.append(f"Memory limited: {len(items)} -> {scope.memory_items} items")
    return limited, tuple(log)


def enforce_token_budget(text: str, scope: ScopeAllocation) -> tuple[str, tuple[str, ...]]:
    """Clip text to fit within token budget.

    Approximate enforcement: ~4 chars per token for English.
    """
    log: list[str] = []
    approx_tokens = len(text) // 4

    if approx_tokens <= scope.token_budget:
        log.append(f"Tokens within budget: ~{approx_tokens}/{scope.token_budget}")
        return text, tuple(log)

    # Clip to approximate token limit
    max_chars = scope.token_budget * 4
    clipped = text[:max_chars]
    log.append(f"Tokens clipped: ~{approx_tokens} -> {scope.token_budget}")
    return clipped, tuple(log)


def enforce_mutation_boundary(source: str, patch: str, scope: ScopeAllocation) -> tuple[str, tuple[str, ...]]:
    """Enforce mutation type constraints.

    Returns the allowed patch and enforcement log.
    """
    log: list[str] = []

    if scope.mutation_surface == MutationType.NONE:
        log.append("Mutation frozen: no changes allowed")
        return "", tuple(log)

    if scope.mutation_surface == MutationType.EXACT_PATCH:
        # Only allow exact search/replace
        if patch.strip() == source.strip():
            log.append("Mutation rejected: patch is identical to source")
            return "", tuple(log)
        log.append("Mutation allowed: exact patch")
        return patch, tuple(log)

    if scope.mutation_surface == MutationType.LOCAL_EDIT:
        # Allow local edits but not broad rewrites
        source_lines = source.splitlines()
        patch_lines = patch.splitlines()
        change_ratio = abs(len(patch_lines) - len(source_lines)) / max(1, len(source_lines))
        if change_ratio > 0.5:
            log.append(f"Mutation rejected: change ratio {change_ratio:.2f} exceeds local edit threshold")
            return "", tuple(log)
        log.append(f"Mutation allowed: local edit (change ratio {change_ratio:.2f})")
        return patch, tuple(log)

    # REFACTOR or BROAD_REWRITE: allow
    log.append(f"Mutation allowed: {scope.mutation_surface.value}")
    return patch, tuple(log)


def enforce_scope(
    source: str,
    patch: str,
    topology_nodes: list[str],
    memory_items: list[str],
    scope: ScopeAllocation,
    contract: TaskContract | None = None,
) -> EnforcedContent:
    """Apply all scope constraints to actual content.

    This is the main entry point for structural enforcement.
    """
    log: list[str] = []

    # Enforce source window
    clipped_lines, source_log = enforce_source_window(source, scope)
    log.extend(source_log)

    # Enforce topology
    limited_nodes, topo_log = enforce_topology(topology_nodes, scope)
    log.extend(topo_log)

    # Enforce memory
    limited_memory, mem_log = enforce_memory(memory_items, scope)
    log.extend(mem_log)

    # Enforce token budget on the combined content
    combined = "\n".join(clipped_lines)
    enforced_text, token_log = enforce_token_budget(combined, scope)
    log.extend(token_log)

    # Enforce mutation boundary
    enforced_patch, mutation_log = enforce_mutation_boundary(source, patch, scope)
    log.extend(mutation_log)

    # Calculate remaining token budget
    remaining = scope.token_budget - len(enforced_text) // 4

    return EnforcedContent(
        source_lines=enforced_text.splitlines(),
        original_line_count=len(source.splitlines()),
        enforced_line_count=len(enforced_text.splitlines()),
        topology_nodes=limited_nodes,
        memory_items=limited_memory,
        token_budget_remaining=max(0, remaining),
        mutation_allowed=bool(enforced_patch),
        enforcement_log=tuple(log),
    )
