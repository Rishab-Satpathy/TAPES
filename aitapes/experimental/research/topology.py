"""Spatial Awareness Mapper for TAPES Foundation.

Maps the immediate folder depth (neighborhood) of a target file.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_gitignore(root_dir: str) -> list[str]:
    """Parse basic .gitignore patterns if pathspec is unavailable."""
    gitignore_path = Path(root_dir) / ".gitignore"
    if not gitignore_path.exists():
        return [".git", "__pycache__", ".venv", "venv", "node_modules"]
        
    patterns = [".git", "__pycache__", ".venv", "venv", "node_modules"]
    try:
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line.rstrip("/"))
    except OSError:
        pass
    return patterns

def _is_ignored(name: str, patterns: list[str]) -> bool:
    """Basic ignore check (exact match or simple glob)."""
    for p in patterns:
        if p == name or (p.startswith("*") and name.endswith(p[1:])):
            return True
    return False

def build_neighborhood_map(target_file: str, source_dir: str = ".") -> str:
    """
    Build a purely spatial neighborhood tree around the target file.
    Only maps the immediate parent directory and its children (siblings of target).
    """
    target_path = Path(source_dir) / target_file
    
    if not target_path.exists():
        # Fallback to root dir scan
        parent_dir = Path(source_dir).resolve()
    else:
        parent_dir = target_path.parent.resolve()

    ignore_patterns = _load_gitignore(source_dir)
    
    lines = [f"📁 {parent_dir.name}/"]
    
    try:
        entries = sorted(os.listdir(parent_dir))
        for entry in entries:
            if _is_ignored(entry, ignore_patterns):
                continue
                
            entry_path = parent_dir / entry
            if entry_path.is_dir():
                lines.append(f"  ├── 📁 {entry}/")
            else:
                if entry_path == target_path.resolve():
                    lines.append(f"  ├── 📄 {entry}  <-- TARGET")
                else:
                    lines.append(f"  ├── 📄 {entry}")
                    
    except OSError:
        lines.append("  [Error reading directory]")
        
    return "\n".join(lines)
