"""MCP Adapters for AITAPES v8.0.

Adapters for filesystem, shell, git, and docker operations.
These adapters are registered as handlers in the tool registry.
"""

from __future__ import annotations

import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Filesystem Adapter ────────────────────────────────────────────────────────

def fs_read(path: str, **kwargs: Any) -> str:
    """Read file contents."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return f.read()


def fs_write(path: str, content: str, **kwargs: Any) -> dict[str, Any]:
    """Write content to a file."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        f.write(content)
    return {"written": str(p), "size": len(content)}


def fs_list(path: str = ".", **kwargs: Any) -> list[str]:
    """List directory contents."""
    p = Path(path).resolve()
    if not p.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    return [str(e.name) for e in p.iterdir()]


__all__ = ["fs_read", "fs_write", "fs_list"]


# ── Shell Adapter ─────────────────────────────────────────────────────────────

def shell_run(command: str, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Execute a shell command."""
    try:
        script_path: str | None = None
        if os.name == "nt":
            temp = Path(os.environ.get("TEMP", "/tmp"))
            temp.mkdir(parents=True, exist_ok=True)
            script_file = temp / "tapes_shell_cmd.ps1"
            script_file.write_text(command, encoding="utf-8")
            script_path = str(script_file)

        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path] if script_path else command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 60),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass


# ── Git Adapter ──────────────────────────────────────────────────────────────

def git_status(**kwargs: Any) -> str:
    """Show git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or "No changes"
    except Exception as e:
        return f"Git error: {e}"


def git_branch(name: str, **kwargs: Any) -> dict[str, str]:
    """Create a new git branch."""
    try:
        subprocess.run(["git", "checkout", "-b", name], check=True, timeout=10)
        return {"branch": name, "created": True}
    except subprocess.CalledProcessError as e:
        return {"branch": name, "created": False, "error": str(e)}


# ── Docker Adapter ───────────────────────────────────────────────────────────

def docker_build(tag: str, path: str = ".", **kwargs: Any) -> dict[str, Any]:
    """Build a Docker image."""
    try:
        result = subprocess.run(
            ["docker", "build", "-t", tag, path],
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 300),
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return {"tag": tag, "success": success, "output": output[-500:]}
    except Exception as e:
        return {"tag": tag, "success": False, "error": str(e)}


def docker_run(image: str, command: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Run a Docker container."""
    try:
        cmd = ["docker", "run", "--rm", image]
        if command:
            cmd.extend(["sh", "-c", command])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 120),
        )
        return {
            "image": image,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"image": image, "success": False, "error": str(e)}


def docker_push(tag: str, **kwargs: Any) -> dict[str, Any]:
    """Push Docker image to registry."""
    try:
        result = subprocess.run(
            ["docker", "push", tag],
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 180),
        )
        return {"tag": tag, "success": result.returncode == 0, "output": result.stdout}
    except Exception as e:
        return {"tag": tag, "success": False, "error": str(e)}


# ── Register adapters ─────────────────────────────────────────────────────────

def register_adapters() -> None:
    """Register all filesystem, shell, git, and docker adapters."""
    from ..registry import get_registry

    registry = get_registry()

    adapter_map = {
        "fs_read": fs_read,
        "fs_write": fs_write,
        "fs_list": fs_list,
        "shell_run": shell_run,
        "git_status": git_status,
        "git_branch": git_branch,
        "docker_build": docker_build,
        "docker_run": docker_run,
        "docker_push": docker_push,
    }

    for name, handler in adapter_map.items():
        tool = registry.get(name)
        if tool:
            tool.handler = handler
            logger.debug("Registered adapter for tool: %s", name)


register_adapters()