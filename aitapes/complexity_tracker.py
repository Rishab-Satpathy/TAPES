"""Centrality-Weighted Context Refresh for TAPES v9.0.

Replaces the static patch_complexity >= 50 threshold with dynamic
PageRank/Eigenvector centrality of the target_symbol being patched.

Dynamic Refresh Logic:
    - Isolated leaf node (Centrality: 0.05): simply record, no refresh
    - Core architectural hub (Centrality: 0.85+): instant threshold breach,
      fetch original User Intent embedding from Ledger, force immediate
      latent-space refresh to re-anchor the architecture
    - Middle zone: weighted threshold = base_threshold / centrality
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Centrality thresholds
HUB_CENTRALITY_THRESHOLD = 0.85  # Instant breach for core architectural hubs
LEAF_CENTRALITY_THRESHOLD = 0.10  # Below this = isolated leaf, just record
BASE_COMPLEXITY_THRESHOLD = 50    # Scaled inversely by centrality


@dataclass
class ComplexityTracker:
    """Tracks patch complexity with centrality-weighted dynamic refresh.

    v9.0: Replaces static threshold with PageRank centrality.
    High-centrality patches (hubs) trigger immediate refresh.
    Low-centrality patches (leaves) are simply recorded.
    """
    patch_complexity: int = 0
    refresh_count: int = 0
    _applied_patches: list[dict[str, Any]] = field(default_factory=list)

    def add_patch(
        self,
        patch_source: str,
        target_symbol: str | None = None,
        source_dir: str = ".",
        patch_info: dict[str, Any] | None = None,
    ) -> bool:
        """Add a patch and check if centrality-weighted refresh is needed.

        Args:
            patch_source: The replacement source code of the patch
            target_symbol: The symbol being patched (for centrality lookup)
            source_dir: Project source directory (for AST indexing)
            patch_info: Optional metadata about the patch

        Returns:
            True if refresh is needed (hub breach or accumulated complexity)
        """
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        extractor = ASTExtractor(source_dir=source_dir)
        node_count = extractor.count_nodes(patch_source)
        self.patch_complexity += node_count

        # Compute centrality for the target symbol
        centrality = 0.0
        if target_symbol:
            extractor.index()
            centrality = extractor.get_centrality(target_symbol)

        self._applied_patches.append({
            "node_count": node_count,
            "cumulative": self.patch_complexity,
            "target_symbol": target_symbol,
            "centrality": centrality,
            **(patch_info or {}),
        })

        logger.info(
            "Patch: +%d nodes (total: %d), symbol=%s, centrality=%.3f",
            node_count, self.patch_complexity, target_symbol, centrality,
        )

        # If the target has NO incoming callers, it's structurally a leaf
        # regardless of PageRank normalization artifacts
        if target_symbol and centrality > 0:
            extractor.index()
            reverse_deps = extractor._reverse_deps
            short = target_symbol.split(".")[-1]
            has_callers = any(
                callee == target_symbol or callee.endswith(f".{short}")
                for callee in reverse_deps
            )
            if not has_callers:
                centrality = 0.0
                logger.debug(
                    "No incoming edges for %s — overriding centrality to 0.0",
                    target_symbol,
                )

        # HUB: Core architectural node — instant breach
        if centrality >= HUB_CENTRALITY_THRESHOLD:
            logger.info(
                "HUB BREACH: %s has centrality %.3f >= %.3f — forcing immediate refresh",
                target_symbol, centrality, HUB_CENTRALITY_THRESHOLD,
            )
            return True

        # LEAF: Isolated node — just record, no refresh
        if centrality < LEAF_CENTRALITY_THRESHOLD:
            logger.debug(
                "Leaf node: %s has centrality %.3f — recording only",
                target_symbol, centrality,
            )
            return False

        # MIDDLE ZONE: dynamic threshold = base / centrality
        # Higher centrality → lower threshold → easier to trigger
        dynamic_threshold = int(BASE_COMPLEXITY_THRESHOLD / max(centrality, 0.01))
        if self.patch_complexity >= dynamic_threshold:
            logger.info(
                "Dynamic threshold breach: complexity %d >= %d (centrality: %.3f)",
                self.patch_complexity, dynamic_threshold, centrality,
            )
            return True

        return False

    def trigger_reanchor(
        self,
        ledger_path: str,
        target_symbol: str | None = None,
        source_dir: str = ".",
    ) -> dict[str, Any]:
        """Fetch intent_embedding from the ledger and re-anchor the subgraph.

        Fetches the ORIGINAL User Intent embedding from the Ledger and
        forces an immediate latent-space refresh to re-anchor the architecture.
        """
        from aitapes.ledger import get_all_embeddings, append_entry
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        self.refresh_count += 1

        # Fetch intent embeddings from ledger
        embeddings = get_all_embeddings(ledger_path)
        # Use the FIRST (original) embedding for re-anchoring
        original_embedding = embeddings[0] if embeddings else []

        # Re-index AST and get fresh subgraph + centrality
        extractor = ASTExtractor(source_dir=source_dir)
        extractor.index()

        subgraph_context = None
        centrality = 0.0
        if target_symbol:
            ctx = extractor.get_subgraph_context(target_symbol)
            subgraph_context = ctx.summary
            centrality = extractor.get_centrality(target_symbol)

        refresh_event = {
            "event": "centrality_reanchor",
            "patch_complexity": self.patch_complexity,
            "centrality": centrality,
            "refresh_count": self.refresh_count,
            "embedding_dims": len(original_embedding) if original_embedding else 0,
            "target_symbol": target_symbol,
            "subgraph_context": subgraph_context,
            "hub_triggered": centrality >= HUB_CENTRALITY_THRESHOLD,
        }

        # Log the refresh event to the ledger
        append_entry(
            ledger_path=ledger_path,
            entry_type="build",
            command="centrality-reanchor",
            input_text=f"centrality_breach:{target_symbol}:{centrality:.3f}",
            output_summary=(
                f"Re-anchored subgraph (centrality: {centrality:.3f}, "
                f"complexity: {self.patch_complexity}, refresh #{self.refresh_count})"
            ),
            details=refresh_event,
            intent_embedding=original_embedding,
        )

        logger.info(
            "Centrality re-anchor #%d: centrality=%.3f, complexity=%d, target=%s",
            self.refresh_count, centrality, self.patch_complexity, target_symbol,
        )

        # Reset complexity counter
        self.patch_complexity = 0

        return refresh_event

    def summary(self) -> dict[str, Any]:
        return {
            "patch_complexity": self.patch_complexity,
            "refresh_count": self.refresh_count,
            "patches_tracked": len(self._applied_patches),
            "hub_threshold": HUB_CENTRALITY_THRESHOLD,
            "leaf_threshold": LEAF_CENTRALITY_THRESHOLD,
            "base_complexity_threshold": BASE_COMPLEXITY_THRESHOLD,
        }
