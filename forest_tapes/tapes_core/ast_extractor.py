"""AST-Subgraph Extractor for TAPES v8.0.

Builds the ASTExtractor interface backed by Python's `ast`.
Extracts call graph and reverse dependency map for a given target_symbol.

Exposes:
    - get_relevant_tests(symbol, test_dir) — for the LEC
    - get_subgraph_context(symbol) — for the Surgeon prompt
    - get_dataflow_context(symbol) — for Omega debate context
"""

from __future__ import annotations

import ast
import os
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
    decorators: tuple[str, ...] = ()


@dataclass(frozen=True)
class CallEdge:
    """A directed edge in the call graph: caller → callee."""
    caller: str
    callee: str
    file: str
    line: int


@dataclass(frozen=True)
class SubgraphContext:
    """Context for a symbol's dependency subgraph."""
    target: SymbolInfo | None
    calls: tuple[CallEdge, ...]        # outgoing calls from target
    callers: tuple[CallEdge, ...]       # incoming calls to target
    related_symbols: tuple[SymbolInfo, ...]  # definitions reachable from target
    node_count: int                     # total AST nodes in subgraph
    summary: str


@dataclass
class ASTExtractor:
    """Extracts call graph and reverse dependency map from Python source.

    Usage:
        extractor = ASTExtractor(source_dir="./my_project")
        extractor.index()

        context = extractor.get_subgraph_context("my_module.my_function")
        tests = extractor.get_relevant_tests("my_module.my_function", "tests/")
    """
    source_dir: str
    _symbols: dict[str, SymbolInfo] = field(default_factory=dict)
    _call_graph: list[CallEdge] = field(default_factory=list)
    _reverse_deps: dict[str, list[str]] = field(default_factory=dict)
    _indexed: bool = False

    def index(self) -> None:
        """Scan all Python files and build the call graph."""
        self._symbols.clear()
        self._call_graph.clear()
        self._reverse_deps.clear()

        source_path = Path(self.source_dir)
        for py_file in source_path.rglob("*.py"):
            rel = str(py_file.relative_to(source_path))
            if ".venv" in rel or "__pycache__" in rel or ".egg-info" in rel:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                self._index_file(rel, source)
            except (SyntaxError, UnicodeDecodeError):
                continue

        # Build reverse dependency map
        for edge in self._call_graph:
            if edge.callee not in self._reverse_deps:
                self._reverse_deps[edge.callee] = []
            self._reverse_deps[edge.callee].append(edge.caller)

        self._indexed = True

    def _index_file(self, file_path: str, source: str) -> None:
        """Index a single Python file."""
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            # Feature 4: The Shattered Host Shield
            print(f"  [SHATTERED HOST] SyntaxError detected in {file_path}. Booting Zero-Context Repair Mode...")
            try:
                from aitapes.llm import call_llm_json
                system = "You are the Surgeon in Zero-Context Repair Mode. Fix the syntax error in the provided code."
                prompt = f"Fix this file. It has a syntax error.\n\n```python\n{source}\n```\n\nReturn VALID JSON ONLY: {{\"repaired_code\": \"<full source code here>\"}}"
                raw = call_llm_json(prompt, system=system)
                if "repaired_code" in raw:
                    repaired_source = raw["repaired_code"]
                    import difflib
                    diff = list(difflib.unified_diff(
                        source.splitlines(keepends=True),
                        repaired_source.splitlines(keepends=True),
                        fromfile=file_path,
                        tofile=file_path + ".repaired"
                    ))
                    if diff:
                        print(f"  [SHATTERED HOST] Proposed fix for {file_path}:")
                        print("".join(diff))
                        from forest_tapes.tapes_core.interaction import ask_user
                        if ask_user("  Apply this repair? (y/N): ", default=False):
                            full_path = Path(self.source_dir) / file_path
                            full_path.write_text(repaired_source, encoding="utf-8")
                            print(f"  [SHATTERED HOST] Repair successful for {file_path}. Resuming graph math.")
                            tree = ast.parse(repaired_source, filename=file_path)
                        else:
                            print("  [SHATTERED HOST] Repair rejected.")
                            return
                    else:
                        return
                else:
                    return
            except Exception as e:
                print(f"  [SHATTERED HOST] Repair failed: {e}")
                return

        module_name = file_path.replace(os.sep, ".").replace("/", ".").removesuffix(".py")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym_name = f"{module_name}.{node.name}"
                end_line = node.end_lineno or node.lineno
                source_lines = source.splitlines()
                sym_source = "\n".join(source_lines[node.lineno - 1:end_line])
                decorators = tuple(
                    ast.dump(d) if not isinstance(d, ast.Name) else d.id
                    for d in node.decorator_list
                )
                self._symbols[sym_name] = SymbolInfo(
                    name=sym_name,
                    kind="function",
                    file=file_path,
                    line_start=node.lineno,
                    line_end=end_line,
                    source=sym_source,
                    decorators=decorators,
                )
                # Extract calls from function body
                self._extract_calls(sym_name, node, file_path)

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
                # Index methods
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
                        self._extract_calls(method_name, item, file_path)

    def _extract_calls(self, caller: str, node: ast.AST, file_path: str) -> None:
        """Extract call edges from an AST node."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee_name = self._resolve_call_name(child)
                if callee_name:
                    self._call_graph.append(CallEdge(
                        caller=caller,
                        callee=callee_name,
                        file=file_path,
                        line=child.lineno,
                    ))

    def _resolve_call_name(self, call: ast.Call) -> str | None:
        """Resolve a call node to a name string."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: list[str] = [func.attr]
            obj = func.value
            while isinstance(obj, ast.Attribute):
                parts.append(obj.attr)
                obj = obj.value
            if isinstance(obj, ast.Name):
                parts.append(obj.id)
            return ".".join(reversed(parts))
        return None

    def get_symbol(self, symbol_name: str) -> SymbolInfo | None:
        """Look up a symbol by name. Tries exact match, then suffix match."""
        if not self._indexed:
            self.index()
        if symbol_name in self._symbols:
            return self._symbols[symbol_name]
        # Suffix match: "my_function" matches "module.my_function"
        candidates = [s for s in self._symbols.values() if s.name.endswith(f".{symbol_name}")]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def get_subgraph_context(self, symbol_name: str) -> SubgraphContext:
        """Get the subgraph context for a symbol — for the Surgeon prompt.

        Returns the symbol's source, outgoing calls, incoming callers, and
        related symbol definitions.
        """
        if not self._indexed:
            self.index()

        target = self.get_symbol(symbol_name)
        if target is None:
            return SubgraphContext(
                target=None,
                calls=(),
                callers=(),
                related_symbols=(),
                node_count=0,
                summary=f"Symbol '{symbol_name}' not found in indexed source.",
            )

        # Outgoing calls from target
        calls = tuple(e for e in self._call_graph if e.caller == target.name)

        # Incoming calls to target (reverse deps)
        reverse_callers = self._reverse_deps.get(target.name, [])
        # Also match by short name
        short_name = target.name.split(".")[-1]
        for callee, callers in self._reverse_deps.items():
            if callee.endswith(f".{short_name}") or callee == short_name:
                reverse_callers.extend(callers)
        callers = tuple(
            e for e in self._call_graph
            if e.caller in set(reverse_callers) and (e.callee == target.name or e.callee.endswith(f".{short_name}"))
        )

        # Related symbols: definitions of callees
        related: list[SymbolInfo] = []
        for edge in calls:
            sym = self.get_symbol(edge.callee)
            if sym and sym.name != target.name:
                related.append(sym)

        # Count AST nodes in target
        node_count = 0
        if target.source:
            try:
                tree = ast.parse(target.source)
                node_count = sum(1 for _ in ast.walk(tree))
            except SyntaxError:
                pass

        return SubgraphContext(
            target=target,
            calls=calls,
            callers=callers,
            related_symbols=tuple(related),
            node_count=node_count,
            summary=(
                f"Symbol: {target.name} ({target.kind}) at {target.file}:{target.line_start}-{target.line_end}\n"
                f"Outgoing calls: {len(calls)}, Callers: {len(callers)}, "
                f"Related defs: {len(related)}, AST nodes: {node_count}"
            ),
        )

    def get_dataflow_context(self, symbol_name: str) -> str:
        """Get data flow context for Omega debate — traces how data flows
        through the symbol and its dependencies."""
        if not self._indexed:
            self.index()

        ctx = self.get_subgraph_context(symbol_name)
        if ctx.target is None:
            return f"No data flow context: symbol '{symbol_name}' not found."

        lines = [
            "DATA FLOW CONTEXT",
            f"Target: {ctx.target.name}",
            f"File: {ctx.target.file}:{ctx.target.line_start}-{ctx.target.line_end}",
            "",
            "--- Target Source ---",
            ctx.target.source,
            "",
        ]

        if ctx.calls:
            lines.append("--- Outgoing Data Flow ---")
            for edge in ctx.calls:
                lines.append(f"  → {edge.callee} (line {edge.line})")
                sym = self.get_symbol(edge.callee)
                if sym:
                    # Show first 5 lines of callee
                    preview = "\n".join(sym.source.splitlines()[:5])
                    lines.append(f"    {preview}")
            lines.append("")

        if ctx.callers:
            lines.append("--- Incoming Data Flow ---")
            for edge in ctx.callers:
                lines.append(f"  ← {edge.caller} (line {edge.line})")
            lines.append("")

        return "\n".join(lines)

    def get_relevant_tests(self, symbol_name: str, test_dir: str) -> list[str]:
        """Find test files that are relevant to a symbol — for the LEC.

        Scans test files for references to the symbol name (direct or imported).
        """
        if not self._indexed:
            self.index()

        target = self.get_symbol(symbol_name)
        short_name = symbol_name.split(".")[-1] if "." in symbol_name else symbol_name

        test_path = Path(self.source_dir) / test_dir
        relevant: list[str] = []

        if not test_path.exists():
            return relevant

        for test_file in test_path.rglob("test_*.py"):
            try:
                content = test_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            # Check if the test file references the symbol
            if short_name in content:
                rel = str(test_file.relative_to(Path(self.source_dir)))
                relevant.append(rel)
                continue

            # Check imports
            if target and target.file:
                module_stem = target.file.replace(os.sep, ".").replace("/", ".").removesuffix(".py")
                if module_stem in content:
                    rel = str(test_file.relative_to(Path(self.source_dir)))
                    relevant.append(rel)

        return relevant

    def count_nodes(self, source_code: str) -> int:
        """Count AST nodes in source code. Used for patch complexity scoring."""
        try:
            tree = ast.parse(source_code)
            return sum(1 for _ in ast.walk(tree))
        except SyntaxError:
            return 0

    def all_symbols(self) -> list[SymbolInfo]:
        """Return all indexed symbols."""
        if not self._indexed:
            self.index()
        return list(self._symbols.values())

    def db_imports_detected(self) -> bool:
        """Scan for database-related imports (sqlite3, sqlalchemy, psycopg2, django.db)."""
        target_imports = {"sqlite3", "sqlalchemy", "psycopg2", "django.db"}
        
        source_path = Path(self.source_dir)
        for py_file in source_path.rglob("*.py"):
            rel = str(py_file.relative_to(source_path))
            if ".venv" in rel or "__pycache__" in rel or ".egg-info" in rel:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=rel)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            if any(name.name.startswith(t) for t in target_imports):
                                return True
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and any(node.module.startswith(t) for t in target_imports):
                            return True
            except (SyntaxError, UnicodeDecodeError):
                continue
        return False

    # ── V9.0 Centrality Upgrade ────────────────────────────────────────────

    def compute_pagerank(
        self,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> dict[str, float]:
        """Compute PageRank centrality for all symbols in the call graph.

        Uses iterative power method. Returns {symbol_name: centrality_score}.
        Isolated leaf nodes score near 0; core architectural hubs score high.

        Args:
            damping: PageRank damping factor (probability of following a link)
            max_iterations: Maximum iterations for convergence
            tolerance: Convergence threshold
        """
        if not self._indexed:
            self.index()

        # Collect all unique nodes
        nodes: set[str] = set()
        for edge in self._call_graph:
            nodes.add(edge.caller)
            nodes.add(edge.callee)
        # Also add all indexed symbols
        nodes.update(self._symbols.keys())

        if not nodes:
            return {}

        node_list = sorted(nodes)
        n = len(node_list)
        node_idx = {name: i for i, name in enumerate(node_list)}

        # Build adjacency: outgoing links per node
        outgoing: dict[int, list[int]] = {i: [] for i in range(n)}
        for edge in self._call_graph:
            caller_idx = node_idx.get(edge.caller)
            callee_idx = node_idx.get(edge.callee)
            if caller_idx is not None and callee_idx is not None:
                outgoing[caller_idx].append(callee_idx)

        # Initialize PageRank uniformly
        rank = [1.0 / n] * n
        base = (1.0 - damping) / n

        for _ in range(max_iterations):
            new_rank = [base] * n

            for i in range(n):
                if outgoing[i]:
                    share = rank[i] / len(outgoing[i])
                    for j in outgoing[i]:
                        new_rank[j] += damping * share
                else:
                    # Dangling node: distribute evenly
                    dangling_share = damping * rank[i] / n
                    for j in range(n):
                        new_rank[j] += dangling_share

            # Check convergence
            diff = sum(abs(new_rank[i] - rank[i]) for i in range(n))
            rank = new_rank
            if diff < tolerance:
                break

        # Normalize to [0, 1] range
        max_rank = max(rank) if rank else 1.0
        if max_rank > 0:
            rank = [r / max_rank for r in rank]

        return {node_list[i]: rank[i] for i in range(n)}

    def get_centrality(self, symbol_name: str) -> float:
        """Get the PageRank centrality score for a specific symbol.

        Returns:
            Centrality score in [0.0, 1.0]. Near 0.0 = isolated leaf,
            near 1.0 = core architectural hub.
        """
        ranks = self.compute_pagerank()

        # Try exact match first
        if symbol_name in ranks:
            return ranks[symbol_name]

        # Try suffix match
        short_name = symbol_name.split(".")[-1] if "." in symbol_name else symbol_name
        candidates = [(name, score) for name, score in ranks.items()
                       if name.endswith(f".{short_name}")]
        if len(candidates) == 1:
            return candidates[0][1]

        return 0.0
