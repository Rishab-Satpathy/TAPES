"""Shell MCP Adapter — Command execution

All operations are permission-checked.
DEV authority required for command execution.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run_command(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
    shell: bool = True,
) -> dict[str, Any]:
    """Run shell command.

    Args:
        command: Command to execute
        cwd: Working directory (default: current)
        env: Environment variables
        timeout: Max execution time in seconds
        shell: Run through shell

    Returns: {"success": true, "stdout": str, "stderr": str, "returncode": int}
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout}s",
            "command": command,
            "returncode": -1,
        }
    except PermissionError:
        return {
            "success": False,
            "error": "Permission denied to execute command",
            "command": command,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Command not found: {command.split()[0]}",
            "command": command,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "command": command,
        }


def run_python(
    code: str,
    timeout: int = 60,
    args: list[str] | None = None,
) -> dict[str, Any]:
    """Run Python code in subprocess.

    Args:
        code: Python code to execute
        timeout: Max execution time in seconds
        args: Command-line arguments to pass

    Returns: {"success": true, "stdout": str, "stderr": str, "returncode": int}
    """
    try:
        python_exec = sys.executable

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            script_path = f.name

        cmd_args = [python_exec, script_path]
        if args:
            cmd_args.extend(args)

        result = subprocess.run(
            cmd_args,
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
            "error": f"Python execution timed out after {timeout}s",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "returncode": -1,
        }
    finally:
        try:
            Path(script_path).unlink()
        except Exception:
            pass


def run_tests(
    test_path: str,
    pytest_args: str = "-x --tb=short",
    cwd: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run pytest on specified path.

    Args:
        test_path: Path to tests
        pytest_args: Arguments for pytest
        cwd: Working directory
        timeout: Max execution time in seconds

    Returns: {"success": true, "stdout": str, "stderr": str, "returncode": int}
    """
    pytest_cmd = f"python -m pytest {test_path} {pytest_args}"
    return run_command(pytest_cmd, cwd=cwd, timeout=timeout)


def build_package(
    package_path: str,
    build_cmd: str = "python -m build",
    cwd: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Build Python package.

    Args:
        package_path: Path to package directory
        build_cmd: Build command
        cwd: Working directory
        timeout: Max execution time in seconds

    Returns: {"success": true, "stdout": str, "stderr": str, "returncode": int}
    """
    return run_command(build_cmd, cwd=cwd or package_path, timeout=timeout)