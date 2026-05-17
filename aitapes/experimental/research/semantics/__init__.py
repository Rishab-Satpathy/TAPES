"""TAPES semantics layer.

Doctrine-separated modules for text matching, ontology, routing, and ambiguity.
All text matching in the TAPES pipeline should flow through this package
to prevent ontology drift and ensure semantic consistency.

v8.0 additions:
    - DynamicOntology: runtime term discovery from failures
"""

from .ambiguity import (
    detect_instability_signal,
    detect_mutation_scope,
    has_cross_scope,
    has_high_stakes,
    has_medium_stakes,
    has_vagueness,
    needs_decomposition,
    blocks_decomposition,
    score_ambiguity,
    score_subjectivity,
    signals_escalation,
    signals_scope_shrink,
    signals_scope_widen,
)
from .dynamic_ontology import DynamicOntology, DynamicEntry
from .matching import MatchTier, contains_any_token, contains_phrase, contains_token, count_tokens, match_tier
from .ontology import SEMANTIC_REGISTRY, SemanticCategory, get_provenance, get_tier, get_words
from .routing import RouteCandidate, RoutingTrace, trace_routing

__all__ = [
    "DynamicEntry",
    "DynamicOntology",
    "MatchTier",
    "RouteCandidate",
    "RoutingTrace",
    "SEMANTIC_REGISTRY",
    "SemanticCategory",
    "contains_any_token",
    "contains_phrase",
    "contains_token",
    "count_tokens",
    "detect_instability_signal",
    "detect_mutation_scope",
    "get_provenance",
    "get_tier",
    "get_words",
    "has_cross_scope",
    "has_high_stakes",
    "has_medium_stakes",
    "has_vagueness",
    "match_tier",
    "needs_decomposition",
    "blocks_decomposition",
    "score_ambiguity",
    "score_subjectivity",
    "signals_escalation",
    "signals_scope_shrink",
    "signals_scope_widen",
    "trace_routing",
]
