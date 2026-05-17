"""LSP Mimic for TAPES v8.0.

Cherry-picked from NovelIdeaEdition's ast_extractor.
Provides SymbolIndex, ReferenceResolver, ScopeExtractor,
and GoToDefinitionSimulator for IDE-like functionality.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SymbolInfo:
    """Information about an extracted symbol."""
    name: str
    kind: str  # "function", "class", "method", "module"
    file: str
    line_start: int
    line_end: int
    source: str


@dataclass
class SymbolIndex:
    """Index of all symbols in a source tree."""
    _symbols: dict[str, SymbolInfo] = field(default_factory=dict)
    _file_symbols: dict[str, list[str]] = field(default_factory=dict)

    def index_dir(self, source_dir: str) -> None:
        """Index all Python files in a directory."""
        source_path = Path(source_dir)
        for py_file in source_path.rglob("*.py"):
            rel = str(py_file.relative_to(source_path))
            if ".venv" in rel or "__pycache__" in rel:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                self._index_source(rel, source)
            except (SyntaxError, UnicodeDecodeError):
                continue

    def _index_source(self, file_path: str, source: str) -> None:
        """Index a single Python file."""
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return

        module_name = file_path.replace("\\", ".").replace("/", ".").removesuffix(".py")
        symbols_in_file: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym_name = f"{module_name}.{node.name}"
                end_line = node.end_lineno or node.lineno
                source_lines = source.splitlines()
                sym_source = "\n".join(source_lines[node.lineno - 1:end_line])
                self._symbols[sym_name] = SymbolInfo(
                    name=sym_name,
                    kind="function",
                    file=file_path,
                    line_start=node.lineno,
                    line_end=end_line,
                    source=sym_source,
                )
                symbols_in_file.append(sym_name)

            elif isinstance(node, ast.ClassDef):
                class_name = f"{module_name}.{node.name}"
                end_line = node.end_lineno or node.lineno
                source_lines = source.splitlines()
                class_source = "\n".join(source_lines[node.lineno - 1:end_line])
                self._symbols[class_name] = SymbolInfo(
                    name=class_name,
                    kind="class",
                    file=file_path,
                    line_start=node.lineno,
                    line_end=end_line,
                    source=class_source,
                )
                symbols_in_file.append(class_name)

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = f"{class_name}.{item.name}"
                        m_end = item.end_lineno or item.lineno
                        method_source = "\n".join(source_lines[item.lineno - 1:m_end])
                        self._symbols[method_name] = SymbolInfo(
                            name=method_name,
                            kind="method",
                            file=file_path,
                            line_start=item.lineno,
                            line_end=m_end,
                            source=method_source,
                        )
                        symbols_in_file.append(method_name)

        self._file_symbols[file_path] = symbols_in_file

    def get_symbol(self, name: str) -> SymbolInfo | None:
        """Get a symbol by name."""
        if name in self._symbols:
            return self._symbols[name]
        short = name.split(".")[-1]
        candidates = [s for s in self._symbols.values() if s.name.endswith(f".{short}")]
        return candidates[0] if len(candidates) == 1 else None

    def get_symbols_in_file(self, file_path: str) -> list[SymbolInfo]:
        """Get all symbols defined in a file."""
        names = self._file_symbols.get(file_path, [])
        return [self._symbols[n] for n in names if n in self._symbols]


@dataclass
class ReferenceResolver:
    """Resolves references to symbols across the codebase."""
    _call_graph: list[tuple[str, str]] = field(default_factory=list)  # (caller, callee)
    _reverse_deps: dict[str, list[str]] = field(default_factory=dict)

    def build_from_index(self, index: SymbolIndex) -> None:
        """Build reference graph from a symbol index."""
        self._call_graph.clear()
        self._reverse_deps.clear()

        for sym in index._symbols.values():
            try:
                tree = ast.parse(sym.source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        callee = self._resolve_call(node)
                        if callee:
                            self._call_graph.append((sym.name, callee))
                            if callee not in self._reverse_deps:
                                self._reverse_deps[callee] = []
                            self._reverse_deps[callee].append(sym.name)
            except SyntaxError:
                continue

    def _resolve_call(self, call: ast.Call) -> str | None:
        """Resolve a call node to a name."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts = [func.attr]
            obj = func.value
            while isinstance(obj, ast.Attribute):
                parts.append(obj.attr)
                obj = obj.value
            if isinstance(obj, ast.Name):
                parts.append(obj.id)
            return ".".join(reversed(parts))
        return None

    def get_references(self, symbol_name: str) -> list[str]:
        """Get all symbols that reference the given symbol."""
        return self._reverse_deps.get(symbol_name, [])


@dataclass
class ScopeExtractor:
    """Extracts scope information for symbols."""
    _scopes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def extract_from_source(self, file_path: str, source: str) -> None:
        """Extract scope information from source code."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = {
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno or node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "locals": self._get_local_names(node),
                    "globals": list(node.globals) if hasattr(node, "globals") else [],
                }
                self._scopes[f"{file_path}:{node.lineno}"] = scope

    def _get_local_names(self, node: ast.AST) -> list[str]:
        """Get locally defined names in a scope."""
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
        return list(names)

    def get_scope(self, file_path: str, line: int) -> dict[str, Any] | None:
        """Get scope info for a location."""
        key = f"{file_path}:{line}"
        return self._scopes.get(key)


class GoToDefinitionSimulator:
    """Simulates IDE go-to-definition functionality."""

    def __init__(self, index: SymbolIndex) -> None:
        self._index = index

    def goto_definition(self, file_path: str, line: int, col: int) -> SymbolInfo | None:
        """Simulate go-to-definition at a position."""
        symbols = self._index.get_symbols_in_file(file_path)
        for sym in symbols:
            if sym.line_start <= line <= sym.line_end:
                return sym
        return None

    def find_references(self, symbol_name: str, resolver: ReferenceResolver) -> list[SymbolInfo]:
        """Find all references to a symbol."""
        refs = resolver.get_references(symbol_name)
        return [self._index.get_symbol(name) for name in refs if self._index.get_symbol(name)]