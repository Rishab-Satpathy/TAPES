"""Topological Drift Detection for TAPES v8.0 / v9.0.

Replaces vector-based semantic grounding with topological AST tracking.
"""
from __future__ import annotations

import re
from typing import Any


from forest_tapes.tapes_core.ast_extractor import ASTExtractor


def extract_expected_nodes(intent: str, extractor: ASTExtractor) -> set[str]:
    """Lightweight heuristic to find expected nodes based on intent and AST."""
    extractor.index()
    symbols = extractor.all_symbols()
    expected = set()
    intent_lower = intent.lower()
    
    for sym in symbols:
        short = sym.name.split(".")[-1].lower()
        if re.search(r'\b' + re.escape(short) + r'\b', intent_lower):
            expected.add(sym.name)
    return expected


def detect_topological_drift(
    intent: str,
    source_dir: str,
    historical_target_symbols: list[str],
) -> dict[str, Any]:
    """Detect topological drift and return Greenfield status + expected nodes."""
    extractor = ASTExtractor(source_dir=source_dir)
    expected_nodes = extract_expected_nodes(intent, extractor)
    
    historical_nodes = set(historical_target_symbols)

    intersection = expected_nodes.intersection(historical_nodes)
    
    # Greenfield if no expected nodes overlap with history
    is_greenfield = len(intersection) == 0
    
    return {
        "expected_nodes": list(expected_nodes),
        "historical_nodes": list(historical_nodes),
        "intersection": list(intersection),
        "is_greenfield": is_greenfield,
    }
