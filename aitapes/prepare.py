"""PREPARE stage — hollow skeletons, symbol ranking, execution locality.

Converts full source files into ranked, compressed context for the LLM.
This is the biggest token saver in TAPES.

Optimizations:
- File hash cache avoids re-parsing unchanged files
- ThreadPoolExecutor parallelizes file processing
- Incremental index rebuilds only changed files
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# ── File hash cache ──────────────────────────────────────────────
_file_hashes: dict[str, str] = {}
_ast_cache: dict[str, ast.AST] = {}
_sym_cache: dict[str, dict] = {}


def _file_hash(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{stat.st_size}_{stat.st_mtime_ns}"
    except OSError:
        return ""


def _cached_parse(path: Path) -> ast.AST | None:
    h = _file_hash(path)
    sp = str(path)
    if sp in _ast_cache and _file_hashes.get(sp) == h:
        return _ast_cache[sp]
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        _ast_cache[sp] = tree
        _file_hashes[sp] = h
        return tree
    except (SyntaxError, OSError):
        return None


def _cached_symbols(path: Path) -> dict:
    h = _file_hash(path)
    sp = str(path)
    if sp in _sym_cache and _file_hashes.get(sp + "_sym") == h:
        return _sym_cache[sp]
    result = {"functions": [], "classes": [], "imports": [], "calls": []}
    tree = _cached_parse(path)
    if tree is None:
        return result
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(node.name)
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    result["calls"].append(child.func.attr)
                elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    result["calls"].append(child.func.id)
        elif isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                result["imports"].append(alias.name.split(".")[0])
    _sym_cache[sp] = result
    _file_hashes[sp + "_sym"] = h
    return result


def _cached_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ── File discovery ───────────────────────────────────────────────

def _find_python_files(source_dir: str) -> list[Path]:
    root = Path(source_dir).resolve()
    files = []
    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        if any(p.startswith(".") or p == "__pycache__" or p == ".venv" for p in rel.parts):
            continue
        files.append(f)
    return files


# ── Hollow skeleton ──────────────────────────────────────────────

def _hollow_skeleton(source: str) -> str:
    out = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines(keepends=True)
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            sig_start = node.lineno - 1
            sig_end = node.body[0].lineno - 2 if node.body and hasattr(node.body[0], 'lineno') else node.lineno
            for i in range(sig_start, max(sig_end, sig_start) + 1):
                if i not in seen_lines and i < len(lines):
                    stripped = lines[i].rstrip("\n")
                    if stripped.strip():
                        out.append(stripped)
                    seen_lines.add(i)
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)):
                doc = node.body[0].value.value if isinstance(node.body[0].value, ast.Constant) else node.body[0].value.s
                first_line = doc.strip().split("\n")[0]
                indent = " " * (node.col_offset + 4)
                out.append(f'{indent}"""' + first_line + '"""')
            out.append("")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            i = node.lineno - 1
            if i not in seen_lines and i < len(lines):
                stripped = lines[i].rstrip("\n")
                if stripped.strip():
                    out.append(stripped)
                seen_lines.add(i)
    return "\n".join(out)


# ── Call graph ───────────────────────────────────────────────────

def _build_call_graph(files: list[Path], source_dir: str) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    file_symbols: dict[str, set[str]] = {}
    root = Path(source_dir).resolve()
    for f in files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        syms = _cached_symbols(f)
        file_symbols[rel] = set(syms["functions"] + syms["classes"])
        graph[rel] = set(syms["calls"])
    for rel, calls in graph.items():
        resolved: set[str] = set()
        for call in calls:
            for other_rel, other_syms in file_symbols.items():
                if call in other_syms and other_rel != rel:
                    resolved.add(other_rel)
        graph[rel] = resolved
    return graph


# ── File scoring ─────────────────────────────────────────────────

def _score_file(
    rel_path: str,
    source: str,
    intent_tokens: set[str],
    target_symbols: set[str],
    call_graph: dict[str, set[str]],
    depth: int = 0,
    visited: set | None = None,
) -> float:
    if visited is None:
        visited = set()
    if rel_path in visited or depth > 3:
        return 0.0
    visited.add(rel_path)
    score = 0.0
    lower = source.lower()
    for sym in target_symbols:
        if sym in lower:
            score += 10.0 / (depth + 1)
    for token in intent_tokens:
        if token in lower:
            score += 2.0 / (depth + 1)
    syms = _cached_symbols(Path(rel_path))
    if rel_path in call_graph:
        for neighbor in call_graph[rel_path]:
            score += _score_file(neighbor, "", intent_tokens, target_symbols, call_graph, depth + 1, visited) * 0.3
    return score


# ── Main prepare ─────────────────────────────────────────────────

def prepare(
    source_dir: str,
    intent: str,
    target_symbols: list[str] | None = None,
    max_files: int = 5,
    hollow: bool = True,
) -> dict[str, Any]:
    files = _find_python_files(source_dir)
    intent_lower = intent.lower()
    intent_tokens = {t for t in re.split(r"\W+", intent_lower) if len(t) > 2}
    target_set = set(target_symbols) if target_symbols else set()
    root = Path(source_dir).resolve()

    # Parallel: build symbol index for all files
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        fut_syms = {pool.submit(_cached_symbols, f): f for f in files}
        fut_sources = {pool.submit(_cached_source, f): f for f in files}

        file_symbols: dict[str, dict] = {}
        full_sources: dict[str, str] = {}
        for fut in as_completed(fut_syms):
            f = fut_syms[fut]
            rel = str(f.relative_to(root)).replace("\\", "/")
            try:
                file_symbols[rel] = fut.result()
            except Exception:
                file_symbols[rel] = {"functions": [], "classes": [], "imports": [], "calls": []}
        for fut in as_completed(fut_sources):
            f = fut_sources[fut]
            rel = str(f.relative_to(root)).replace("\\", "/")
            try:
                full_sources[rel] = fut.result()
            except Exception:
                full_sources[rel] = ""

    call_graph = _build_call_graph(files, source_dir)

    # Parallel: score all files
    scored: list[tuple[float, str, str]] = []
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        fut_scores = {}
        for f in files:
            rel = str(f.relative_to(root)).replace("\\", "/")
            source = full_sources.get(rel, "")
            fut = pool.submit(_score_file, rel, source, intent_tokens, target_set, call_graph)
            fut_scores[fut] = (rel, source)
        for fut in as_completed(fut_scores):
            rel, source = fut_scores[fut]
            try:
                score = fut.result()
            except Exception:
                score = 0.0
            scored.append((score, rel, source))

    scored.sort(key=lambda x: -x[0])

    # Parallel: build hollow skeletons for top files
    ranked_files: list[tuple[str, float, str]] = []
    expanded: dict[str, str] = {}
    expanded_set: set[str] = set()

    top_files = [(score, rel, source) for score, rel, source in scored[:max_files * 2]]
    for score, rel, source in top_files:
        if target_set:
            for sym in target_set:
                if sym in source:
                    expanded[rel] = source
                    expanded_set.add(rel)
                    break

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        fut_skeletons = {}
        for score, rel, source in top_files:
            if rel in expanded_set:
                continue
            if hollow:
                fut = pool.submit(_hollow_skeleton, source)
                fut_skeletons[fut] = (score, rel, source)
        for fut in as_completed(fut_skeletons):
            score, rel, source = fut_skeletons[fut]
            try:
                content = fut.result()
            except Exception:
                content = source
            ranked_files.append((rel, score, content))

    for score, rel, source in top_files:
        if rel not in expanded_set and not any(r == rel for r, _, _ in ranked_files):
            ranked_files.append((rel, score, "" if hollow else source))

    ranked_files = ranked_files[:max_files]
    ranking = {rel: round(score, 1) for score, rel, _ in scored}

    retrieval_contract = {
        "intent": intent,
        "target_symbols": list(target_set) if target_set else [],
        "expanded_files": list(expanded.keys()),
        "skeleton_files": [r for r, _, _ in ranked_files if r not in expanded_set],
        "mutation_boundary": "local_edit",
        "total_files_scored": len(scored),
        "top_file": scored[0][1] if scored else "",
    }

    return {
        "files": ranked_files,
        "expanded": expanded,
        "symbols": file_symbols,
        "ranking": ranking,
        "retrieval_contract": retrieval_contract,
        "call_graph": call_graph,
    }


# ── Context formatting ──────────────────────────────────────────

def format_context(prepared: dict[str, Any], intent: str) -> str:
    parts = [f"Task: {intent}"]
    parts.append(f"Mutation boundary: local_edit.\n")
    if prepared["expanded"]:
        parts.append("=== TARGET DEFINITIONS (full code) ===")
        for path, source in prepared["expanded"].items():
            parts.append(f"\n# {path}\n```python\n{source}\n```")
    skeleton_files = [(p, s, c) for p, s, c in prepared["files"] if p not in prepared["expanded"]]
    if skeleton_files:
        parts.append("\n=== CONTEXT (signatures only) ===")
        for path, score, content in skeleton_files:
            if content.strip():
                parts.append(f"\n# {path}\n{content}")
    return "\n".join(parts)


# ── Diff formatting ──────────────────────────────────────────────

def format_diff(before: str, after: str, filepath: str = "") -> str:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=filepath,
        tofile=filepath,
        n=3,
    )
    return "".join(diff)


# ── Impacted test mapping ────────────────────────────────────────

_test_map: dict[str, set[str]] | None = None

def _build_test_map(source_dir: str) -> dict[str, set[str]]:
    """Map each source file to its related test files by import analysis."""
    global _test_map
    if _test_map is not None:
        return _test_map
    root = Path(source_dir).resolve()
    test_dirs = [root / "tests", root / "test"]
    mapping: dict[str, set[str]] = {}

    for td in test_dirs:
        if not td.exists():
            continue
        for tf in td.rglob("test_*.py"):
            try:
                source = tf.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in source.split("\n"):
                m = re.match(r"(?:from|import)\s+(?:\w+\.)*(\w+)", line.strip())
                if m:
                    mod = m.group(1)
                    if mod not in mapping:
                        mapping[mod] = set()
                    mapping[mod].add(str(tf))

    _test_map = mapping
    return mapping


def get_impacted_tests(source_dir: str, changed_files: list[str]) -> list[str]:
    """Return test files that import from any of the changed files."""
    mapping = _build_test_map(source_dir)
    tests: set[str] = set()
    for cf in changed_files:
        module_name = Path(cf).stem
        if module_name in mapping:
            tests.update(mapping[module_name])
    return sorted(tests)
