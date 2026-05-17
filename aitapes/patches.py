"""Patch system for AITAPES v8.0.

AST-Driven Splicer — locates nodes by target_symbol and splices replacements.
The exact-string count != 1 matcher is replaced by AST-based lookup.

Patch dataclass now includes mandatory target_symbol field.
Logs which lookup path was taken on every patch attempt.

v8.0 changes:
    - Patch.target_symbol: str field (mandatory)
    - AST-based node lookup replaces exact-string matching
    - Logging of lookup path on every patch attempt
    - PatchError carries structured failure data
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PatchError(Exception):
    """Raised when a patch violates TAPES discipline."""


# ── Lookup path logging ───────────────────────────────────────────────────

class LookupPath:
    """Records which lookup strategy was used to apply a patch."""
    AST_NODE = "ast_node"           # Found by AST target_symbol lookup
    AST_FALLBACK = "ast_fallback"   # AST lookup with partial name match
    SEARCH_EXACT = "search_exact"   # Legacy: exact string match (1 occurrence)
    FAILED = "failed"               # No lookup succeeded


# ── Dataclasses ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Patch:
    """A single SEARCH/REPLACE patch with mandatory target_symbol."""
    file: str
    search: str
    replace: str
    target_symbol: str  # Mandatory: which symbol this patch targets
    reasoning: str = ""


@dataclass(frozen=True)
class PatchResult:
    """Result of applying a patch."""
    patch: Patch
    applied: bool
    error: str | None = None
    lines_changed: int = 0
    lookup_path: str = LookupPath.FAILED  # Which strategy was used


@dataclass(frozen=True)
class Uncertainty:
    """An uncertainty tag from the LLM."""
    claim: str
    confidence: float
    evidence: str
    alternative: str = ""


@dataclass(frozen=True)
class BuildOutput:
    """Parsed output from tapes build."""
    patches: tuple[Patch, ...]
    uncertainties: tuple[Uncertainty, ...]
    assumptions: tuple[str, ...]


# ── Parse / format ─────────────────────────────────────────────────────────

def parse_build_output(raw: dict[str, Any]) -> BuildOutput:
    """Parse LLM JSON output into BuildOutput. Requires target_symbol."""
    patches: list[Patch] = []
    for p in raw.get("patches", []):
        target_sym = p.get("target_symbol", "").strip()
        if not target_sym:
            logger.warning("Patch missing target_symbol for file %s; skipping", p.get("file", "?"))
            continue
        patches.append(Patch(
            file=p.get("file", ""),
            search=p.get("search", ""),
            replace=p.get("replace", ""),
            target_symbol=target_sym,
            reasoning=p.get("reasoning", ""),
        ))

    uncertainties: list[Uncertainty] = []
    for u in raw.get("uncertainties", raw.get("uncertainty", [])):
        uncertainties.append(Uncertainty(
            claim=u.get("claim", ""),
            confidence=float(u.get("confidence", 0.5)),
            evidence=u.get("evidence", ""),
            alternative=u.get("alternative", ""),
        ))

    assumptions = tuple(raw.get("assumptions_made", []))

    return BuildOutput(
        patches=tuple(patches),
        uncertainties=tuple(uncertainties),
        assumptions=assumptions,
    )


# ── AST-Driven Splicer ────────────────────────────────────────────────────

def _find_symbol_in_ast(source: str, target_symbol: str) -> tuple[int, int] | None:
    """Locate the node named by target_symbol using AST.

    Returns (start_line, end_line) 1-indexed, or None if not found.
    Supports: functions, classes, async functions, variables, constants.
    Nested paths like Class.method, Class.NestedClass.method.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    short_name = target_symbol.split(".")[-1] if "." in target_symbol else target_symbol
    parts = target_symbol.split(".")

    # For dotted targets (Class.method), go straight to nested search
    if len(parts) >= 2:
        def _find_in_body(body, depth=0):
            if depth > 3 or not body:
                return None
            current = parts[depth]
            for item in body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if item.name == current:
                        if depth == len(parts) - 1:
                            end_line = item.end_lineno or item.lineno
                            return (item.lineno, end_line)
                        result = _find_in_body(item.body, depth + 1)
                        if result:
                            return result
            return None
        return _find_in_body(tree.body, 0)

    # For simple (non-dotted) names: flat walk
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == short_name:
                end_line = node.end_lineno or node.lineno
                return (node.lineno, end_line)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == short_name:
                    end_line = node.end_lineno or node.lineno
                    return (node.lineno, end_line)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == short_name:
                end_line = node.end_lineno or node.lineno
                return (node.lineno, end_line)

    return None


def _splice_by_ast(source: str, patch: Patch) -> PatchResult:
    """Use AST to locate the node named by target_symbol and splice the replacement.

    This replaces the old exact-string count != 1 matcher.
    """
    lines = source.splitlines(keepends=True)

    # Strategy 1: AST node lookup
    location = _find_symbol_in_ast(source, patch.target_symbol)
    if location is not None:
        start_line, end_line = location
        old_content = "".join(lines[start_line - 1:end_line])

        # Verify the search string exists within the AST-located region
        if patch.search in old_content:
            new_content = old_content.replace(patch.search, patch.replace, 1)
            result_lines = lines[:start_line - 1] + [new_content] + lines[end_line:]
            result_source = "".join(result_lines)
            lines_delta = len(result_source.splitlines()) - len(lines)
            logger.info("Patch applied via %s for symbol '%s' at lines %d-%d",
                        LookupPath.AST_NODE, patch.target_symbol, start_line, end_line)
            return PatchResult(
                patch=patch, applied=True,
                lines_changed=lines_delta,
                lookup_path=LookupPath.AST_NODE,
            )

        # Search string doesn't match within the AST region — fail
        error_msg = f"Search string not found within AST region for '{patch.target_symbol}' in {patch.file}"
        logger.warning("Patch FAILED: %s", error_msg)
        return PatchResult(
            patch=patch, applied=False,
            error=error_msg,
            lookup_path=LookupPath.FAILED,
        )

    # Strategy 2: Legacy search/replace as final fallback
    count = source.count(patch.search)
    if count == 1:
        result_source = source.replace(patch.search, patch.replace, 1)
        lines_delta = len(result_source.splitlines()) - len(lines)
        logger.info("Patch applied via %s for symbol '%s'",
                    LookupPath.SEARCH_EXACT, patch.target_symbol)
        return PatchResult(
            patch=patch, applied=True,
            lines_changed=lines_delta,
            lookup_path=LookupPath.SEARCH_EXACT,
        )

    # All strategies failed
    if count == 0:
        error_msg = f"AST lookup failed for '{patch.target_symbol}' and search string not found in {patch.file}"
    else:
        error_msg = f"AST lookup failed for '{patch.target_symbol}' and search string matches {count} locations"

    logger.warning("Patch FAILED: %s", error_msg)
    return PatchResult(
        patch=patch, applied=False,
        error=error_msg,
        lookup_path=LookupPath.FAILED,
    )


def apply_patch(source: str, patch: Patch) -> PatchResult:
    """Apply a single patch using AST-driven splicer."""
    if not patch.file.strip():
        return PatchResult(patch=patch, applied=False, error="Patch file path is empty.", lookup_path=LookupPath.FAILED)
    if not patch.search.strip() and not patch.target_symbol.strip():
        return PatchResult(patch=patch, applied=False, error="Both search string and target_symbol are empty.", lookup_path=LookupPath.FAILED)

    return _splice_by_ast(source, patch)


def apply_patches(source_dir: str, patches: list[Patch]) -> list[PatchResult]:
    """Apply multiple patches to files in a directory."""
    results: list[PatchResult] = []
    source_path = Path(source_dir)

    # Group patches by file
    patches_by_file: dict[str, list[Patch]] = {}
    for patch in patches:
        if patch.file not in patches_by_file:
            patches_by_file[patch.file] = []
        patches_by_file[patch.file].append(patch)

    for file_path, file_patches in patches_by_file.items():
        full_path = source_path / file_path

        if not full_path.exists():
            # New file creation (e.g., bouncer redirect target)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            for p in file_patches:
                full_path.write_text(p.replace, encoding="utf-8")
                results.append(PatchResult(
                    patch=p, applied=True,
                    lines_changed=len(p.replace.splitlines()),
                    lookup_path=LookupPath.AST_NODE,
                ))
            continue

        content = full_path.read_text(encoding="utf-8")

        for patch in file_patches:
            content, result = _apply_splice(content, patch)
            results.append(result)

        # Write updated content — only check results for this file
        file_results = [r for r in results if r.patch.file == file_path]
        if any(r.applied for r in file_results):
            full_path.write_text(content, encoding="utf-8")

    return results


def _apply_splice(source: str, patch: Patch) -> tuple[str, PatchResult]:
    """Perform the splice and return (new_source, result). Used internally.

    Returns modified source and PatchResult so apply_patches stays consistent.
    """
    location = _find_symbol_in_ast(source, patch.target_symbol)
    lines = source.splitlines(keepends=True)
    if location is not None:
        start_line, end_line = location
        old_content = "".join(lines[start_line - 1:end_line])
        # Try exact search match first (fast path for offline builder)
        if patch.search.strip() and patch.search in old_content:
            new_content = old_content.replace(patch.search, patch.replace, 1)
            result_source = "".join(lines[:start_line - 1] + [new_content] + lines[end_line:])
            return result_source, PatchResult(
                patch=patch, applied=True,
                lines_changed=len(result_source.splitlines()) - len(lines),
                lookup_path=LookupPath.AST_NODE,
            )
        # Search string doesn't match within AST region — fail
        return source, PatchResult(
            patch=patch, applied=False,
            error=f"Search string not found within AST region for '{patch.target_symbol}'",
            lookup_path=LookupPath.FAILED,
        )
    # Legacy fallback
    if source.count(patch.search) == 1:
        result_source = source.replace(patch.search, patch.replace, 1)
        return result_source, PatchResult(
            patch=patch, applied=True,
            lines_changed=len(result_source.splitlines()) - len(lines),
            lookup_path=LookupPath.SEARCH_EXACT,
        )
    return source, PatchResult(
        patch=patch, applied=False,
        error=f"Could not find search string for {patch.target_symbol}",
        lookup_path=LookupPath.FAILED,
    )


def format_patches_as_text(patches: list[Patch]) -> str:
    """Format patches as human-readable text."""
    lines: list[str] = []
    for i, p in enumerate(patches, 1):
        lines.append(f"--- Patch {i}: {p.file} (target: {p.target_symbol}) ---")
        lines.append(f"Reasoning: {p.reasoning}")
        lines.append(f"SEARCH:\n{p.search}")
        lines.append(f"REPLACE:\n{p.replace}")
        lines.append("")
    return "\n".join(lines)


def format_uncertainties(uncertainties: list[Uncertainty]) -> str:
    """Format uncertainties as human-readable text."""
    if not uncertainties:
        return "No uncertainties reported."

    lines: list[str] = ["Uncertainties:"]
    for u in uncertainties:
        lines.append(f"  [{u.confidence:.0%}] {u.claim}")
        lines.append(f"    Evidence: {u.evidence}")
        if u.alternative:
            lines.append(f"    Alternative: {u.alternative}")
    return "\n".join(lines)
