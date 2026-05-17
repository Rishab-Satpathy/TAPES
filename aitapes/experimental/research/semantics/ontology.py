"""Canonical pressure vocabulary and semantic registry for TAPES.

This module defines the single source of truth for pressure-related
semantic categories. All modules that classify ambiguity, instability,
or pressure MUST use these registries to prevent ontology drift.

Each registry entry includes:
    - canonical name
    - word list (for matching)
    - provenance (why these words belong together)
    - matching tier (how they should be matched)
"""

from __future__ import annotations

from enum import StrEnum

from .matching import MatchTier


class SemanticCategory(StrEnum):
    # Ambiguity cluster
    AMBIGUITY = "ambiguity"
    SUBJECTIVITY = "subjectivity"
    CROSS_SCOPE = "cross_scope"
    VAGUENESS = "vagueness"

    # Stakes cluster
    HIGH_STAKES = "high_stakes"
    MEDIUM_STAKES = "medium_stakes"

    # Intent classification
    PATCH_INTENT = "patch_intent"
    BUG_INTENT = "bug_intent"
    FEATURE_INTENT = "feature_intent"
    REFACTOR_INTENT = "refactor_intent"
    TEST_INTENT = "test_intent"
    EXPLAIN_INTENT = "explain_intent"

    # Evidence routing
    RUNTIME_EVIDENCE = "runtime_evidence"
    DEPENDENCY_EVIDENCE = "dependency_evidence"
    INTERFACE_EVIDENCE = "interface_evidence"
    COMPONENT_EVIDENCE = "component_evidence"
    SECURITY_EVIDENCE = "security_evidence"

    # Instability signals
    INSTABILITY_HIGH = "instability_high"
    INSTABILITY_MODERATE = "instability_moderate"

    # Mutation scope signals
    MUTATION_BROAD = "mutation_broad"
    MUTATION_EXACT = "mutation_exact"
    MUTATION_LOCAL = "mutation_local"

    # Decomposition triggers
    DECOMPOSITION_NEEDED = "decomposition_needed"
    DECOMPOSITION_BLOCKED = "decomposition_blocked"

    # Pressure escalation signals
    PRESSURE_ESCALATION = "pressure_escalation"
    PRESSURE_MAINTAIN = "pressure_maintain"

    # Scope widening signals
    SCOPE_WIDEN = "scope_widen"
    SCOPE_SHRINK = "scope_shrink"


# Registry: category -> (words, tier, provenance)
SEMANTIC_REGISTRY: dict[SemanticCategory, tuple[tuple[str, ...], MatchTier, str]] = {
    # --- Ambiguity cluster ---
    SemanticCategory.AMBIGUITY: (
        ("some", "maybe", "appropriate", "reasonable", "etc", "and so on", "handle", "stuff", "thing"),
        MatchTier.TOKEN,
        "Words that weaken task specificity; matched by word boundary to avoid false positives like 'awesome' containing 'some'.",
    ),
    SemanticCategory.SUBJECTIVITY: (
        ("best", "good", "better", "should", "ideal", "perfect"),
        MatchTier.TOKEN,
        "Subjective quality judgments that resist deterministic validation.",
    ),
    SemanticCategory.CROSS_SCOPE: (
        ("across", "all files", "whole repo", "entire project", "dependencies", "integration"),
        MatchTier.TOKEN,
        "Scope-expanding terms that increase reasoning spread risk.",
    ),
    SemanticCategory.VAGUENESS: (
        ("some", "maybe", "appropriate", "reasonable", "etc", "and so on", "thing", "stuff"),
        MatchTier.TOKEN,
        "Vague terms needing clarification. Differs from AMBIGUITY: excludes 'handle' which is action-oriented.",
    ),

    # --- Stakes cluster ---
    SemanticCategory.HIGH_STAKES: (
        ("production", "security", "payment", "auth", "legal", "medical", "critical"),
        MatchTier.TOKEN,
        "Domain terms indicating high-consequence mutation territory.",
    ),
    SemanticCategory.MEDIUM_STAKES: (
        ("important", "review", "release", "customer"),
        MatchTier.TOKEN,
        "Terms indicating elevated but non-critical stakes.",
    ),

    # --- Intent classification ---
    SemanticCategory.PATCH_INTENT: (
        ("patch", "search", "replace", "edit"),
        MatchTier.TOKEN,
        "Exact-match mutation intent. Checked before BUG_INTENT in classification priority.",
    ),
    SemanticCategory.BUG_INTENT: (
        ("bug", "fix", "error", "crash", "broken", "fails", "failure"),
        MatchTier.TOKEN,
        "Defect correction intent.",
    ),
    SemanticCategory.FEATURE_INTENT: (
        ("feature", "add", "build", "implement", "create"),
        MatchTier.TOKEN,
        "New capability intent.",
    ),
    SemanticCategory.REFACTOR_INTENT: (
        ("refactor", "cleanup", "simplify", "restructure"),
        MatchTier.TOKEN,
        "Structural improvement intent.",
    ),
    SemanticCategory.TEST_INTENT: (
        ("test", "pytest", "unit test", "coverage"),
        MatchTier.TOKEN,
        "Testing intent.",
    ),
    SemanticCategory.EXPLAIN_INTENT: (
        ("explain", "why", "describe", "understand"),
        MatchTier.TOKEN,
        "Documentation/comprehension intent.",
    ),

    # --- Evidence routing ---
    SemanticCategory.RUNTIME_EVIDENCE: (
        ("trace", "runtime", "stack", "crash log", "exception"),
        MatchTier.TOKEN,
        "Runtime observation terms that route to EXECUTION_TRACE representation.",
    ),
    SemanticCategory.DEPENDENCY_EVIDENCE: (
        ("dependency", "import", "coupling", "module graph", "topology"),
        MatchTier.TOKEN,
        "Structural coupling terms that route to TOPOLOGY_GRAPH representation.",
    ),
    SemanticCategory.INTERFACE_EVIDENCE: (
        ("api", "interface", "schema", "type", "contract"),
        MatchTier.TOKEN,
        "Type system terms that route to TYPED_INTERFACE_GRAPH representation.",
    ),
    SemanticCategory.COMPONENT_EVIDENCE: (
        ("ui", "component", "screen", "layout", "button"),
        MatchTier.TOKEN,
        "UI structure terms that route to COMPONENT_HIERARCHY representation.",
    ),
    SemanticCategory.SECURITY_EVIDENCE: (
        ("security", "permission", "data flow", "injection", "trust boundary"),
        MatchTier.TOKEN,
        "Security surface terms that route to DATA_FLOW_GRAPH representation.",
    ),

    # --- Instability signals ---
    SemanticCategory.INSTABILITY_HIGH: (
        ("flaky", "intermittent", "race condition", "deadlock", "timeout", "memory leak", "segfault", "corrupt"),
        MatchTier.TOKEN,
        "Terms indicating high instability that require adversarial validation.",
    ),
    SemanticCategory.INSTABILITY_MODERATE: (
        ("sometimes fails", "occasionally", "inconsistent", "unreliable", "deprecated"),
        MatchTier.TOKEN,
        "Terms indicating moderate instability that increase validation pressure.",
    ),

    # --- Mutation scope signals ---
    SemanticCategory.MUTATION_BROAD: (
        ("rewrite all", "full rewrite", "complete rewrite", "start over", "from scratch", "blanket"),
        MatchTier.PHRASE,
        "Terms indicating broad mutation scope. Uses PHRASE tier because 'rewrite all' is a multi-word signal.",
    ),
    SemanticCategory.MUTATION_EXACT: (
        ("search replace", "search/replace", "exact patch", "find and replace", "find/replace"),
        MatchTier.PHRASE,
        "Terms indicating exact-match mutation scope.",
    ),
    SemanticCategory.MUTATION_LOCAL: (
        ("this function", "this method", "this class", "this file", "local only", "one function"),
        MatchTier.PHRASE,
        "Terms indicating local mutation scope.",
    ),

    # --- Decomposition triggers ---
    SemanticCategory.DECOMPOSITION_NEEDED: (
        ("multiple things", "several issues", "all of these", "everything", "all the", "both"),
        MatchTier.TOKEN,
        "Terms indicating the task should be decomposed into subtasks.",
    ),
    SemanticCategory.DECOMPOSITION_BLOCKED: (
        ("single", "atomic", "one thing", "only", "just this", "exactly one"),
        MatchTier.PHRASE,
        "Terms indicating the task should NOT be decomposed.",
    ),

    # --- Pressure escalation signals ---
    SemanticCategory.PRESSURE_ESCALATION: (
        ("escalate", "need more power", "stronger model", "better model", "give up", "too hard"),
        MatchTier.PHRASE,
        "Terms indicating the current cognition surface is insufficient.",
    ),
    SemanticCategory.PRESSURE_MAINTAIN: (
        ("keep going", "continue", "maintain", "proceed", "same approach"),
        MatchTier.PHRASE,
        "Terms indicating current pressure level is appropriate.",
    ),

    # --- Scope widening signals ---
    SemanticCategory.SCOPE_WIDEN: (
        ("need more context", "wider scope", "see more", "look at", "consider", "related to"),
        MatchTier.PHRASE,
        "Terms indicating the reasoning surface should be widened.",
    ),
    SemanticCategory.SCOPE_SHRINK: (
        ("narrow", "focused", "just this", "only this", "stay local", "don't expand"),
        MatchTier.PHRASE,
        "Terms indicating the reasoning surface should be narrowed.",
    ),
}


def get_words(category: SemanticCategory) -> tuple[str, ...]:
    return SEMANTIC_REGISTRY[category][0]


def get_tier(category: SemanticCategory) -> MatchTier:
    return SEMANTIC_REGISTRY[category][1]


def get_provenance(category: SemanticCategory) -> str:
    return SEMANTIC_REGISTRY[category][2]
