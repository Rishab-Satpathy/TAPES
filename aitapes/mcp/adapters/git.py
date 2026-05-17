"""Git MCP Adapter — Version control operations

All operations are permission-checked.
SAFE authority allows read-only operations.
DEV authority allows branch operations.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run_git(args: list[str], cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
    """Run git command and return result."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Git command timed out after {timeout}s",
            "returncode": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "git command not found",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "returncode": -1,
        }


def git_status(cwd: str = ".") -> dict[str, Any]:
    """Show git working tree status.

    SAFE authority — read-only operation.
    """
    result = _run_git(["status", "--porcelain"], cwd=cwd)
    if result["success"]:
        lines = result["stdout"].strip().split("\n") if result["stdout"].strip() else []
        result["files"] = [line[2:] for line in lines if len(line) > 2]
        result["count"] = len(result["files"])
    return result


def git_diff(cwd: str = ".", target: str = "HEAD") -> dict[str, Any]:
    """Show changes between commits.

    SAFE authority — read-only operation.
    """
    result = _run_git(["diff", "--stat", target], cwd=cwd)
    return result


def git_log(
    cwd: str = ".",
    max_count: int = 10,
    format: str = "%h %s",
) -> dict[str, Any]:
    """Show commit logs.

    SAFE authority — read-only operation.
    """
    result = _run_git(["log", f"--max-count={max_count}", f"--pretty=format:{format}"], cwd=cwd)
    if result["success"]:
        result["commits"] = result["stdout"].strip().split("\n") if result["stdout"].strip() else []
    return result


def git_branch(
    operation: str = "list",
    name: str | None = None,
    cwd: str = ".",
) -> dict[str, Any]:
    """List/create/delete git branches.

    DEV authority — write operation.
    """
    if operation == "list":
        result = _run_git(["branch", "-a"], cwd=cwd)
        if result["success"]:
            result["branches"] = result["stdout"].strip().split("\n") if result["stdout"].strip() else []
        return result

    elif operation == "create" and name:
        result = _run_git(["checkout", "-b", name], cwd=cwd)
        if result["success"]:
            result["branch"] = name
        return result

    elif operation == "delete" and name:
        result = _run_git(["branch", "-d", name], cwd=cwd)
        if result["success"]:
            result["branch"] = name
        return result

    return {"success": False, "error": f"Unknown operation: {operation}"}


def git_commit(message: str, cwd: str = ".") -> dict[str, Any]:
    """Create a commit.

    DEV authority — write operation.
    """
    result = _run_git(["commit", "-m", message], cwd=cwd)
    if result["success"]:
        result["message"] = message
    return result


def git_add(paths: list[str], cwd: str = ".") -> dict[str, Any]:
    """Stage files for commit.

    DEV authority — write operation.
    """
    result = _run_git(["add"] + paths, cwd=cwd)
    if result["success"]:
        result["staged"] = paths
    return result


def git_stash(cwd: str = ".") -> dict[str, Any]:
    """Stash changes.

    DEV authority — write operation.
    """
    result = _run_git(["stash"], cwd=cwd)
    return result


def git_checkout(revision: str, cwd: str = ".") -> dict[str, Any]:
    """Checkout revision.

    DEV authority — write operation.
    """
    result = _run_git(["checkout", revision], cwd=cwd)
    return result