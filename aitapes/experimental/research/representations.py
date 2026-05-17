"""Representation constructors for TAPES.

These modules actually build the representations that the router selects.
Without them, the router picks a label but the model sees nothing structured.

Representation types:
    - AST window: source code clipped to relevant lines
    - Dependency graph: import relationships between modules
    - Execution trace: stack frames and runtime events
    - Component hierarchy: UI component relationships
    - Data flow graph: source-to-sink paths
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ASTWindow:
    """A window of source code with AST context."""
    file_path: str
    lines: list[str]
    start_line: int
    end_line: int
    functions: list[str]
    classes: list[str]
    imports: list[str]


@dataclass(frozen=True)
class DependencyNode:
    """A single node in a dependency graph."""
    name: str
    file_path: str
    imports: tuple[str, ...]
    imported_by: tuple[str, ...]


@dataclass(frozen=True)
class DependencyGraph:
    """A graph of module dependencies."""
    nodes: tuple[DependencyNode, ...]
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExecutionFrame:
    """A single frame in an execution trace."""
    function: str
    file_path: str
    line_number: int
    locals_snapshot: dict[str, str]


@dataclass(frozen=True)
class ExecutionTrace:
    """A trace of execution through the code."""
    frames: tuple[ExecutionFrame, ...]
    error: str | None = None


@dataclass(frozen=True)
class ComponentNode:
    """A node in a component hierarchy."""
    name: str
    component_type: str  # "function", "class", "module"
    children: tuple[str, ...]


@dataclass(frozen=True)
class ComponentHierarchy:
    """A hierarchy of components."""
    root: ComponentNode
    all_nodes: tuple[ComponentNode, ...]


@dataclass(frozen=True)
class DataFlowEdge:
    """An edge in a data flow graph."""
    source: str
    sink: str
    data_type: str


@dataclass(frozen=True)
class DataFlowGraph:
    """A graph of data flow paths."""
    edges: tuple[DataFlowEdge, ...]
    sources: tuple[str, ...]
    sinks: tuple[str, ...]


def build_ast_window(source: str, file_path: str, target_line: int, window_lines: int) -> ASTWindow:
    """Build an AST window around a target line.

    Extracts functions, classes, and imports visible in the window.
    """
    lines = source.splitlines()
    start = max(0, target_line - window_lines // 2)
    end = min(len(lines), start + window_lines)
    window_lines_list = lines[start:end]

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    try:
        tree = ast.parse("\n".join(lines))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if start <= node.lineno <= end:
                    functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if start <= node.lineno <= end:
                    classes.append(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    if node.module:
                        imports.append(node.module)
    except SyntaxError:
        # Fallback: regex-based extraction
        for i, line in enumerate(window_lines_list, start=start + 1):
            if re.match(r"\s*def\s+\w+", line):
                match = re.match(r"\s*def\s+(\w+)", line)
                if match:
                    functions.append(match.group(1))
            elif re.match(r"\s*class\s+\w+", line):
                match = re.match(r"\s*class\s+(\w+)", line)
                if match:
                    classes.append(match.group(1))
            elif re.match(r"\s*(import|from)\s+", line):
                imports.append(line.strip())

    return ASTWindow(
        file_path=file_path,
        lines=window_lines_list,
        start_line=start + 1,
        end_line=end,
        functions=functions,
        classes=classes,
        imports=imports,
    )


def build_dependency_graph(source_dir: str) -> DependencyGraph:
    """Build a dependency graph from a source directory.

    Scans Python files for import statements and builds a graph.
    """
    nodes: list[DependencyNode] = []
    edges: list[tuple[str, str]] = []
    source_path = Path(source_dir)

    # First pass: collect all files and their imports
    file_imports: dict[str, list[str]] = {}
    for py_file in source_path.rglob("*.py"):
        rel_path = str(py_file.relative_to(source_path))
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            file_imports[rel_path] = imports
        except (SyntaxError, OSError):
            file_imports[rel_path] = []

    # Second pass: build nodes and edges
    for file_path, imports in file_imports.items():
        module_name = file_path.replace("/", ".").replace("\\", ".").replace(".py", "")
        imported_by: list[str] = []

        # Find what imports this module
        for other_file, other_imports in file_imports.items():
            for imp in other_imports:
                if module_name in imp or imp in module_name:
                    other_module = other_file.replace("/", ".").replace("\\", ".").replace(".py", "")
                    imported_by.append(other_module)
                    edges.append((other_module, module_name))

        nodes.append(DependencyNode(
            name=module_name,
            file_path=file_path,
            imports=tuple(imports),
            imported_by=tuple(imported_by),
        ))

    return DependencyGraph(nodes=tuple(nodes), edges=tuple(edges))


def build_execution_trace(frames: list[dict[str, str | int]], error: str | None = None) -> ExecutionTrace:
    """Build an execution trace from frame data.

    Each frame dict should have:
        - function: str
        - file_path: str
        - line_number: int
        - locals: dict[str, str] (optional)
    """
    trace_frames = []
    for frame in frames:
        trace_frames.append(ExecutionFrame(
            function=str(frame.get("function", "unknown")),
            file_path=str(frame.get("file_path", "unknown")),
            line_number=int(frame.get("line_number", 0)),
            locals_snapshot=dict(frame.get("locals", {})),
        ))
    return ExecutionTrace(frames=tuple(trace_frames), error=error)


def build_component_hierarchy(source: str, root_name: str = "root") -> ComponentHierarchy:
    """Build a component hierarchy from source code.

    Extracts functions and classes as components.
    """
    nodes: list[ComponentNode] = []

    try:
        tree = ast.parse(source)
        children: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                component = ComponentNode(
                    name=node.name,
                    component_type="function",
                    children=(),
                )
                nodes.append(component)
                children.append(node.name)
            elif isinstance(node, ast.ClassDef):
                class_children: list[str] = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_children.append(item.name)
                component = ComponentNode(
                    name=node.name,
                    component_type="class",
                    children=tuple(class_children),
                )
                nodes.append(component)
                children.append(node.name)

        root = ComponentNode(
            name=root_name,
            component_type="module",
            children=tuple(children),
        )
        return ComponentHierarchy(root=root, all_nodes=tuple(nodes))

    except SyntaxError:
        root = ComponentNode(name=root_name, component_type="module", children=())
        return ComponentHierarchy(root=root, all_nodes=())


def build_data_flow_graph(source: str) -> DataFlowGraph:
    """Build a data flow graph from source code.

    Identifies sources (assignments, function params) and sinks (returns, prints, assignments).
    """
    edges: list[DataFlowEdge] = []
    sources: list[str] = []
    sinks: list[str] = []

    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Function parameters are sources
                for arg in node.args.args:
                    sources.append(f"{node.name}.{arg.arg}")
                # Return statements are sinks
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        sinks.append(f"{node.name}.return")
                        if child.value:
                            edges.append(DataFlowEdge(
                                source=f"{node.name}.input",
                                sink=f"{node.name}.return",
                                data_type="return_value",
                            ))
            elif isinstance(node, ast.Assign):
                # Assignments are both sources and sinks
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        sinks.append(f"assign.{target.id}")
    except SyntaxError:
        pass

    return DataFlowGraph(edges=tuple(edges), sources=tuple(sources), sinks=tuple(sinks))
