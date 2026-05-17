"""Runtime telemetry observer for TAPES.

Tracks real generation behavior and converts it into RuntimeSignals
that the pressure kernel can consume. Without this, the pressure
kernel runs on all-zero inputs and can never detect actual failures.

Usage:
    observer = RuntimeObserver()

    # After each generation attempt
    observer.record_patch_attempt(success=True)
    observer.record_syntax_check(passed=True)
    observer.record_assumption("inferred file path")

    # When switching representations
    observer.record_representation_switch()

    # When boundary widens
    observer.record_boundary_widen()

    # Get current signals
    signals = observer.get_signals()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .pressure_kernel import RuntimeSignals


@dataclass
class RuntimeObserver:
    """Tracks real generation behavior for the pressure kernel.

    Unlike RuntimeSignals (which is frozen and passed externally),
    this observer accumulates state across multiple generation attempts.
    """

    # Patch tracking
    patch_attempts: int = 0
    patch_failures: int = 0
    broad_rewrite_attempted: bool = False

    # Contradiction tracking
    contradiction_count: int = 0
    _contradictions_seen: set[str] = field(default_factory=set)

    # Branch tracking
    unresolved_branches: int = 0

    # Scope tracking
    out_of_scope_references: int = 0
    _out_of_scope_seen: set[str] = field(default_factory=set)

    # Representation tracking
    representation_switches: int = 0
    _last_representation: str | None = None

    # Validation tracking
    validation_failures: int = 0

    # Topology tracking
    topology_nodes_touched: int = 1

    # Failure pattern tracking
    similar_failures: int = 0
    _failure_signatures: list[str] = field(default_factory=list)

    # Syntax tracking
    syntax_failures: int = 0

    # Assumption tracking
    assumptions_made: int = 0
    _assumptions_seen: set[str] = field(default_factory=set)

    # Hallucination tracking
    hallucinated_imports: int = 0
    hallucinated_apis: int = 0
    _hallucinations_seen: set[str] = field(default_factory=set)

    def record_patch_attempt(self, success: bool) -> None:
        """Record a patch attempt."""
        self.patch_attempts += 1
        if not success:
            self.patch_failures += 1

    def record_broad_rewrite(self) -> None:
        """Record that a broad rewrite was attempted."""
        self.broad_rewrite_attempted = True

    def record_contradiction(self, description: str) -> None:
        """Record a contradiction found during generation."""
        sig = description.strip().lower()
        if sig not in self._contradictions_seen:
            self._contradictions_seen.add(sig)
            self.contradiction_count += 1

    def record_unresolved_branch(self) -> None:
        """Record an unresolved inference branch."""
        self.unresolved_branches += 1

    def record_out_of_scope(self, reference: str) -> None:
        """Record a reference made outside the allowed scope."""
        ref = reference.strip().lower()
        if ref not in self._out_of_scope_seen:
            self._out_of_scope_seen.add(ref)
            self.out_of_scope_references += 1

    def record_representation_switch(self, new_representation: str) -> None:
        """Record a switch in representation type."""
        if self._last_representation is not None and self._last_representation != new_representation:
            self.representation_switches += 1
        self._last_representation = new_representation

    def record_validation_failure(self) -> None:
        """Record a validation failure."""
        self.validation_failures += 1

    def record_topology_touch(self, node_count: int = 1) -> None:
        """Record topology nodes touched."""
        self.topology_nodes_touched = max(self.topology_nodes_touched, node_count)

    def record_similar_failure(self, signature: str) -> None:
        """Record a failure with a similar signature to a previous one."""
        self._failure_signatures.append(signature)
        # Count how many times this signature has been seen before
        count = self._failure_signatures.count(signature)
        if count > 1:
            self.similar_failures = max(self.similar_failures, count - 1)

    def record_syntax_failure(self) -> None:
        """Record a syntax error in generated code."""
        self.syntax_failures += 1

    def record_assumption(self, assumption: str) -> None:
        """Record an assumption made during generation."""
        a = assumption.strip().lower()
        if a not in self._assumptions_seen:
            self._assumptions_seen.add(a)
            self.assumptions_made += 1

    def record_hallucinated_import(self, module: str) -> None:
        """Record a hallucinated import (module doesn't exist)."""
        m = module.strip().lower()
        if m not in self._hallucinations_seen:
            self._hallucinations_seen.add(m)
            self.hallucinated_imports += 1

    def record_hallucinated_api(self, api: str) -> None:
        """Record a hallucinated API call (API doesn't exist)."""
        a = api.strip().lower()
        if a not in self._hallucinations_seen:
            self._hallucinations_seen.add(a)
            self.hallucinated_apis += 1

    def get_signals(self) -> RuntimeSignals:
        """Convert accumulated state to RuntimeSignals for the pressure kernel."""
        return RuntimeSignals(
            patch_attempts=self.patch_attempts,
            patch_failures=self.patch_failures,
            broad_rewrite_attempted=self.broad_rewrite_attempted,
            contradiction_count=self.contradiction_count,
            unresolved_branches=self.unresolved_branches,
            out_of_scope_references=self.out_of_scope_references,
            representation_switches=self.representation_switches,
            validation_failures=self.validation_failures,
            topology_nodes_touched=self.topology_nodes_touched,
            similar_failures=self.similar_failures,
        )

    def reset(self) -> None:
        """Reset observer state for a new generation session."""
        self.__init__()

    def summary(self) -> dict[str, int | bool]:
        """Return a summary of observed telemetry."""
        return {
            "patch_attempts": self.patch_attempts,
            "patch_failures": self.patch_failures,
            "syntax_failures": self.syntax_failures,
            "contradictions": self.contradiction_count,
            "out_of_scope_refs": self.out_of_scope_references,
            "representation_switches": self.representation_switches,
            "validation_failures": self.validation_failures,
            "similar_failures": self.similar_failures,
            "assumptions_made": self.assumptions_made,
            "hallucinated_imports": self.hallucinated_imports,
            "hallucinated_apis": self.hallucinated_apis,
            "broad_rewrite_attempted": self.broad_rewrite_attempted,
        }
