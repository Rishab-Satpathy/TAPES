"""Dynamic Ontology for TAPES v8.0.

Extends semantics/ontology.py to a class with a synchronous_update() method.
Wired to the checkpoint trigger in why_ledger.py.

The updater scans:
    - reasoning field of failed Patch objects
    - evidence field of failed check criteria

For terms absent from the current registry, adds confirmed anomalies
with a DYNAMIC provenance tag.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .matching import MatchTier
from .ontology import SEMANTIC_REGISTRY, SemanticCategory, get_words

logger = logging.getLogger(__name__)

# Minimum term length to avoid noise
MIN_TERM_LENGTH = 3

# Maximum dynamic entries per category
MAX_DYNAMIC_ENTRIES = 20

DYNAMIC_PROVENANCE = "DYNAMIC"


@dataclass
class DynamicEntry:
    """A dynamically discovered ontology term."""
    term: str
    category: SemanticCategory
    source: str  # "patch_reasoning" or "check_evidence"
    provenance: str = DYNAMIC_PROVENANCE
    occurrence_count: int = 1


@dataclass
class DynamicOntology:
    """Extends the static SEMANTIC_REGISTRY with dynamically discovered terms.

    Wired to checkpoint triggers in why_ledger.py. On each checkpoint,
    scans failed patches and checks for novel terms.
    """
    _dynamic_entries: dict[str, DynamicEntry] = field(default_factory=dict)
    _static_words: set[str] = field(default_factory=set)
    _initialized: bool = False

    def _ensure_initialized(self) -> None:
        """Cache all static words for fast lookup."""
        if self._initialized:
            return
        for category in SemanticCategory:
            try:
                words = get_words(category)
                self._static_words.update(w.lower() for w in words)
            except KeyError:
                continue
        self._initialized = True

    def synchronous_update(
        self,
        failed_patches: list[dict[str, Any]] | None = None,
        failed_checks: list[dict[str, Any]] | None = None,
    ) -> list[DynamicEntry]:
        """Scan failed patches and checks for terms absent from the registry.

        Args:
            failed_patches: List of dicts with 'reasoning' field
            failed_checks: List of dicts with 'evidence' field

        Returns:
            List of newly added DynamicEntry objects
        """
        self._ensure_initialized()
        new_entries: list[DynamicEntry] = []

        # Scan patch reasoning fields
        if failed_patches:
            for patch_data in failed_patches:
                reasoning = patch_data.get("reasoning", "")
                if reasoning:
                    found = self._extract_novel_terms(reasoning, "patch_reasoning")
                    new_entries.extend(found)

        # Scan check evidence fields
        if failed_checks:
            for check_data in failed_checks:
                evidence = check_data.get("evidence", "")
                if evidence:
                    found = self._extract_novel_terms(evidence, "check_evidence")
                    new_entries.extend(found)

        if new_entries:
            logger.info("Dynamic ontology update: %d new terms discovered", len(new_entries))
            for entry in new_entries:
                logger.debug("  + '%s' from %s → %s", entry.term, entry.source, entry.category.value)

        return new_entries

    def _extract_novel_terms(self, text: str, source: str) -> list[DynamicEntry]:
        """Extract terms from text that are absent from the static registry."""
        new_entries: list[DynamicEntry] = []

        # Tokenize: extract word-boundary tokens
        tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text.lower())

        # Also extract multi-word phrases (2-3 word sequences)
        words = text.lower().split()
        phrases: list[str] = []
        for i in range(len(words) - 1):
            phrase = " ".join(words[i:i+2])
            if len(phrase) >= MIN_TERM_LENGTH:
                phrases.append(phrase)
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if len(phrase) >= MIN_TERM_LENGTH:
                phrases.append(phrase)

        candidates = set(t for t in tokens if len(t) >= MIN_TERM_LENGTH)
        candidates.update(phrases)

        # Filter out terms already in static registry
        novel = candidates - self._static_words

        # Filter out common English stopwords
        stopwords = {
            "the", "and", "for", "not", "but", "with", "this", "that", "from",
            "are", "was", "were", "been", "have", "has", "had", "does", "did",
            "will", "would", "could", "should", "can", "may", "must", "shall",
            "its", "our", "your", "their", "all", "any", "each", "every",
            "none", "both", "other", "such", "into", "over", "than", "more",
            "most", "very", "also", "then", "just", "here", "there", "when",
            "where", "which", "while", "before", "after", "above", "below",
            "between", "through", "during", "without", "within", "about",
        }
        novel -= stopwords

        for term in novel:
            if term in self._dynamic_entries:
                self._dynamic_entries[term].occurrence_count += 1
                continue

            # Classify into the best-fit category
            category = self._classify_term(term, text)
            if category is None:
                continue

            # Check limit
            category_count = sum(
                1 for e in self._dynamic_entries.values()
                if e.category == category
            )
            if category_count >= MAX_DYNAMIC_ENTRIES:
                continue

            entry = DynamicEntry(
                term=term,
                category=category,
                source=source,
                provenance=DYNAMIC_PROVENANCE,
            )
            self._dynamic_entries[term] = entry
            new_entries.append(entry)

        return new_entries

    def _classify_term(self, term: str, context: str) -> SemanticCategory | None:
        """Classify a novel term into a semantic category based on context.

        Uses keyword heuristics on the surrounding context.
        """
        context_lower = context.lower()

        # Error/failure context → instability
        if any(w in context_lower for w in ("error", "fail", "crash", "bug", "exception")):
            return SemanticCategory.INSTABILITY_HIGH

        # Security context
        if any(w in context_lower for w in ("security", "injection", "vulnerability", "auth", "permission")):
            return SemanticCategory.SECURITY_EVIDENCE

        # Dependency context
        if any(w in context_lower for w in ("import", "dependency", "module", "coupling")):
            return SemanticCategory.DEPENDENCY_EVIDENCE

        # Ambiguity context
        if any(w in context_lower for w in ("unclear", "ambiguous", "vague", "uncertain")):
            return SemanticCategory.AMBIGUITY

        # Runtime context
        if any(w in context_lower for w in ("runtime", "trace", "stack", "execution")):
            return SemanticCategory.RUNTIME_EVIDENCE

        # Default: moderate instability (catch-all for failure-related terms)
        if any(w in context_lower for w in ("failed", "failure", "incorrect", "wrong")):
            return SemanticCategory.INSTABILITY_MODERATE

        return None

    def get_dynamic_words(self, category: SemanticCategory) -> tuple[str, ...]:
        """Get dynamically discovered words for a category."""
        return tuple(
            e.term for e in self._dynamic_entries.values()
            if e.category == category
        )

    def get_all_words(self, category: SemanticCategory) -> tuple[str, ...]:
        """Get static + dynamic words for a category."""
        static = get_words(category)
        dynamic = self.get_dynamic_words(category)
        return static + dynamic

    def all_dynamic_entries(self) -> list[DynamicEntry]:
        """Return all dynamic entries."""
        return list(self._dynamic_entries.values())

    def summary(self) -> dict[str, Any]:
        """Summary of dynamic ontology state."""
        by_category: dict[str, int] = {}
        for entry in self._dynamic_entries.values():
            cat = entry.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_dynamic_terms": len(self._dynamic_entries),
            "by_category": by_category,
            "by_source": {
                "patch_reasoning": sum(1 for e in self._dynamic_entries.values() if e.source == "patch_reasoning"),
                "check_evidence": sum(1 for e in self._dynamic_entries.values() if e.source == "check_evidence"),
            },
        }
