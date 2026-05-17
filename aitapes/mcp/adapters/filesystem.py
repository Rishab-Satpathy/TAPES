"""Filesystem MCP Adapter — Read/Write operations

All operations are permission-checked before execution.
Authority level determines which operations are allowed.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any


def read_file(path: str, encoding: str = "utf-8") -> dict[str, Any]:
    """Read file contents.

    Returns: {"success": true, "content": str, "path": str}
    """
    try:
        p = Path(path).resolve()
        content = p.read_text(encoding=encoding)
        return {"success": True, "content": content, "path": str(p), "size": len(content)}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def list_directory(path: str, pattern: str | None = None) -> dict[str, Any]:
    """List directory contents.

    Args:
        path: Directory path
        pattern: Optional glob pattern filter

    Returns: {"success": true, "entries": [...], "path": str}
    """
    try:
        p = Path(path).resolve()
        if not p.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        entries = []
        for entry in p.iterdir():
            if pattern and not entry.match(pattern):
                continue
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
                "path": str(entry),
            })

        return {"success": True, "entries": entries, "path": str(p), "count": len(entries)}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def search_files(
    root: str,
    pattern: str,
    file_pattern: str = "*",
    max_results: int = 100,
) -> dict[str, Any]:
    """Search files by name pattern.

    Args:
        root: Root directory to search
        pattern: Regex pattern to match
        file_pattern: Glob pattern for files (default: *)
        max_results: Maximum results to return

    Returns: {"success": true, "matches": [...], "count": int}
    """
    try:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            return {"success": False, "error": f"Not a directory: {root}"}

        regex = re.compile(pattern)
        matches = []

        for file_path in root_path.rglob(file_pattern):
            if ".venv" in str(file_path) or "__pycache__" in str(file_path):
                continue
            if file_path.is_file() and regex.search(file_path.name):
                matches.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "relative": str(file_path.relative_to(root_path)),
                    "size": file_path.stat().st_size,
                })
                if len(matches) >= max_results:
                    break

        return {"success": True, "matches": matches, "count": len(matches), "pattern": pattern}
    except re.error as e:
        return {"success": False, "error": f"Invalid regex: {e}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def get_file_info(path: str) -> dict[str, Any]:
    """Get file/directory metadata.

    Returns: {"success": true, "info": {...}}
    """
    try:
        p = Path(path).resolve()
        stat = p.stat()

        info = {
            "name": p.name,
            "path": str(p),
            "type": "dir" if p.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "readable": os.access(p, os.R_OK),
            "writable": os.access(p, os.W_OK),
            "executable": os.access(p, os.X_OK),
        }

        if p.is_file():
            info["extension"] = p.suffix

        return {"success": True, "info": info}
    except FileNotFoundError:
        return {"success": False, "error": f"Path not found: {path}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def read_multiple_files(paths: list[str]) -> dict[str, Any]:
    """Read multiple files at once.

    Args:
        paths: List of file paths

    Returns: {"success": true, "files": {path: content}, "errors": [...]}
    """
    results: dict[str, str] = {}
    errors: list[str] = []

    for path in paths:
        result = read_file(path)
        if result["success"]:
            results[path] = result["content"]
        else:
            errors.append(f"{path}: {result['error']}")

    return {
        "success": True,
        "files": results,
        "count": len(results),
        "errors": errors if errors else None,
    }


def write_file(path: str, content: str, encoding: str = "utf-8") -> dict[str, Any]:
    """Write content to file.

    Requires DEV authority or higher.
    """
    try:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"success": True, "path": str(p), "size": len(content)}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def copy_file(src: str, dst: str) -> dict[str, Any]:
    """Copy file or directory.

    Requires DEV authority or higher.
    """
    try:
        src_path = Path(src).resolve()
        dst_path = Path(dst).resolve()

        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)

        return {"success": True, "src": str(src_path), "dst": str(dst_path)}
    except FileNotFoundError:
        return {"success": False, "error": f"Source not found: {src}"}
    except PermissionError:
        return {"success": False, "error": f"Permission denied"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def delete_file(path: str, recursive: bool = False) -> dict[str, Any]:
    """Delete file or directory.

    Requires DEV authority and is destructive.
    """
    try:
        p = Path(path).resolve()

        if p.is_dir():
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()
        else:
            p.unlink()

        return {"success": True, "path": str(p)}
    except FileNotFoundError:
        return {"success": False, "error": f"Path not found: {path}"}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}