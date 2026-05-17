from __future__ import annotations

from dataclasses import dataclass

from ..semantics import contains_any_token, trace_routing
from ..semantics.ontology import SemanticCategory, get_words
from .models import InstabilityEstimate, MutationType, Representation, TaskContract, TaskType


@dataclass(frozen=True)
class RoutedRepresentation:
    """Representation with explainability trace."""
    representation: Representation
    confidence: float
    matched_words: tuple[str, ...]
    fallback: bool
    reason: str


def route_representation(contract: TaskContract, instability: InstabilityEstimate) -> Representation:
    """Choose the smallest sufficient representation to reduce abstraction mismatch.
    Routing precedence is deterministic: first evidence match wins.
    Order: RUNTIME > DEPENDENCY > INTERFACE > COMPONENT > PATCH > SECURITY > SCAFFOLDED > STRUCTURED > DIRECT."""
    result = route_representation_with_trace(contract, instability)
    return result.representation


def route_representation_with_trace(contract: TaskContract, instability: InstabilityEstimate) -> RoutedRepresentation:
    """Route with full explainability trace."""
    text = contract.raw_intent.lower()

    # Use ontology-backed routing via semantics layer
    trace = trace_routing(text)

    # Evidence-based routing: use trace results if available
    if trace.winner == SemanticCategory.RUNTIME_EVIDENCE:
        return RoutedRepresentation(
            representation=Representation.EXECUTION_TRACE,
            confidence=trace.total_evidence,
            matched_words=_extract_matched_words(trace, SemanticCategory.RUNTIME_EVIDENCE),
            fallback=False,
            reason="Runtime evidence detected in task intent.",
        )
    if trace.winner == SemanticCategory.DEPENDENCY_EVIDENCE:
        return RoutedRepresentation(
            representation=Representation.TOPOLOGY_GRAPH,
            confidence=trace.total_evidence,
            matched_words=_extract_matched_words(trace, SemanticCategory.DEPENDENCY_EVIDENCE),
            fallback=False,
            reason="Dependency evidence detected in task intent.",
        )
    if trace.winner == SemanticCategory.INTERFACE_EVIDENCE:
        return RoutedRepresentation(
            representation=Representation.TYPED_INTERFACE_GRAPH,
            confidence=trace.total_evidence,
            matched_words=_extract_matched_words(trace, SemanticCategory.INTERFACE_EVIDENCE),
            fallback=False,
            reason="Interface evidence detected in task intent.",
        )
    if trace.winner == SemanticCategory.COMPONENT_EVIDENCE:
        return RoutedRepresentation(
            representation=Representation.COMPONENT_HIERARCHY,
            confidence=trace.total_evidence,
            matched_words=_extract_matched_words(trace, SemanticCategory.COMPONENT_EVIDENCE),
            fallback=False,
            reason="Component evidence detected in task intent.",
        )

    # Mutation-based routing: use ontology for mutation scope detection
    if contract.allowed_mutation in {MutationType.EXACT_PATCH, MutationType.LOCAL_EDIT}:
        return RoutedRepresentation(
            representation=Representation.AST_SOURCE_WINDOW,
            confidence=0.9,
            matched_words=(),
            fallback=False,
            reason="Mutation type is exact or local; AST source window is sufficient.",
        )

    if trace.winner == SemanticCategory.SECURITY_EVIDENCE:
        return RoutedRepresentation(
            representation=Representation.DATA_FLOW_GRAPH,
            confidence=trace.total_evidence,
            matched_words=_extract_matched_words(trace, SemanticCategory.SECURITY_EVIDENCE),
            fallback=False,
            reason="Security evidence detected in task intent.",
        )

    # Pressure-based routing
    if instability.score >= 0.6 or contract.missing_information:
        return RoutedRepresentation(
            representation=Representation.SCAFFOLDED_REASONING,
            confidence=min(1.0, instability.score),
            matched_words=(),
            fallback=False,
            reason="High instability or missing information requires scaffolded reasoning.",
        )

    # Task-type routing
    if contract.task_type in {TaskType.FEATURE, TaskType.REFACTOR}:
        return RoutedRepresentation(
            representation=Representation.STRUCTURED_CONTRACT,
            confidence=0.8,
            matched_words=(),
            fallback=False,
            reason="Feature or refactor task type uses structured contract.",
        )

    # Default
    return RoutedRepresentation(
        representation=Representation.DIRECT,
        confidence=0.5,
        matched_words=(),
        fallback=True,
        reason="No strong evidence for specific representation; defaulting to direct.",
    )


def _extract_matched_words(trace, category: SemanticCategory) -> tuple[str, ...]:
    """Extract matched words for a specific category from the routing trace."""
    for candidate in trace.candidates:
        if candidate.category == category:
            return candidate.matched_words
    return ()


def representation_prompt_rule(representation: Representation) -> str:
    rules = {
        Representation.DIRECT: "Use direct reasoning; do not expand beyond the task contract.",
        Representation.STRUCTURED_CONTRACT: "Reason through the explicit contract fields before proposing output.",
        Representation.AST_SOURCE_WINDOW: "Use only the bounded source window and AST facts; do not infer unseen code.",
        Representation.TOPOLOGY_GRAPH: "Reason over dependency edges and neighboring nodes, not raw full-repo text.",
        Representation.EXECUTION_TRACE: "Reason from observed runtime events, stack frames, and failing assertions.",
        Representation.TYPED_INTERFACE_GRAPH: "Reason from types, schemas, signatures, and contract boundaries.",
        Representation.COMPONENT_HIERARCHY: "Reason from component relationships and visible UI state.",
        Representation.DATA_FLOW_GRAPH: "Reason from source-to-sink paths and trust boundaries.",
        Representation.SCAFFOLDED_REASONING: "First list knowns, unknowns, and forbidden assumptions before output.",
    }
    return rules.get(representation, "Use direct reasoning; do not expand beyond the task contract.")
