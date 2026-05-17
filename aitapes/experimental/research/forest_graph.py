"""Minimal forest topology graph for TAPES.

Builds a graph of files, imports, classes, and methods.
Used for:
    - Neighborhood widening
    - Blast-radius estimation
    - Local topology reasoning
    - Topology-aware representation routing
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileNode:
    """A file in the forest graph."""
    path: str
    module_name: str
    imports: tuple[str, ...]
    classes: tuple[str, ...]
    functions: tuple[str, ...]


@dataclass(frozen=True)
class ClassNode:
    """A class in the forest graph."""
    name: str
    file_path: str
    methods: tuple[str, ...]
    bases: tuple[str, ...]


@dataclass(frozen=True)
class ForestGraph:
    """A minimal dependency graph for topology-aware routing."""
    files: tuple[FileNode, ...]
    classes: tuple[ClassNode, ...]
    edges: tuple[tuple[str, str], ...]  # (source_module, target_module)


def build_forest_graph(source_dir: str) -> ForestGraph:
    """Build a forest graph from a source directory.

    Scans Python files and extracts:
    - File-level imports
    - Class definitions with methods
    - Function definitions
    """
    source_path = Path(source_dir)
    files: list[FileNode] = []
    classes: list[ClassNode] = []
    edges: list[tuple[str, str]] = []

    for py_file in source_path.rglob("*.py"):
        rel_path = str(py_file.relative_to(source_path))
        module_name = rel_path.replace("/", ".").replace("\\", ".").replace(".py", "")

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)

            imports: list[str] = []
            class_names: list[str] = []
            function_names: list[str] = []

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                        edges.append((module_name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                        edges.append((module_name, node.module))
                elif isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
                    methods: list[str] = []
                    bases: list[str] = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                    classes.append(ClassNode(
                        name=node.name,
                        file_path=rel_path,
                        methods=tuple(methods),
                        bases=tuple(bases),
                    ))
                elif isinstance(node, ast.FunctionDef):
                    function_names.append(node.name)

            files.append(FileNode(
                path=rel_path,
                module_name=module_name,
                imports=tuple(imports),
                classes=tuple(class_names),
                functions=tuple(function_names),
            ))

        except (SyntaxError, OSError):
            files.append(FileNode(
                path=rel_path,
                module_name=module_name,
                imports=(),
                classes=(),
                functions=(),
            ))

    return ForestGraph(
        files=tuple(files),
        classes=tuple(classes),
        edges=tuple(edges),
    )


def get_neighborhood(graph: ForestGraph, module_name: str, radius: int = 1) -> list[str]:
    """Get the neighborhood of a module within a given radius.

    radius=1: immediate imports
    radius=2: imports of imports
    """
    visited: set[str] = {module_name}
    current_level = [module_name]

    for _ in range(radius):
        next_level: list[str] = []
        for module in current_level:
            # Find what this module imports
            for source, target in graph.edges:
                if source == module and target not in visited:
                    visited.add(target)
                    next_level.append(target)
                elif target == module and source not in visited:
                    visited.add(source)
                    next_level.append(source)
        current_level = next_level

    return [m for m in visited if m != module_name]


def estimate_blast_radius(graph: ForestGraph, file_path: str) -> int:
    """Estimate the blast radius of changing a file.

    Returns the number of modules that would be affected.
    """
    # Find the module name for this file
    module_name = None
    for f in graph.files:
        if f.path == file_path:
            module_name = f.module_name
            break

    if module_name is None:
        return 0

    # Count all modules that import this module
    affected: set[str] = set()
    for source, target in graph.edges:
        if target == module_name:
            affected.add(source)

    return len(affected)


def get_topology_for_routing(graph: ForestGraph, file_path: str, radius: int = 1) -> list[str]:
    """Get topology information for representation routing.

    Returns a list of module names in the neighborhood.
    """
    module_name = None
    for f in graph.files:
        if f.path == file_path:
            module_name = f.module_name
            break

    if module_name is None:
        return []

    return get_neighborhood(graph, module_name, radius)
