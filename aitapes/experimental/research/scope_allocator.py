from __future__ import annotations

from .models import InstabilityEstimate, MutationType, Representation, ScopeAllocation, TaskContract

# Threshold provenance: token budget and scope sizing constants.
# These are empirical values tuned to prevent hallucination under uncertainty.
# The token-per-word multiplier (12) intentionally overestimates to widen caution
# boundaries and trigger decomposition earlier. This is a pressure-amplification
# strategy, not an accuracy optimization.
TOKEN_PER_WORD_MULTIPLIER = 12   # Intentionally high: widen caution boundaries
TOKEN_BUDGET_MAX = 8192          # Upper bound to prevent runaway reasoning
TOKEN_BUDGET_MIN = 256           # Lower bound to ensure minimum cognition surface

# Source window sizing by representation
SOURCE_LINES_DIRECT = 0          # No source needed for direct reasoning
SOURCE_LINES_AST_LOW = 80       # Low instability: smaller window
SOURCE_LINES_AST_HIGH = 160     # High instability: wider window for context
SOURCE_LINES_TOPOLOGY = 40      # Topology graphs: moderate window
SOURCE_LINES_SCAFFOLDED = 40    # Scaffolded: moderate window
SOURCE_LINES_DEFAULT = 60       # Default: moderate window

# Instability thresholds for scope sizing
INSTABILITY_AST_LOW = 0.45      # Below this: smaller AST window
INSTABILITY_SUBTASK_LOW = 0.55  # Below this: single subtask
INSTABILITY_SPREAD_RISK = 0.25  # Above this: widen topology radius
INSTABILITY_BROAD_CAP = 0.35    # Above this: cap broad rewrite to local edit

# Subtask limits
SUBTASKS_MAX = 4                # Maximum concurrent subtasks


def allocate_scope(contract: TaskContract, instability: InstabilityEstimate, representation: Representation) -> ScopeAllocation:
    """Control reasoning boundaries so the model is not forced to carry excess surface."""
    word_count = max(1, len(contract.raw_intent.split()))
    base_tokens = max(TOKEN_BUDGET_MIN, word_count * TOKEN_PER_WORD_MULTIPLIER)
    instability_multiplier = 1.0 + instability.score
    token_budget = min(TOKEN_BUDGET_MAX, int(base_tokens * instability_multiplier))

    if representation == Representation.DIRECT:
        source_lines = SOURCE_LINES_DIRECT
        topology_radius = 0
        memory_items = 0
        subtasks = 1
    elif representation == Representation.AST_SOURCE_WINDOW:
        source_lines = SOURCE_LINES_AST_LOW if instability.score < INSTABILITY_AST_LOW else SOURCE_LINES_AST_HIGH
        topology_radius = 1
        memory_items = 2
        subtasks = 1 if instability.score < INSTABILITY_SUBTASK_LOW else 2
    elif representation in {Representation.TOPOLOGY_GRAPH, Representation.DATA_FLOW_GRAPH}:
        source_lines = SOURCE_LINES_TOPOLOGY
        topology_radius = 2 if instability.reasoning_spread_risk >= INSTABILITY_SPREAD_RISK else 1
        memory_items = 3
        subtasks = 3
    elif representation == Representation.SCAFFOLDED_REASONING:
        source_lines = SOURCE_LINES_SCAFFOLDED
        topology_radius = 1
        memory_items = 2
        subtasks = 2
    else:
        source_lines = SOURCE_LINES_DEFAULT
        topology_radius = 1
        memory_items = 2
        subtasks = 2

    allowed_assumptions = 0 if contract.missing_information else 1
    mutation_surface = _bounded_mutation_surface(contract.allowed_mutation, instability)

    return ScopeAllocation(
        source_window_lines=source_lines,
        topology_radius=topology_radius,
        memory_items=memory_items,
        allowed_assumptions=allowed_assumptions,
        max_subtasks=min(SUBTASKS_MAX, subtasks),
        mutation_surface=mutation_surface,
        token_budget=token_budget,
    )


def _bounded_mutation_surface(mutation: MutationType, instability: InstabilityEstimate) -> MutationType:
    if mutation == MutationType.BROAD_REWRITE and instability.score >= INSTABILITY_BROAD_CAP:
        return MutationType.LOCAL_EDIT
    return mutation
