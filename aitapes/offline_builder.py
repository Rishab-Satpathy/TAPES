"""Offline code transformer — generates real patches without LLM.

Uses AST analysis + templates to produce meaningful code changes.
Demo-ready: no API keys needed, always works.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .patches import Patch, BuildOutput, Uncertainty


def _find_python_files(source_dir: str) -> list[Path]:
    root = Path(source_dir).resolve()
    files = []
    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        if any(p.startswith(".") or p == "__pycache__" or p == ".venv" for p in rel.parts):
            continue
        files.append(f)
    return files


def _classify_intent(intent: str) -> str:
    t = intent.lower()
    if "docstring" in t or "document" in t: return "add_docstrings"
    if "validate" in t or "validation" in t or "check" in t: return "add_validation"
    if "auth" in t or "token" in t or "bearer" in t or "authentication" in t: return "add_auth"
    if "pagination" in t or "page" in t or "total_count" in t: return "add_pagination"
    if "error" in t or "except" in t or "try" in t: return "add_error_handling"
    if "test" in t or "unit" in t: return "add_tests"
    if "rename" in t or "refactor" in t: return "rename_symbol"
    if "constant" in t or "config" in t: return "extract_constant"
    if "fix" in t or "bug" in t or "issue" in t: return "fix_common_bug"
    if " log " in t or "debug" in t: return "add_logging"
    if "type" in t and ("hint" in t or "annotation" in t): return "add_type_hints"
    return "add_docstrings"


def _needs_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", [])
    return not (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.Str)))


def _has_logging(node: ast.FunctionDef) -> bool:
    for s in node.body[:5]:
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Attribute):
            if isinstance(s.value.func.value, ast.Name) and s.value.func.value.id == "logger":
                return True
    return False


def generate_patches(source_dir: str, intent: str) -> BuildOutput:
    files = _find_python_files(source_dir)
    task = _classify_intent(intent)
    patches: list[Patch] = []
    root_path = Path(source_dir).resolve()

    for filepath in files:
        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        rel_path = str(filepath.relative_to(root_path)).replace("\\", "/")
        lines_list = source.splitlines(keepends=True)

        def node_text(node: ast.AST) -> str:
            end = max(getattr(node, 'end_lineno', node.lineno), node.lineno)
            return "".join(lines_list[node.lineno - 1:end])

        if task == "add_docstrings":
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if _needs_docstring(node):
                        full = node_text(node)
                        lines = full.split("\n")
                        header = lines[0]
                        body = "\n".join(lines[1:])
                        indent = " " * (node.col_offset + 4)
                        kind = "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class"
                        doc = _docstring_for(node.name, kind)
                        new = header + "\n" + indent + doc.strip() + ("\n" + body if body else "")
                        patches.append(Patch(file=rel_path, search=full, replace=new,
                            target_symbol=node.name, reasoning=f"Add {kind} docstring to {node.name}"))

        elif task == "add_logging":
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("__"):
                    if not _has_logging(node):
                        old = node_text(node)
                        indent = " " * (node.col_offset + 4)
                        new = old + f"\n{indent}import logging\n{indent}logger = logging.getLogger(__name__)\n{indent}logger.debug(\"Entering {node.name}()\")"
                        patches.append(Patch(file=rel_path, search=old, replace=new,
                            target_symbol=node.name, reasoning=f"Add logging to {node.name}()"))

        elif task == "add_validation":
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = [a.arg for a in node.args.args if a.arg != "self"]
                    if params:
                        param = params[0]
                        old = node_text(node)
                        indent = " " * (node.col_offset + 4)
                        new = old + f"\n{indent}if {param} is None:\n{indent}    raise ValueError(\"{param} cannot be None\")"
                        patches.append(Patch(file=rel_path, search=old, replace=new,
                            target_symbol=node.name, reasoning=f"Add None validation to {param}"))

        elif task == "extract_constant":
            for node in ast.walk(tree):
                if isinstance(node, (ast.Str, ast.Constant)) and isinstance(node.value if isinstance(node, ast.Constant) else node.s, str):
                    val = node.value if isinstance(node, ast.Constant) else node.s
                    if len(val) > 10 and not val.startswith("__"):
                        line = source.splitlines()[node.lineno - 1]
                        varname = re.sub(r'[^a-zA-Z_]', '', val.upper().replace(" ", "_")[:20]) or "CONFIG_VALUE"
                        patches.append(Patch(file=rel_path, search=line, replace=line + f"\n\n{varname} = {repr(val)}",
                            target_symbol=varname, reasoning=f"Extract constant {varname}"))
                    break

        elif task == "fix_common_bug":
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for stmt in node.body:
                        if isinstance(stmt, ast.Try):
                            for handler in stmt.handlers:
                                if handler.type is None or (isinstance(handler.type, ast.Name) and handler.type.id == "Exception"):
                                    if not handler.body or not isinstance(handler.body[-1], ast.Raise):
                                        old = node_text(handler)
                                        indent = " " * (handler.col_offset + 4)
                                        patches.append(Patch(file=rel_path, search=old, replace=old + f"\n{indent}logging.exception(\"Error in {node.name}()\")",
                                            target_symbol=node.name, reasoning=f"Add exception logging to {node.name}()"))

        elif task == "add_auth":
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith(("read_", "create_", "delete_", "list_", "get_", "post_", "put_")):
                    if not any("Authorization" in ast.dump(s) or "token" in ast.dump(s) for s in node.body[:5]):
                        old = node_text(node)
                        indent = " " * (node.col_offset + 4)
                        new = old.rstrip("\n") + f"\n{indent}    token = request.headers.get(\"Authorization\")\n{indent}    if not token or not token.startswith(\"Bearer \"):\n{indent}        raise HTTPException(status_code=401, detail=\"Invalid or missing token\")\n"
                        patches.append(Patch(file=rel_path, search=old, replace=new,
                            target_symbol=node.name, reasoning=f"Add auth token check to {node.name}()"))

        elif task == "add_pagination":
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and "list" in node.name.lower():
                    old_text = node_text(node)
                    if "total_count" not in old_text:
                        old = old_text
                        indent = " " * (node.col_offset + 4)
                        new = old.rstrip("\n") + f"\n{indent}    total = len(results) if isinstance(results, list) else 0\n{indent}    return {{\"data\": results, \"total_count\": total, \"page\": page, \"pages\": (total + limit - 1) // limit}}\n"
                        patches.append(Patch(file=rel_path, search=old, replace=new,
                            target_symbol=node.name, reasoning=f"Add pagination metadata to {node.name}()"))

        if len(patches) >= 5:
            break

    return BuildOutput(patches=tuple(patches[:5]), uncertainties=(), assumptions=())


def _docstring_for(name: str, kind: str = "function") -> str:
    return f'    """{name.replace("_", " ").title()}."""\n'


def display_patches(patches: list[Patch]) -> None:
    for i, p in enumerate(patches, 1):
        print(f"\n  Patch {i}: {p.file} -> {p.target_symbol}")
        print(f"    Reason: {p.reasoning[:60]}")
        print(f"    Search: {p.search[:60]}...")
        print(f"    Replace: {p.replace[:60]}...")
