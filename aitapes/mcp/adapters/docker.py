"""Docker MCP Adapter — Container operations

All operations are permission-checked.
SAFE authority allows read-only operations (ps, logs).
FULL authority allows destructive operations (stop, rm).
"""

from __future__ import annotations

import subprocess
from typing import Any


def _run_docker(args: list[str], timeout: int = 60) -> dict[str, Any]:
    """Run docker command and return result."""
    try:
        result = subprocess.run(
            ["docker"] + args,
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
    except FileNotFoundError:
        return {
            "success": False,
            "error": "docker command not found — is Docker installed?",
            "returncode": -1,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Docker command timed out after {timeout}s",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "returncode": -1,
        }


def docker_ps(all_containers: bool = False) -> dict[str, Any]:
    """List running Docker containers.

    SAFE authority — read-only operation.
    """
    args = ["ps"]
    if all_containers:
        args.append("-a")

    result = _run_docker(args)
    if result["success"]:
        lines = result["stdout"].strip().split("\n") if result["stdout"].strip() else []
        headers = lines[0].split() if lines else []
        result["containers"] = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                result["containers"].append({
                    "id": parts[0],
                    "image": parts[1],
                    "status": " ".join(parts[2:]),
                })
    return result


def docker_logs(
    container: str,
    tail: int = 100,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch container logs.

    DEV authority — read operation.
    """
    args = ["logs", "--tail", str(tail), container]
    if since:
        args.extend(["--since", since])

    result = _run_docker(args, timeout=30)
    if result["success"]:
        result["logs"] = result["stdout"]
    return result


def docker_build(
    tag: str,
    path: str = ".",
    dockerfile: str = "Dockerfile",
) -> dict[str, Any]:
    """Build Docker image.

    FULL authority — build operation.
    """
    args = ["build", "-t", tag, "-f", dockerfile, path]
    result = _run_docker(args, timeout=600)
    if result["success"]:
        result["tag"] = tag
        result["path"] = path
    return result


def docker_run(
    image: str,
    name: str | None = None,
    detach: bool = True,
    ports: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run Docker container.

    FULL authority — run operation.
    """
    args = ["run"]
    if detach:
        args.append("-d")
    if name:
        args.extend(["--name", name])
    if ports:
        for host, container in ports.items():
            args.extend(["-p", f"{host}:{container}"])
    if env:
        for k, v in env.items():
            args.extend(["-e", f"{k}={v}"])

    args.append(image)

    result = _run_docker(args, timeout=300)
    if result["success"]:
        result["container"] = result["stdout"].strip()
        result["image"] = image
    return result


def docker_stop(container: str) -> dict[str, Any]:
    """Stop running container.

    FULL authority — destructive operation.
    """
    result = _run_docker(["stop", container], timeout=60)
    if result["success"]:
        result["container"] = container
    return result


def docker_rm(container: str, force: bool = False) -> dict[str, Any]:
    """Remove container.

    FULL authority — destructive operation.
    """
    args = ["rm"]
    if force:
        args.append("-f")
    args.append(container)

    result = _run_docker(args, timeout=60)
    if result["success"]:
        result["container"] = container
    return result


def docker_images() -> dict[str, Any]:
    """List Docker images.

    SAFE authority — read-only operation.
    """
    result = _run_docker(["images"])
    if result["success"]:
        lines = result["stdout"].strip().split("\n") if result["stdout"].strip() else []
        result["images"] = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3:
                result["images"].append({
                    "repository": parts[0],
                    "tag": parts[1],
                    "id": parts[2],
                })
    return result